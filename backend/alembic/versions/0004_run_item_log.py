"""run item log: per-item scraping failure diagnostics

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runitemlog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("scrapingrun.id"), nullable=False),
        sa.Column("hash_id", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_runitemlog_run_id", "runitemlog", ["run_id"])
    op.create_index("ix_runitemlog_hash_id", "runitemlog", ["hash_id"])


def downgrade() -> None:
    op.drop_index("ix_runitemlog_hash_id", table_name="runitemlog")
    op.drop_index("ix_runitemlog_run_id", table_name="runitemlog")
    op.drop_table("runitemlog")
