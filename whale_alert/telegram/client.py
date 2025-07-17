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
            alert = await self._parse_whale_alert(message)
            if not alert:
                logger.warning("Could not parse whale alert message")
                return

            # Create a new whale alert in the database
            with get_db() as db:
                # Check if alert already exists
                existing_alert = get_whale_alert_by_hash(db, alert.hash)
                if existing_alert:
                    logger.info(f"Alert with hash {alert.hash} already exists")
                    return

                # Create the alert in the database
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
        worker_name = f"worker-{worker_id}"
        logger.info(f"{worker_name} started")
        
        try:
            while self._is_running:
                try:
                    # Get a message from the queue with a timeout
                    try:
                        message = await asyncio.wait_for(
                            self.message_queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue
                        
                    # Process the message
                    try:
                        await self._process_message(message)
                    except asyncio.CancelledError:
                        logger.info(f"{worker_name} was cancelled while processing a message")
                        raise
                    except Exception as e:
                        logger.error(f"{worker_name} error processing message: {e}", exc_info=True)
                    finally:
                        # Mark the task as done
                        self.message_queue.task_done()
                        
                except asyncio.CancelledError:
                    logger.info(f"{worker_name} was cancelled")
                    raise
                    
                except Exception as e:
                    logger.error(f"{worker_name} unexpected error: {e}", exc_info=True)
                    # Small delay to prevent tight error loops
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info(f"{worker_name} cancellation received")
            raise
            
        except Exception as e:
            logger.error(f"{worker_name} fatal error: {e}", exc_info=True)
            raise
            
        finally:
            logger.info(f"{worker_name} stopped")
        
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

    async def _parse_whale_alert(self, message: Message) -> Optional[WhaleAlertCreate]:
        """Parse a Whale Alert message using LLM.
        
        Args:
            message: The Telegram message to parse
            
        Returns:
            Optional[WhaleAlertCreate]: The parsed whale alert data, or None if parsing failed
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
            
            # Convert WhaleAlertData to WhaleAlertCreate
            alert_dict = alert_data.model_dump()
            return WhaleAlertCreate(**alert_dict)
            
        except Exception as e:
            logger.error(f"Error in LLM parsing: {e}", exc_info=True)
            return None

    async def start(self) -> None:
        """Start the Telegram client and worker tasks."""
        try:
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
                asyncio.create_task(
                    self._worker(i),
                    name=f"worker-{i}"
                )
                for i in range(self.num_workers)
            ]
            
            logger.info(f"Started {len(self.worker_tasks)} worker tasks")
            
            try:
                # Keep the client running until interrupted
                await self.client.run_until_disconnected()
            except asyncio.CancelledError:
                logger.info("Client connection was cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in client connection: {e}", exc_info=True)
                raise
            finally:
                # Clean up on exit
                await self.stop()
                
        except asyncio.CancelledError:
            logger.info("Startup was cancelled")
            raise
        except Exception as e:
            logger.error(f"Failed to start client: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the Telegram client and worker tasks gracefully."""
        if not self._is_running:
            return
            
        logger.info("Stopping Telegram client and workers...")
        self._is_running = False
        
        # Cancel all worker tasks
        tasks_to_cancel = []
        for task in self.worker_tasks:
            if not task.done() and not task.cancelled():
                task.cancel()
                tasks_to_cancel.append(task)
        
        # Wait for all workers to complete with a timeout
        if tasks_to_cancel:
            logger.info(f"Waiting for {len(tasks_to_cancel)} workers to finish...")
            done, pending = await asyncio.wait(
                tasks_to_cancel,
                timeout=5.0,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Log any pending tasks that didn't complete
            if pending:
                logger.warning(f"{len(pending)} tasks did not complete gracefully")
                for task in pending:
                    logger.debug(f"Pending task: {task}")
            

        # Disconnect the Telegram client
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("Telegram client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting Telegram client: {e}", exc_info=True)
        
        # Clear the worker tasks list
        self.worker_tasks.clear()
            
        logger.info("Telegram client and workers stopped")
