"""create invitations table

Revision ID: 0004_invitations
Revises: 0003_organizations_and_memberships
Create Date: 2025-10-22 11:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_invitations'
down_revision = '0003_organizations_and_memberships'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('invited_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('accepted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('invitations')
