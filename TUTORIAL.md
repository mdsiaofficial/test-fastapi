# Twatter — FastAPI Pattern Tutorial

A code-walkthrough of the three patterns that make this codebase tick. Read this
alongside the code — every snippet below is copied from the project, so you can
open the file and follow along.

| # | Pattern | Where to look |
|---|---------|---------------|
| 1 | **Auth dependencies** — "require auth" vs "auth if present" | `src/app/security.py`, `src/app/routers/auth.py` |
| 2 | **Service layer** — thin routers, batched queries, no N+1 | `src/app/services/posts.py`, `src/app/services/users.py` |
| 3 | **Cursor pagination** — keyset pages that never skip rows | `src/app/schemas/common.py`, any list endpoint |

---

## 0. The big picture: one-directional layering

Every request travels through the same layers, always in the same direction:

```
 HTTP request
      │
      ▼
 Router        (parses params, declares auth, sets status codes)
      │  calls
      ▼
 Service       (queries, counts, serializes — pure business logic)
      │  uses
      ▼
 Models + Schemas  (what the data looks like)
      │
      ▼
 Database / JSON response
```

- **Routers** (`app/routers/`) know about HTTP: `Depends()`, `Query()`, status codes, exceptions.
- **Services** (`app/services/`) know about the database and business rules — they don't import FastAPI dependencies.
- **Models** (`app/models/`) define tables; **schemas** (`app/schemas/`) define request/response shapes.

Keep the arrows pointing down and the codebase stays easy to navigate, test, and extend.

---

## 1. Pattern 1 — Auth dependencies

### 1.1 The idea

Instead of every route manually extracting the `Authorization` header, decoding the
JWT, and loading the user from the database, you write that logic **once** as a
FastAPI *dependency* and declare it in a route's signature. FastAPI resolves the
dependency, runs it, and injects the result into your handler.

The clever part of this codebase is that there are **two** public auth dependencies
that share one private resolver — one for "this endpoint requires a logged-in user"
and one for "auth is optional, personalize the response if you can".

### 1.2 The scheme that makes it possible (`security.py`)

```python
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False
)
```

Two things to notice:

- **`tokenUrl`** — not used by your code at runtime. It tells Swagger UI's
  "Authorize" button where to send the login form. Purely documentation.
- **`auto_error=False`** — the important one. With the default `auto_error=True`, a
  missing `Authorization` header raises 401 *inside the dependency itself*, and you
  can't tell "no token" apart from "invalid token". With `False`, it returns `None`
  when the header is absent, and **your** code decides what that means. This single
  flag is what enables optional auth.

### 1.3 Token design — one secret, two token kinds (`security.py`)

```python
def _create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "jti": uuid4().hex,          # unique ID — two tokens are never identical
        "sub": str(user_id),         # "subject" — the standard JWT claim for the user
        "type": token_type,          # "access" or "refresh" — your claim
        "iat": now,                  # issued at
        "exp": now + expires_delta,  # expires
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

Three patterns worth stealing:

1. **`jti`** — `exp` has second resolution, so two tokens issued in the same second
   would be byte-identical without it. `jti` makes every token unique (and gives you
   a handle for future revocation).
2. **`type` claim** — one HMAC secret signs both access and refresh tokens. The
   `type` claim is checked on every decode so a refresh token can never be used as
   an access token, and vice versa.
3. **`sub` as a string** — JWT payloads are JSON, your ids are ints. Store `sub` as
   a string and parse it back with `int(payload["sub"])` — wrapped in `try/except`
   so a validly-signed but malformed token returns 401 instead of crashing with a
   500 (the refresh endpoint originally missed this guard — a fixed bug).

### 1.4 The shared resolver + two public dependencies (`security.py`)

```python
async def _resolve_user(credentials: str | None, db: AsyncSession, expected_type: str) -> User | None:
    if credentials is None:
        return None                       # no header → nobody is logged in
    payload = decode_token(credentials)   # invalid/expired → raises 401 for us
    if payload.get("type") != expected_type:
        raise _INVALID_CREDENTIALS
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _INVALID_CREDENTIALS from exc
    user = await db.get(User, user_id)    # DB lookup by primary key
    if user is None or not user.is_active:
        raise _INVALID_CREDENTIALS
    return user
