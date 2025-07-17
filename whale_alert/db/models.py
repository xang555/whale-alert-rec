"""Database models for the Whale Alert application."""
import logging
from datetime import datetime
from typing import Optional, List

# Configure logging
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from sqlalchemy.orm.decl_api import DeclarativeBase as Base
from sqlalchemy.types import TypeDecorator

from whale_alert.config import settings

# Create SQLAlchemy engine and session
engine = create_engine(
    str(settings.TIMESCALEDB_URL),
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

class WhaleAlert(Base):
    """Model for storing Whale Alert messages."""

    __tablename__ = "whale_alerts"
    __table_args__ = (
        # Composite primary key with timestamp for TimescaleDB compatibility
        {'comment': "Stores parsed whale alert messages from Telegram"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        primary_key=True,
        index=True,
        server_default=func.now(),
        comment="The timestamp of the whale alert"
    )
    blockchain: Mapped[str] = mapped_column(
        comment="The blockchain where the transaction occurred"
    )
    symbol: Mapped[str] = mapped_column(
        comment="The cryptocurrency symbol (e.g., BTC, ETH)"
    )
    amount: Mapped[float] = mapped_column(
        comment="The amount of cryptocurrency transferred"
    )
    amount_usd: Mapped[float] = mapped_column(
        comment="The USD value of the transferred amount"
    )
    from_address: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="The source address of the transaction"
    )
    to_address: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="The destination address of the transaction"
    )
    transaction_type: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="The type of transaction (e.g., transfer, deposit, withdrawal)"
    )
    hash: Mapped[str] = mapped_column(
        unique=True,
        index=True,
        comment="The transaction hash or unique identifier"
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="When this record was created in the database"
    )

    def __repr__(self) -> str:
        """Return string representation of the model."""
        return (
            f"<WhaleAlert(id={self.id}, "
            f"timestamp={self.timestamp.isoformat() if self.timestamp else None}, "
            f"blockchain={self.blockchain}, "
            f"symbol={self.symbol}, "
            f"amount={self.amount}, "
            f"amount_usd={self.amount_usd})>"
        )


def init_db() -> None:
    """Initialize the database with TimescaleDB extension and create tables."""
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import ProgrammingError, OperationalError

    # Create tables first
    Base.metadata.create_all(bind=engine)
    
    # Create a new connection for extension and hypertable operations
    with engine.connect() as connection:
        # Start a new transaction
        with connection.begin():
            # Create timescaledb extension if it doesn't exist
            try:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
                logger.info("TimescaleDB extension checked/created")
            except (ProgrammingError, OperationalError) as e:
                logger.warning(f"Could not create timescaledb extension: {e}")
                # Continue even if extension creation fails

        # Check if the table exists before trying to convert to hypertable
        inspector = inspect(engine)
        if 'whale_alerts' in inspector.get_table_names(schema='public'):
            # Start a new transaction for hypertable check
            with connection.begin():
                # Check if the table is already a hypertable
                result = connection.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT 1 FROM _timescaledb_catalog.hypertable 
                            WHERE table_name = 'whale_alerts'
                        )
                    """)
                ).scalar()
                
                if not result:
                    try:
                        # Convert to hypertable if not already one
                        connection.execute(
                            text("""
                                SELECT create_hypertable(
                                    'public.whale_alerts', 'timestamp',
                                    if_not_exists => TRUE,
                                    migrate_data => TRUE
                                )
                            """)
                        )
                        logger.info("Successfully converted whale_alerts to hypertable")
                    except Exception as e:
                        logger.warning(f"Could not convert whale_alerts to hypertable: {e}")
                        # Continue even if hypertable conversion fails
    
    logger.info("Database initialization complete")


def get_db() -> Session:
    """Get a database session.
    
    Yields:
        Session: A database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize the database when the module is imported
init_db()
