"""Main application entry point for Whale Alert."""

import asyncio
import logging
import signal
import sys
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
                await asyncio.wait_for(self.client.stop(), timeout=5.0)
                logger.info("Telegram client stopped")
            except asyncio.TimeoutError:
                logger.warning("Client shutdown timed out, forcing disconnect")
                if (
                    hasattr(self.client, "client")
                    and self.client.client
                    and self.client.client.is_connected()
                ):
                    await self.client.client.disconnect()
            except Exception as e:
                logger.error(f"Error during client shutdown: {e}", exc_info=True)

        # Get all tasks except the current one
        client_task = getattr(self, "_client_task", None)
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and t is not client_task and not t.done()
        ]

        if tasks:
            logger.info(f"Cancelling {len(tasks)} remaining tasks...")
            for task in tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()

            # Wait for tasks to complete
            if tasks:
                try:
                    done, pending = await asyncio.wait(
                        tasks, timeout=2.0, return_when=asyncio.ALL_COMPLETED
                    )
                    if pending:
                        logger.warning(f"{len(pending)} tasks did not complete in time")
                except Exception as e:
                    logger.error(
                        f"Error waiting for tasks to complete: {e}", exc_info=True
                    )

        # Dispose DB connections
        try:
            engine.dispose()
        except Exception as e:
            logger.error(f"Error disposing engine: {e}")

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
        # Clean up the event loop
        pending = asyncio.all_tasks(loop=loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
