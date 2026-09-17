"""add tax return configuration and archiving

Revision ID: f3c8b1e66a42
Revises: e2b7a0d55f31
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f3c8b1e66a42"
down_revision = "e2b7a0d55f31"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tax_returns") as batch_op:
        batch_op.add_column(sa.Column("has_income_statements", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("has_donation_statements", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("has_investment_statements", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("tax_returns") as batch_op:
        batch_op.drop_column("is_archived")
        batch_op.drop_column("has_investment_statements")
        batch_op.drop_column("has_donation_statements")
        batch_op.drop_column("has_income_statements")
