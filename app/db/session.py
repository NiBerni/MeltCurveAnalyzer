"""
Database session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import DATABASE_URL

# Engine & Session Factory (Beispiel für SQLite/PostgreSQL)
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)


def get_session():
    """Returns a thread-safe scoped database session."""
    return db_session()
