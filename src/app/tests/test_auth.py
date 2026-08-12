from datetime import UTC, datetime, timedelta

import jwt
from conftest import auth_headers, login, register_user

from app.config import settings


def test_register_success(client):
    data = register_user(client, "alice")
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    # display_name defaults to the username when not provided.
    assert data["user"]["display_name"] == "alice"


def test_register_defaults_display_name_to_username(client):
    data = register_user(client, "bob", display_name=None)
    assert data["user"]["display_name"] == "bob"


def test_register_duplicate_email(client):
    register_user(client, "alice")
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice2",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 409


def test_register_duplicate_username(client):
    register_user(client, "alice")
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice2@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 409


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "not-an-email",
            "password": "password123",
        },
    )
    assert response.status_code == 422


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_login_with_email(client):
    register_user(client, "alice")
    data = login(client, "alice@example.com")
    assert data["user"]["username"] == "alice"


def test_login_with_username(client):
    register_user(client, "alice")
    data = login(client, "alice")
    assert data["access_token"]


def test_login_wrong_password(client):
    register_user(client, "alice")
    response = client.post(
        "/api/auth/login",
        data={"username": "alice", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "ghost", "password": "password123"},
    )
    assert response.status_code == 401


def test_me(client):
    data = register_user(client, "alice")
    response = client.get("/api/users/me", headers=auth_headers(data["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"


def test_me_requires_auth(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_refresh_flow(client):
    data = register_user(client, "alice")
    response = client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert response.status_code == 200
    fresh = response.json()
    assert fresh["access_token"] != data["access_token"]

    # The new access token is valid.
    me = client.get("/api/users/me", headers=auth_headers(fresh["access_token"]))
    assert me.status_code == 200


def test_refresh_rejects_access_token(client):
    data = register_user(client, "alice")
    response = client.post(
        "/api/auth/refresh", json={"refresh_token": data["access_token"]}
    )
    assert response.status_code == 401


def test_refresh_rejects_garbage(client):
    response = client.post(
        "/api/auth/refresh", json={"refresh_token": "not-a-token"}
    )
    assert response.status_code == 401


def test_refresh_rejects_token_without_subject(client):
    """A validly-signed refresh token missing `sub` must 401, not 500."""
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "jti": "x" * 32,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
