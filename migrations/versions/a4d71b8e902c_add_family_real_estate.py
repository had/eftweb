"""Add family real estate properties."""

import sqlalchemy as sa
from alembic import op

revision = "a4d71b8e902c"
down_revision = "ef2a91c7d430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "real_estate_properties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_principal_home", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("estimated_value", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint(
            "estimated_value >= 0 AND estimated_value <= 999999999999.99",
            name="ck_property_estimated_value",
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_real_estate_properties_family_id", "real_estate_properties", ["family_id"])
    op.create_index(
        "uq_property_family_principal_home",
        "real_estate_properties",
        ["family_id"],
        unique=True,
        sqlite_where=sa.text("is_principal_home = 1"),
        postgresql_where=sa.text("is_principal_home = true"),
    )


def downgrade():
    op.drop_table("real_estate_properties")
