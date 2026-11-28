"""Add acquisition and optional sell dates to family properties."""

import sqlalchemy as sa
from alembic import op

revision = "b6e92d41ac73"
down_revision = "a4d71b8e902c"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve existing properties without inventing historical acquisition dates.
    with op.batch_alter_table(
        "real_estate_properties", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.add_column(sa.Column("acquisition_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("sell_date", sa.Date(), nullable=True))
        batch.create_check_constraint(
            "ck_property_dates",
            "sell_date IS NULL OR (acquisition_date IS NOT NULL AND sell_date >= acquisition_date)",
        )


def downgrade():
    with op.batch_alter_table(
        "real_estate_properties", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.drop_constraint("ck_property_dates", type_="check")
        batch.drop_column("sell_date")
        batch.drop_column("acquisition_date")
