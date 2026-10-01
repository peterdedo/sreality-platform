"""widen price_czk columns to bigint (luxury listings exceed int32)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01

Sreality list prices can exceed PostgreSQL INTEGER max (~2.1e9 CZK). A single
such listing previously aborted the whole scrape via NumericValueOutOfRange
during flush (seen as \"Scraping run failed\" while resolving region).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "listing",
        "price_czk",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "pricehistory",
        "price_czk",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "pricehistory",
        "price_czk",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "listing",
        "price_czk",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
