# Twatter — a Twitter-like social media & blogging API

A production-shaped FastAPI backend for a social network / micro-blogging platform in
the style of Twitter: users, posts (short tweets or long-form blog posts with a title),
follows, likes, replies, reposts, hashtags and a home feed.

Built with **FastAPI + async SQLAlchemy 2.0 + PostgreSQL**, with JWT auth, Alembic
migrations, Docker Compose, and a full pytest suite.

## Features

- **Auth** — register, login (email or username), JWT access + refresh tokens, bcrypt
  password hashing
- **Users** — public profiles with follower/following/post stats, profile updates,
  follow / unfollow, follower & following lists
- **Posts** — create short "tweets" or longer blog-style posts (optional `title`),
  fetch by id, delete (owner only)
- **Social graph** — likes, replies (comments), reposts (optionally with a quote)
- **Hashtags** — automatically extracted from post content, searchable
- **Home feed** — posts from people you follow plus your own, newest first
- **Cursor pagination** — every list endpoint returns `items` + `next_cursor`
- **Migrations** — Alembic with an async environment; schema managed by `alembic upgrade head`

## Tech stack

| Layer      | Choice                                             |
| ---------- | -------------------------------------------------- |
| Framework  | FastAPI + Uvicorn                                  |
| ORM        | SQLAlchemy 2.0 (async) + Pydantic v2               |
| Database   | PostgreSQL 16 (psycopg 3); SQLite/aiosqlite in tests |
| Auth       | JWT (PyJWT) + bcrypt                               |
| Migrations | Alembic                                            |
| Tooling    | uv, pytest, ruff                                   |

## Project structure

```
src/app/
├── main.py            # app entry point: lifespan, CORS, router registration
├── config.py          # pydantic-settings (env / .env)
├── database.py        # async engine, session factory, Base, init_db
├── security.py        # bcrypt hashing, JWT tokens, auth dependencies
├── models/            # SQLAlchemy ORM models (user, post, social)
├── schemas/           # Pydantic request/response models
├── services/          # shared business logic (post serialization, pagination)
├── routers/           # API routers: auth, users, posts, feed, hashtags
└── tests/             # pytest suite (53 tests)
alembic/               # migrations (async env.py)
docker-compose.yml     # Postgres + API
Dockerfile
```

## Quickstart (local dev)

Requirements: [uv](https://docs.astral.sh/uv/) and (for the default database) Docker.

```bash
# 1. Configure environment
cp .env.example .env

# 2. Start PostgreSQL (only the db service; the api service is for all-in-docker runs)
docker compose up -d db

# 3. Install dependencies
uv sync

# 4. Create the schema
uv run alembic upgrade head

# 5. Run the API (hot reload)
uv run uvicorn app.main:app --reload
```

Open the interactive docs at http://127.0.0.1:8000/docs (the `Authorize` button works
with the `/api/auth/login` form). Health check: http://127.0.0.1:8000/health.

### All-in-Docker

```bash
docker compose up --build
```

starts PostgreSQL and the API (running migrations on boot) at http://127.0.0.1:8000.

### Tests & lint

```bash
uv run pytest        # 53 tests, isolated SQLite database, no Postgres needed
uv run ruff check .  # lint
```

## API overview

All endpoints are prefixed with `/api`.

### Auth
| Method | Path                | Description                              |
| ------ | ------------------- | ---------------------------------------- |
| POST   | `/auth/register`    | Create account → access + refresh tokens |
| POST   | `/auth/login`       | Login (form: username or email + password) |
| POST   | `/auth/refresh`     | Exchange a refresh token for a new pair  |

### Users
| Method | Path                          | Description                     |
| ------ | ----------------------------- | ------------------------------- |
| GET    | `/users/me`                   | Current user (includes email)   |
| PATCH  | `/users/me`                   | Update display_name / bio / avatar_url |
| GET    | `/users/{username}`           | Public profile with stats       |
| POST   | `/users/{username}/follow`    | Follow a user                   |
| DELETE | `/users/{username}/follow`    | Unfollow a user                 |
| GET    | `/users/{username}/followers` | Paginated followers             |
| GET    | `/users/{username}/following` | Paginated following             |
| GET    | `/users/{username}/posts`     | A user's posts (`include_replies=true` to include replies) |

### Posts & interactions
| Method | Path                        | Description                          |
| ------ | --------------------------- | ------------------------------------ |
| POST   | `/posts`                    | Create a post (`title` optional)     |
| GET    | `/posts/{id}`               | Post detail with counts + `is_liked` |
| DELETE | `/posts/{id}`               | Delete own post (cascades replies/reposts/likes) |
| POST   | `/posts/{id}/replies`       | Reply to a post                      |
| GET    | `/posts/{id}/replies`       | Paginated replies                    |
| POST   | `/posts/{id}/repost`        | Repost (`quote` optional)            |
| DELETE | `/posts/{id}/repost`        | Remove your repost                   |
| POST   | `/posts/{id}/like`          | Like a post                          |
| DELETE | `/posts/{id}/like`          | Unlike a post                        |
| GET    | `/posts/{id}/likes`         | Paginated users who liked            |

### Feed & hashtags
| Method | Path                      | Description                                   |
| ------ | ------------------------- | --------------------------------------------- |
| GET    | `/feed`                   | Home feed (followed users + self; `include_replies=true` optional) |
| GET    | `/hashtags/{name}/posts`  | Posts containing a hashtag (case-insensitive) |

### Pagination

List endpoints accept `limit` (default 20, max 100) and `cursor` (the last item's id)
and return `{"items": [...], "next_cursor": <id | null>}`. Pass `next_cursor` back as
`cursor` to fetch the next page.

### Authentication

Protected endpoints expect `Authorization: Bearer <access_token>`. Obtain tokens via
`POST /api/auth/register` or `POST /api/auth/login`. Access tokens expire after
`ACCESS_TOKEN_EXPIRE_MINUTES` (default 30); use `POST /api/auth/refresh` with the
refresh token to get a new pair.

## Configuration

Settings are read from environment variables or a `.env` file (see `.env.example`):

| Variable                    | Default                                                       | Description              |
| --------------------------- | ------------------------------------------------------------- | ------------------------ |
| `DATABASE_URL`              | `postgresql+psycopg://postgres:postgres@localhost:5432/twatter` | Async SQLAlchemy URL     |
| `JWT_SECRET_KEY`            | `change-me-in-production-...`                                 | HMAC key for JWT (≥32 chars) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`                                                        | Access token lifetime    |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30`                                                          | Refresh token lifetime   |
| `CORS_ORIGINS`              | `*`                                                           | Comma-separated origins  |
| `DEBUG`                     | `false`                                                       | Verbose SQL logging      |

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"  # after model edits
uv run alembic upgrade head                                   # apply
uv run alembic downgrade -1                                   # roll back one step
```

The app also calls `create_all` on startup as a dev convenience; production should rely
on `alembic upgrade head` only.
