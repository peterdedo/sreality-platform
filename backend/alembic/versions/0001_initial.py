"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("district", sa.String(), nullable=True),
        sa.Column("municipality", sa.String(), nullable=True),
        sa.Column("quarter", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=False, server_default="Česká republika"),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lon", sa.Float(), nullable=True),
        sa.Column("locality_region_id", sa.Integer(), nullable=True),
        sa.Column("locality_district_id", sa.Integer(), nullable=True),
        sa.Column("locality_municipality_id", sa.Integer(), nullable=True),
        sa.Column("locality_ward_id", sa.Integer(), nullable=True),
        sa.Column("locality_quarter_id", sa.Integer(), nullable=True),
        sa.Column("locality_street_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_location_region", "location", ["region"])
    op.create_index("ix_location_district", "location", ["district"])
    op.create_index("ix_location_municipality", "location", ["municipality"])
    op.create_index("ix_location_locality_region_id", "location", ["locality_region_id"])
    op.create_index("ix_location_locality_district_id", "location", ["locality_district_id"])
    op.create_index("ix_location_locality_municipality_id", "location", ["locality_municipality_id"])

    op.create_table(
        "listing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hash_id", sa.String(), nullable=False),
        sa.Column("category_main_cb", sa.Integer(), nullable=False),
        sa.Column("category_type_cb", sa.Integer(), nullable=False),
        sa.Column("category_sub_cb", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("price_czk", sa.Integer(), nullable=True),
        sa.Column("price_czk_unit", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="CZK"),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lon", sa.Float(), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
    )
    op.create_unique_constraint("uq_listing_hash_id", "listing", ["hash_id"])
    op.create_index("ix_listing_hash_id", "listing", ["hash_id"])
    op.create_index("ix_listing_category_main_cb", "listing", ["category_main_cb"])
    op.create_index("ix_listing_category_type_cb", "listing", ["category_type_cb"])
    op.create_index("ix_listing_category_sub_cb", "listing", ["category_sub_cb"])
    op.create_index("ix_listing_price_czk", "listing", ["price_czk"])
    op.create_index("ix_listing_location_id", "listing", ["location_id"])
    op.create_index("ix_listing_is_active", "listing", ["is_active"])
    op.create_index("ix_listing_removed_at", "listing", ["removed_at"])

    op.create_table(
        "listingdetail",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("meta_description", sa.String(), nullable=True),
        sa.Column("usable_area", sa.Integer(), nullable=True),
        sa.Column("floor_area", sa.Integer(), nullable=True),
        sa.Column("built_up_area", sa.Integer(), nullable=True),
        sa.Column("floor", sa.String(), nullable=True),
        sa.Column("ownership", sa.String(), nullable=True),
        sa.Column("building_type", sa.String(), nullable=True),
        sa.Column("building_condition", sa.String(), nullable=True),
        sa.Column("material", sa.String(), nullable=True),
        sa.Column("object_kind", sa.String(), nullable=True),
        sa.Column("energy_efficiency_rating", sa.String(), nullable=True),
        sa.Column("furnished", sa.Boolean(), nullable=True),
        sa.Column("balcony", sa.Boolean(), nullable=True),
        sa.Column("terrace", sa.Boolean(), nullable=True),
        sa.Column("loggia", sa.Boolean(), nullable=True),
        sa.Column("cellar", sa.Boolean(), nullable=True),
        sa.Column("garage", sa.Boolean(), nullable=True),
        sa.Column("basin", sa.Boolean(), nullable=True),
        sa.Column("parking_lots", sa.Integer(), nullable=True),
        sa.Column("low_energy", sa.Boolean(), nullable=True),
        sa.Column("easy_access", sa.Boolean(), nullable=True),
        sa.Column("no_barriers", sa.String(), nullable=True),
        sa.Column("broker_id", sa.String(), nullable=True),
        sa.Column("broker_company", sa.String(), nullable=True),
        sa.Column("note_about_price", sa.String(), nullable=True),
        sa.Column("id_of_order", sa.String(), nullable=True),
        sa.Column("start_of_offer", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_listingdetail_listing_id", "listingdetail", ["listing_id"])
    op.create_index("ix_listingdetail_listing_id", "listingdetail", ["listing_id"])

    op.create_table(
        "pricehistory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=False),
        sa.Column("price_czk", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pricehistory_listing_id", "pricehistory", ["listing_id"])
    op.create_index("ix_pricehistory_recorded_at", "pricehistory", ["recorded_at"])

    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloaded_path", sa.String(), nullable=True),
    )
    op.create_index("ix_image_listing_id", "image", ["listing_id"])

    op.create_table(
        "scrapingrun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(), nullable=True),
    )

    op.create_table(
        "rawpayload",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=True),
        sa.Column("hash_id", sa.String(), nullable=True),
        sa.Column("payload_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rawpayload_listing_id", "rawpayload", ["listing_id"])
    op.create_index("ix_rawpayload_hash_id", "rawpayload", ["hash_id"])
    op.create_index("ix_rawpayload_fetched_at", "rawpayload", ["fetched_at"])

    op.create_table(
        "analyticsnapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id"), nullable=True),
        sa.Column("category_main_cb", sa.Integer(), nullable=True),
        sa.Column("category_type_cb", sa.Integer(), nullable=True),
        sa.Column("listing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_price_czk", sa.Float(), nullable=True),
        sa.Column("median_price_czk", sa.Float(), nullable=True),
        sa.Column("avg_price_per_m2", sa.Float(), nullable=True),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_analyticsnapshot_snapshot_date", "analyticsnapshot", ["snapshot_date"])
    op.create_index("ix_analyticsnapshot_location_id", "analyticsnapshot", ["location_id"])
    op.create_index("ix_analyticsnapshot_category_main_cb", "analyticsnapshot", ["category_main_cb"])
    op.create_index("ix_analyticsnapshot_category_type_cb", "analyticsnapshot", ["category_type_cb"])


def downgrade() -> None:
    op.drop_table("analyticsnapshot")
    op.drop_table("rawpayload")
    op.drop_table("scrapingrun")
    op.drop_table("image")
    op.drop_table("pricehistory")
    op.drop_table("listingdetail")
    op.drop_table("listing")
    op.drop_table("location")
