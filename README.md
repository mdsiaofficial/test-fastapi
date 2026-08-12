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
└── tests/             # pytest suite (60 tests)
alembic/               # migrations (async env.py)
docker-compose.yml         # API in Docker + PostgreSQL on your host machine
docker-compose.full.yml    # optional: everything in Docker (Postgres + API)
Dockerfile
```

## How the codebase runs

### 1. Startup

`uvicorn app.main:app` imports `src/app/main.py`, which builds the FastAPI app:

1. **Config** (`config.py`) loads settings from env vars / `.env` via pydantic-settings.
2. **Database** (`database.py`) creates the async engine and session factory from
   `DATABASE_URL`.
3. **App + lifespan** (`main.py`) creates the app and registers the lifespan handler,
   which calls `init_db()` on startup (a dev convenience that runs `create_all`;
   production uses `alembic upgrade head` instead).
4. **Middleware** — CORS is added from `CORS_ORIGINS`.
5. **Routers** — `auth`, `users`, `posts`, `feed`, and `hashtags` routers are mounted
   under the `/api` prefix.

### 2. A request's journey

```
POST /api/posts  {content, title}   +  Authorization: Bearer <token>
        │
        ▼
 main.py              → router is mounted under /api → hits routers/posts.py
        │
        ▼
 FastAPI dependencies → get_db() opens an AsyncSession
                       → get_current_user() decodes the JWT, loads the User
        │
        ▼
 router handler       → validates the body (PostCreate), calls the service
        │
        ▼
 services/posts.py    → _create_post() writes the Post, extracts hashtags
        │
        ▼
 response model       → PostRead serializes the ORM object back to JSON
```

Every endpoint follows this same pipeline: **router → dependencies → service →
model/schema → response**. The DB session comes from the `get_db` dependency and is
closed automatically when the request finishes.

### 3. Auth, in one picture

```
Authorization header
        │
        ▼
OAuth2PasswordBearer (auto_error=False) ── no header → None → optional-auth mode
        │
        ▼
security.py _resolve_user() → decode + verify signature/expiry
        │                     → check token `type` (access vs refresh)
        │                     → load User by `sub`, check is_active
        ▼
   User (injected into your handler)
```

`Depends(get_current_user)` requires auth; `Depends(get_optional_current_user)`
allows anonymous access while still personalizing responses (e.g. `is_liked`).

### 4. A full round-trip, end to end

```bash
# Register (returns access + refresh tokens)
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Create a post (auth required)
curl -s -X POST http://127.0.0.1:8000/api/posts \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Hello #FastAPI world!"}'

# Read it back anonymously — is_liked will be false, no token needed
curl -s http://127.0.0.1:8000/api/posts/1
```

For a deep dive into the three key patterns (auth dependencies, the service layer,
cursor pagination), see **[TUTORIAL.md](TUTORIAL.md)**.

## Quickstart (local dev)

Requirements: [uv](https://docs.astral.sh/uv/), a local PostgreSQL server, and Docker
(only needed for the containerized API below).

```bash
# 1. Configure environment — edit DATABASE_URL to match your local Postgres
cp .env.example .env

# 2. Make sure PostgreSQL is running, then create the database once:
createdb twatter   # as a role with CREATEDB, e.g. sudo -u postgres createdb twatter

# 3. Install dependencies
uv sync

# 4. Create the schema
uv run alembic upgrade head

# 5. Run the API (hot reload)
uv run uvicorn app.main:app --reload
```

Open the interactive docs at http://127.0.0.1:8000/docs (the `Authorize` button works
with the `/api/auth/login` form). Health check: http://127.0.0.1:8000/health.

### Run the API in Docker (PostgreSQL stays on your machine)

```bash
docker compose up --build
```

Builds the image, applies migrations (`alembic upgrade head`) and serves the API at
http://127.0.0.1:8000. PostgreSQL is **not** containerized — the container connects to
the one running on your host machine.

**How the networking works:** containers use the default bridge network and reach your
host's Postgres via `host.docker.internal` — Docker Desktop's built-in alias for the
host machine. It works out of the box on Docker Desktop for Linux, macOS and Windows,
and even a Postgres that only listens on `127.0.0.1` is reachable (verified
empirically). Check which engine you have with `docker info | grep -i operating`.

> ⚠️ **Don't use `network_mode: host` on Docker Desktop** — its engine runs inside a
> VM, so `localhost` inside the container is the *VM's* loopback, not your machine's,
> and the container can't reach your Postgres (`Connection refused`). That's exactly
> why this compose file uses `host.docker.internal` instead.

The container's `DATABASE_URL` is built from `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST`, `POSTGRES_PORT` and `POSTGRES_DB` (defaults: `ashiq` / `1212` /
`host.docker.internal` / `5432` / `twatter`). Override any of them, e.g.:

```bash
POSTGRES_PASSWORD=secret docker compose up --build
```

**Native Linux Docker Engine (no VM):** no edits needed — the compose file already
includes `extra_hosts: ["host.docker.internal:host-gateway"]`, which makes the name
resolve there too. One catch: on native Linux it maps to the bridge gateway (not
loopback), so your Postgres must accept TCP connections beyond `127.0.0.1`
(`listen_addresses = '*'` in `postgresql.conf` plus a matching `pg_hba.conf` rule). If
you'd rather keep Postgres loopback-only, use `network_mode: host` with
`POSTGRES_HOST=localhost` instead (that variant works only on native Linux).

### Everything in Docker (optional)

No local Postgres handy? Run Postgres and the API both containerized:

```bash
docker compose -f docker-compose.full.yml up --build
```

Same result at http://127.0.0.1:8000. The API's `DATABASE_URL` points at the `db`
service (`postgres:16-alpine`, credentials `ashiq` / `1212` / `twatter`). Port 5432 is
not published, so this containerized Postgres never clashes with a local one.

### Tests & lint

```bash
uv run pytest        # 60 tests, isolated SQLite database, no Postgres needed
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
| DELETE | `/users/me`                   | Soft-delete (deactivate) the account — tokens stop working |
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

Every list is ordered by `id DESC` (newest first) and the cursor is the same `id`
column, so pages never skip or duplicate rows as new items are created between
requests. The followers / following / likes lists follow the same contract.

### Authentication

Protected endpoints expect `Authorization: Bearer <access_token>`. Obtain tokens via
`POST /api/auth/register` or `POST /api/auth/login`. Access tokens expire after
`ACCESS_TOKEN_EXPIRE_MINUTES` (default 30); use `POST /api/auth/refresh` with the
refresh token to get a new pair.

## Configuration

Settings are read from environment variables or a `.env` file (see `.env.example`):

| Variable                    | Default                                                       | Description              |
| --------------------------- | ------------------------------------------------------------- | ------------------------ |
| `DATABASE_URL`              | `postgresql+psycopg://ashiq:1212@localhost:5432/twatter` | Async SQLAlchemy URL (adjust to your local Postgres) |
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
