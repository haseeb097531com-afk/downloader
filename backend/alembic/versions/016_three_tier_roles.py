"""3-tier role hierarchy migration

Revision ID: 016_three_tier_roles
Revises: 015_remote_control
Create Date: 2026-10-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "016_three_tier_roles"
down_revision: Union[str, None] = "015_remote_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_OWNER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _upgrade_sqlite(bind)
    else:
        _upgrade_postgres(bind)


def _upgrade_sqlite(bind) -> None:
    # Add parent_id if not exists
    existing = bind.execute(sa.text("PRAGMA table_info(users)")).fetchall()
    existing_cols = {row[1] for row in existing}
    if "parent_id" not in existing_cols:
        op.execute("ALTER TABLE users ADD COLUMN parent_id VARCHAR(36)")
    if "ix_users_parent_id" not in {row[0] for row in bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'")).fetchall()}:
        op.execute("CREATE INDEX ix_users_parent_id ON users (parent_id)")

    owner_result = bind.execute(sa.text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
    owner_row = owner_result.fetchone()
    if owner_row:
        owner_id = str(owner_row[0])
        op.execute(f"UPDATE users SET parent_id = '{owner_id}' WHERE role != 'admin' AND parent_id IS NULL")
    op.execute("UPDATE users SET parent_id = NULL WHERE role = 'admin'")

    if "role_tmp" not in existing_cols:
        op.execute("ALTER TABLE users ADD COLUMN role_tmp VARCHAR(10)")
    op.execute("UPDATE users SET role_tmp = 'owner' WHERE role = 'admin'")
    op.execute("UPDATE users SET role_tmp = 'user' WHERE role IN ('user', 'viewer')")

    op.execute("DROP INDEX IF EXISTS ix_users_role")
    if "role" in existing_cols:
        op.execute("ALTER TABLE users DROP COLUMN role")
    op.execute("ALTER TABLE users RENAME COLUMN role_tmp TO role")
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def _upgrade_postgres(bind) -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
        batch_op.create_index(op.f("ix_users_parent_id"), ["parent_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_users_parent_id",
            "users",
            ["parent_id"],
            ["id"],
        )

    owner_result = bind.execute(sa.text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
    owner_row = owner_result.fetchone()
    if owner_row:
        owner_id = str(owner_row[0])
        op.execute(f"UPDATE users SET parent_id = '{owner_id}' WHERE role != 'admin' AND parent_id IS NULL")
    op.execute("UPDATE users SET parent_id = NULL WHERE role = 'admin'")

    new_role = sa.Enum("owner", "sub_admin", "user", name="user_role_new")
    new_role.create(bind, checkfirst=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role_tmp", new_role, nullable=True))

    op.execute("UPDATE users SET role_tmp = 'owner' WHERE role = 'admin'")
    op.execute("UPDATE users SET role_tmp = 'user' WHERE role IN ('user', 'viewer')")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")

    op.execute("ALTER TABLE users RENAME COLUMN role_tmp TO role")
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    sa.Enum(name="user_role").drop(bind, checkfirst=True)
    op.execute("ALTER TYPE user_role_new RENAME TO user_role")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _downgrade_sqlite(bind)
    else:
        _downgrade_postgres(bind)


def _downgrade_sqlite(bind) -> None:
    op.execute("ALTER TABLE users ADD COLUMN role_tmp VARCHAR(6)")
    op.execute("UPDATE users SET role_tmp = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE users SET role_tmp = 'user' WHERE role = 'user'")
    op.execute("DROP INDEX IF EXISTS ix_users_role")
    op.execute("ALTER TABLE users DROP COLUMN role")
    op.execute("ALTER TABLE users RENAME COLUMN role_tmp TO role")
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_parent_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_users_parent_id"))
        batch_op.drop_column("parent_id")


def _downgrade_postgres(bind) -> None:
    op.execute("ALTER TYPE user_role RENAME TO user_role_new")

    old_role = sa.Enum("admin", "user", "viewer", name="user_role")
    old_role.create(bind, checkfirst=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role_tmp", old_role, nullable=True))

    op.execute("UPDATE users SET role_tmp = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE users SET role_tmp = 'user' WHERE role = 'user'")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")

    op.execute("ALTER TABLE users RENAME COLUMN role_tmp TO role")
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    sa.Enum(name="user_role_new").drop(bind, checkfirst=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_parent_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_users_parent_id"))
        batch_op.drop_column("parent_id")
