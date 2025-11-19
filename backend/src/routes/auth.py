"""
Authentication routes for user registration, login, token refresh, and logout.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from src.database import get_db
from src.models import User, Tenant, RefreshToken
from src.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    get_current_user
)
from src.config import REFRESH_TOKEN_EXPIRE_DAYS

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================
# Request/Response Schemas
# ============================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str  # UUID of selected tenant


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    email: str


class TenantResponse(BaseModel):
    id: str
    name: str


# ============================================
# Routes
# ============================================

@router.get("/tenants", response_model=list[TenantResponse])
async def get_tenants(db: Session = Depends(get_db)):
    """
    Get list of available tenants for registration dropdown.
    This is a public endpoint.
    """
    tenants = db.query(Tenant).all()
    return [{"id": str(t.id), "name": t.name} for t in tenants]


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    Returns access token in body and sets refresh token as HttpOnly cookie.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == request.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID"
        )

    # Create user with hashed password
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        tenant_id=request.tenant_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create tokens
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )

    raw_refresh_token, token_hash, expires_at = create_refresh_token()

    # Store refresh token hash in database
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(refresh_token_record)
    db.commit()

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,  # Only send over HTTPS (disable for local dev if needed)
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth/refresh"  # Only sent to refresh endpoint
    )

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return tokens.
    Returns access token in body and sets refresh token as HttpOnly cookie.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Create access token
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )

    # Create and store refresh token
    raw_refresh_token, token_hash, expires_at = create_refresh_token()

    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(refresh_token_record)
    db.commit()

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth/refresh"
    )

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Get a new access token using refresh token from cookie.
    Also rotates the refresh token for security.
    """
    # Get refresh token from cookie
    raw_refresh_token = request.cookies.get("refresh_token")
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )

    # Hash the token to look it up
    token_hash = hash_refresh_token(raw_refresh_token)

    # Find the token in database
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check if expired
    if stored_token.expires_at < datetime.utcnow():
        # Delete expired token
        db.delete(stored_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    # Get the user
    user = db.query(User).filter(User.id == stored_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Create new access token
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )

    # Rotate refresh token (delete old, create new)
    db.delete(stored_token)

    new_raw_token, new_token_hash, new_expires_at = create_refresh_token()
    new_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=new_expires_at
    )
    db.add(new_refresh_token)
    db.commit()

    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=new_raw_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth/refresh"
    )

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Logout user by invalidating refresh token.
    Clears the refresh token cookie.
    """
    # Get refresh token from cookie
    raw_refresh_token = request.cookies.get("refresh_token")

    if raw_refresh_token:
        # Delete from database
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if stored_token:
            db.delete(stored_token)
            db.commit()

    # Clear the cookie
    response.delete_cookie(
        key="refresh_token",
        path="/auth/refresh"
    )

    return {"message": "Logged out successfully"}
