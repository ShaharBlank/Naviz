"""Create optional account-sync tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "naviz_favorites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("place", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_naviz_favorites_subject", "naviz_favorites", ["subject"])
    op.create_table(
        "naviz_preferences",
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subject"),
    )
    op.create_table(
        "naviz_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("origin_label", sa.String(length=200), nullable=False),
        sa.Column("destination", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_naviz_history_created_at", "naviz_history", ["created_at"])
    op.create_index("ix_naviz_history_expires_at", "naviz_history", ["expires_at"])
    op.create_index("ix_naviz_history_subject", "naviz_history", ["subject"])


def downgrade() -> None:
    op.drop_index("ix_naviz_history_subject", table_name="naviz_history")
    op.drop_index("ix_naviz_history_expires_at", table_name="naviz_history")
    op.drop_index("ix_naviz_history_created_at", table_name="naviz_history")
    op.drop_table("naviz_history")
    op.drop_table("naviz_preferences")
    op.drop_index("ix_naviz_favorites_subject", table_name="naviz_favorites")
    op.drop_table("naviz_favorites")
