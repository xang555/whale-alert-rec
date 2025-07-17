"""Telegram client for the Whale Alert application."""
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument

from whale_alert.config import settings, logger
from whale_alert.db.crud import create_whale_alert, get_whale_alert_by_hash
from whale_alert.db.session import get_db
from whale_alert.schemas import WhaleAlertCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Regular expressions for parsing Whale Alert messages
WHALE_ALERT_PATTERNS = [
    # Pattern for standard whale alerts
    re.compile(
        r'🔄 (?P<amount>[\d,\.]+) (?P<symbol>[A-Z]+) \(\$(?P<amount_usd>[\d,\.]+(?:[KMBT])?\)?)?.*?from (?P<from_address>0x[a-fA-F0-9]+|\*{6}).*?to (?P<to_address>0x[a-fA-F0-9]+|\*{6}).*?on (?P<blockchain>[A-Za-z ]+)',
        re.DOTALL
    ),
    # Add more patterns as needed
]

class WhaleAlertClient:
    """Telegram client for listening to Whale Alert messages."""

    def __init__(self):
        """Initialize the Telegram client."""
        self.client = TelegramClient(
            settings.SESSION_NAME,
            settings.API_ID,
            settings.API_HASH,
        )
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up event handlers for the Telegram client."""

        @self.client.on(events.NewMessage(chats=settings.CHANNEL_USERNAME))
        async def handle_whale_alert(event: events.NewMessage.Event) -> None:
            """Handle incoming Whale Alert messages."""
            try:
                message = event.message
                logger.info(f"New message received: {message.text}")
                
                # Parse the whale alert message
                alert_data = self._parse_whale_alert(message)
                if not alert_data:
                    logger.warning("Could not parse whale alert message")
                    return

                # Create a new whale alert in the database
                with get_db() as db:
                    # Check if alert already exists
                    existing_alert = get_whale_alert_by_hash(db, alert_data["hash"])
                    if existing_alert:
                        logger.info(f"Alert with hash {alert_data['hash']} already exists")
                        return

                    # Create new alert
                    alert = WhaleAlertCreate(**alert_data)
                    created_alert = create_whale_alert(db, alert)
                    logger.info(f"Created new whale alert: {created_alert.id}")

            except Exception as e:
                logger.error(f"Error processing whale alert: {e}", exc_info=True)

    def _parse_whale_alert(self, message: Message) -> Optional[Dict[str, Any]]:
        """Parse a Whale Alert message into a structured format."""
        if not message.text:
            return None

        text = message.text
        logger.debug(f"Parsing whale alert message: {text}")

        # Try to match the message against known patterns
        for pattern in WHALE_ALERT_PATTERNS:
            match = pattern.search(text)
            if match:
                data = match.groupdict()
                
                # Clean and convert the data
                amount = float(data["amount"].replace(",", ""))
                
                # Handle amount in USD (e.g., 1.2M -> 1,200,000)
                amount_usd_str = data.get("amount_usd", "0").replace(",", "")
                if "K" in amount_usd_str:
                    amount_usd = float(amount_usd_str.replace("K", "")) * 1_000
                elif "M" in amount_usd_str:
                    amount_usd = float(amount_usd_str.replace("M", "")) * 1_000_000
                elif "B" in amount_usd_str:
                    amount_usd = float(amount_usd_str.replace("B", "")) * 1_000_000_000
                elif "T" in amount_usd_str:
                    amount_usd = float(amount_usd_str.replace("T", "")) * 1_000_000_000_000
                else:
                    amount_usd = float(amount_usd_str) if amount_usd_str else 0.0
                
                # Get transaction hash from the message if available
                tx_hash = self._extract_transaction_hash(text) or f"{int(datetime.utcnow().timestamp())}-{data['symbol']}"
                
                return {
                    "timestamp": message.date or datetime.utcnow(),
                    "blockchain": data["blockchain"].strip(),
                    "symbol": data["symbol"].strip(),
                    "amount": amount,
                    "amount_usd": amount_usd,
                    "from_address": data.get("from_address", "").strip() or None,
                    "to_address": data.get("to_address", "").strip() or None,
                    "transaction_type": "transfer",  # Default transaction type
                    "hash": tx_hash,
                }

        logger.warning(f"Could not parse whale alert message: {text}")
        return None

    def _extract_transaction_hash(self, text: str) -> Optional[str]:
        """Extract transaction hash from the message text."""
        # Look for common hash patterns
        hash_patterns = [
            r'(?i)hash[:\s]+(0x[a-fA-F0-9]+)',
            r'(?i)txn?[:\s]+(0x[a-fA-F0-9]+)',
            r'(?<![a-zA-Z0-9])(0x[a-fA-F0-9]{64})(?![a-zA-Z0-9])',
        ]
        
        for pattern in hash_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None

    async def start(self) -> None:
        """Start the Telegram client."""
        await self.client.start(phone=settings.PHONE_NUMBER)
        logger.info("Telegram client started")
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Stop the Telegram client."""
        await self.client.disconnect()
        logger.info("Telegram client stopped")
