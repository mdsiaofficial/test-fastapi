import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Hashtag, Post
from app.models.social import Like
from app.models.user import User
from app.schemas.common import Page
from app.schemas.post import PostCreate, PostRead, ReplyCreate, RepostCreate
from app.schemas.user import UserPublic
from app.security import get_current_user, get_optional_current_user
from app.services.posts import build_posts_page, get_post_or_404, serialize_posts

router = APIRouter(prefix="/posts", tags=["posts"])

HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")


def extract_hashtags(content: str) -> list[str]:
    """Return unique, lowercased hashtag names found in the content."""
    return sorted({match[1:].lower() for match in HASHTAG_RE.findall(content)})


async def _get_or_create_hashtags(
    db: AsyncSession, names: list[str]
) -> list[Hashtag]:
    if not names:
        return []
    existing = (
        await db.scalars(select(Hashtag).where(Hashtag.name.in_(names)))
    ).all()
    by_name = {tag.name: tag for tag in existing}
    fresh = [Hashtag(name=name) for name in names if name not in by_name]
    if fresh:
        db.add_all(fresh)
        await db.flush()
    return list(by_name.values()) + fresh


async def _create_post(
    db: AsyncSession,
    user: User,
    content: str,
    *,
    title: str | None = None,
    reply_to_id: int | None = None,
    repost_of_id: int | None = None,
) -> Post:
    content = content.strip()
    if not content and repost_of_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Content must not be empty",
        )
    if reply_to_id is not None and repost_of_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A post cannot be both a reply and a repost",
        )

    post = Post(
        author_id=user.id,
        title=title,
        content=content,
        reply_to_id=reply_to_id,
        repost_of_id=repost_of_id,
    )
    post.hashtags = await _get_or_create_hashtags(db, extract_hashtags(content))
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    post = await _create_post(db, user, payload.content, title=payload.title)
    items = await serialize_posts(db, [post], user)
    return items[0]


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    post = await get_post_or_404(db, post_id)
    items = await serialize_posts(db, [post], user)
    return items[0]


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    post = await get_post_or_404(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts",
        )
    await db.delete(post)
    await db.commit()


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------
@router.post("/{post_id}/replies", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def reply_to_post(
    post_id: int,
    payload: ReplyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    await get_post_or_404(db, post_id)
    post = await _create_post(db, user, payload.content, reply_to_id=post_id)
    items = await serialize_posts(db, [post], user)
    return items[0]


@router.get("/{post_id}/replies", response_model=Page[PostRead])
async def list_replies(
    post_id: int,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[PostRead]:
    await get_post_or_404(db, post_id)
    stmt = (
        select(Post)
        .where(Post.reply_to_id == post_id)
        .order_by(Post.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(Post.id < cursor)
    posts = (await db.scalars(stmt)).all()
    return await build_posts_page(db, posts, limit, user)


# ---------------------------------------------------------------------------
# Reposts
# ---------------------------------------------------------------------------
@router.post("/{post_id}/repost", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def repost_post(
    post_id: int,
    payload: RepostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    original = await get_post_or_404(db, post_id)
    existing = await db.scalar(
        select(Post).where(
            Post.author_id == user.id, Post.repost_of_id == original.id
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already reposted this post"
        )
    post = await _create_post(
        db, user, payload.quote or "", repost_of_id=original.id
    )
    items = await serialize_posts(db, [post], user)
    return items[0]



@router.delete("/{post_id}/repost", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repost(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await get_post_or_404(db, post_id)
    repost = await db.scalar(
        select(Post).where(
            Post.author_id == user.id, Post.repost_of_id == post_id
        )
    )
    if repost is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repost not found"
        )
    await db.delete(repost)
    await db.commit()


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------
@router.post("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await get_post_or_404(db, post_id)
    if await db.get(Like, (user.id, post_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Post already liked"
        )
    db.add(Like(user_id=user.id, post_id=post_id))
    try:
        await db.commit()
    except IntegrityError as exc:
        # Safety net for concurrent duplicate likes.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Post already liked"
        ) from exc


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await get_post_or_404(db, post_id)
    like = await db.get(Like, (user.id, post_id))
    if like is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not liked"
        )
    await db.delete(like)
    await db.commit()


@router.get("/{post_id}/likes", response_model=Page[UserPublic])
async def list_likes(
    post_id: int,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[UserPublic]:
    await get_post_or_404(db, post_id)
    stmt = (
        select(User)
        .join(Like, Like.user_id == User.id)
        .where(Like.post_id == post_id)
        .order_by(Like.created_at.desc(), User.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(User.id < cursor)
    users = (await db.scalars(stmt)).all()
    items = [UserPublic.model_validate(u) for u in users]
    next_cursor = users[-1].id if len(users) == limit else None
    return Page(items=items, next_cursor=next_cursor)
