from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Post
from app.models.social import Follow
from app.models.user import User
from app.schemas.common import Page
from app.schemas.post import PostRead
from app.schemas.user import UserPrivate, UserPublic, UserUpdate, UserWithStats
from app.security import get_current_user, get_optional_current_user
from app.services.posts import build_posts_page, get_user_by_username

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPrivate)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserPrivate)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{username}", response_model=UserWithStats)
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    _user: User | None = Depends(get_optional_current_user),
) -> UserWithStats:
    target = await get_user_by_username(db, username)

    followers_count = await db.scalar(
        select(func.count()).select_from(Follow).where(Follow.followed_id == target.id)
    )
    following_count = await db.scalar(
        select(func.count()).select_from(Follow).where(Follow.follower_id == target.id)
    )
    posts_count = await db.scalar(
        select(func.count())
        .select_from(Post)
        .where(Post.author_id == target.id, Post.repost_of_id.is_(None))
    )

    public = UserPublic.model_validate(target).model_dump()
    return UserWithStats(
        **public,
        followers_count=followers_count or 0,
        following_count=following_count or 0,
        posts_count=posts_count or 0,
    )


@router.post("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await get_user_by_username(db, username)
    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself"
        )
    if await db.get(Follow, (user.id, target.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already following this user"
        )
    db.add(Follow(follower_id=user.id, followed_id=target.id))
    try:
        await db.commit()
    except IntegrityError as exc:
        # Safety net for concurrent duplicate follows.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already following this user"
        ) from exc


@router.delete("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await get_user_by_username(db, username)
    follow = await db.get(Follow, (user.id, target.id))
    if follow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="You are not following this user"
        )
    await db.delete(follow)
    await db.commit()


@router.get("/{username}/followers", response_model=Page[UserPublic])
async def list_followers(
    username: str,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[UserPublic]:
    target = await get_user_by_username(db, username)
    stmt = (
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.followed_id == target.id)
        .order_by(Follow.created_at.desc(), User.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(User.id < cursor)
    users = (await db.scalars(stmt)).all()
    return _user_page(users, limit)


@router.get("/{username}/following", response_model=Page[UserPublic])
async def list_following(
    username: str,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[UserPublic]:
    target = await get_user_by_username(db, username)
    stmt = (
        select(User)
        .join(Follow, Follow.followed_id == User.id)
        .where(Follow.follower_id == target.id)
        .order_by(Follow.created_at.desc(), User.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(User.id < cursor)
    users = (await db.scalars(stmt)).all()
    return _user_page(users, limit)


@router.get("/{username}/posts", response_model=Page[PostRead])
async def list_user_posts(
    username: str,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    include_replies: bool = False,
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[PostRead]:
    target = await get_user_by_username(db, username)
    stmt = select(Post).where(Post.author_id == target.id)
    if not include_replies:
        stmt = stmt.where(Post.reply_to_id.is_(None))
    stmt = stmt.order_by(Post.id.desc()).limit(limit)
    if cursor is not None:
        stmt = stmt.where(Post.id < cursor)
    posts = (await db.scalars(stmt)).all()
    return await build_posts_page(db, posts, limit, user)


def _user_page(users: list[User], limit: int) -> Page[UserPublic]:
    items = [UserPublic.model_validate(u) for u in users]
    next_cursor = users[-1].id if len(users) == limit else None
    return Page(items=items, next_cursor=next_cursor)
