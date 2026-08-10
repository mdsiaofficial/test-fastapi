"""Password hashing, JWT token helpers, and FastAPI auth dependencies."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenPair

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False
)

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
def _create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        # jti makes every token unique, even when issued in the same second.
        "jti": uuid4().hex,
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id, REFRESH_TOKEN_TYPE, timedelta(days=settings.refresh_token_expire_days)
    )


def create_token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def _resolve_user(
    credentials: str | None, db: AsyncSession, expected_type: str
) -> User | None:
    if credentials is None:
        return None
    payload = decode_token(credentials)
    if payload.get("type") != expected_type:
        raise _INVALID_CREDENTIALS
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _INVALID_CREDENTIALS from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _INVALID_CREDENTIALS
    return user


async def get_current_user(
    credentials: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid access token and return the authenticated user."""
    user = await _resolve_user(credentials, db, ACCESS_TOKEN_TYPE)
    if user is None:
        raise _INVALID_CREDENTIALS
    return user


async def get_optional_current_user(
    credentials: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the authenticated user if a valid token is sent, else None."""
    return await _resolve_user(credentials, db, ACCESS_TOKEN_TYPE)
