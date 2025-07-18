"""LLM-based message parsing for Whale Alert messages."""
import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar

import tiktoken
from openai import AsyncOpenAI, APIError, RateLimitError
from pydantic import BaseModel, Field, ConfigDict, ValidationError

from whale_alert.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Define the schema for the expected output
class WhaleAlertData(BaseModel):
    """Structured data extracted from Whale Alert messages."""
    model_config = ConfigDict(extra='forbid')
    
    timestamp: str = Field(..., description="The timestamp of the transaction in ISO format")
    blockchain: str = Field(..., description="The blockchain where the transaction occurred")
    symbol: str = Field(..., description="The cryptocurrency symbol (e.g., BTC, ETH)")
    amount: float = Field(..., description="The amount of cryptocurrency transferred")
    amount_usd: float = Field(..., description="The USD value of the transferred amount")
    from_address: Optional[str] = Field(default=None, description="The source address of the transaction")
    to_address: Optional[str] = Field(default=None, description="The destination address of the transaction")
    transaction_type: str = Field(default="transfer", description="The type of transaction (e.g., transfer, deposit, withdrawal)")
    hash: str = Field(..., description="The transaction hash or unique identifier")


class LLMParser:
    """LLM-based parser for Whale Alert messages."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o", temperature: float = 0.0):
        """Initialize the LLM parser.
        
        Args:
            api_key: The OpenAI API key
            model: The OpenAI model to use for parsing
            temperature: The temperature parameter for the model (0.0 for deterministic output)
        """
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Try to get the appropriate encoding for the model, fall back to cl100k_base if not found
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found, using cl100k_base encoding")
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
    async def _parse_with_retry(
        self,
        model: Type[T],
        content: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[T]:
        """Parse content into a Pydantic model with retry logic.
        
        Args:
            model: The Pydantic model to parse into
            content: The content to parse
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            
        Returns:
            Parsed model or None if parsing failed after all retries
        """
        delay = initial_delay
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Truncate the message if it's too long
                max_tokens = 8000  # Leave room for the prompt
                tokens = self.encoding.encode(content)
                if len(tokens) > max_tokens:
                    truncated_text = self.encoding.decode(tokens[:max_tokens])
                    logger.warning(f"Message was too long and was truncated: {len(tokens)} tokens")
                else:
                    truncated_text = content
                
                # Prepare the system prompt
                system_prompt = """You are an expert at parsing Whale Alert messages from Telegram. 
                Extract the following information from the message:
                - Timestamp (if not present, use current time in ISO format)
                - Blockchain name (e.g., Ethereum, Bitcoin, etc.)
                - Cryptocurrency symbol (e.g., BTC, ETH, USDT)
                - Amount of cryptocurrency transferred (as a number)
                - USD value of the transfer (as a number)
                - Source address (if available that is include Unknown, otherwise null)
                - Destination address (if available that is include Unknown, otherwise null)
                - Transaction type (transfer, deposit, withdrawal, etc.)
                - Transaction hash (required, generate 32 characters hex string from transaction details)
                
                Return the data in a valid JSON object that matches this schema:
                {
                    "timestamp": "string (ISO format)",
                    "blockchain": "string",
                    "symbol": "string (uppercase)",
                    "amount": number,
                    "amount_usd": number,
                    "from_address": "string or null",
                    "to_address": "string or null",
                    "transaction_type": "string (default: 'transfer')",
                    "hash": "string (required)"
                }
                """
                
                # Call the OpenAI API
                response = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": truncated_text}
                    ],
                    response_format={"type": "json_object"},
                )
                
                # Extract the response content
                response_content = response.choices[0].message.content
                if not response_content:
                    raise ValueError("Empty response from LLM")
                
                # Parse and validate the response
                data = json.loads(response_content)
                return model.model_validate(data)
                
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = f"Validation error: {str(e)}"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                continue
                
            except (APIError, RateLimitError) as e:
                last_error = f"API error: {str(e)}"
                logger.warning(f"API error on attempt {attempt + 1}: {last_error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                continue
                
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error on attempt {attempt + 1}: {last_error}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                continue
        
        logger.error(f"Failed to parse message after {max_retries} attempts. Last error: {last_error}")
        return None
    
    async def parse_message(self, message_text: str) -> Optional[WhaleAlertData]:
        """Parse a Whale Alert message using an LLM.
        
        Args:
            message_text: The raw message text from Telegram
            
        Returns:
            Optional[WhaleAlertData]: The parsed whale alert data, or None if parsing failed
        """
        try:
            return await self._parse_with_retry(WhaleAlertData, message_text)
        except Exception as e:
            logger.error(f"Error in LLM parsing: {e}", exc_info=True)
            return None
    
    @classmethod
    async def create(
        cls, 
        api_key: str, 
        model: str = "gpt-4o", 
        temperature: float = 0.0
    ) -> 'LLMParser':
        """Create a new instance of LLMParser.
        
        Args:
            api_key: The OpenAI API key
            model: The OpenAI model to use
            temperature: The temperature parameter for the model
            
        Returns:
            An instance of LLMParser
        """
        if not api_key:
            raise ValueError("OpenAI API key is required")
            
        return cls(api_key=api_key, model=model, temperature=temperature)
