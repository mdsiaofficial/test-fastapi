from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.social import Like

# Many-to-many association between posts and hashtags.
post_hashtags = Table(
    "post_hashtags",
    Base.metadata,
    Column(
        "post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "hashtag_id", ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    posts: Mapped[list[Post]] = relationship(
        secondary=post_hashtags, back_populates="hashtags"
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Optional title turns a short "tweet" into a longer blog-style post.
    title: Mapped[str | None] = mapped_column(String(280), default=None)
    content: Mapped[str] = mapped_column(Text)
    # Self-references: a reply points at its parent, a repost at the original.
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True, default=None
    )
    repost_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
    hashtags: Mapped[list[Hashtag]] = relationship(
        secondary=post_hashtags, back_populates="posts"
    )
    likes: Mapped[list[Like]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    reply_to: Mapped[Post | None] = relationship(
        back_populates="replies", remote_side=[id], foreign_keys=[reply_to_id]
    )
    replies: Mapped[list[Post]] = relationship(
        back_populates="reply_to",
        foreign_keys=[reply_to_id],
        cascade="all, delete-orphan",
    )
    repost_of: Mapped[Post | None] = relationship(
        back_populates="reposts", remote_side=[id], foreign_keys=[repost_of_id]
    )
    reposts: Mapped[list[Post]] = relationship(
        back_populates="repost_of",
        foreign_keys=[repost_of_id],
        cascade="all, delete-orphan",
    )
