"""add family tax returns and archiving

Revision ID: e2b7a0d55f31
Revises: d1a6f9c44e20
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e2b7a0d55f31"
down_revision = "d1a6f9c44e20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("families") as batch_op:
        batch_op.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "tax_returns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("family_id", "year", name="uq_tax_return_family_year"),
    )


def downgrade():
    op.drop_table("tax_returns")
    with op.batch_alter_table("families") as batch_op:
        batch_op.drop_column("is_archived")
