"""Add stock purchases and purchase-backed sale allocations.

Revision ID: c2e6a8f41d90
Revises: b9e4c27a810f
"""

import sqlalchemy as sa
from alembic import op

from app.constants import JAVASCRIPT_MAX_SAFE_INTEGER

revision = "c2e6a8f41d90"
down_revision = "b9e4c27a810f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("plan_name", sa.String(256), nullable=False),
        sa.Column("creation_token", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("stock_id", "creation_token", name="uq_stock_purchase_creation_token"),
        sa.CheckConstraint(
            f"quantity > 0 AND quantity <= {JAVASCRIPT_MAX_SAFE_INTEGER}",
            name="ck_stock_purchase_quantity",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_stock_purchases_stock_id", "stock_purchases", ["stock_id"])
    with op.batch_alter_table("stock_sale_allocations") as batch:
        batch.alter_column("vesting_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("purchase_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_stock_sale_allocation_purchase",
            "stock_purchases",
            ["purchase_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_stock_sale_allocations_purchase_id", ["purchase_id"])
        batch.create_unique_constraint(
            "uq_stock_sale_allocation_purchase", ["sale_id", "purchase_id"]
        )
        batch.create_check_constraint(
            "ck_stock_sale_allocation_source",
            "(vesting_id IS NOT NULL AND purchase_id IS NULL) OR (vesting_id IS NULL AND purchase_id IS NOT NULL)",
        )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT COUNT(*) FROM stock_sale_allocations WHERE purchase_id IS NOT NULL")
        )
        .scalar()
    ):
        raise RuntimeError(
            "Delete sales allocated to purchases before downgrading stock purchases."
        )
    with op.batch_alter_table("stock_sale_allocations") as batch:
        batch.drop_constraint("ck_stock_sale_allocation_source", type_="check")
        batch.drop_constraint("uq_stock_sale_allocation_purchase", type_="unique")
        batch.drop_index("ix_stock_sale_allocations_purchase_id")
        batch.drop_constraint("fk_stock_sale_allocation_purchase", type_="foreignkey")
        batch.drop_column("purchase_id")
        batch.alter_column("vesting_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("stock_purchases")