```

That is the *entire* auth logic. Both public dependencies are thin wrappers:

```python
async def get_current_user(
    credentials: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _resolve_user(credentials, db, ACCESS_TOKEN_TYPE)
    if user is None:
        raise _INVALID_CREDENTIALS
    return user


async def get_optional_current_user(
    credentials: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    return await _resolve_user(credentials, db, ACCESS_TOKEN_TYPE)
```

This is **composition over duplication**: both depend on one `_resolve_user`. If you
ever add a check (admin-only, email-verified, rate-limit), you add it in one place.

### 1.5 Using them in routes

**Required auth** — creating a post (`routers/posts.py`):

```python
@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    post = await _create_post(db, user, payload.content, title=payload.title)
    ...
```

**Optional auth** — viewing a post publicly, but personalizing `is_liked`
(`routers/posts.py`):

```python
@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostRead:
    post = await get_post_or_404(db, post_id)
    items = await serialize_posts(db, [post], user)   # user may be None
    return items[0]
```

One endpoint, two audiences: anonymous callers get `user=None`; logged-in callers
get their `User` object. The serializer uses it to fill `is_liked`.

### 1.6 The request lifecycle, end to end

```
GET /posts/42  with  Authorization: Bearer <token>
        │
        ▼
OAuth2PasswordBearer extracts the token ── no header → None → anonymous mode
        │
        ▼
decode_token() verifies signature + exp ── bad → 401 "Invalid or expired token"
        │
        ▼
type claim == "access"?
        │
        ▼
db.get(User, sub)  +  is_active check ── missing/deactivated → 401
        │
        ▼
   your User object, ready to use
```

### 1.7 Supporting pieces

- **Password hashing** (`security.py`): `bcrypt.hashpw`/`checkpw`, never stored in
  plain text. `verify_password` also catches `ValueError` so a corrupt hash returns
  `False` instead of raising.
- **Login** (`routers/auth.py`): uses `OAuth2PasswordRequestForm` (form fields, not
  JSON — that's what Swagger's "Authorize" button sends). Lookup is
  `or_(User.email == identifier, User.username == identifier)` — one query, two ways
  to log in.
- **Refresh** (`routers/auth.py`): decode → check `type == "refresh"` → load user →
  issue a fresh pair. Stateless, no server-side session storage.

---

## 2. Pattern 2 — Service layer

### 2.1 Why services exist

A route handler should be a *translator*, not a brain. The codebase enforces this
with a `services/` package that owns the business logic while routers stay thin.

### 2.2 Lookup helpers with the contract in the name (`services/posts.py`)

```python
async def get_post_or_404(db: AsyncSession, post_id: int) -> Post:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post
```

The name documents the contract: *returns a Post or raises 404*. Every route that
needs a post calls this — no `if post is None` blocks copy-pasted across the routers.
Same idea: `get_user_by_username`.

### 2.3 `serialize_posts` — defeating the N+1 problem

This is the pattern to study hardest (`services/posts.py`):

```python
async def serialize_posts(
    db: AsyncSession, posts: list[Post], current_user: User | None
) -> list[PostRead]:
    if not posts:
        return []

    ids = [post.id for post in posts]

    # ONE query, eager-loading author + hashtags for ALL posts at once
    loaded = (
        await db.scalars(
            select(Post)
            .where(Post.id.in_(ids))
            .options(selectinload(Post.author), selectinload(Post.hashtags))
        )
    ).all()
    by_id = {post.id: post for post in loaded}

    # THREE grouped COUNT queries for every post at once
    like_counts, reply_counts, repost_counts = await _count_rows(db, ids)

    # ONE query for "which of these did current_user like?"
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
    ...
```

**What is the N+1 problem?** The naive version queries the database *once per post*:
author, hashtags, like count, reply count, repost count, liked-by-me — up to 6
queries × 20 posts = **120 round-trips** per page. This code replaces every one of
those with a single batched query:

- `selectinload(Post.author)` / `selectinload(Post.hashtags)` — eager-loads the
  relationships of *all* posts in one extra query (`WHERE id IN (...)`).
- `_count_rows` — runs three `GROUP BY` queries and builds `{post_id: count}` dicts:
  `SELECT post_id, COUNT(*) ... WHERE post_id IN (...) GROUP BY post_id`.
- `liked_ids` — one `SELECT ... WHERE post_id IN (...) AND user_id = me` answers
  `is_liked` for the whole page.

Total: **6 queries regardless of page size.** That is the difference between "works
in dev" and "survives production".

### 2.4 The page wrappers (`services/posts.py`, `services/users.py`)

```python
async def build_posts_page(db, posts, limit, current_user) -> Page[PostRead]:
    items = await serialize_posts(db, posts, current_user)
    next_cursor = posts[-1].id if len(posts) == limit else None
    return Page(items=items, next_cursor=next_cursor)
```

and, for user lists:

```python
def build_users_page(users: list[User], limit: int) -> Page[UserPublic]:
    items = [UserPublic.model_validate(u) for u in users]
    next_cursor = users[-1].id if len(users) == limit else None
    return Page(items=items, next_cursor=next_cursor)
```

One builder per entity type, reused by every list endpoint.

### 2.5 Why services take plain parameters instead of `Depends`

```python
async def serialize_posts(db: AsyncSession, posts: list[Post], current_user: User | None) -> list[PostRead]:
```

No `Depends()` inside services — `db` and `current_user` are passed *in* by the
router. That is deliberate:

- **Testability** — call `serialize_posts` with any session; no HTTP context needed.
- **Reusability** — the same function serves `GET /posts/{id}`, the home feed,
  hashtag search, and user profiles. Each route just hands it different posts.
- **One direction of knowledge** — routers know FastAPI (`Depends`, `Query`,
  exceptions); services know the database. Never the reverse.

> **Observation for you:** `_create_post`, `_get_or_create_hashtags`, and
> `extract_hashtags` live in `routers/posts.py`, not in `services/`. That's a small
> layering inconsistency — moving them into `services/posts.py` would make every
> layer's job unambiguous. Try it as an exercise.

---

## 3. Pattern 3 — Cursor pagination

### 3.1 Keyset vs OFFSET

List endpoints return `{"items": [...], "next_cursor": 123}`, and the client asks
for the next page by passing the cursor back. That is **keyset pagination**: instead
of "skip 20 rows" (`OFFSET`), you say "give me everything before this marker"
(`WHERE id < 123`).

Why keyset beats offset:

- **No skipped/duplicated rows** — with OFFSET, if someone posts between page 1 and
  page 2, rows shift and you see a post twice (or miss one). With keyset, new rows
  are *above* your cursor, so you only ever see rows below it.
- **Stable under concurrent writes** — the same property, applied to followers and
  likes.
- **Index-friendly** — `WHERE id < X ORDER BY id DESC` uses the primary key index;
  OFFSET must count and discard N rows on every request.

### 3.2 The envelope: a generic schema (`schemas/common.py`)

```python
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Cursor-paginated response envelope."""

    items: list[T]
    next_cursor: int | None = None
```

One envelope, reused everywhere via `Page[PostRead]`, `Page[UserPublic]`, … — your
next list endpoint gets the pagination contract for free.

### 3.3 The query pattern (every list endpoint)

```python
stmt = (
    select(Post)
    .where(Post.reply_to_id == post_id)
    .order_by(Post.id.desc())
    .limit(limit)
)
if cursor is not None:
    stmt = stmt.where(Post.id < cursor)   # "everything older than this marker"
posts = (await db.scalars(stmt)).all()
return await build_posts_page(db, posts, limit, user)
```

### 3.4 The `next_cursor` logic

```python
next_cursor = posts[-1].id if len(posts) == limit else None
```

- **Fewer than `limit` rows returned** → definitely the last page → `None`.
- **Exactly `limit` rows** → there *might* be more → return the last item's id.

Note the honest contract: a full page means "maybe more", not "definitely more". If
there isn't more, the next request returns an empty `items` list with
`next_cursor: None` — a valid final page, and the client stops.

### 3.5 ⚠️ The invariant — and the bug it prevents

> **The ORDER BY columns must encode exactly what the cursor encodes — nothing more, nothing less.**

The followers list originally did:

```python
.order_by(Follow.created_at.desc(), User.id.desc())   # ordered by TWO columns
...
.where(User.id < cursor)                              # but the cursor = ONE column
```

The cursor only encoded `id`, but the ordering depended on `created_at` first. When
follow recency disagreed with user-id order (a newer account follows an older one),
rows were **silently skipped** across pages — someone followed a user and that user
never appeared in anyone's paginated follower list. The fix aligns them:

```python
.order_by(User.id.desc())     # one column, the same one the cursor uses
```

**The general rule:** pick your cursor column first. Then make `ORDER BY` exactly
that column. If you need a secondary sort key, it must be *included in the cursor*
(a composite cursor) — never sort by something the cursor doesn't encode.

### 3.6 Bonus: the feed's subquery trick (`routers/feed.py`)

```python
following_ids = select(Follow.followed_id).where(Follow.follower_id == user.id)

stmt = select(Post).where(
    or_(Post.author_id == user.id, Post.author_id.in_(following_ids))
)
```

`following_ids` is a `select()` statement that is never executed on its own —
SQLAlchemy inlines it as `WHERE author_id IN (SELECT followed_id FROM follows ...)`.
One round-trip, no separate query to build a Python list of ids. Elegant, steal it.

---

## 4. Exercises

Test your understanding — each one can be done in an hour or two:

1. **Move the hashtag helpers.** Move `extract_hashtags`, `_get_or_create_hashtags`,
   and `_create_post` from `routers/posts.py` into `services/posts.py`, and update
   the imports. Run `uv run pytest` — all tests must still pass.
2. **Add a `search` endpoint.** `GET /posts/search?q=...` that matches content
   case-insensitively and returns a `Page[PostRead]`. Reuse `build_posts_page`.
   Think about the pagination invariant (3.5) while writing it.
3. **Add a rate limit dependency.** Write a `Depends`-style dependency in
   `security.py` that rejects more than N requests per minute from the same client
   with 429. Wire it into the auth router.
4. **Personalize the profile.** Add `is_following: bool` to `UserWithStats`, filled
   when the caller is authenticated (`get_optional_current_user`) — the same pattern
   as `is_liked`.

## 5. Cheat sheet

| Concept | The one-liner |
|---------|---------------|
| Required auth | `user: User = Depends(get_current_user)` |
| Optional auth | `user: User \| None = Depends(get_optional_current_user)` |
| No header = no auth | `OAuth2PasswordBearer(..., auto_error=False)` |
| One secret, two tokens | the `type` claim, checked on every decode |
| Thin router | HTTP concerns only; business logic lives in `services/` |
| No N+1 | batch with `selectinload` + `GROUP BY` counts + one `IN (...)` |
| Pagination envelope | `Page[T]` from `schemas/common.py` |
| Pagination invariant | `ORDER BY` must encode exactly the cursor column |
| Cursor semantics | full page → `next_cursor = last_id`; short page → `None` |
