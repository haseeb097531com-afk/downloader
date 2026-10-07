"""Add paused download status and celery task tracking

Revision ID: 003_paused_downloads
Revises: 002_profiles_migration
Create Date: 2026-10-02 16:20:00.000000

The ``downloads.status`` column is a plain VARCHAR(50) (see 001_initial_migration),
so adding ``DownloadStatus.PAUSED`` needs no enum rewrite - only the indexes that
back the library and queue screens, plus the ``celery_task_id`` column used to
correlate a running Celery task with its download row.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003_paused_downloads'
down_revision: Union[str, None] = '002_profiles_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('downloads', sa.Column('celery_task_id', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_downloads_celery_task_id'), 'downloads', ['celery_task_id'], unique=False)
    op.create_index(op.f('ix_downloads_completed_at'), 'downloads', ['completed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_downloads_completed_at'), table_name='downloads')
    op.drop_index(op.f('ix_downloads_celery_task_id'), table_name='downloads')
    op.drop_column('downloads', 'celery_task_id')