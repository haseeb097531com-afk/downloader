"""Create extraction_attempts table for Phase 6A fallback audit logging."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_extraction_attempts"
down_revision: Union[str, None] = "004_processing_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, default=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_extraction_attempts_url", "extraction_attempts", ["url"])
    op.create_index("ix_extraction_attempts_provider", "extraction_attempts", ["provider"])
    op.create_index("ix_extraction_attempts_created_at", "extraction_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_extraction_attempts_created_at", table_name="extraction_attempts")
    op.drop_index("ix_extraction_attempts_provider", table_name="extraction_attempts")
    op.drop_index("ix_extraction_attempts_url", table_name="extraction_attempts")
    op.drop_table("extraction_attempts")
