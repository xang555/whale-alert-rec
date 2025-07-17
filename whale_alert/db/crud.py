"""Database operations for the Whale Alert application."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from whale_alert.db.models import WhaleAlert
from whale_alert.schemas import WhaleAlertCreate


def create_whale_alert(db: Session, alert: WhaleAlertCreate) -> WhaleAlert:
    """Create a new whale alert in the database.

    Args:
        db: Database session.
        alert: Whale alert data.

    Returns:
        WhaleAlert: The created whale alert.
    """
    db_alert = WhaleAlert(
        timestamp=alert.timestamp,
        blockchain=alert.blockchain,
        symbol=alert.symbol,
        amount=alert.amount,
        amount_usd=alert.amount_usd,
        from_address=alert.from_address,
        to_address=alert.to_address,
        transaction_type=alert.transaction_type,
        hash=alert.hash,
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


def get_whale_alert(db: Session, alert_id: int) -> Optional[WhaleAlert]:
    """Get a whale alert by ID.

    Args:
        db: Database session.
        alert_id: ID of the alert to retrieve.

    Returns:
        Optional[WhaleAlert]: The whale alert if found, None otherwise.
    """
    return db.query(WhaleAlert).filter(WhaleAlert.id == alert_id).first()


def get_whale_alert_by_hash(db: Session, hash_str: str) -> Optional[WhaleAlert]:
    """Get a whale alert by transaction hash.

    Args:
        db: Database session.
        hash_str: Transaction hash.

    Returns:
        Optional[WhaleAlert]: The whale alert if found, None otherwise.
    """
    return db.query(WhaleAlert).filter(WhaleAlert.hash == hash_str).first()


def get_whale_alerts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    symbol: Optional[str] = None,
    min_amount: Optional[float] = None,
    min_amount_usd: Optional[float] = None,
) -> List[WhaleAlert]:
    """Get a list of whale alerts with optional filters.

    Args:
        db: Database session.
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.
        start_time: Filter alerts after this timestamp.
        end_time: Filter alerts before this timestamp.
        symbol: Filter by cryptocurrency symbol.
        min_amount: Filter by minimum amount.
        min_amount_usd: Filter by minimum amount in USD.

    Returns:
        List[WhaleAlert]: List of whale alerts matching the criteria.
    """
    query = db.query(WhaleAlert)

    if start_time:
        query = query.filter(WhaleAlert.timestamp >= start_time)
    if end_time:
        query = query.filter(WhaleAlert.timestamp <= end_time)
    if symbol:
        query = query.filter(WhaleAlert.symbol == symbol.upper())
    if min_amount is not None:
        query = query.filter(WhaleAlert.amount >= min_amount)
    if min_amount_usd is not None:
        query = query.filter(WhaleAlert.amount_usd >= min_amount_usd)

    return query.offset(skip).limit(limit).all()
