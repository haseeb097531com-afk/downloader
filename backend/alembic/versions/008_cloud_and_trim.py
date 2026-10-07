"""Add trim and cloud backup columns to downloads table for Phase 9A."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_cloud_and_trim"
down_revision: Union[str, None] = "007_download_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("downloads", sa.Column("trim_start", sa.String(20), nullable=True))
    op.add_column("downloads", sa.Column("trim_end", sa.String(20), nullable=True))
    op.add_column("downloads", sa.Column("cloud_backed_up", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("downloads", sa.Column("cloud_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("downloads", "cloud_url")
    op.drop_column("downloads", "cloud_backed_up")
    op.drop_column("downloads", "trim_end")
    op.drop_column("downloads", "trim_start")
