"""Add grant numbers, broker provenance, and import receipts."""

import sqlalchemy as sa
from alembic import op

revision = "d8f41a2c6b90"
down_revision = "c2e6a8f41d90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stock_grants", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.add_column(sa.Column("grant_number", sa.String(256), nullable=True))
        batch.create_unique_constraint("uq_stock_grant_number", ["stock_id", "grant_number"])
    with op.batch_alter_table("stock_sales", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.add_column(sa.Column("import_source", sa.String(32), nullable=True))
        batch.add_column(sa.Column("source_order_number", sa.String(256), nullable=True))
        batch.add_column(sa.Column("source_fingerprint", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_stock_sale_source_group",
            [
                "stock_id",
                "import_source",
                "source_order_number",
                "transaction_date",
                "proceeds_per_share",
                "currency",
            ],
        )
    op.create_table(
        "stock_import_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("creation_token", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("stock_id", "creation_token", name="uq_stock_import_token"),
    )


def downgrade():
    op.drop_table("stock_import_receipts")
    with op.batch_alter_table("stock_sales", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_constraint("uq_stock_sale_source_group", type_="unique")
        for column in ("source_fingerprint", "source_order_number", "import_source"):
            batch.drop_column(column)
    with op.batch_alter_table("stock_grants", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_constraint("uq_stock_grant_number", type_="unique")
        batch.drop_column("grant_number")
