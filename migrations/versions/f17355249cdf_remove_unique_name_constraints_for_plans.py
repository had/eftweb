"""Remove unique name constraints for plans

Revision ID: f17355249cdf
Revises: 3f01520aad12
Create Date: 2024-05-04 17:49:27.901424

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f17355249cdf'
down_revision = '3f01520aad12'
branch_labels = None
depends_on = None


def upgrade():
    # Remove unique constraint for rsu_plans
    op.rename_table('rsu_plans', 'rsu_plans_tmp')
    op.create_table('rsu_plans',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('project_id', sa.Integer(), nullable=True),
                    sa.Column('name', sa.String(length=256), nullable=True),
                    sa.Column('approval_date', sa.Date(), nullable=True),
                    sa.Column('symbol', sa.String(length=16), nullable=True),
                    sa.Column('stock_currency', sa.String(length=3), nullable=True),
                    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.execute('INSERT INTO rsu_plans (id, project_id, name, approval_date, symbol, stock_currency) SELECT id, project_id, name, approval_date, symbol, stock_currency from rsu_plans_tmp')
    op.drop_table('rsu_plans_tmp')

    # Remove unique constraint for direct_stocks_plan
    op.rename_table('direct_stocks_plan', 'direct_stocks_plan_tmp')
    op.create_table('direct_stocks_plan',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('project_id', sa.Integer(), nullable=True),
                    sa.Column('name', sa.String(length=256), nullable=True),
                    sa.Column('symbol', sa.String(length=16), nullable=True),
                    sa.Column('stock_currency', sa.String(length=3), nullable=True),
                    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.execute('INSERT INTO direct_stocks_plan (id, project_id, name, symbol, stock_currency) SELECT id, project_id, name, symbol, stock_currency from direct_stocks_plan_tmp')
    op.drop_table('direct_stocks_plan_tmp')

    # Remove unique constraint for direct_stocks_plan
    op.rename_table('stockoption_plans', 'stockoption_plans_tmp')
    op.create_table('stockoption_plans',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('project_id', sa.Integer(), nullable=True),
                    sa.Column('name', sa.String(length=256), nullable=True),
                    sa.Column('taxpayer_owner', sa.Integer(), nullable=True),
                    sa.Column('symbol', sa.String(length=16), nullable=True),
                    sa.Column('stock_currency', sa.String(length=3), nullable=True),
                    sa.Column('strike_price', sa.Float(), nullable=True),
                    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.execute(
        'INSERT INTO stockoption_plans (id, project_id, name, taxpayer_owner, symbol, stock_currency, strike_price) SELECT id, project_id, name, taxpayer_owner, symbol, stock_currency, strike_price from stockoption_plans_tmp')
    op.drop_table('stockoption_plans_tmp')


def downgrade():
    # ignore this downgrade case
    pass
