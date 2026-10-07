"""Authentication and authorization migration

Revision ID: 013_authentication
Revises: 012_bulk_import
Create Date: 2026-10-04 06:30:00.000000
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013_authentication"
down_revision: Union[str, None] = "012_bulk_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hard-coded UUID for the default "local" admin user so the backfill is
# deterministic across every environment (dev, CI, production).
_DEFAULT_OWNER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------ #
    # 1. Create users table
    # ------------------------------------------------------------------ #
    user_role = sa.Enum("admin", "user", "viewer", name="user_role")
    user_role.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)

    # ------------------------------------------------------------------ #
    # 2. Create audit_logs table
    # ------------------------------------------------------------------ #
    audit_action = sa.Enum(
        "login_success",
        "login_failure",
        "logout",
        "lockout",
        "permission_denied",
        "user_create",
        "user_update",
        "user_delete",
        "password_change",
        "settings_change",
        "download_delete",
        "download_purge",
        "export_csv",
        "export_pdf",
        name="audit_action",
    )
    audit_action.create(bind, checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)

    # ------------------------------------------------------------------ #
    # 3. Insert the default "local" admin user
    # ------------------------------------------------------------------ #
    # Password is "changeme" – the user will be forced to change it on first login.
    # The actual hash is computed by the app at startup; here we insert a known
    # user row so that the owner_id backfill below has a valid target.
    # In practice the seed_user startup hook will upsert this row with the
    # properly-hashed password.
    op.execute(
        f"""
        INSERT INTO users (id, created_at, updated_at, username, email, password_hash, role, is_active, must_change_password, failed_login_count, locked_until, last_login_at, token_version)
        VALUES ('{_DEFAULT_OWNER_ID}', datetime('now'), datetime('now'), 'local', NULL, 'PLACEHOLDER', 'admin', 1, 1, 0, NULL, NULL, 0)
        """
    )

    # ------------------------------------------------------------------ #
    # 4. Add owner_id columns + backfill
    # ------------------------------------------------------------------ #
    _add_owner_id("downloads", bind)
    _add_owner_id("profiles", bind)
    _add_owner_id("profile_videos", bind)
    _add_owner_id("bulk_jobs", bind)
    _add_owner_id("bulk_items", bind)
    _add_owner_id("video_analysis", bind)
    _add_owner_id("media_fingerprints", bind)
    _add_owner_id("pending_links", bind)
    _add_owner_id("download_queue", bind)

    # Backfill all existing rows to the default owner.
    for table in (
        "downloads",
        "profiles",
        "profile_videos",
        "bulk_jobs",
        "bulk_items",
        "video_analysis",
        "media_fingerprints",
        "pending_links",
        "download_queue",
    ):
        op.execute(
            f"UPDATE {table} SET owner_id = '{_DEFAULT_OWNER_ID}' WHERE owner_id IS NULL"
        )


def _add_owner_id(table: str, bind) -> None:
    """Add a nullable owner_id column to ``table``."""
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.String(length=36), nullable=True))
        batch_op.create_index(op.f(f"ix_{table}_owner_id"), ["owner_id"], unique=False)
        batch_op.create_foreign_key(
            f"fk_{table}_owner_id",
            "users",
            ["owner_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop owner_id columns in reverse order.
    for table in (
        "download_queue",
        "pending_links",
        "media_fingerprints",
        "video_analysis",
        "bulk_items",
        "bulk_jobs",
        "profile_videos",
        "profiles",
        "downloads",
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_owner_id", type_="foreignkey")
            batch_op.drop_index(op.f(f"ix_{table}_owner_id"))
            batch_op.drop_column("owner_id")

    op.drop_table("audit_logs")
    op.drop_table("users")

    sa.Enum(name="audit_action").drop(bind, checkfirst=True)
    sa.Enum(name="user_role").drop(bind, checkfirst=True)
