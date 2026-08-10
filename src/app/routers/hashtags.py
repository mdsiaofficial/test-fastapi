from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Hashtag, Post, post_hashtags
from app.models.user import User
from app.schemas.common import Page
from app.schemas.post import PostRead
from app.security import get_optional_current_user
from app.services.posts import build_posts_page

router = APIRouter(prefix="/hashtags", tags=["hashtags"])


@router.get("/{name}/posts", response_model=Page[PostRead])
async def list_hashtag_posts(
    name: str,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[PostRead]:
    tag = await db.scalar(select(Hashtag).where(Hashtag.name == name.lower()))
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Hashtag not found"
        )
    stmt = (
        select(Post)
        .join(post_hashtags, post_hashtags.c.post_id == Post.id)
        .where(post_hashtags.c.hashtag_id == tag.id)
        .order_by(Post.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(Post.id < cursor)
    posts = (await db.scalars(stmt)).all()
    return await build_posts_page(db, posts, limit, user)
