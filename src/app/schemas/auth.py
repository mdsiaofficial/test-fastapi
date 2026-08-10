from pydantic import BaseModel

from app.schemas.user import UserPrivate


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(TokenPair):
    user: UserPrivate


class RefreshRequest(BaseModel):
    refresh_token: str
