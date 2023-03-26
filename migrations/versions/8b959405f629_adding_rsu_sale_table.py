"""Adding RSU sale table

Revision ID: 8b959405f629
Revises: a7c6de4ed921
Create Date: 2023-03-25 13:36:54.958169

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b959405f629'
down_revision = 'a7c6de4ed921'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('rsu_sales',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
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
    op.drop_table('rsu_sales')
    # ### end Alembic commands ###
