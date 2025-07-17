"""Pydantic models for the Whale Alert application."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WhaleAlertBase(BaseModel):
    """Base model for Whale Alert data."""

    timestamp: datetime = Field(..., description="The timestamp of the alert")
    blockchain: str = Field(..., description="The blockchain where the transaction occurred")
    symbol: str = Field(..., description="The cryptocurrency symbol")
    amount: float = Field(..., description="The amount of cryptocurrency transferred")
    amount_usd: float = Field(..., description="The USD value of the transferred amount")
    from_address: Optional[str] = Field(None, description="The source address of the transaction")
    to_address: Optional[str] = Field(None, description="The destination address of the transaction")
    transaction_type: Optional[str] = Field(None, description="The type of transaction")
    hash: str = Field(..., description="The transaction hash")


class WhaleAlertCreate(WhaleAlertBase):
    """Model for creating a new whale alert."""

    pass


class WhaleAlertInDB(WhaleAlertBase):
    """Model for whale alert data in the database."""

    id: int
    created_at: datetime

    class Config:
        """Pydantic config."""

        orm_mode = True


class WhaleAlertResponse(WhaleAlertInDB):
    """Response model for whale alert data."""

    pass
