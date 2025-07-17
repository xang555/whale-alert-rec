"""Database models for the Whale Alert application."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from whale_alert.config import settings

# Create SQLAlchemy engine and session
engine = create_engine(str(settings.TIMESCALEDB_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


class WhaleAlert(Base):
    """Model for storing Whale Alert messages."""

    __tablename__ = "whale_alerts"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    blockchain = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    amount_usd = Column(Float, nullable=False)
    from_address = Column(String, nullable=True)
    to_address = Column(String, nullable=True)
    transaction_type = Column(String, nullable=True)
    hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Return string representation of the model."""
        return (
            f"<WhaleAlert(id={self.id}, "
            f"timestamp={self.timestamp}, "
            f"blockchain={self.blockchain}, "
            f"symbol={self.symbol}, "
            f"amount={self.amount}, "
            f"amount_usd={self.amount_usd})>"
        )


def init_db() -> None:
    """Initialize the database with TimescaleDB extension and create tables."""
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    # Create the database schema if it doesn't exist
    with engine.connect() as connection:
        # Create timescaledb extension if it doesn't exist
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            connection.commit()
        except ProgrammingError as e:
            print(f"Warning: Could not create timescaledb extension: {e}")
            connection.rollback()

        # Create tables
        Base.metadata.create_all(bind=engine)

        # Convert the table to a hypertable if it's not already
        try:
            connection.execute(
                text(
                    """
                    SELECT create_hypertable(
                        'whale_alerts', 'timestamp',
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    )
                    """
                )
            )
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not create hypertable: {e}")
            connection.rollback()


# Initialize the database when the module is imported
init_db()
