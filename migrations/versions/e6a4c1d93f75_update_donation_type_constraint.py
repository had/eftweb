"""update donation type constraint

Revision ID: e6a4c1d93f75
Revises: d5e9f3a28b04
Create Date: 2026-09-25 00:00:00.000000

"""

from alembic import op

revision = "e6a4c1d93f75"
down_revision = "d5e9f3a28b04"
branch_labels = None
depends_on = None

NEW_DONATION_TYPE_CONSTRAINT = (
    "donation_type IN "
    "('people_in_need', 'public_interest', 'religious_heritage', "
    "'european_people_in_need', 'european_public_interest', "
    "'political_party', 'election_campaign')"
)
OLD_DONATION_TYPE_CONSTRAINT = (
    "donation_type IN "
    "('people_in_need', 'domestic_violence', 'public_interest', "
    "'religious_heritage', 'european_public_interest', "
    "'political_party', 'election_campaign')"
)


def upgrade():
    with op.batch_alter_table("donation_statements") as batch_op:
        batch_op.drop_constraint("ck_donation_statements_type", type_="check")
        batch_op.create_check_constraint("ck_donation_statements_type", NEW_DONATION_TYPE_CONSTRAINT)


def downgrade():
    with op.batch_alter_table("donation_statements") as batch_op:
        batch_op.drop_constraint("ck_donation_statements_type", type_="check")
        batch_op.create_check_constraint("ck_donation_statements_type", OLD_DONATION_TYPE_CONSTRAINT)
