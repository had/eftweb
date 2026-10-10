"""Drop obsolete stock sale tables and their data.

Revision ID: 7ab43e902d16
Revises: f7b2d6e84c16
Create Date: 2026-10-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "7ab43e902d16"
down_revision = "f7b2d6e84c16"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("rsu_sales")
    op.drop_table("direct_stocks_sales")


def downgrade():
    # Restore the previous schema only; the discarded sale data cannot be recovered.
    for table_name in ("direct_stocks_sales", "rsu_sales"):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=16), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=True),
            sa.Column("sell_date", sa.Date(), nullable=True),
            sa.Column("sell_price", sa.Float(), nullable=True),
            sa.Column("sell_currency", sa.String(length=3), nullable=True),
            sa.Column("fees", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
