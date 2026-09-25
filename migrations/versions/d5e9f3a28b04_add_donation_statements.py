"""add donation statements

Revision ID: d5e9f3a28b04
Revises: c4d8e2f17a93
Create Date: 2026-09-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d5e9f3a28b04"
down_revision = "c4d8e2f17a93"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "donation_statements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tax_return_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("donation_type", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "donation_type IN "
            "('people_in_need', 'domestic_violence', 'public_interest', "
            "'religious_heritage', 'european_public_interest', "
            "'political_party', 'election_campaign')",
            name="ck_donation_statements_type",
        ),
        sa.ForeignKeyConstraint(["tax_return_id"], ["tax_returns.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("donation_statements")
