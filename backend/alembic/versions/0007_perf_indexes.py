"""performance indexes for map and price-history queries

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_pricehistory_listing_id_recorded_at",
        "pricehistory",
        ["listing_id", "recorded_at"],
    )
    op.create_index("ix_listing_first_seen_at", "listing", ["first_seen_at"])
    op.create_index("ix_listing_last_seen_at", "listing", ["last_seen_at"])
    op.execute(
        sa.text(
            "CREATE INDEX ix_listing_active_gps "
            "ON listing (gps_lat, gps_lon) "
            "WHERE is_active = true AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_listing_active_gps"))
    op.drop_index("ix_listing_last_seen_at", table_name="listing")
    op.drop_index("ix_listing_first_seen_at", table_name="listing")
    op.drop_index("ix_pricehistory_listing_id_recorded_at", table_name="pricehistory")
