"""Profiles migration

Revision ID: 002_profiles_migration
Revises: 001_initial_migration
Create Date: 2026-10-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002_profiles_migration'
down_revision: Union[str, None] = '001_initial_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('profile_url', sa.String(length=1024), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=1024), nullable=True),
        sa.Column('total_videos', sa.Integer(), nullable=True),
        sa.Column('last_scraped_at', sa.DateTime(), nullable=True),
        sa.Column('auto_download', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_url')
    )
    op.create_index(op.f('ix_profiles_platform'), 'profiles', ['platform'], unique=False)
    op.create_index(op.f('ix_profiles_username'), 'profiles', ['username'], unique=False)

    op.create_table('profile_videos',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('profile_id', sa.String(length=36), nullable=False),
        sa.Column('video_url', sa.String(length=1024), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=1024), nullable=True),
        sa.Column('upload_date', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('download_id', sa.String(length=36), nullable=True),
        sa.Column('discovered_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['download_id'], ['downloads.id'], ),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_profile_videos_profile_id'), 'profile_videos', ['profile_id'], unique=False)
    op.create_index(op.f('ix_profile_videos_video_url'), 'profile_videos', ['video_url'], unique=True)

def downgrade() -> None:
    op.drop_index(op.f('ix_profile_videos_video_url'), table_name='profile_videos')
    op.drop_index(op.f('ix_profile_videos_profile_id'), table_name='profile_videos')
    op.drop_table('profile_videos')
    op.drop_index(op.f('ix_profiles_username'), table_name='profiles')
    op.drop_index(op.f('ix_profiles_platform'), table_name='profiles')
    op.drop_table('profiles')
