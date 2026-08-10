from conftest import auth_headers, register_user


def test_hashtag_search(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    headers = auth_headers(token)

    client.post(
        "/api/posts",
        json={"content": "Post about #Python"},
        headers=headers,
    )
    client.post(
        "/api/posts",
        json={"content": "More #python content"},
        headers=headers,
    )
    client.post(
        "/api/posts",
        json={"content": "Nothing to see here"},
        headers=headers,
    )

    response = client.get("/api/hashtags/python/posts")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2


def test_hashtag_search_is_case_insensitive(client):
    alice = register_user(client, "alice")
    headers = auth_headers(alice["access_token"])
    client.post(
        "/api/posts", json={"content": "Using #FastAPI"}, headers=headers
    )
    response = client.get("/api/hashtags/FASTAPI/posts")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_hashtag_not_found(client):
    response = client.get("/api/hashtags/doesnotexist/posts")
    assert response.status_code == 404


def test_hashtag_posts_include_like_counts(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    headers = auth_headers(alice["access_token"])
    post_id = client.post(
        "/api/posts", json={"content": "Hello #fastapi"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/posts/{post_id}/like",
        headers=auth_headers(bob["access_token"]),
    )

    items = client.get("/api/hashtags/fastapi/posts").json()["items"]
    assert items[0]["like_count"] == 1
