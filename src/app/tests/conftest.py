import asyncio
import os
import tempfile
from pathlib import Path

# Environment must be configured before the app is imported so the engine
# binds to a throwaway SQLite database.
_TMP = Path(tempfile.mkdtemp(prefix="twatter-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-1234567890"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    # The lifespan handler runs init_db(), creating all tables.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    asyncio.run(_reset_tables())


async def _reset_tables() -> None:
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def register_user(
    client: TestClient,
    username: str,
    email: str | None = None,
    password: str = "password123",
    display_name: str | None = None,
) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
            "display_name": display_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(
    client: TestClient, username_or_email: str, password: str = "password123"
) -> dict:
    response = client.post(
        "/api/auth/login",
        data={"username": username_or_email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
