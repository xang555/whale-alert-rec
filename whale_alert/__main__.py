"""Main entry point for the Whale Alert application."""
import asyncio
import logging
import signal
import sys
from typing import Any, Dict, Optional

from whale_alert.config import logger, settings
from whale_alert.telegram.client import WhaleAlertClient


class WhaleAlertApp:
    """Main application class for the Whale Alert bot."""

    def __init__(self):
        """Initialize the application."""
        self.client: Optional[WhaleAlertClient] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting Whale Alert application...")

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown, sig)

        try:
            # Initialize and start the Telegram client
            self.client = WhaleAlertClient()
            await self.client.start()

            # Keep the application running until shutdown is requested
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            logger.info("Shutdown requested, cleaning up...")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shut down the application gracefully."""
        logger.info("Shutting down Whale Alert application...")

        # Shutdown the Telegram client if it exists
        if self.client:
            await self.client.stop()

        logger.info("Application shutdown complete")

    def _handle_shutdown(self, signum: int) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signal.Signals(signum).name}, shutting down...")
        self._shutdown_event.set()


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

    app = WhaleAlertApp()

    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
