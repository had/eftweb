"""Adding retirement investment segment

Revision ID: b8bc26dc7ed2
Revises: b621f57d7290
Create Date: 2022-03-31 10:29:13.927820

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8bc26dc7ed2'
down_revision = 'b621f57d7290'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('retirementinvestment_segments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('per_transfers_1_6NS', sa.Integer(), nullable=True),
    sa.Column('per_transfers_2_6NT', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tax_statements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('retirementinvestment_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_retirementinvestment_to_statement", 'retirementinvestment_segments', ['retirementinvestment_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tax_statements', schema=None) as batch_op:
        batch_op.drop_constraint("fk_retirementinvestment_to_statement", type_='foreignkey')
        batch_op.drop_column('retirementinvestment_id')

    op.drop_table('retirementinvestment_segments')
    # ### end Alembic commands ###
