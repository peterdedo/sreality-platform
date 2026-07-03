"""advanced analytics (Pokročilé analýzy): valuation, anomaly, spatial grid, analytics runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- extend analyticsnapshot with market-dynamics columns ---
    op.add_column("analyticsnapshot", sa.Column("median_days_on_market", sa.Float(), nullable=True))
    op.add_column("analyticsnapshot", sa.Column("avg_days_on_market", sa.Float(), nullable=True))
    op.add_column("analyticsnapshot", sa.Column("price_drop_share", sa.Float(), nullable=True))
    op.add_column("analyticsnapshot", sa.Column("median_first_to_last_price_change_pct", sa.Float(), nullable=True))

    # --- valuationmodel (model registry) ---
    op.create_table(
        "valuationmodel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("segment_key", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False, server_default="log_price_czk"),
        sa.Column("feature_list", postgresql.JSONB(), nullable=False),
        sa.Column("coefficients", postgresql.JSONB(), nullable=False),
        sa.Column("intercept", sa.Float(), nullable=False),
        sa.Column("r2", sa.Float(), nullable=True),
        sa.Column("n_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trained_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
    )
    op.create_index("ix_valuationmodel_version", "valuationmodel", ["version"])
    op.create_index("ix_valuationmodel_segment_key", "valuationmodel", ["segment_key"])
    op.create_index("ix_valuationmodel_trained_at", "valuationmodel", ["trained_at"])

    # --- listingvaluation (latest estimate per listing) ---
    op.create_table(
        "listingvaluation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=False),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("valuationmodel.id"), nullable=True),
        sa.Column("expected_price_czk", sa.Float(), nullable=True),
        sa.Column("expected_price_per_m2", sa.Float(), nullable=True),
        sa.Column("residual_absolute", sa.Float(), nullable=True),
        sa.Column("residual_percent", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=False, server_default="unavailable"),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_listingvaluation_listing_id", "listingvaluation", ["listing_id"])
    op.create_index("ix_listingvaluation_listing_id", "listingvaluation", ["listing_id"])
    op.create_index("ix_listingvaluation_computed_at", "listingvaluation", ["computed_at"])

    # --- listinganomaly (latest score per listing) ---
    op.create_table(
        "listinganomaly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listing.id"), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("anomaly_flags", postgresql.JSONB(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint("uq_listinganomaly_listing_id", "listinganomaly", ["listing_id"])
    op.create_index("ix_listinganomaly_listing_id", "listinganomaly", ["listing_id"])
    op.create_index("ix_listinganomaly_anomaly_score", "listinganomaly", ["anomaly_score"])
    op.create_index("ix_listinganomaly_computed_at", "listinganomaly", ["computed_at"])

    # --- spatialgridmetric ---
    op.create_table(
        "spatialgridmetric",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grid_id", sa.String(), nullable=False),
        sa.Column("lat_center", sa.Float(), nullable=False),
        sa.Column("lon_center", sa.Float(), nullable=False),
        sa.Column("category_main_cb", sa.Integer(), nullable=True),
        sa.Column("category_type_cb", sa.Integer(), nullable=True),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("listing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_price_per_m2", sa.Float(), nullable=True),
        sa.Column("price_drop_intensity", sa.Float(), nullable=True),
        sa.Column("turnover_rate", sa.Float(), nullable=True),
    )
    op.create_index("ix_spatialgridmetric_grid_id", "spatialgridmetric", ["grid_id"])
    op.create_index("ix_spatialgridmetric_category_main_cb", "spatialgridmetric", ["category_main_cb"])
    op.create_index("ix_spatialgridmetric_category_type_cb", "spatialgridmetric", ["category_type_cb"])
    op.create_index("ix_spatialgridmetric_metric_date", "spatialgridmetric", ["metric_date"])

    # --- analyticsrun (Pokročilé analýzy recompute history) ---
    op.create_table(
        "analyticsrun",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("items_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("analyticsrun")
    op.drop_table("spatialgridmetric")
    op.drop_table("listinganomaly")
    op.drop_table("listingvaluation")
    op.drop_table("valuationmodel")
    op.drop_column("analyticsnapshot", "median_first_to_last_price_change_pct")
    op.drop_column("analyticsnapshot", "price_drop_share")
    op.drop_column("analyticsnapshot", "avg_days_on_market")
    op.drop_column("analyticsnapshot", "median_days_on_market")
