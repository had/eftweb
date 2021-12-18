"""Introducing charity segment (2)

Revision ID: b621f57d7290
Revises: 0d7f2edc76ac
Create Date: 2021-12-17 23:13:41.914211

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b621f57d7290'
down_revision = '0d7f2edc76ac'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tax_statements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('charity_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_charity_to_statement", 'charity_segments', ['charity_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tax_statements', schema=None) as batch_op:
        batch_op.drop_constraint("fk_charity_to_statement", type_='foreignkey')
        batch_op.drop_column('charity_id')

    # ### end Alembic commands ###