"""Adding a generic SaleEvent table

Revision ID: 3c73c602245f
Revises: ffa8aecac3d7
Create Date: 2023-07-26 13:54:17.135504

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c73c602245f'
down_revision = 'ffa8aecac3d7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sale_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.Enum('RSU', 'ESPP', 'STOCKOPTIONS', name='stocktype'), nullable=True),
    sa.Column('symbol', sa.String(length=16), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('sell_date', sa.Date(), nullable=True),
    sa.Column('sell_price', sa.Float(), nullable=True),
    sa.Column('sell_currency', sa.String(length=3), nullable=True),
    sa.Column('fees', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sale_events')
    # ### end Alembic commands ###
