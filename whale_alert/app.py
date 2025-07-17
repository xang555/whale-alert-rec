"""Main application entry point for Whale Alert."""

import asyncio
import logging
import signal
import sys
import os
from typing import Any, Optional, Set

from whale_alert.config import settings, logger
from whale_alert.telegram.client import WhaleAlertClient
from whale_alert.db.models import init_db, engine


class WhaleAlertApp:
    """Main application class for the Whale Alert bot."""

    def __init__(self):
        """Initialize the application."""
        self.client: Optional[WhaleAlertClient] = None
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout = 10.0  # seconds
        self._shutting_down = False
        self._tasks: Set[asyncio.Task] = set()

    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting Whale Alert application...")

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig, f=None: self._handle_shutdown(s, f)
                )
            except NotImplementedError:
                # Windows doesn't support signal handlers
                pass

        try:
            # Ensure the database is initialized
            init_db()

            # Initialize the Telegram client
            self.client = WhaleAlertClient()

            # Start the client in the background so we can wait for signals
            self._client_task = asyncio.create_task(
                self.client.start(), name="whale-alert-client"
            )

            # Wait until a shutdown signal is received
            await self._shutdown_event.wait()
            logger.info("Shutdown event triggered")

        except asyncio.CancelledError:
            logger.info("Startup was cancelled")
            return
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            # Perform graceful shutdown
            await self.shutdown()

            # Ensure the client task finishes
            if hasattr(self, "_client_task"):
                try:
                    await self._client_task
                except asyncio.CancelledError:
                    logger.info("Client task cancelled during shutdown")
                except Exception:
                    logger.exception("Client task raised an exception during shutdown")

    async def create_task(self, coro):
        """Create a tracked task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def shutdown(self) -> None:
        """Shut down the application gracefully."""
        if self._shutting_down:
            return

        self._shutting_down = True
        logger.info("Shutting down Whale Alert application...")

        # Shutdown the client with a timeout
        if self.client:
            logger.info("Stopping Telegram client...")
            try:
                # Set a very short timeout for client shutdown
                await asyncio.wait_for(self.client.stop(), timeout=1.0)
                logger.info("Telegram client stopped")
            except asyncio.TimeoutError:
                logger.warning("Client shutdown timed out, forcing disconnect")
                if hasattr(self.client, "client") and self.client.client:
                    try:
                        if self.client.client.is_connected():
                            # Force disconnect without waiting
                            if hasattr(self.client.client, '_sender'):
                                self.client.client._sender.disconnect()
                            await self.client.client.disconnect()
                            logger.info("Forcibly disconnected Telegram client")
                    except Exception as e:
                        logger.error(f"Error during forced disconnect: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error during client shutdown: {e}", exc_info=True)
            finally:
                # Force cleanup of the client
                if hasattr(self, 'client') and self.client:
                    if hasattr(self.client, 'client'):
                        if hasattr(self.client.client, '_disconnected'):
                            self.client.client._disconnected.set()
                    self.client = None

        # Get all tasks except the current one
        current_task = asyncio.current_task()
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not current_task
            and t is not getattr(self, "_client_task", None)
            and not t.done()
        ]

        # Cancel all tasks
        if tasks:
            logger.info(f"Cancelling {len(tasks)} remaining tasks...")
            for task in tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()

            # Wait for tasks to complete with a very short timeout
            if tasks:
                try:
                    done, pending = await asyncio.wait(
                        tasks, 
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if pending:
                        logger.warning(f"{len(pending)} tasks did not complete in time")
                        # Force cancel any remaining tasks
                        for task in pending:
                            if not task.done():
                                try:
                                    task.cancel()
                                    # Try to set the cancelled exception if possible
                                    if hasattr(task, 'set_exception'):
                                        task.set_exception(asyncio.CancelledError())
                                except Exception as e:
                                    logger.debug(f"Error cancelling task {task}: {e}")
                except Exception as e:
                    logger.error(
                        f"Error waiting for tasks to complete: {e}", 
                        exc_info=True
                    )

        # Clean up any remaining async generators
        try:
            await asyncio.get_event_loop().shutdown_asyncgens()
        except Exception as e:
            logger.error(f"Error shutting down async generators: {e}", exc_info=True)

        # Dispose DB connections
        try:
            engine.dispose()
            logger.debug("Database engine disposed")
        except Exception as e:
            logger.error(f"Error disposing engine: {e}", exc_info=True)

        # Log any remaining tasks
        remaining_tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if remaining_tasks:
            logger.warning(f"{len(remaining_tasks)} tasks still running after shutdown")
            for task in remaining_tasks:
                logger.debug(f"Remaining task: {task}")
                # Try to cancel the task if it's not done
                if not task.done():
                    try:
                        task.cancel()
                        if hasattr(task, 'set_exception'):
                            task.set_exception(asyncio.CancelledError())
                    except Exception as e:
                        logger.debug(f"Error cancelling remaining task {task}: {e}")

        logger.info("Application shutdown complete")

    def _handle_shutdown(self, signum: int, frame: Any = None) -> None:
        """Handle shutdown signals."""
        if self._shutdown_event.is_set():
            logger.warning("Shutdown already in progress, ignoring additional signal")
            return

        signal_name = (
            signal.Signals(signum).name
            if hasattr(signal, "Signals")
            else f"SIG{signum}"
        )
        logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")

        # Trigger shutdown through the main task
        self._shutdown_event.set()

        # Disconnect the Telegram client promptly so run_until_disconnected returns
        if self.client:
            asyncio.create_task(self.client.stop())

def main() -> int:
    """Run the Whale Alert application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )

    # Suppress verbose logging from external libraries
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    
    # Create the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Set up a timer to force exit if shutdown takes too long
    def force_exit():
        logger.warning("Forcing application exit after timeout...")
        # Try to log remaining tasks
        try:
            loop = asyncio.get_event_loop()
            remaining = [t for t in asyncio.all_tasks(loop=loop) if not t.done()]
            if remaining:
                logger.warning(f"Force exiting with {len(remaining)} tasks still running")
                for task in remaining:
                    logger.warning(f"- {task}")
        except Exception as e:
            logger.error(f"Error during force exit: {e}")
        
        # Force exit
        os._exit(1)
    
    # Import threading here to avoid circular imports
    import threading
    
    # Schedule the force exit after 5 seconds
    force_exit_timer = None
    
    app = None
    try:
        # Create and run the application
        app = WhaleAlertApp()
        loop.run_until_complete(app.start())
        return 0
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        return 0
    except asyncio.CancelledError:
        logger.info("Application cancelled")
        return 0
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        return 1
    finally:
        try:
            # Set up force exit timer with a shorter timeout
            force_exit_timer = threading.Timer(3.0, force_exit)
            force_exit_timer.daemon = True
            force_exit_timer.start()
            
            try:
                # Ensure the application is properly shut down
                if app and not app._shutdown_event.is_set():
                    logger.info("Ensuring application is properly shut down...")
                    loop.run_until_complete(app.shutdown())
                
                # Cancel all remaining tasks
                tasks = [t for t in asyncio.all_tasks(loop=loop) if not t.done()]
                if tasks:
                    logger.info(f"Cancelling {len(tasks)} remaining tasks...")
                    for task in tasks:
                        if not task.done() and not task.cancelled():
                            task.cancel()
                    
                    # Wait for tasks to complete with a short timeout
                    if tasks:
                        try:
                            done, pending = loop.run_until_complete(asyncio.wait(
                                tasks, 
                                timeout=1.5,
                                return_when=asyncio.FIRST_COMPLETED
                            ))
                            if pending:
                                logger.warning(f"{len(pending)} tasks did not complete in time")
                        except Exception as e:
                            logger.warning(f"Error waiting for tasks to complete: {e}")
            finally:
                # Cancel the force exit timer if we completed successfully
                if force_exit_timer.is_alive():
                    force_exit_timer.cancel()
            
            # Shutdown async generators
            loop.run_until_complete(loop.shutdown_asyncgens())
            
            # Stop the loop
            loop.stop()
            
            # Run the loop one more time to process any pending callbacks
            loop.run_forever()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            # Cancel the force exit timer if it was set and still running
            if force_exit_timer and force_exit_timer.is_alive():
                force_exit_timer.cancel()
            
            # Close the loop
            try:
                loop.close()
            except Exception as e:
                logger.error(f"Error closing event loop: {e}")
            
            asyncio.set_event_loop(None)
            
            # Force exit if we get here and there are still running threads
            if threading.active_count() > 1:
                logger.warning("Forcing exit due to remaining threads")
                os._exit(1)


if __name__ == "__main__":
    sys.exit(main())
