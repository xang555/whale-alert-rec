"""Telegram client for the Whale Alert application."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message

from whale_alert.config import settings, logger
from whale_alert.db.crud import create_whale_alert, get_whale_alert_by_hash
from whale_alert.db.session import get_db
from whale_alert.llm import LLMParser
from whale_alert.schemas import WhaleAlertCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhaleAlertClient:
    """Telegram client for listening to Whale Alert messages."""

    def __init__(self, max_queue_size: int = 1000, num_workers: int = 3):
        """Initialize the Telegram client.
        
        Args:
            max_queue_size: Maximum number of messages to queue before blocking
            num_workers: Number of worker tasks to process messages concurrently
        """
        self.client = TelegramClient(
            settings.SESSION_NAME,
            settings.API_ID,
            settings.API_HASH,
        )
        self.llm_parser: Optional[LLMParser] = None
        self.max_queue_size = max_queue_size
        self.num_workers = num_workers
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=max_queue_size)
        self.worker_tasks: list[asyncio.Task] = []
        self._is_running = False
        self._setup_handlers()

    async def _init_llm_parser(self) -> None:
        """Initialize the LLM parser with configuration from settings."""
        if not self.llm_parser and settings.OPENAI_API_KEY:
            try:
                self.llm_parser = await LLMParser.create(
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE
                )
                logger.info(f"Initialized LLM parser with model: {settings.LLM_MODEL}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize LLM parser: {e}")
                return False
        return False

    async def _process_message(self, message: Message) -> None:
        """Process a single message from the queue.
        
        Args:
            message: The Telegram message to process
        """
        try:
            if not message.text:
                logger.warning("Received empty message")
                return
                
            logger.info(f"Processing message: {message.text[:100]}...")
            
            # Parse the whale alert message using LLM
            alert_data = await self._parse_whale_alert(message)
            if not alert_data:
                logger.warning("Could not parse whale alert message")
                return

            # Create a new whale alert in the database
            with get_db() as db:
                # Check if alert already exists
                existing_alert = get_whale_alert_by_hash(db, alert_data.hash)
                if existing_alert:
                    logger.info(f"Alert with hash {alert_data.hash} already exists")
                    return

                # Convert to Pydantic model for database
                alert_dict = alert_data.dict()
                alert = WhaleAlertCreate(**alert_dict)
                created_alert = create_whale_alert(db, alert)
                logger.info(f"Created new whale alert: {created_alert.id}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Consider adding retry logic here if needed
            
    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes messages from the queue.
        
        Args:
            worker_id: The ID of this worker (for logging)
        """
        logger.info(f"Starting worker {worker_id}")
        while self._is_running or not self.message_queue.empty():
            try:
                # Get a message from the queue with a timeout
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0  # Check self._is_running periodically
                    )
                except asyncio.TimeoutError:
                    continue
                    
                # Process the message
                logger.debug(f"Worker {worker_id} processing message")
                await self._process_message(message)
                
                # Mark the task as done
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                
        logger.info(f"Worker {worker_id} stopped")
        
    def _setup_handlers(self) -> None:
        """Set up event handlers for the Telegram client."""
        @self.client.on(events.NewMessage(chats=settings.CHANNEL_USERNAME))
        async def handle_whale_alert(event: events.NewMessage.Event) -> None:
            """Handle incoming Whale Alert messages by adding them to the queue."""
            try:
                message = event.message
                if not message.text:
                    logger.warning("Received empty message")
                    return
                    
                logger.info(f"Queueing new message: {message.text[:100]}...")
                
                # Add message to the queue
                try:
                    self.message_queue.put_nowait(message)
                    logger.debug(f"Queue size: {self.message_queue.qsize()}")
                except asyncio.QueueFull:
                    logger.error("Message queue is full, dropping message")
                    
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    async def _parse_whale_alert(self, message: Message) -> Optional[WhaleAlertData]:
        """Parse a Whale Alert message using LLM.
        
        Args:
            message: The Telegram message to parse
            
        Returns:
            Optional[WhaleAlertData]: The parsed whale alert data, or None if parsing failed
        """
        if not message.text or not self.llm_parser:
            return None
            
        try:
            # Parse the message using the LLM
            alert_data = await self.llm_parser.parse_message(message.text)
            if not alert_data:
                logger.warning("LLM parsing returned no data")
                return None
                
            # Use message date if timestamp is not provided by the LLM
            if not alert_data.timestamp and message.date:
                alert_data.timestamp = message.date.isoformat()
                
            return alert_data
            
        except Exception as e:
            logger.error(f"Error in LLM parsing: {e}", exc_info=True)
            return None

    async def start(self) -> None:
        """Start the Telegram client and worker tasks."""
        # Initialize LLM parser first
        if not await self._init_llm_parser():
            logger.error("Failed to initialize LLM parser")
            return
            
        # Start the Telegram client
        await self.client.start(phone=settings.PHONE_NUMBER)
        logger.info("Telegram client started")
        
        # Start worker tasks
        self._is_running = True
        self.worker_tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.num_workers)
        ]
        
        logger.info(f"Started {len(self.worker_tasks)} worker tasks")
        
        try:
            # Keep the client running until interrupted
            await self.client.run_until_disconnected()
        finally:
            # Clean up on exit
            await self.stop()

    async def stop(self) -> None:
        """Stop the Telegram client and worker tasks gracefully."""
        if not self._is_running:
            return
            
        logger.info("Stopping Telegram client and workers...")
        self._is_running = False
        
        # Cancel all worker tasks
        for task in self.worker_tasks:
            if not task.done():
                task.cancel()
                
        # Wait for all workers to complete
        if self.worker_tasks:
            logger.info("Waiting for workers to finish...")
            await asyncio.wait(self.worker_tasks)
            
        # Disconnect the Telegram client
        if self.client.is_connected():
            await self.client.disconnect()
            
        logger.info("Telegram client and workers stopped")
