"""Devices table for remote control pairing.

Revision ID: 015_devices
Revises: 014_web_push
Create Date: 2026-10-04 08:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015_devices"
down_revision: Union[str, None] = "014_web_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform_hint", sa.String(length=50), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_token_hash"), "devices", ["token_hash"], unique=True)
    op.create_index(op.f("ix_devices_owner_id"), "devices", ["owner_id"], unique=False)
    op.create_index(op.f("ix_devices_is_active"), "devices", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_is_active"), table_name="devices")
    op.drop_index(op.f("ix_devices_owner_id"), table_name="devices")
    op.drop_index(op.f("ix_devices_token_hash"), table_name="devices")
    op.drop_table("devices")
