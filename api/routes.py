"""API routes for querying historical whale alerts."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import api_key_auth, generate_api_key
from api.database import engine

router = APIRouter()

# Mapping of supported intervals to materialized view names
MATERIALIZED_VIEWS = {
    "15m": "whale_alerts_15min",
    "1h": "whale_alerts_1hour", 
    "4h": "whale_alerts_4hour",
    "1d": "whale_alerts_1day",
    "1w": "whale_alerts_1week",
    "1m": "whale_alerts_1month",
}


class WhaleAlertAggregation(BaseModel):
    """Schema for aggregated whale alert data."""
    time_bucket: datetime
    blockchain: str
    symbol: str
    transaction_count: int
    total_amount: float
    total_amount_usd: float
    min_amount: float
    max_amount: float
    min_amount_usd: float
    max_amount_usd: float
    transfer_count: int
    mint_count: int
    burn_count: int
    whale_volume_usd: float
    whale_transaction_count: int
    mega_whale_volume_usd: Optional[float] = None
    mega_whale_transaction_count: Optional[int] = None
    institutional_volume_usd: Optional[float] = None
    institutional_transaction_count: Optional[int] = None
    net_mint_burn_usd: Optional[float] = None


@router.get("/whale-alerts", response_model=List[WhaleAlertAggregation])
async def get_whale_alerts(
    interval: str = Query(
        ..., 
        description="Aggregation interval. One of: " + ", ".join(MATERIALIZED_VIEWS.keys()),
        regex="^(15m|1h|4h|1d|1w|1m)$"
    ),
    blockchain: Optional[str] = Query(None, description="Filter by blockchain"),
    symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records to return"),
    start_time: Optional[datetime] = Query(None, description="Start time filter (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End time filter (ISO format)"),
    api_key: str = Depends(api_key_auth)
) -> List[WhaleAlertAggregation]:
    """
    Retrieve historical whale alerts aggregated by the specified interval using optimized materialized views.
    
    This endpoint leverages pre-computed materialized views for optimal performance:
    - 15m: 15-minute aggregations
    - 1h: 1-hour aggregations with mega whale metrics
    - 4h: 4-hour aggregations with mega whale metrics  
    - 1d: 1-day aggregations with mega whale and institutional metrics
    - 1w: 1-week aggregations with mega whale and institutional metrics
    - 1m: 1-month aggregations with full metrics including net mint/burn
    """
    if interval not in MATERIALIZED_VIEWS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Supported: {', '.join(MATERIALIZED_VIEWS.keys())}",
        )
    
    # Validate time range
    if start_time and end_time and start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="start_time must be before end_time"
        )
    
    view_name = MATERIALIZED_VIEWS[interval]
    
    # Build dynamic WHERE clause
    where_conditions = []
    params = {"limit": limit}
    
    if blockchain:
        where_conditions.append("blockchain = :blockchain")
        params["blockchain"] = blockchain
        
    if symbol:
        where_conditions.append("symbol = :symbol") 
        params["symbol"] = symbol
        
    if start_time:
        where_conditions.append("time_bucket >= :start_time")
        params["start_time"] = start_time
        
    if end_time:
        where_conditions.append("time_bucket <= :end_time")
        params["end_time"] = end_time
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    # Build query based on available columns in each materialized view
    base_columns = """
        time_bucket,
        blockchain,
        symbol,
        transaction_count,
        total_amount,
        total_amount_usd,
        min_amount,
        max_amount,
        min_amount_usd,
        max_amount_usd,
        transfer_count,
        mint_count,
        burn_count,
        whale_volume_usd,
        whale_transaction_count
    """
    
    # Add columns based on interval (following the materialized view schemas)
    if interval in ["1h", "4h"]:
        columns = base_columns + ",\n        mega_whale_volume_usd,\n        mega_whale_transaction_count,\n        NULL::numeric as institutional_volume_usd,\n        NULL::integer as institutional_transaction_count,\n        NULL::numeric as net_mint_burn_usd"
    elif interval in ["1d", "1w"]:
        columns = base_columns + ",\n        mega_whale_volume_usd,\n        mega_whale_transaction_count,\n        institutional_volume_usd,\n        institutional_transaction_count,\n        NULL::numeric as net_mint_burn_usd"
    elif interval == "1m":
        columns = base_columns + ",\n        mega_whale_volume_usd,\n        mega_whale_transaction_count,\n        institutional_volume_usd,\n        institutional_transaction_count,\n        net_mint_burn_usd"
    else:  # 15m
        columns = base_columns + ",\n        NULL::numeric as mega_whale_volume_usd,\n        NULL::integer as mega_whale_transaction_count,\n        NULL::numeric as institutional_volume_usd,\n        NULL::integer as institutional_transaction_count,\n        NULL::numeric as net_mint_burn_usd"
    
    stmt = text(f"""
        SELECT {columns}
        FROM {view_name}
        {where_clause}
        ORDER BY time_bucket DESC, blockchain, symbol
        LIMIT :limit
    """)
    
    async with engine.connect() as conn:
        result = await conn.execute(stmt, params)
        records = result.fetchall()
    
    return [
        WhaleAlertAggregation(
            time_bucket=row.time_bucket,
            blockchain=row.blockchain,
            symbol=row.symbol,
            transaction_count=row.transaction_count,
            total_amount=float(row.total_amount),
            total_amount_usd=float(row.total_amount_usd),
            min_amount=float(row.min_amount),
            max_amount=float(row.max_amount),
            min_amount_usd=float(row.min_amount_usd),
            max_amount_usd=float(row.max_amount_usd),
            transfer_count=row.transfer_count,
            mint_count=row.mint_count,
            burn_count=row.burn_count,
            whale_volume_usd=float(row.whale_volume_usd),
            whale_transaction_count=row.whale_transaction_count,
            mega_whale_volume_usd=float(row.mega_whale_volume_usd) if row.mega_whale_volume_usd else None,
            mega_whale_transaction_count=row.mega_whale_transaction_count,
            institutional_volume_usd=float(row.institutional_volume_usd) if row.institutional_volume_usd else None,
            institutional_transaction_count=row.institutional_transaction_count,
            net_mint_burn_usd=float(row.net_mint_burn_usd) if row.net_mint_burn_usd else None,
        )
        for row in records
    ]


@router.get("/whale-alerts/summary", response_model=dict)
async def get_whale_alerts_summary(
    interval: str = Query(
        ..., 
        description="Aggregation interval. One of: " + ", ".join(MATERIALIZED_VIEWS.keys()),
        regex="^(15m|1h|4h|1d|1w|1m)$"
    ),
    blockchain: Optional[str] = Query(None, description="Filter by blockchain"),
    symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    start_time: Optional[datetime] = Query(None, description="Start time filter (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End time filter (ISO format)"),
    api_key: str = Depends(api_key_auth)
) -> dict:
    """
    Get summary statistics for whale alerts in the specified interval.
    """
    if interval not in MATERIALIZED_VIEWS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Supported: {', '.join(MATERIALIZED_VIEWS.keys())}",
        )
    
    if start_time and end_time and start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="start_time must be before end_time"
        )
    
    view_name = MATERIALIZED_VIEWS[interval]
    
    # Build WHERE clause
    where_conditions = []
    params = {}
    
    if blockchain:
        where_conditions.append("blockchain = :blockchain")
        params["blockchain"] = blockchain
        
    if symbol:
        where_conditions.append("symbol = :symbol")
        params["symbol"] = symbol
        
    if start_time:
        where_conditions.append("time_bucket >= :start_time")
        params["start_time"] = start_time
        
    if end_time:
        where_conditions.append("time_bucket <= :end_time")
        params["end_time"] = end_time
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    stmt = text(f"""
        SELECT 
            COUNT(*) as total_periods,
            COUNT(DISTINCT blockchain) as unique_blockchains,
            COUNT(DISTINCT symbol) as unique_symbols,
            SUM(transaction_count) as total_transactions,
            SUM(total_amount_usd) as total_volume_usd,
            SUM(whale_volume_usd) as total_whale_volume_usd,
            SUM(whale_transaction_count) as total_whale_transactions,
            AVG(total_amount_usd) as avg_volume_per_period,
            MIN(time_bucket) as earliest_period,
            MAX(time_bucket) as latest_period
        FROM {view_name}
        {where_clause}
    """)
    
    async with engine.connect() as conn:
        result = await conn.execute(stmt, params)
        row = result.fetchone()
    
    return {
        "interval": interval,
        "total_periods": row.total_periods,
        "unique_blockchains": row.unique_blockchains, 
        "unique_symbols": row.unique_symbols,
        "total_transactions": row.total_transactions,
        "total_volume_usd": float(row.total_volume_usd) if row.total_volume_usd else 0,
        "total_whale_volume_usd": float(row.total_whale_volume_usd) if row.total_whale_volume_usd else 0,
        "total_whale_transactions": row.total_whale_transactions,
        "avg_volume_per_period": float(row.avg_volume_per_period) if row.avg_volume_per_period else 0,
        "earliest_period": row.earliest_period,
        "latest_period": row.latest_period,
        "filters": {
            "blockchain": blockchain,
            "symbol": symbol,
            "start_time": start_time,
            "end_time": end_time
        }
    }


@router.get("/health", response_model=dict)
async def health_check() -> dict:
    """
    Health check endpoint - does not require authentication.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.1.0"
    }