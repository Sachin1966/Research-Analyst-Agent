"""
Authentication & Security Module for Research Paper Agent.

Handles:
- Password hashing & verification using bcrypt
- JSON Web Token (JWT) generation & decoding (PyJWT)
- FastAPI dependencies for protected endpoints (get_current_user, get_optional_user)
- 7-Day Free Trial and Pro plan access verification middleware
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
import bcrypt
from fastapi import Header, Cookie, HTTPException, status, Depends

import database

# Secret key for signing JWT tokens (can be set via JWT_SECRET environment variable)
JWT_SECRET = os.environ.get("JWT_SECRET", "veritas-core-research-jwt-super-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token for an authenticated user."""
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency that returns the current authenticated user if present,
    or None if the request is unauthenticated. Checks both Authorization header and Cookie.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1].strip()
    elif access_token:
        token = access_token.strip()

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    try:
        user_id = int(payload["sub"])
        user = database.get_user_by_id(user_id)
        return user
    except Exception:
        return None


async def get_current_user(user: Optional[Dict[str, Any]] = Depends(get_optional_user)) -> Dict[str, Any]:
    """
    FastAPI dependency that enforces authentication. Raises 401 if user is not logged in.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def verify_trial_or_pro(user: Dict[str, Any]):
    """
    Validates whether the user's 7-day free trial is active or if they have a Pro subscription.
    Raises HTTP 402 Payment Required if expired.
    """
    status_info = database.get_user_trial_status(user)
    if not status_info["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "TRIAL_EXPIRED",
                "message": "Your 7-day free trial has expired. Please upgrade to Pro to unlock unlimited model access.",
                "trial_status": status_info
            }
        )
    return status_info

