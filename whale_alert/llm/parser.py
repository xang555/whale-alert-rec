"""LLM-based message parsing for Whale Alert messages."""
import json
import logging
from typing import Any, Dict, Optional

import tiktoken
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from whale_alert.config import settings

logger = logging.getLogger(__name__)

# Define the schema for the expected output
class WhaleAlertData(BaseModel):
    """Structured data extracted from Whale Alert messages."""
    
    timestamp: str = Field(..., description="The timestamp of the transaction in ISO format")
    blockchain: str = Field(..., description="The blockchain where the transaction occurred")
    symbol: str = Field(..., description="The cryptocurrency symbol (e.g., BTC, ETH)")
    amount: float = Field(..., description="The amount of cryptocurrency transferred")
    amount_usd: float = Field(..., description="The USD value of the transferred amount")
    from_address: Optional[str] = Field(None, description="The source address of the transaction")
    to_address: Optional[str] = Field(None, description="The destination address of the transaction")
    transaction_type: str = Field("transfer", description="The type of transaction (e.g., transfer, deposit, withdrawal)")
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
        
    async def parse_message(self, message_text: str) -> Optional[WhaleAlertData]:
        """Parse a Whale Alert message using an LLM.
        
        Args:
            message_text: The raw message text from Telegram
            
        Returns:
            Optional[WhaleAlertData]: The parsed whale alert data, or None if parsing failed
        """
        try:
            # Truncate the message if it's too long
            max_tokens = 8000  # Leave room for the prompt
            tokens = self.encoding.encode(message_text)
            if len(tokens) > max_tokens:
                truncated_text = self.encoding.decode(tokens[:max_tokens])
                logger.warning(f"Message was too long and was truncated: {len(tokens)} tokens")
            else:
                truncated_text = message_text
            
            # Prepare the system prompt
            system_prompt = """You are an expert at parsing Whale Alert messages from Telegram. 
            Extract the following information from the message:
            - Timestamp (if not present, use current time)
            - Blockchain name
            - Cryptocurrency symbol (e.g., BTC, ETH)
            - Amount of cryptocurrency transferred
            - USD value of the transfer
            - Source address (if available)
            - Destination address (if available)
            - Transaction type (transfer, deposit, withdrawal, etc.)
            - Transaction hash or unique identifier
            
            Return the data in JSON format matching the WhaleAlertData schema. 
            If a field is not present in the message, set it to null.
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
            
            # Extract and validate the response
            content = response.choices[0].message.content
            if not content:
                logger.error("Empty response from LLM")
                return None
                
            # Parse the JSON response
            try:
                data = json.loads(content)
                # Validate against our Pydantic model
                return WhaleAlertData(**data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                return None
            except Exception as e:
                logger.error(f"Validation error for LLM response: {e}")
                return None
                
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
