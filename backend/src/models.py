"""
SQLAlchemy models for the analytics platform.
Implements multi-tenant data isolation with proper relationships.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.database import Base


class Tenant(Base):
    """
    Represents an organization/company in the multi-tenant system.
    Each tenant has isolated data from other tenants.
    """
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """
    User account belonging to a tenant.
    Stores hashed password, never plaintext.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """
    Stores hashed refresh tokens for secure session management.
    Tokens are hashed before storage for security.
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class Dataset(Base):
    """
    Metadata for an uploaded CSV dataset.
    Stores column information and links to actual row data.
    """
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    columns = Column(JSONB, nullable=False)  # [{name: str, type: "categorical"|"continuous"}, ...]
    row_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="datasets")
    user = relationship("User", back_populates="datasets")
    rows = relationship("DatasetRow", back_populates="dataset", cascade="all, delete-orphan")


class DatasetRow(Base):
    """
    Individual row of data from an uploaded CSV.
    Uses JSONB for flexible schema storage.
    """
    __tablename__ = "dataset_rows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)  # Denormalized for RLS
    row_data = Column(JSONB, nullable=False)

    # Relationships
    dataset = relationship("Dataset", back_populates="rows")


# Keep legacy model for backward compatibility during development
class GapminderData(Base):
    """Legacy gapminder table - can be removed after migration."""
    __tablename__ = "gapminder_data"

    id = Column(Integer, primary_key=True, index=True)
    country = Column(String, index=True)
    continent = Column(String, index=True)
    year = Column(Integer, index=True)
    life_exp = Column(Float)
    pop = Column(Integer)
    gdp_per_cap = Column(Float)
