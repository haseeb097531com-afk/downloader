"""No-op child migration to resolve the duplicate device-table branch.

This keeps a single linear migration chain while preserving the device schema
created by 015_devices.
"""

from typing import Sequence, Union

revision: str = "015_remote_control"
down_revision: Union[str, None] = "015_devices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The device table is created in 015_devices; this migration intentionally
    # keeps the head linear and prevents a split Alembic branch.
    pass


def downgrade() -> None:
    pass
