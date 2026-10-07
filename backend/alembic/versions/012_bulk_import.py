"""Bulk import models migration

Revision ID: 012_bulk_import
Revises: 011_content_moderation
Create Date: 2026-10-04 05:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012_bulk_import'
down_revision: Union[str, None] = '011_content_moderation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bulk_job_type = sa.Enum('links', 'profiles', name='bulk_job_type')
    bulk_job_type.create(op.get_bind(), checkfirst=True)
    bulk_job_status = sa.Enum('running', 'completed', 'partial', name='bulk_job_status')
    bulk_job_status.create(op.get_bind(), checkfirst=True)
    bulk_item_status = sa.Enum('pending', 'queued', 'downloading', 'completed', 'failed', name='bulk_item_status')
    bulk_item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'bulk_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('job_type', bulk_job_type, nullable=False),
        sa.Column('total_items', sa.Integer(), nullable=False),
        sa.Column('processed_items', sa.Integer(), nullable=False),
        sa.Column('failed_items', sa.Integer(), nullable=False),
        sa.Column('status', bulk_job_status, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bulk_jobs_job_type'), 'bulk_jobs', ['job_type'], unique=False)
    op.create_index(op.f('ix_bulk_jobs_status'), 'bulk_jobs', ['status'], unique=False)

    op.create_table(
        'bulk_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('status', bulk_item_status, nullable=False),
        sa.Column('download_id', sa.String(length=36), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['bulk_jobs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bulk_items_job_id'), 'bulk_items', ['job_id'], unique=False)
    op.create_index(op.f('ix_bulk_items_status'), 'bulk_items', ['status'], unique=False)
    op.create_index(op.f('ix_bulk_items_url'), 'bulk_items', ['url'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bulk_items_url'), table_name='bulk_items')
    op.drop_index(op.f('ix_bulk_items_status'), table_name='bulk_items')
    op.drop_index(op.f('ix_bulk_items_job_id'), table_name='bulk_items')
    op.drop_table('bulk_items')
    op.drop_index(op.f('ix_bulk_jobs_status'), table_name='bulk_jobs')
    op.drop_index(op.f('ix_bulk_jobs_job_type'), table_name='bulk_jobs')
    op.drop_table('bulk_jobs')
    bulk_item_status = sa.Enum('pending', 'queued', 'downloading', 'completed', 'failed', name='bulk_item_status')
    bulk_item_status.drop(op.get_bind(), checkfirst=True)
    bulk_job_status = sa.Enum('running', 'completed', 'partial', name='bulk_job_status')
    bulk_job_status.drop(op.get_bind(), checkfirst=True)
    bulk_job_type = sa.Enum('links', 'profiles', name='bulk_job_type')
    bulk_job_type.drop(op.get_bind(), checkfirst=True)
