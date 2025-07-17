"""Database models for the Whale Alert application."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine,
    func,
    text,
    inspect,
    PrimaryKeyConstraint,
    BigInteger,
    TIMESTAMP,
    Column,
    String,
    Numeric,
    DateTime,
)
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import (
    declarative_base,
    Mapped,
    mapped_column,
    sessionmaker,
    Session,
)

from whale_alert.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create SQLAlchemy engine and session factory
engine = create_engine(
    str(settings.TIMESCALEDB_URL),
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)

# Base model class
Base = declarative_base()


class WhaleAlert(Base):
    """Database model for storing whale alerts."""

    __tablename__ = "whale_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, primary_key=True)
    hash = Column(String(64), nullable=False, index=True)
    blockchain = Column(String(50), nullable=False)
    symbol = Column(String(10), nullable=False)
    amount = Column(Numeric(36, 18), nullable=False)
    amount_usd = Column(Numeric(36, 2), nullable=False)
    from_address = Column(String(128), nullable=True)
    to_address = Column(String(128), nullable=True)
    transaction_hash = Column(String(128), nullable=True)
    transaction_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Create a composite primary key
    __table_args__ = (
        PrimaryKeyConstraint("timestamp", "id"),
        # Remove the postgresql_partition_by as we'll handle hypertable creation separately
    )

    def __repr__(self) -> str:
        return f"<WhaleAlert(id={self.id}, symbol={self.symbol}, amount={self.amount} {self.symbol}, amount_usd=${self.amount_usd})>"


def init_db() -> None:
    """Initialize the database with TimescaleDB extension and create tables."""
    # First, ensure the TimescaleDB extension exists
    with engine.connect() as conn:
        with conn.begin():
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
                logger.info("TimescaleDB extension checked/created")
            except (ProgrammingError, OperationalError) as e:
                logger.warning(f"Could not create timescaledb extension: {e}")

    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    logger.info("Ensured whale_alerts table exists")

    # Convert to hypertable - using a different approach for TimescaleDB
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            # First, ensure the table is not already a hypertable
            result = conn.execute(
                text(
                    """
                SELECT EXISTS (
                    SELECT 1 FROM _timescaledb_catalog.hypertable 
                    WHERE table_name = 'whale_alerts'
                )
                """
                )
            )
            is_hypertable = result.scalar()

            if not is_hypertable:
                conn.execute(
                    text(
                        """
                    SELECT create_hypertable(
                        'public.whale_alerts',
                        'timestamp',
                        if_not_exists => TRUE
                    )
                    """
                    )
                )
                logger.info("Successfully converted whale_alerts to hypertable")
            else:
                logger.info("whale_alerts is already a hypertable")

        except Exception as e:
            logger.error(f"Could not convert whale_alerts to hypertable: {e}")
            raise

    # Create indexes after hypertable creation
    with engine.begin() as conn:
        try:
            # Create a unique constraint that includes the partition key
            conn.execute(
                text(
                    """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_whale_alerts_unique_hash 
                ON public.whale_alerts (timestamp, hash);
                
                CREATE INDEX IF NOT EXISTS idx_whale_alerts_hash 
                ON public.whale_alerts (hash);
                
                CREATE INDEX IF NOT EXISTS idx_whale_alerts_timestamp 
                ON public.whale_alerts (timestamp DESC);
                
                CREATE INDEX IF NOT EXISTS idx_whale_alerts_symbol 
                ON public.whale_alerts (symbol);
                """
                )
            )
            logger.info("Created indexes on whale_alerts table")
        except Exception as e:
            logger.error(f"Could not create indexes: {e}")
            raise

    logger.info("Database initialization complete")


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Database initialization should be invoked explicitly by the application
