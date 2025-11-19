"""
Database configuration and session management.
Includes RLS context setting for multi-tenant isolation.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fullstack_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency that provides a database session.
    Use for routes that don't require tenant context (e.g., login, register).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_with_tenant(tenant_id: str, user_id: str = None):
    """
    Returns a database session with RLS context set.
    This enables Postgres Row Level Security policies.

    Args:
        tenant_id: The tenant UUID to set for RLS
        user_id: Optional user UUID for user-specific RLS policies

    Returns:
        Database session with RLS context configured
    """
    db = SessionLocal()
    try:
        # Set the tenant context for RLS policies
        db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        if user_id:
            db.execute(text(f"SET app.current_user_id = '{user_id}'"))
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context_with_tenant(tenant_id: str, user_id: str = None):
    """
    Context manager version for use in non-dependency scenarios.

    Usage:
        with get_db_context_with_tenant(tenant_id) as db:
            # db has RLS context set
            pass
    """
    db = SessionLocal()
    try:
        db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        if user_id:
            db.execute(text(f"SET app.current_user_id = '{user_id}'"))
        yield db
    finally:
        db.close()
