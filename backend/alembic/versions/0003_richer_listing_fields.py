"""richer listing fields: locality_text, seller_type, land_area, floor_number,
total_floors, elevator, garden, last_updated_at; fix furnished bool->str

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- listing ---
    op.add_column("listing", sa.Column("locality_text", sa.String(), nullable=True))
    op.add_column("listing", sa.Column("seller_type", sa.String(), nullable=True))
    op.create_index("ix_listing_seller_type", "listing", ["seller_type"])

    # --- listingdetail ---
    op.add_column("listingdetail", sa.Column("land_area", sa.Integer(), nullable=True))
    op.add_column("listingdetail", sa.Column("floor_number", sa.Integer(), nullable=True))
    op.add_column("listingdetail", sa.Column("total_floors", sa.Integer(), nullable=True))
    op.add_column("listingdetail", sa.Column("elevator", sa.String(), nullable=True))
    op.add_column("listingdetail", sa.Column("garden", sa.Boolean(), nullable=True))
    op.add_column("listingdetail", sa.Column("last_updated_at", sa.DateTime(), nullable=True))

    # furnished was previously a mis-parsed bool (see app/models/listing_detail.py
    # docstring): sreality's furnished_cb is a 3-value codebook (1=Ano,2=Ne,3=Castecne),
    # and casting it through bool() mis-stored "Ne" as True. Converting the column to
    # string; any existing bool data is dropped via USING NULL rather than guessing a
    # codebook value back out of a corrupted boolean.
    op.execute("ALTER TABLE listingdetail ALTER COLUMN furnished DROP DEFAULT")
    op.execute("ALTER TABLE listingdetail ALTER COLUMN furnished TYPE VARCHAR USING NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE listingdetail ALTER COLUMN furnished TYPE BOOLEAN USING NULL")
    op.drop_column("listingdetail", "last_updated_at")
    op.drop_column("listingdetail", "garden")
    op.drop_column("listingdetail", "elevator")
    op.drop_column("listingdetail", "total_floors")
    op.drop_column("listingdetail", "floor_number")
    op.drop_column("listingdetail", "land_area")
    op.drop_index("ix_listing_seller_type", table_name="listing")
    op.drop_column("listing", "seller_type")
    op.drop_column("listing", "locality_text")
