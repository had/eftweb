"""Add a release_date to RSUVestings

Revision ID: 5649893ed72f
Revises: f17355249cdf
Create Date: 2024-05-11 11:28:25.276915

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5649893ed72f'
down_revision = 'f17355249cdf'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rsu_stocks',sa.Column('release_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('rsu_stocks', 'release_date')
