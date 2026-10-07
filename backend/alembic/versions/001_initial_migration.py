"""Initial migration

Revision ID: 001_initial_migration
Revises: 
Create Date: 2026-10-02 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_migration'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('downloads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('file_path', sa.String(length=1024), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('quality', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.String(length=2000), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('is_watermark_free', sa.Boolean(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_downloads_url'), 'downloads', ['url'], unique=False)

    op.create_table('download_queue',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('download_id', sa.String(length=36), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['download_id'], ['downloads.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('download_id')
    )
    op.create_index(op.f('ix_download_queue_position'), 'download_queue', ['position'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_download_queue_position'), table_name='download_queue')
    op.drop_table('download_queue')
    op.drop_index(op.f('ix_downloads_url'), table_name='downloads')
    op.drop_table('downloads')
