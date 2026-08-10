from conftest import auth_headers, register_user


def _create_post(client, token, content, title=None):
    return client.post(
        "/api/posts",
        json={"content": content, "title": title},
        headers=auth_headers(token),
    )


def test_get_profile_with_stats(client):
    register_user(client, "alice")
    response = client.get("/api/users/alice")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["followers_count"] == 0
    assert body["following_count"] == 0
    assert body["posts_count"] == 0
    # Email is private and must not leak on public profiles.
    assert "email" not in body


def test_get_profile_not_found(client):
    response = client.get("/api/users/nobody")
    assert response.status_code == 404


def test_update_profile(client):
    data = register_user(client, "alice")
    response = client.patch(
        "/api/users/me",
        json={"bio": "Hello world", "display_name": "Alice A."},
        headers=auth_headers(data["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Hello world"
    assert body["display_name"] == "Alice A."

    profile = client.get("/api/users/alice").json()
    assert profile["bio"] == "Hello world"


def test_update_profile_requires_auth(client):
    response = client.patch("/api/users/me", json={"bio": "hi"})
    assert response.status_code == 401


def test_follow_and_unfollow(client):
    alice = register_user(client, "alice")
    register_user(client, "bob")

    # Alice follows Bob.
    response = client.post(
        "/api/users/bob/follow", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 204

    bob_profile = client.get("/api/users/bob").json()
    assert bob_profile["followers_count"] == 1
    alice_profile = client.get("/api/users/alice").json()
    assert alice_profile["following_count"] == 1

    followers = client.get("/api/users/bob/followers").json()
    assert [u["username"] for u in followers["items"]] == ["alice"]
    following = client.get("/api/users/alice/following").json()
    assert [u["username"] for u in following["items"]] == ["bob"]

    # Unfollow.
    response = client.delete(
        "/api/users/bob/follow", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 204
    assert client.get("/api/users/bob").json()["followers_count"] == 0


def test_follow_requires_auth(client):
    register_user(client, "bob")
    response = client.post("/api/users/bob/follow")
    assert response.status_code == 401


def test_cannot_follow_self(client):
    alice = register_user(client, "alice")
    response = client.post(
        "/api/users/alice/follow", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 400


def test_follow_duplicate_conflict(client):
    alice = register_user(client, "alice")
    register_user(client, "bob")
    headers = auth_headers(alice["access_token"])
    client.post("/api/users/bob/follow", headers=headers)
    response = client.post("/api/users/bob/follow", headers=headers)
    assert response.status_code == 409


def test_unfollow_not_following(client):
    alice = register_user(client, "alice")
    register_user(client, "bob")
    response = client.delete(
        "/api/users/bob/follow", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 404


def test_list_user_posts(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    assert _create_post(client, token, "First post").status_code == 201
    assert _create_post(client, token, "Second post").status_code == 201

    response = client.get("/api/users/alice/posts")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["content"] == "Second post"  # newest first


def test_user_posts_exclude_replies_by_default(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    post = _create_post(client, token, "Original").json()
    client.post(
        f"/api/posts/{post['id']}/replies",
        json={"content": "A reply"},
        headers=auth_headers(token),
    )

    default = client.get("/api/users/alice/posts").json()
    assert len(default["items"]) == 1
    with_replies = client.get(
        "/api/users/alice/posts", params={"include_replies": "true"}
    ).json()
    assert len(with_replies["items"]) == 2


def test_pagination_limit_bounds(client):
    response = client.get("/api/users/nobody/posts", params={"limit": 101})
    assert response.status_code == 422
    response = client.get("/api/users/nobody/posts", params={"limit": 0})
    assert response.status_code == 422


def test_pagination_cursor(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    for i in range(3):
        _create_post(client, token, f"Post {i}")

    page1 = client.get("/api/users/alice/posts", params={"limit": 2}).json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] == page1["items"][-1]["id"]

    page2 = client.get(
        "/api/users/alice/posts",
        params={"limit": 2, "cursor": page1["next_cursor"]},
    ).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
