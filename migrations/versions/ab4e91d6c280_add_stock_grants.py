"""Add stock grants and their explicit vesting releases.

Revision ID: ab4e91d6c280
Revises: 6d2f8a9c1e40
Create Date: 2026-10-25 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER

revision = "ab4e91d6c280"
down_revision = "6d2f8a9c1e40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("grant_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("vesting_start_date", sa.Date(), nullable=False),
        sa.Column("schedule_type", sa.String(32), nullable=False),
        sa.Column("customized", sa.Boolean(), nullable=False),
        sa.Column("creation_token", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("stock_id", "creation_token", name="uq_stock_grant_creation_token"),
        sa.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_grant_quantity",
        ),
        sa.CheckConstraint("schedule_type IN ('quarterly', 'cliff-quarterly')", name="ck_stock_grant_schedule_type"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "grant_vestings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grant_id", sa.Integer(), sa.ForeignKey("stock_grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_grant_vesting_quantity",
        ),
    )
    op.create_index("ix_grant_vestings_grant_id", "grant_vestings", ["grant_id"])


def downgrade():
    op.drop_index("ix_grant_vestings_grant_id", table_name="grant_vestings")
    op.drop_table("grant_vestings")
    op.drop_table("stock_grants")
