"""Introducing charity segment

Revision ID: 0d7f2edc76ac
Revises: 467943ee26c7
Create Date: 2021-12-17 16:58:23.170487

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d7f2edc76ac'
down_revision = '467943ee26c7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('charity_segments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('charity_7UD', sa.Integer(), nullable=True),
    sa.Column('charity_7UF', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('charity_segments')
    # ### end Alembic commands ###