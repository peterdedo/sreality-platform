"""region_unknown_reason on listing

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("region_unknown_reason", sa.String(), nullable=True))
    op.create_index("ix_listing_region_unknown_reason", "listing", ["region_unknown_reason"])


def downgrade() -> None:
    op.drop_index("ix_listing_region_unknown_reason", table_name="listing")
    op.drop_column("listing", "region_unknown_reason")
