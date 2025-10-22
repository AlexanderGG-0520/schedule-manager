"""create organizations and membership tables

Revision ID: 0003_organizations_and_memberships
Revises: 0002_add_last_confirmation_sent_at
Create Date: 2025-10-22 10:45:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_organizations_and_memberships'
down_revision = '0002_add_last_confirmation_sent_at'
branch_labels = None
depends_on = None


def upgrade():
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create association table organization_members
    op.create_table(
        'organization_members',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), primary_key=True),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Add organization_id column to events
    op.add_column('events', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True))
    op.create_index(op.f('ix_events_organization_id'), 'events', ['organization_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_events_organization_id'), table_name='events')
    op.drop_column('events', 'organization_id')
    op.drop_table('organization_members')
    op.drop_table('organizations')
