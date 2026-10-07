"""Create pending_links table for Phase 7A desktop clipboard integration."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_pending_links"
down_revision: Union[str, None] = "005_extraction_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pending_link_status = sa.Enum("pending", "dismissed", "downloaded", name="pending_link_status")
    pending_link_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "pending_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("status", pending_link_status, nullable=False, default="pending"),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pending_links_url", "pending_links", ["url"])
    op.create_index("ix_pending_links_platform", "pending_links", ["platform"])
    op.create_index("ix_pending_links_status", "pending_links", ["status"])
    op.create_index("ix_pending_links_detected_at", "pending_links", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_pending_links_detected_at", table_name="pending_links")
    op.drop_index("ix_pending_links_status", table_name="pending_links")
    op.drop_index("ix_pending_links_platform", table_name="pending_links")
    op.drop_index("ix_pending_links_url", table_name="pending_links")
    op.drop_table("pending_links")
    pending_link_status = sa.Enum("pending", "dismissed", "downloaded", name="pending_link_status")
    pending_link_status.drop(op.get_bind(), checkfirst=True)
