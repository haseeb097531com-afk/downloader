"""Multi-tenant schema migration

Revision ID: 017_multi_tenant
Revises: 016_three_tier_roles
Create Date: 2026-10-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "017_multi_tenant"
down_revision: Union[str, None] = "016_three_tier_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_OWNER_ID = "00000000-0000-0000-0000-000000000001"
_TABLES_WITH_TENANT_ID = [
    "downloads",
    "profiles",
    "profile_videos",
    "bulk_jobs",
    "bulk_items",
    "video_analysis",
    "media_fingerprints",
    "pending_links",
    "download_queue",
    "audit_logs",
    "devices",
    "push_subscriptions",
    "download_schedules",
    "extraction_attempts",
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _upgrade_sqlite(bind)
    else:
        _upgrade_postgres(bind)


def _upgrade_sqlite(bind) -> None:
    # Create tenants table
    bind.execute(sa.text("""
        CREATE TABLE tenants (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            plan VARCHAR(20) NOT NULL DEFAULT 'trial',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            owner_user_id VARCHAR(36),
            settings_json TEXT,
            created_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
            suspended_at DATETIME
        )
    """))

    bind.execute(sa.text("CREATE INDEX ix_tenants_slug ON tenants (slug)"))
    bind.execute(sa.text("CREATE INDEX ix_tenants_owner_user_id ON tenants (owner_user_id)"))

    # Insert default tenant
    bind.execute(sa.text(f"""
        INSERT INTO tenants (id, name, slug, plan, status, owner_user_id)
        VALUES ('default-tenant', 'Primary Workspace', 'primary', 'pro', 'active', '{_DEFAULT_OWNER_ID}')
    """))

    default_tenant_id = "default-tenant"

    # Add tenant_id columns to all existing tables
    for table in _TABLES_WITH_TENANT_ID:
        existing_cols = {row[1] for row in bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()}
        if "tenant_id" not in existing_cols:
            bind.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN tenant_id VARCHAR(36)"))
            bind.execute(sa.text(f"CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id)"))

    # Backfill tenant_id on all existing rows
    for table in _TABLES_WITH_TENANT_ID:
        bind.execute(sa.text(f"UPDATE {table} SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL"))

    # Add tenant_role column to users
    existing_cols = {row[1] for row in bind.execute(sa.text("PRAGMA table_info(users)")).fetchall()}
    if "tenant_role" not in existing_cols:
        bind.execute(sa.text("ALTER TABLE users ADD COLUMN tenant_role VARCHAR(20)"))

    # Backfill tenant_role
    bind.execute(sa.text(f"UPDATE users SET tenant_role = 'super_admin' WHERE id = '{_DEFAULT_OWNER_ID}'"))
    bind.execute(sa.text(f"""
        UPDATE users
        SET tenant_role = 'tenant_owner'
        WHERE id != '{_DEFAULT_OWNER_ID}'
          AND id IN (SELECT DISTINCT owner_id FROM downloads WHERE owner_id IS NOT NULL)
    """))
    bind.execute(sa.text("""
        UPDATE users
        SET tenant_role = 'member'
        WHERE tenant_role IS NULL
    """))


def _upgrade_postgres(bind) -> None:
    # Create enum types for tenant
    plan_enum = sa.Enum("trial", "starter", "pro", "enterprise", name="tenant_plan")
    plan_enum.create(bind, checkfirst=True)

    status_enum = sa.Enum("pending", "active", "suspended", name="tenant_status")
    status_enum.create(bind, checkfirst=True)

    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", plan_enum, nullable=False, server_default="trial"),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
        sa.Column("owner_user_id", sa.String(36), nullable=True),
        sa.Column("settings_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("suspended_at", sa.DateTime, nullable=True),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=False)
    op.create_index(op.f("ix_tenants_owner_user_id"), "tenants", ["owner_user_id"], unique=False)
    op.create_foreign_key("fk_tenants_owner_user_id", "tenants", "users", ["owner_user_id"], ["id"])

    # Insert default tenant
    bind.execute(sa.text(f"""
        INSERT INTO tenants (id, name, slug, plan, "status", owner_user_id)
        VALUES ('default-tenant', 'Primary Workspace', 'primary', 'pro', 'active', '{_DEFAULT_OWNER_ID}')
    """))

    default_tenant_id = "default-tenant"

    # Add tenant_id columns to all existing tables
    for table in _TABLES_WITH_TENANT_ID:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("tenant_id", sa.String(36), nullable=True))
            batch_op.create_index(op.f(f"ix_{table}_tenant_id"), ["tenant_id"], unique=False)

    # Backfill tenant_id on all existing rows
    for table in _TABLES_WITH_TENANT_ID:
        bind.execute(sa.text(f"UPDATE {table} SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL"))

    # Add tenant_role column to users
    tenant_role_enum = sa.Enum("super_admin", "tenant_owner", "member", name="tenant_role")
    tenant_role_enum.create(bind, checkfirst=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("tenant_role", tenant_role_enum, nullable=True))

    # Backfill tenant_role
    bind.execute(sa.text(f"UPDATE users SET tenant_role = 'super_admin' WHERE id = '{_DEFAULT_OWNER_ID}'"))
    bind.execute(sa.text(f"""
        UPDATE users
        SET tenant_role = 'tenant_owner'
        WHERE id != '{_DEFAULT_OWNER_ID}'
          AND id IN (SELECT DISTINCT owner_id FROM downloads WHERE owner_id IS NOT NULL)
    """))
    bind.execute(sa.text("""
        UPDATE users
        SET tenant_role = 'member'
        WHERE tenant_role IS NULL
    """))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _downgrade_sqlite(bind)
    else:
        _downgrade_postgres(bind)


def _downgrade_sqlite(bind) -> None:
    # Drop tenant_id columns
    for table in _TABLES_WITH_TENANT_ID:
        # SQLite does not support DROP COLUMN directly in older versions, but modern SQLite does.
        # We attempt to drop index then column.
        bind.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table}_tenant_id"))
        try:
            bind.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN tenant_id"))
        except Exception:
            pass

    # Drop tenant_role from users
    bind.execute(sa.text("ALTER TABLE users DROP COLUMN tenant_role"))

    # Drop tenants table
    bind.execute(sa.text("DROP TABLE IF EXISTS tenants"))


def _downgrade_postgres(bind) -> None:
    # Drop tenant_id columns
    for table in _TABLES_WITH_TENANT_ID:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(op.f(f"ix_{table}_tenant_id"))
            batch_op.drop_column("tenant_id")

    # Drop tenant_role from users
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("tenant_role")

    sa.Enum(name="tenant_role").drop(bind, checkfirst=True)

    # Drop tenants table and related enums/indexes
    op.drop_constraint("fk_tenants_owner_user_id", "tenants", type_="foreignkey")
    op.drop_index(op.f("ix_tenants_owner_user_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")

    sa.Enum(name="tenant_status").drop(bind, checkfirst=True)
    sa.Enum(name="tenant_plan").drop(bind, checkfirst=True)
