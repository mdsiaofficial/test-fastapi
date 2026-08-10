from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(
        min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$"
    )
    display_name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(
        default=None, min_length=1, max_length=100
    )


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserPublic(BaseModel):
    """Public profile information, safe to expose to any client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class UserPrivate(UserPublic):
    """Full profile information, only returned to the account owner."""

    email: str


class UserWithStats(UserPublic):
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
