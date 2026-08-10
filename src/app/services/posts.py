"""Shared business logic for posts: loading, stats, and serialization."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.social import Like
from app.models.user import User
from app.schemas.common import Page
from app.schemas.post import PostRead
from app.schemas.user import UserPublic


async def get_post_or_404(db: AsyncSession, post_id: int) -> Post:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


async def get_user_by_username(db: AsyncSession, username: str) -> User:
    user = await db.scalar(select(User).where(User.username == username.lower()))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


async def _count_rows(db: AsyncSession, post_ids: list[int]) -> tuple[dict, dict, dict]:
    """Return (like, reply, repost) counts keyed by post id."""
    if not post_ids:
        return {}, {}, {}

    like_rows = await db.execute(
        select(Like.post_id, func.count())
        .where(Like.post_id.in_(post_ids))
        .group_by(Like.post_id)
    )
    reply_rows = await db.execute(
        select(Post.reply_to_id, func.count())
        .where(Post.reply_to_id.in_(post_ids))
        .group_by(Post.reply_to_id)
    )
    repost_rows = await db.execute(
        select(Post.repost_of_id, func.count())
        .where(Post.repost_of_id.in_(post_ids))
        .group_by(Post.repost_of_id)
    )
    return (
        dict(like_rows.all()),
        dict(reply_rows.all()),
        dict(repost_rows.all()),
    )


async def serialize_posts(
    db: AsyncSession, posts: list[Post], current_user: User | None
) -> list[PostRead]:
    """Build PostRead responses with author, hashtags, counts, and is_liked."""
    if not posts:
        return []

    ids = [post.id for post in posts]
    loaded = (
        await db.scalars(
            select(Post)
            .where(Post.id.in_(ids))
            .options(selectinload(Post.author), selectinload(Post.hashtags))
        )
    ).all()
    by_id = {post.id: post for post in loaded}

    like_counts, reply_counts, repost_counts = await _count_rows(db, ids)

    liked_ids: set[int] = set()
    if current_user is not None:
        liked_ids = set(
            (
                await db.scalars(
                    select(Like.post_id).where(
                        Like.post_id.in_(ids), Like.user_id == current_user.id
                    )
                )
            ).all()
        )

    result: list[PostRead] = []
    for post in posts:
        record = by_id.get(post.id)
        if record is None:  # pragma: no cover - defensive
            continue
        result.append(
            PostRead(
                id=record.id,
                author=UserPublic.model_validate(record.author),
                title=record.title,
                content=record.content,
                hashtags=[tag.name for tag in record.hashtags],
                reply_to_id=record.reply_to_id,
                repost_of_id=record.repost_of_id,
                is_reply=record.reply_to_id is not None,
                is_repost=record.repost_of_id is not None,
                like_count=like_counts.get(record.id, 0),
                reply_count=reply_counts.get(record.id, 0),
                repost_count=repost_counts.get(record.id, 0),
                is_liked=record.id in liked_ids,
                created_at=record.created_at,
            )
        )
    return result


async def build_posts_page(
    db: AsyncSession, posts: list[Post], limit: int, current_user: User | None
) -> Page[PostRead]:
    """Wrap a list of posts (ordered id desc) into a cursor-paginated page."""
    items = await serialize_posts(db, posts, current_user)
    next_cursor = posts[-1].id if len(posts) == limit else None
    return Page(items=items, next_cursor=next_cursor)
