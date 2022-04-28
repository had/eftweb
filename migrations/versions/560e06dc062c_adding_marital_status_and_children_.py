"""Adding marital status and children count to Project table

Revision ID: 560e06dc062c
Revises: 65a6a9a7fe2d
Create Date: 2022-04-28 16:43:55.911806

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '560e06dc062c'
down_revision = '65a6a9a7fe2d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('married', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('nb_children', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('nb_children')
        batch_op.drop_column('married')

    # ### end Alembic commands ###
