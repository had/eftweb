"""add income statements

Revision ID: c4d8e2f17a93
Revises: f3c8b1e66a42
Create Date: 2026-09-18 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c4d8e2f17a93"
down_revision = "f3c8b1e66a42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "income_statements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tax_return_id", sa.Integer(), nullable=False),
        sa.Column("taxpayer_role", sa.String(length=16), nullable=False),
        sa.Column("employer_name", sa.String(length=255), nullable=False),
        sa.Column("known_employment_income", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("income_tax_withheld", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "supplementary_pension_contributions",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.CheckConstraint(
            "taxpayer_role IN ('taxpayer1', 'taxpayer2')",
            name="ck_income_statements_taxpayer_role",
        ),
        sa.ForeignKeyConstraint(["tax_return_id"], ["tax_returns.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("income_statements")
