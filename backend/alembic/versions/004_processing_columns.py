"""Add post-processing columns to downloads

Revision ID: 004_processing_columns
Revises: 003_paused_downloads
Create Date: 2026-10-03 04:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '004_processing_columns'
down_revision: Union[str, None] = '003_paused_downloads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('downloads', sa.Column('thumbnail_local', sa.String(length=1024), nullable=True))
    op.add_column('downloads', sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('downloads', sa.Column('processing_error', sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column('downloads', 'processing_error')
    op.drop_column('downloads', 'processed')
    op.drop_column('downloads', 'thumbnail_local')
