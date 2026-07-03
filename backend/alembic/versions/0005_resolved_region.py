"""resolved region fields on listing

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("resolved_region_id", sa.Integer(), nullable=True))
    op.add_column("listing", sa.Column("resolved_region_name", sa.String(), nullable=True))
    op.add_column("listing", sa.Column("region_source", sa.String(), nullable=True))
    op.create_index("ix_listing_resolved_region_id", "listing", ["resolved_region_id"])
    op.create_index("ix_listing_resolved_region_name", "listing", ["resolved_region_name"])
    op.create_index("ix_listing_region_source", "listing", ["region_source"])


def downgrade() -> None:
    op.drop_index("ix_listing_region_source", table_name="listing")
    op.drop_index("ix_listing_resolved_region_name", table_name="listing")
    op.drop_index("ix_listing_resolved_region_id", table_name="listing")
    op.drop_column("listing", "region_source")
    op.drop_column("listing", "resolved_region_name")
    op.drop_column("listing", "resolved_region_id")
