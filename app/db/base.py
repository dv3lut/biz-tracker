"""SQLAlchemy declarative base module."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all ORM models."""

    pass
