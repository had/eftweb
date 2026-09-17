"""add family and family members

Revision ID: d1a6f9c44e20
Revises: 2126ef7ea728
Create Date: 2026-09-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d1a6f9c44e20"
down_revision = "2126ef7ea728"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(role IN ('taxpayer1', 'taxpayer2') AND position = 1) "
            "OR (role = 'child' AND position BETWEEN 1 AND 6)",
            name="ck_family_members_role_position",
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "role", "position", name="uq_family_member_slot"),
    )


def downgrade():
    op.drop_table("family_members")
    op.drop_table("families")
