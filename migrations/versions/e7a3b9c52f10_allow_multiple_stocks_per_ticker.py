"""Allow separate family holdings with the same ticker and prevent stock ID reuse."""

import sqlalchemy as sa
from alembic import op

revision = "e7a3b9c52f10"
down_revision = "d8f41a2c6b90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stocks", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_constraint("uq_stock_family_symbol", type_="unique")


def downgrade():
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT family_id, symbol FROM stocks GROUP BY family_id, symbol "
                "HAVING COUNT(*) > 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Cannot restore ticker uniqueness while a family has multiple stocks with the same "
            "ticker (including archived stocks). Resolve duplicate tickers before downgrading."
        )
    with op.batch_alter_table("stocks") as batch:
        batch.create_unique_constraint("uq_stock_family_symbol", ["family_id", "symbol"])
