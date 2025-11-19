"""
Authentication utilities for password hashing and JWT token management.
"""

from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import hashlib
import secrets
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

# Security scheme for bearer token authentication
security = HTTPBearer()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Returns the hashed password as a string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Returns True if the password matches.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def create_access_token(user_id: str, tenant_id: str, email: str) -> str:
    """
    Create a short-lived JWT access token.
    Contains user_id, tenant_id, and email in the payload.
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Create a long-lived refresh token.
    Returns (raw_token, token_hash, expiry_datetime).
    The raw token is sent to the client, the hash is stored in DB.
    """
    # Generate a secure random token
    raw_token = secrets.token_urlsafe(32)

    # Hash the token for storage (using SHA256, not bcrypt for performance)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Calculate expiry
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    return raw_token, token_hash, expires_at


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for database lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Returns the payload if valid, raises HTTPException if invalid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Verify it's an access token
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get the current authenticated user.
    Extracts and validates the JWT from the Authorization header.

    Returns dict with user_id, tenant_id, and email.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    return {
        "user_id": payload["sub"],
        "tenant_id": payload["tenant_id"],
        "email": payload["email"]
    }
