from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.social import Follow, Like


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    following: Mapped[list[Follow]] = relationship(
        back_populates="follower",
        foreign_keys=[Follow.follower_id],
        cascade="all, delete-orphan",
    )
    followers: Mapped[list[Follow]] = relationship(
        back_populates="followed",
        foreign_keys=[Follow.followed_id],
        cascade="all, delete-orphan",
    )
    likes: Mapped[list[Like]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
