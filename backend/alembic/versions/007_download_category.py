"""Add category column to downloads table for Phase 8A auto-categorization."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_download_category"
down_revision: Union[str, None] = "006_pending_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("downloads", sa.Column("category", sa.String(100), nullable=True))
    op.create_index("ix_downloads_category", "downloads", ["category"])


def downgrade() -> None:
    op.drop_index("ix_downloads_category", table_name="downloads")
    op.drop_column("downloads", "category")
