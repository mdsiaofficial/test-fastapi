from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, feed, hashtags, posts, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: ensure tables exist. Use `alembic upgrade head` in production.
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, users.router, posts.router, feed.router, hashtags.router):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {
        "message": f"{settings.app_name} is running...",
        "docs": "/docs",
        "time": datetime.now(UTC).isoformat(),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}
