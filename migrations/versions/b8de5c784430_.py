"""Removing owner column for stocks and RSU plans, as they are not used

Revision ID: b8de5c784430
Revises: 0f6517250d4a
Create Date: 2023-07-24 21:27:54.332887

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8de5c784430'
down_revision = '0f6517250d4a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('direct_stocks', schema=None) as batch_op:
        batch_op.drop_column('taxpayer_owner')

    with op.batch_alter_table('rsu_plans', schema=None) as batch_op:
        batch_op.drop_column('taxpayer_owner')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('rsu_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('taxpayer_owner', sa.INTEGER(), nullable=True))

    with op.batch_alter_table('direct_stocks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('taxpayer_owner', sa.INTEGER(), nullable=True))

    # ### end Alembic commands ###
