"""Initial schema: sessions + card_assets

Revision ID: 0001_initial
Revises:
Create Date: 2025-11-09

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # harmless if missing perms

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "card_assets",
        sa.Column("oracle_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("small_url", sa.Text, nullable=True),
        sa.Column("local_small_path", sa.Text, nullable=True),
        sa.Column("etag", sa.Text, nullable=True),
        sa.Column("last_modified", sa.Text, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("card_assets")
    op.drop_table("sessions")
