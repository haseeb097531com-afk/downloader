"""Download schedules migration

Revision ID: 010_download_schedules
Revises: 009_smart_deduplication
Create Date: 2026-10-04 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010_download_schedules'
down_revision: Union[str, None] = '009_smart_deduplication'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'download_schedules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('profile_id', sa.String(length=36), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('trigger_type', sa.String(length=20), nullable=False),
        sa.Column('cron_expression', sa.String(length=128), nullable=True),
        sa.Column('run_time', sa.Time(), nullable=True),
        sa.Column('days_of_week', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('quality_preference', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_download_schedules_profile_id'), 'download_schedules', ['profile_id'], unique=False)
    op.create_index(op.f('ix_download_schedules_url'), 'download_schedules', ['url'], unique=False)
    op.create_index(op.f('ix_download_schedules_is_active'), 'download_schedules', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_download_schedules_is_active'), table_name='download_schedules')
    op.drop_index(op.f('ix_download_schedules_url'), table_name='download_schedules')
    op.drop_index(op.f('ix_download_schedules_profile_id'), table_name='download_schedules')
    op.drop_table('download_schedules')
