"""Add family stocks.

Revision ID: 6d2f8a9c1e40
Revises: 7ab43e902d16
Create Date: 2026-10-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "6d2f8a9c1e40"
down_revision = "7ab43e902d16"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "symbol", name="uq_stock_family_symbol"),
    )


def downgrade():
    op.drop_table("stocks")
