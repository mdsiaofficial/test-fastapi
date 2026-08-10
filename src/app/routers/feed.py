from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Post
from app.models.social import Follow
from app.models.user import User
from app.schemas.common import Page
from app.schemas.post import PostRead
from app.security import get_current_user
from app.services.posts import build_posts_page

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=Page[PostRead])
async def home_feed(
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    include_replies: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[PostRead]:
    """Posts from people the user follows plus their own, newest first."""
    following_ids = select(Follow.followed_id).where(Follow.follower_id == user.id)
    stmt = select(Post).where(
        or_(Post.author_id == user.id, Post.author_id.in_(following_ids))
    )
    if not include_replies:
        stmt = stmt.where(Post.reply_to_id.is_(None))
    stmt = stmt.order_by(Post.id.desc()).limit(limit)
    if cursor is not None:
        stmt = stmt.where(Post.id < cursor)

    posts = (await db.scalars(stmt)).all()
    return await build_posts_page(db, posts, limit, user)
