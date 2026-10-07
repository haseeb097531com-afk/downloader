"""Create media_fingerprints table for Phase 11A smart deduplication."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_smart_deduplication"
down_revision: Union[str, None] = "008_video_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_fingerprints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("download_id", sa.String(36), sa.ForeignKey("downloads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phash", sa.String(16), nullable=False),
        sa.Column("keyframe_paths", sa.JSON(), nullable=False),
    )
    op.create_index("ix_media_fingerprints_download_id", "media_fingerprints", ["download_id"], unique=True)
    op.create_index("ix_media_fingerprints_phash", "media_fingerprints", ["phash"])


def downgrade() -> None:
    op.drop_index("ix_media_fingerprints_phash", table_name="media_fingerprints")
    op.drop_index("ix_media_fingerprints_download_id", table_name="media_fingerprints")
    op.drop_table("media_fingerprints")
