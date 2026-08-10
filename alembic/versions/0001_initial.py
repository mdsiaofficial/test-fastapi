"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-09

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "hashtags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hashtags_name", "hashtags", ["name"], unique=True)

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=280), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
        sa.Column("repost_of_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_id"], ["posts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["repost_of_id"], ["posts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_reply_to_id", "posts", ["reply_to_id"])
    op.create_index("ix_posts_repost_of_id", "posts", ["repost_of_id"])

    op.create_table(
        "post_hashtags",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("hashtag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hashtag_id"], ["hashtags.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "hashtag_id"),
    )

    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Integer(), nullable=False),
        sa.Column("followed_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["followed_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["follower_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("follower_id", "followed_id"),
    )

    op.create_table(
        "likes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )


def downgrade() -> None:
    op.drop_table("likes")
    op.drop_table("follows")
    op.drop_table("post_hashtags")
    op.drop_table("posts")
    op.drop_table("hashtags")
    op.drop_table("users")
