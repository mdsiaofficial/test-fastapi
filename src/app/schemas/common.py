from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Cursor-paginated response envelope."""

    items: list[T]
    next_cursor: int | None = None
