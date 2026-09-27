"""add IFU statements

Revision ID: f7b2d6e84c16
Revises: e6a4c1d93f75
Create Date: 2026-09-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f7b2d6e84c16"
down_revision = "e6a4c1d93f75"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifu_statements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tax_return_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("box_2tr", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2tt", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2dc", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2cg", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2bh", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2ck", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2df", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2dh", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2yy", sa.Numeric(precision=12, scale=2)),
        sa.Column("box_2zz", sa.Numeric(precision=12, scale=2)),
        sa.ForeignKeyConstraint(["tax_return_id"], ["tax_returns.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("ifu_statements")
