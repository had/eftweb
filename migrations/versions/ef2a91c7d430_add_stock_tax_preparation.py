"""Stock tax inputs, historical FX and persisted source statements.

Revision ID: ef2a91c7d430
Revises: d8f41a2c6b90
"""

import sqlalchemy as sa
from alembic import op

revision = "ef2a91c7d430"
down_revision = "e7a3b9c52f10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_grants", sa.Column("approval_date", sa.Date(), nullable=True))
    op.add_column("stock_grants", sa.Column("taxpayer_role", sa.String(16), nullable=True))
    for table in ("grant_vestings", "stock_purchases"):
        op.add_column(
            table,
            sa.Column("acquisition_fmv", sa.Numeric(14, 6), nullable=False, server_default="0"),
        )
    op.add_column(
        "stock_sales", sa.Column("fees", sa.Numeric(14, 2), nullable=False, server_default="0")
    )
    op.add_column(
        "tax_returns",
        sa.Column("has_stock_statements", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "capital_gain_statements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tax_return_id",
            sa.Integer(),
            sa.ForeignKey("tax_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(80)),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("stock_id", sa.Integer()),
        sa.Column("computed", sa.JSON(), nullable=False),
        sa.Column("reported", sa.JSON(), nullable=False),
        sa.Column("metadata_snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tax_return_id", "source_key", name="uq_capital_source"),
    )
    op.create_table(
        "capital_gain_helper_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "statement_id",
            sa.Integer(),
            sa.ForeignKey("capital_gain_statements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "stock_tax_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tax_return_id",
            sa.Integer(),
            sa.ForeignKey("tax_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tax_return_id", "token", name="uq_stock_tax_receipt"),
    )
    op.create_table(
        "usd_eur_rates",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("usd_per_eur", sa.Numeric(20, 12), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
    )
    op.create_table(
        "fx_coverage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_date", sa.Date(), nullable=False),
        sa.Column("last_date", sa.Date(), nullable=False),
    )


def downgrade():
    for table in (
        "capital_gain_helper_lines",
        "capital_gain_statements",
        "stock_tax_receipts",
        "usd_eur_rates",
        "fx_coverage",
    ):
        op.drop_table(table)
    for table, columns in (
        ("tax_returns", ["has_stock_statements"]),
        ("stock_sales", ["fees"]),
        ("grant_vestings", ["acquisition_fmv"]),
        ("stock_purchases", ["acquisition_fmv"]),
        ("stock_grants", ["approval_date", "taxpayer_role"]),
    ):
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column)
