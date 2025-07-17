"""Database session management for the Whale Alert application."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from whale_alert.db.models import SessionLocal


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get a database session as a context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
