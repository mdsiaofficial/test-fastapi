"""Shared business logic for users: pagination helpers."""

from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import UserPublic


def build_users_page(users: list[User], limit: int) -> Page[UserPublic]:
    """Wrap a list of users (ordered by id desc) into a cursor-paginated page."""
    items = [UserPublic.model_validate(u) for u in users]
    next_cursor = users[-1].id if len(users) == limit else None
    return Page(items=items, next_cursor=next_cursor)
