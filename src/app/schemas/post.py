from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic

MAX_POST_LENGTH = 5000
MAX_TITLE_LENGTH = 280


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_POST_LENGTH)
    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)


class ReplyCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_POST_LENGTH)


class RepostCreate(BaseModel):
    """Optional quote to attach to a repost; an empty/None quote is a plain repost."""

    quote: str | None = Field(default=None, max_length=MAX_POST_LENGTH)


class PostRead(BaseModel):
    id: int
    author: UserPublic
    title: str | None = None
    content: str
    hashtags: list[str] = []
    reply_to_id: int | None = None
    repost_of_id: int | None = None
    is_reply: bool = False
    is_repost: bool = False
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    is_liked: bool = False
    created_at: datetime
