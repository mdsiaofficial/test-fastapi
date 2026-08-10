from conftest import auth_headers, register_user


def _post(client, token, content):
    return client.post(
        "/api/posts", json={"content": content}, headers=auth_headers(token)
    ).json()["id"]


def test_feed_shows_own_and_followed_posts(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    carol = register_user(client, "carol")

    alice_token = alice["access_token"]
    _post(client, alice_token, "Alice's post")
    _post(client, bob["access_token"], "Bob's post")
    _post(client, carol["access_token"], "Carol's post")

    client.post(
        "/api/users/bob/follow", headers=auth_headers(alice_token)
    )

    feed = client.get("/api/feed", headers=auth_headers(alice_token)).json()
    contents = [item["content"] for item in feed["items"]]
    assert "Alice's post" in contents  # own posts
    assert "Bob's post" in contents  # followed user
    assert "Carol's post" not in contents  # not followed


def test_feed_requires_auth(client):
    response = client.get("/api/feed")
    assert response.status_code == 401


def test_feed_excludes_replies_by_default(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    alice_token = alice["access_token"]

    post_id = _post(client, alice_token, "Original")
    client.post(
        f"/api/posts/{post_id}/replies",
        json={"content": "A reply"},
        headers=auth_headers(bob["access_token"]),
    )
    client.post(
        "/api/users/bob/follow", headers=auth_headers(alice_token)
    )

    default = client.get("/api/feed", headers=auth_headers(alice_token)).json()
    assert [i["content"] for i in default["items"]] == ["Original"]

    with_replies = client.get(
        "/api/feed",
        params={"include_replies": "true"},
        headers=auth_headers(alice_token),
    ).json()
    assert len(with_replies["items"]) == 2


def test_feed_is_newest_first_and_paginated(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    bob_token = bob["access_token"]

    for i in range(3):
        _post(client, bob_token, f"Bob post {i}")

    alice_token = alice["access_token"]
    client.post("/api/users/bob/follow", headers=auth_headers(alice_token))

    page1 = client.get(
        "/api/feed", params={"limit": 2}, headers=auth_headers(alice_token)
    ).json()
    assert [i["content"] for i in page1["items"]] == ["Bob post 2", "Bob post 1"]
    assert page1["next_cursor"] == page1["items"][-1]["id"]

    page2 = client.get(
        "/api/feed",
        params={"limit": 2, "cursor": page1["next_cursor"]},
        headers=auth_headers(alice_token),
    ).json()
    assert [i["content"] for i in page2["items"]] == ["Bob post 0"]
    assert page2["next_cursor"] is None
