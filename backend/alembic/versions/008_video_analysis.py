"""Create video_analysis table for Phase 10A AI transcription and summarization."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_video_analysis"
down_revision: Union[str, None] = "008_cloud_and_trim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    analysis_status = sa.Enum("pending", "processing", "completed", "failed", name="analysis_status")
    analysis_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "video_analysis",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("download_id", sa.String(36), nullable=False),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("srt_path", sa.String(1024), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("translated", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", analysis_status, nullable=False, default="pending"),
        sa.Column("error", sa.String(2000), nullable=True),
    )
    op.create_index("ix_video_analysis_download_id", "video_analysis", ["download_id"])
    op.create_index("ix_video_analysis_status", "video_analysis", ["status"])


def downgrade() -> None:
    op.drop_index("ix_video_analysis_status", table_name="video_analysis")
    op.drop_index("ix_video_analysis_download_id", table_name="video_analysis")
    op.drop_table("video_analysis")
    analysis_status = sa.Enum("pending", "processing", "completed", "failed", name="analysis_status")
    analysis_status.drop(op.get_bind(), checkfirst=True)
