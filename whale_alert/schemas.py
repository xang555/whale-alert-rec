"""Pydantic models for the Whale Alert application."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union, Literal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# Enums for validation
class TransactionType(str, Enum):
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    SWAP = "swap"
    OTHER = "other"


class Blockchain(str, Enum):
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    BINANCE = "binance"
    SOLANA = "solana"
    POLKADOT = "polkadot"
    CARDANO = "cardano"
    XRP = "xrp"
    OTHER = "other"


class WhaleAlertBase(BaseModel):
    """Base model for Whale Alert data."""
    model_config = ConfigDict(
        extra='forbid',
        str_strip_whitespace=True,
        str_to_lower=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The timestamp of the alert"
    )
    blockchain: str = Field(
        ...,
        description="The blockchain where the transaction occurred",
        min_length=1,
        max_length=50
    )
    symbol: str = Field(
        ...,
        description="The cryptocurrency symbol (e.g., BTC, ETH)",
        min_length=1,
        max_length=10,
        pattern=r'^[A-Z0-9]+$'
    )
    amount: float = Field(
        ...,
        description="The amount of cryptocurrency transferred",
        gt=0
    )
    amount_usd: float = Field(
        ...,
        description="The USD value of the transferred amount",
        gt=0
    )
    from_address: Optional[str] = Field(
        default=None,
        description="The source address of the transaction",
        min_length=20,
        max_length=100
    )
    to_address: Optional[str] = Field(
        default=None,
        description="The destination address of the transaction",
        min_length=20,
        max_length=100
    )
    transaction_type: TransactionType = Field(
        default=TransactionType.TRANSFER,
        description="The type of transaction"
    )
    hash: str = Field(
        ...,
        description="The transaction hash or unique identifier",
        min_length=10,
        max_length=100
    )
    
    @field_validator('symbol')
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Convert symbol to uppercase and remove any whitespace."""
        return v.strip().upper()
    
    @field_validator('blockchain')
    @classmethod
    def normalize_blockchain(cls, v: str) -> str:
        """Convert blockchain name to lowercase and remove any whitespace."""
        return v.strip().lower()
    
    @field_validator('from_address', 'to_address', mode='before')
    @classmethod
    def normalize_address(cls, v: Optional[str]) -> Optional[str]:
        """Normalize blockchain addresses."""
        if v is None:
            return None
        return v.strip()
    
    @model_validator(mode='after')
    def validate_amounts(self) -> 'WhaleAlertBase':
        """Validate that amount and amount_usd are consistent."""
        # This is a simple check - in a real app you might want to add more validation
        # based on current exchange rates
        if self.amount <= 0 or self.amount_usd <= 0:
            raise ValueError("Amounts must be positive")
        return self


class WhaleAlertCreate(WhaleAlertBase):
    """Model for creating a new whale alert."""

    pass


class WhaleAlertUpdate(BaseModel):
    """Model for updating an existing whale alert."""
    timestamp: Optional[datetime] = Field(
        default=None,
        description="The timestamp of the alert"
    )
    blockchain: Optional[str] = Field(
        default=None,
        description="The blockchain where the transaction occurred",
        min_length=1,
        max_length=50
    )
    symbol: Optional[str] = Field(
        default=None,
        description="The cryptocurrency symbol (e.g., BTC, ETH)",
        min_length=1,
        max_length=10,
        pattern=r'^[A-Z0-9]+$'
    )
    amount: Optional[float] = Field(
        default=None,
        description="The amount of cryptocurrency transferred",
        gt=0
    )
    amount_usd: Optional[float] = Field(
        default=None,
        description="The USD value of the transferred amount",
        gt=0
    )
    from_address: Optional[str] = Field(
        default=None,
        description="The source address of the transaction",
        min_length=20,
        max_length=100
    )
    to_address: Optional[str] = Field(
        default=None,
        description="The destination address of the transaction",
        min_length=20,
        max_length=100
    )
    transaction_type: Optional[TransactionType] = Field(
        default=None,
        description="The type of transaction"
    )
    hash: Optional[str] = Field(
        default=None,
        description="The transaction hash or unique identifier",
        min_length=10,
        max_length=100
    )


class WhaleAlertInDB(WhaleAlertBase):
    """Model for whale alert data in the database."""
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

    id: int = Field(..., description="The unique identifier for the alert")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the alert was created in the database"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="When the alert was last updated in the database"
    )
    
    @model_validator(mode='after')
    def set_updated_at(self) -> 'WhaleAlertInDB':
        """Set updated_at to current time if not set."""
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        return self


class WhaleAlertResponse(WhaleAlertInDB):
    """Response model for whale alert data."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "timestamp": "2023-01-01T12:00:00Z",
                "blockchain": "ethereum",
                "symbol": "ETH",
                "amount": 1000.0,
                "amount_usd": 1800000.0,
                "from_address": "0x1234...",
                "to_address": "0x5678...",
                "transaction_type": "transfer",
                "hash": "0xabcdef123456...",
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z"
            }
        }
    )


# Additional response models for API endpoints
class WhaleAlertStats(BaseModel):
    """Statistics about whale alerts."""
    total_alerts: int = Field(..., description="Total number of alerts")
    total_amount_usd: float = Field(..., description="Total USD value of all alerts")
    average_amount_usd: float = Field(..., description="Average USD value per alert")
    max_amount_usd: float = Field(..., description="Maximum USD value of any alert")
    alerts_by_blockchain: Dict[str, int] = Field(..., description="Number of alerts by blockchain")
    alerts_by_symbol: Dict[str, int] = Field(..., description="Number of alerts by cryptocurrency symbol")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_alerts": 150,
                "total_amount_usd": 50000000.0,
                "average_amount_usd": 333333.33,
                "max_amount_usd": 2500000.0,
                "alerts_by_blockchain": {"ethereum": 100, "bitcoin": 50},
                "alerts_by_symbol": {"ETH": 70, "BTC": 50, "USDT": 30}
            }
        }
    )


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""
    items: List[WhaleAlertResponse] = Field(..., description="List of whale alerts")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "pages": 10
            }
        }
    )
