"""Tenant subscription fields migration

Revision ID: 018_tenant_subscription
Revises: 017_multi_tenant
Create Date: 2026-10-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "018_tenant_subscription"
down_revision: Union[str, None] = "017_multi_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _upgrade_sqlite(bind)
    else:
        _upgrade_postgres(bind)


def _upgrade_sqlite(bind) -> None:
    bind.execute(sa.text("""
        ALTER TABLE tenants ADD COLUMN plan_started_at DATETIME
    """))
    bind.execute(sa.text("""
        ALTER TABLE tenants ADD COLUMN plan_expires_at DATETIME
    """))
    bind.execute(sa.text("""
        ALTER TABLE tenants ADD COLUMN auto_renew BOOLEAN DEFAULT 0
    """))
    bind.execute(sa.text("""
        ALTER TABLE tenants ADD COLUMN trial_used BOOLEAN DEFAULT 0
    """))
    bind.execute(sa.text("""
        ALTER TABLE tenants ADD COLUMN quota_override_until DATETIME
    """))

    bind.execute(sa.text("""
        UPDATE tenants
        SET plan = 'enterprise', plan_started_at = datetime('now'), auto_renew = 1, trial_used = 1
        WHERE id = 'default-tenant'
    """))


def _upgrade_postgres(bind) -> None:
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(sa.Column("plan_started_at", sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column("plan_expires_at", sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column("auto_renew", sa.Boolean, nullable=True, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("trial_used", sa.Boolean, nullable=True, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("quota_override_until", sa.DateTime, nullable=True))

    bind.execute(sa.text("""
        UPDATE tenants
        SET plan = 'enterprise', plan_started_at = now(), auto_renew = true, trial_used = true
        WHERE id = 'default-tenant'
    """))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _downgrade_sqlite(bind)
    else:
        _downgrade_postgres(bind)


def _downgrade_sqlite(bind) -> None:
    bind.execute(sa.text("ALTER TABLE tenants DROP COLUMN plan_started_at"))
    bind.execute(sa.text("ALTER TABLE tenants DROP COLUMN plan_expires_at"))
    bind.execute(sa.text("ALTER TABLE tenants DROP COLUMN auto_renew"))
    bind.execute(sa.text("ALTER TABLE tenants DROP COLUMN trial_used"))


def _downgrade_postgres(bind) -> None:
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("quota_override_until")
        batch_op.drop_column("trial_used")
        batch_op.drop_column("auto_renew")
        batch_op.drop_column("plan_expires_at")
        batch_op.drop_column("plan_started_at")
