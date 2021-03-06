"""Aligning column names with easyfrenchtax project

Revision ID: a0d37ef1690e
Revises: 9045de055e80
Create Date: 2022-04-28 16:23:56.866378

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0d37ef1690e'
down_revision = '9045de055e80'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('charity_segments', 'charity_7UD', new_column_name='charity_donation_7UD')
    op.alter_column('charity_segments', 'charity_7UF', new_column_name='charity_donation_7UF')
    op.alter_column('income_segments', 'income_1', new_column_name='salary_1_1AJ')
    op.alter_column('income_segments', 'income_2', new_column_name='salary_2_1BJ')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('charity_segments', 'charity_donation_7UD', new_column_name='charity_7UD')
    op.alter_column('charity_segments', 'charity_donation_7UF', new_column_name='charity_7UF')
    op.alter_column('income_segments', 'salary_1_1AJ', new_column_name='income_1')
    op.alter_column('income_segments', 'salary_2_1BJ', new_column_name='income_2')

    # ### end Alembic commands ###
