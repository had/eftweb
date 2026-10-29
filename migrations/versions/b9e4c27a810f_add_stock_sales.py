"""Add stock sales and explicit vesting allocations.

Revision ID: b9e4c27a810f
Revises: ab4e91d6c280
"""

import sqlalchemy as sa
from alembic import op

from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER

revision = "b9e4c27a810f"
down_revision = "ab4e91d6c280"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("proceeds_per_share", sa.Numeric(14, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("creation_token", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("stock_id", "creation_token", name="uq_stock_sale_creation_token"),
        sa.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_sale_quantity",
        ),
        sa.CheckConstraint("proceeds_per_share > 0", name="ck_stock_sale_price"),
        sa.CheckConstraint("currency = 'USD'", name="ck_stock_sale_currency"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_stock_sales_stock_id", "stock_sales", ["stock_id"])
    op.create_table(
        "stock_sale_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sale_id",
            sa.Integer(),
            sa.ForeignKey("stock_sales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vesting_id",
            sa.Integer(),
            sa.ForeignKey("grant_vestings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("sale_id", "vesting_id", name="uq_stock_sale_allocation_vesting"),
        sa.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_sale_allocation_quantity",
        ),
    )
    op.create_index("ix_stock_sale_allocations_sale_id", "stock_sale_allocations", ["sale_id"])
    op.create_index(
        "ix_stock_sale_allocations_vesting_id", "stock_sale_allocations", ["vesting_id"]
    )


def downgrade():
    op.drop_table("stock_sale_allocations")
    op.drop_table("stock_sales")
