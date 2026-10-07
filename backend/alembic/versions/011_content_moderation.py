"""Add content moderation fields to downloads

Revision ID: 011_content_moderation
Revises: 010_download_schedules
Create Date: 2026-10-04 04:14:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011_content_moderation'
down_revision: Union[str, None] = '010_download_schedules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('downloads', sa.Column('quarantined', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('downloads', sa.Column('quarantine_reason', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('downloads', 'quarantine_reason')
    op.drop_column('downloads', 'quarantined')
