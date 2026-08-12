import asyncio

from conftest import auth_headers, register_user
from sqlalchemy import text

from app.database import engine


def test_create_post(client):
    alice = register_user(client, "alice")
    response = client.post(
        "/api/posts",
        json={"content": "Hello, world!"},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "Hello, world!"
    assert body["author"]["username"] == "alice"
    assert body["like_count"] == 0
    assert body["reply_count"] == 0
    assert body["is_liked"] is False


def test_create_blog_post_with_title(client):
    alice = register_user(client, "alice")
    response = client.post(
        "/api/posts",
        json={
            "content": "A long-form blog post body...",
            "title": "My first article",
        },
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My first article"


def test_create_post_extracts_hashtags(client):
    alice = register_user(client, "alice")
    response = client.post(
        "/api/posts",
        json={"content": "Learning #FastAPI with #Python and #FastAPI again!"},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 201
    assert response.json()["hashtags"] == ["fastapi", "python"]


def test_create_post_requires_auth(client):
    response = client.post("/api/posts", json={"content": "Hello"})
    assert response.status_code == 401


def test_create_post_empty_content(client):
    alice = register_user(client, "alice")
    response = client.post(
        "/api/posts",
        json={"content": "   "},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 422


def test_get_post(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Hello"}, headers=auth_headers(token)
    ).json()["id"]

    response = client.get(f"/api/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["content"] == "Hello"


def test_get_post_requires_auth_for_is_liked(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Hello"}, headers=auth_headers(token)
    ).json()["id"]
    client.post(f"/api/posts/{post_id}/like", headers=auth_headers(bob["access_token"]))

    anonymous = client.get(f"/api/posts/{post_id}").json()
    assert anonymous["is_liked"] is False
    liked = client.get(
        f"/api/posts/{post_id}", headers=auth_headers(bob["access_token"])
    ).json()
    assert liked["is_liked"] is True


def test_get_post_404(client):
    response = client.get("/api/posts/999999")
    assert response.status_code == 404


def test_delete_own_post(client):
    alice = register_user(client, "alice")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Bye"}, headers=auth_headers(token)
    ).json()["id"]

    response = client.delete(f"/api/posts/{post_id}", headers=auth_headers(token))
    assert response.status_code == 204
    assert client.get(f"/api/posts/{post_id}").status_code == 404


def test_delete_others_post_forbidden(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    post_id = client.post(
        "/api/posts",
        json={"content": "Mine"},
        headers=auth_headers(alice["access_token"]),
    ).json()["id"]

    response = client.delete(
        f"/api/posts/{post_id}", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 403


def test_reply_to_post(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Question?"}, headers=auth_headers(token)
    ).json()["id"]

    reply = client.post(
        f"/api/posts/{post_id}/replies",
        json={"content": "An answer"},
        headers=auth_headers(bob["access_token"]),
    )
    assert reply.status_code == 201
    reply_body = reply.json()
    assert reply_body["is_reply"] is True
    assert reply_body["reply_to_id"] == post_id

    replies = client.get(f"/api/posts/{post_id}/replies").json()
    assert len(replies["items"]) == 1
    assert replies["items"][0]["content"] == "An answer"

    detail = client.get(f"/api/posts/{post_id}").json()
    assert detail["reply_count"] == 1


def test_repost_with_and_without_quote(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Original"}, headers=auth_headers(token)
    ).json()["id"]

    repost = client.post(
        f"/api/posts/{post_id}/repost",
        json={"quote": "Check this out"},
        headers=auth_headers(bob["access_token"]),
    )
    assert repost.status_code == 201
    repost_body = repost.json()
    assert repost_body["is_repost"] is True
    assert repost_body["repost_of_id"] == post_id
    assert repost_body["content"] == "Check this out"

    assert client.get(f"/api/posts/{post_id}").json()["repost_count"] == 1


def test_duplicate_repost_conflict(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Original"}, headers=auth_headers(token)
    ).json()["id"]

    headers = auth_headers(bob["access_token"])
    client.post(f"/api/posts/{post_id}/repost", json={}, headers=headers)
    response = client.post(f"/api/posts/{post_id}/repost", json={}, headers=headers)
    assert response.status_code == 409


def test_delete_repost(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Original"}, headers=auth_headers(token)
    ).json()["id"]

    headers = auth_headers(bob["access_token"])
    client.post(f"/api/posts/{post_id}/repost", json={}, headers=headers)
    response = client.delete(f"/api/posts/{post_id}/repost", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/posts/{post_id}").json()["repost_count"] == 0


def test_like_and_unlike(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Nice"}, headers=auth_headers(token)
    ).json()["id"]

    headers = auth_headers(bob["access_token"])
    response = client.post(f"/api/posts/{post_id}/like", headers=headers)
    assert response.status_code == 204

    detail = client.get(f"/api/posts/{post_id}").json()
    assert detail["like_count"] == 1

    likes = client.get(f"/api/posts/{post_id}/likes").json()
    assert [u["username"] for u in likes["items"]] == ["bob"]

    response = client.delete(f"/api/posts/{post_id}/like", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/posts/{post_id}").json()["like_count"] == 0


def test_duplicate_like_conflict(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Nice"}, headers=auth_headers(token)
    ).json()["id"]

    headers = auth_headers(bob["access_token"])
    client.post(f"/api/posts/{post_id}/like", headers=headers)
    response = client.post(f"/api/posts/{post_id}/like", headers=headers)
    assert response.status_code == 409


def test_unlike_not_liked_404(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Nice"}, headers=auth_headers(token)
    ).json()["id"]

    response = client.delete(
        f"/api/posts/{post_id}/like", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 404


def test_create_post_with_overlong_hashtag_truncates(client):
    """Hashtags longer than the Hashtag.name column must be capped, not error."""
    alice = register_user(client, "alice")
    tag = "a" * 200
    response = client.post(
        "/api/posts",
        json={"content": f"Check #{tag}"},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 201
    assert response.json()["hashtags"] == ["a" * 100]


def test_likes_pagination_returns_every_liker_once(client):
    """Cursor pages must not skip rows when like recency differs from id order."""
    alice = register_user(client, "alice")
    u1 = register_user(client, "userone")
    u3 = register_user(client, "userthree")
    post_id = client.post(
        "/api/posts", json={"content": "Like me"}, headers=auth_headers(alice["access_token"])
    ).json()["id"]

    # userthree likes first (older like), then userone (newer like).
    client.post(f"/api/posts/{post_id}/like", headers=auth_headers(u3["access_token"]))
    client.post(f"/api/posts/{post_id}/like", headers=auth_headers(u1["access_token"]))

    # Backdate userthree's like so recency order conflicts with user id order.
    async def backdate() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE likes SET created_at = datetime('now', '-10 seconds')"
                    " WHERE user_id = :uid AND post_id = :pid"
                ),
                {"uid": u3["user"]["id"], "pid": post_id},
            )

    asyncio.run(backdate())

    seen = []
    cursor = None
    for _ in range(5):
        params = {"limit": 1}
        if cursor is not None:
            params["cursor"] = cursor
        body = client.get(f"/api/posts/{post_id}/likes", params=params).json()
        seen.extend(item["username"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == ["userone", "userthree"]


def test_delete_post_cascades_likes_and_replies(client):
    alice = register_user(client, "alice")
    bob = register_user(client, "bob")
    token = alice["access_token"]
    post_id = client.post(
        "/api/posts", json={"content": "Bye"}, headers=auth_headers(token)
    ).json()["id"]

    client.post(f"/api/posts/{post_id}/like", headers=auth_headers(bob["access_token"]))
    client.post(
        f"/api/posts/{post_id}/replies",
        json={"content": "Bye reply"},
        headers=auth_headers(bob["access_token"]),
    )

    response = client.delete(f"/api/posts/{post_id}", headers=auth_headers(token))
    assert response.status_code == 204
    # The reply post is gone too.
    replies = client.get(f"/api/posts/{post_id}/replies")
    assert replies.status_code == 404
