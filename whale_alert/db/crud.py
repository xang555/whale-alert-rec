"""Database CRUD operations for the Whale Alert application."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, TypeVar, Type, cast
import hashlib
import uuid

from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import SQLAlchemyError

from whale_alert.db.models import WhaleAlert, Base
from whale_alert.schemas import (
    WhaleAlertBase,
    WhaleAlertInDB,
    WhaleAlertResponse,
    WhaleAlertUpdate,
)
from whale_alert.config import logger

# Type variable for Pydantic models
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


def _generate_hash_from_alert_data(alert: WhaleAlertBase) -> str:
    """Generate a unique hash from alert data.
    
    Args:
        alert: The whale alert data
        
    Returns:
        A unique hash string (64 characters max)
    """
    # Create a string from key alert data, handling None values
    timestamp_str = str(alert.timestamp) if alert.timestamp else "unknown"
    blockchain_str = str(alert.blockchain) if alert.blockchain else "unknown"
    symbol_str = str(alert.symbol) if alert.symbol else "unknown"
    amount_str = str(alert.amount) if alert.amount else "0"
    from_addr_str = str(alert.from_address) if alert.from_address else "unknown"
    to_addr_str = str(alert.to_address) if alert.to_address else "unknown"
    
    hash_input = f"{timestamp_str}_{blockchain_str}_{symbol_str}_{amount_str}_{from_addr_str}_{to_addr_str}"
    
    # Add a UUID component for additional uniqueness
    hash_input += f"_{uuid.uuid4()}"
    
    # Generate SHA256 hash and truncate to 64 characters
    return hashlib.sha256(hash_input.encode()).hexdigest()[:64]


def create_whale_alert(
    db: Session, alert: WhaleAlertBase, commit: bool = True, max_retries: int = 10
) -> WhaleAlertResponse:
    """Create a new whale alert in the database.

    If a hash collision is detected, a new hash will be generated using a more robust strategy.

    Args:
        db: Database session
        alert: The whale alert data
        commit: Whether to commit the transaction
        max_retries: Maximum number of hash regeneration attempts

    Returns:
        The created whale alert

    Raises:
        ValueError: If max_retries is exceeded
    """
    try:
        original_hash = alert.hash
        current_alert = alert
        
        # If the original hash is None, empty, or looks like a placeholder, generate a proper hash
        if not original_hash or original_hash in ["b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6", ""]:
            original_hash = _generate_hash_from_alert_data(alert)
            alert_dict = current_alert.model_dump()
            alert_dict["hash"] = original_hash
            current_alert = WhaleAlertBase(**alert_dict)
            logger.info(f"Generated new hash from alert data: {original_hash}")
        
        for attempt in range(max_retries):
            # Check if alert with the same hash already exists
            existing_alert = get_whale_alert_by_hash(db, current_alert.hash)
            
            if not existing_alert:
                break
                
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate unique hash after {max_retries} attempts"
                           f" for original hash: {original_hash}")
                raise ValueError("Maximum hash regeneration attempts exceeded")
                
            # Generate a new unique hash using UUID and truncate to fit database limit
            unique_suffix = str(uuid.uuid4()).replace('-', '')[:8]
            # Ensure the new hash doesn't exceed 64 characters
            if len(original_hash) + len(unique_suffix) + 1 > 64:
                # If original hash is too long, use a hash of the original hash + suffix
                hash_input = f"{original_hash}_{unique_suffix}_{attempt}"
                new_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:64]
            else:
                new_hash = f"{original_hash}_{unique_suffix}"
            
            logger.debug(f"Hash collision detected for {current_alert.hash}, "
                       f"trying new hash: {new_hash}")
            
            # Create a new alert with the updated hash
            alert_dict = current_alert.model_dump()
            alert_dict["hash"] = new_hash
            current_alert = WhaleAlertBase(**alert_dict)
        
        # Create new alert with the unique hash
        db_alert = WhaleAlert(**current_alert.model_dump())
        db.add(db_alert)

        if commit:
            db.commit()
            db.refresh(db_alert)
            logger.info(f"Created new whale alert with id {db_alert.id} and hash {db_alert.hash}")

        return WhaleAlertResponse.model_validate(db_alert, from_attributes=True)

    except SQLAlchemyError as e:
        logger.error(f"Database error creating whale alert: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating whale alert: {e}")
        db.rollback()
        raise


def get_whale_alert(
    db: Session, alert_id: int, lock: bool = False
) -> Optional[WhaleAlertResponse]:
    """Get a whale alert by ID.

    Args:
        db: Database session
        alert_id: The ID of the alert to retrieve
        lock: Whether to lock the row for update

    Returns:
        The whale alert if found, else None
    """
    query = select(WhaleAlert).where(WhaleAlert.id == alert_id)

    if lock:
        query = query.with_for_update()

    result = db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        return None

    return WhaleAlertResponse.model_validate(alert, from_attributes=True)


def get_whale_alert_by_hash(
    db: Session, hash_str: str, lock: bool = False
) -> Optional[WhaleAlertResponse]:
    """Get a whale alert by its transaction hash.

    Args:
        db: Database session
        hash_str: The transaction hash to search for
        lock: Whether to lock the row for update

    Returns:
        The whale alert if found, else None
    """
    query = select(WhaleAlert).where(WhaleAlert.hash == hash_str)

    if lock:
        query = query.with_for_update()

    result = db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        return None

    return WhaleAlertResponse.model_validate(alert, from_attributes=True)


def get_recent_whale_alerts(
    db: Session,
    hours: int = 24,
    min_amount_usd: Optional[float] = None,
    limit: int = 100,
    symbol: Optional[str] = None,
    blockchain: Optional[str] = None,
) -> List[WhaleAlertResponse]:
    """Get recent whale alerts from the last N hours with optional filters.

    This is a convenience wrapper around get_whale_alerts with sensible defaults
    for getting recent alerts.

    Args:
        db: Database session
        hours: Number of hours to look back
        min_amount_usd: Optional minimum USD value to filter alerts
        limit: Maximum number of records to return
        symbol: Optional cryptocurrency symbol to filter by
        blockchain: Optional blockchain name to filter by

    Returns:
        List of recent whale alerts matching the criteria
    """
    # Calculate the time threshold
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Build the query using the more general get_whale_alerts function
    return get_whale_alerts(
        db=db,
        start_time=time_threshold,
        min_amount_usd=min_amount_usd,
        symbol=symbol,
        blockchain=blockchain,
        limit=min(limit, 1000),  # Enforce a reasonable limit
        order_by="timestamp_desc",
    )


def get_whale_alerts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    symbol: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    min_amount_usd: Optional[float] = None,
    max_amount_usd: Optional[float] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    blockchain: Optional[str] = None,
    transaction_type: Optional[str] = None,
    from_address: Optional[str] = None,
    to_address: Optional[str] = None,
    order_by: str = "timestamp_desc",
) -> List[WhaleAlertResponse]:
    """Get a list of whale alerts with optional filtering and sorting.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        symbol: Filter by cryptocurrency symbol (case-insensitive)
        min_amount: Filter by minimum amount in native token
        max_amount: Filter by maximum amount in native token
        min_amount_usd: Filter by minimum amount in USD
        max_amount_usd: Filter by maximum amount in USD
        start_time: Filter alerts after this timestamp
        end_time: Filter alerts before this timestamp
        blockchain: Filter by blockchain name (case-insensitive)
        transaction_type: Filter by transaction type (case-insensitive)
        from_address: Filter by source address (case-insensitive)
        to_address: Filter by destination address (case-insensitive)
        order_by: Field and direction to order by (e.g., 'timestamp_desc', 'amount_asc')

    Returns:
        List of whale alerts matching the criteria
    """
    # Build the base query
    query = select(WhaleAlert)

    # Apply filters
    conditions = []

    if symbol:
        conditions.append(WhaleAlert.symbol.ilike(f"%{symbol}%"))
    if min_amount is not None:
        conditions.append(WhaleAlert.amount >= min_amount)
    if max_amount is not None:
        conditions.append(WhaleAlert.amount <= max_amount)
    if min_amount_usd is not None:
        conditions.append(WhaleAlert.amount_usd >= min_amount_usd)
    if max_amount_usd is not None:
        conditions.append(WhaleAlert.amount_usd <= max_amount_usd)
    if start_time:
        conditions.append(WhaleAlert.timestamp >= start_time)
    if end_time:
        conditions.append(WhaleAlert.timestamp <= end_time)
    if blockchain:
        conditions.append(WhaleAlert.blockchain.ilike(f"%{blockchain}%"))
    if transaction_type:
        conditions.append(WhaleAlert.transaction_type.ilike(f"%{transaction_type}%"))
    if from_address:
        conditions.append(WhaleAlert.from_address.ilike(f"%{from_address}%"))
    if to_address:
        conditions.append(WhaleAlert.to_address.ilike(f"%{to_address}%"))

    # Apply all conditions
    if conditions:
        query = query.where(and_(*conditions))

    # Apply ordering
    order_field, order_dir = (order_by.split("_") + ["desc"])[:2]
    order_field = order_field.lower()
    order_dir = order_dir.upper()

    # Map order field to model attribute
    order_mapping = {
        "timestamp": WhaleAlert.timestamp,
        "amount": WhaleAlert.amount,
        "amount_usd": WhaleAlert.amount_usd,
    }

    order_field = order_mapping.get(order_field, WhaleAlert.timestamp)

    if order_dir == "ASC":
        query = query.order_by(order_field.asc())
    else:
        query = query.order_by(order_field.desc())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    try:
        result = db.execute(query)
        alerts = result.scalars().all()

        # Convert to Pydantic models
        return [
            WhaleAlertResponse.model_validate(alert, from_attributes=True)
            for alert in alerts
        ]

    except SQLAlchemyError as e:
        logger.error(f"Database error fetching whale alerts: {e}")
        raise


def get_whale_alerts_by_symbol(
    db: Session,
    symbol: str,
    hours: Optional[int] = None,
    min_amount_usd: Optional[float] = None,
    skip: int = 0,
    limit: int = 100,
    exact_match: bool = False,
) -> List[WhaleAlertResponse]:
    """Get whale alerts for a specific cryptocurrency symbol.

    Args:
        db: Database session
        symbol: Cryptocurrency symbol to filter by
        hours: Optional number of hours to look back
        min_amount_usd: Optional minimum USD value to filter alerts
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        exact_match: If True, match symbol exactly (case-insensitive)

    Returns:
        List of whale alerts matching the criteria
    """
    # Build the time filter if hours is specified
    start_time = None
    if hours is not None:
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Build the symbol filter
    symbol_filter = WhaleAlert.symbol.ilike(f"%{symbol}%")
    if exact_match:
        symbol_filter = func.lower(WhaleAlert.symbol) == func.lower(symbol)

    # Build the base query
    query = (
        select(WhaleAlert)
        .where(symbol_filter)
        .order_by(WhaleAlert.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )

    # Add time filter if specified
    if start_time:
        query = query.where(WhaleAlert.timestamp >= start_time)

    # Add amount filter if specified
    if min_amount_usd is not None:
        query = query.where(WhaleAlert.amount_usd >= min_amount_usd)

    # Execute the query
    try:
        result = db.execute(query)
        alerts = result.scalars().all()

        return [
            WhaleAlertResponse.model_validate(alert, from_attributes=True)
            for alert in alerts
        ]

    except SQLAlchemyError as e:
        logger.error(f"Database error fetching alerts for symbol {symbol}: {e}")
        raise


def update_whale_alert(
    db: Session,
    alert_id: int,
    alert_update: WhaleAlertUpdate,
) -> Optional[WhaleAlertResponse]:
    """Update a whale alert.

    Args:
        db: Database session
        alert_id: ID of the alert to update
        alert_update: Fields to update

    Returns:
        The updated whale alert if found, else None
    """
    try:
        # Get the existing alert with a lock
        result = db.execute(
            select(WhaleAlert).where(WhaleAlert.id == alert_id).with_for_update()
        )
        db_alert = result.scalar_one_or_none()

        if not db_alert:
            return None

        # Update fields from the update model
        update_data = alert_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_alert, field, value)

        db_alert.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(db_alert)

        return WhaleAlertResponse.model_validate(db_alert, from_attributes=True)

    except SQLAlchemyError as e:
        logger.error(f"Database error updating alert {alert_id}: {e}")
        db.rollback()
        raise


def delete_whale_alert(
    db: Session,
    alert_id: int,
) -> bool:
    """Delete a whale alert by ID.

    Args:
        db: Database session
        alert_id: ID of the alert to delete

    Returns:
        True if the alert was deleted, False if not found
    """
    try:
        result = db.execute(
            delete(WhaleAlert).where(WhaleAlert.id == alert_id).returning(WhaleAlert.id)
        )

        deleted = result.scalar_one_or_none() is not None

        if deleted:
            db.commit()
            logger.info(f"Deleted whale alert with id {alert_id}")
        else:
            logger.warning(f"Attempted to delete non-existent alert with id {alert_id}")

        return deleted

    except SQLAlchemyError as e:
        logger.error(f"Database error deleting alert {alert_id}: {e}")
        db.rollback()
        raise


def get_whale_alert_stats(
    db: Session,
    time_window_hours: int = 24,
    group_by: str = "symbol",
) -> List[Dict[str, Any]]:
    """Get statistics about whale alerts in a time window.

    Args:
        db: Database session
        time_window_hours: Number of hours to look back
        group_by: Field to group by (symbol, blockchain, or transaction_type)

    Returns:
        List of dictionaries containing statistics
    """
    # Validate group_by field
    valid_group_by = {"symbol", "blockchain", "transaction_type"}
    if group_by not in valid_group_by:
        raise ValueError(f"group_by must be one of {valid_group_by}")

    # Calculate time threshold
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

    # Get the model field to group by
    group_by_field = getattr(WhaleAlert, group_by)

    # Build the query
    query = (
        select(
            group_by_field.label("group"),
            func.count(WhaleAlert.id).label("count"),
            func.sum(WhaleAlert.amount).label("total_amount"),
            func.sum(WhaleAlert.amount_usd).label("total_amount_usd"),
            func.avg(WhaleAlert.amount_usd).label("avg_amount_usd"),
            func.max(WhaleAlert.amount_usd).label("max_amount_usd"),
        )
        .where(WhaleAlert.timestamp >= time_threshold)
        .group_by(group_by_field)
        .order_by(func.count(WhaleAlert.id).desc())
    )

    # Execute the query
    try:
        result = db.execute(query)
        return [dict(row) for row in result.mappings()]

    except SQLAlchemyError as e:
        logger.error(f"Database error fetching alert stats: {e}")
        raise
