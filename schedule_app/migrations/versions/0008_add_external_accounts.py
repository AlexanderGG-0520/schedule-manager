"""add external accounts and integration logging

Revision ID: 0008_add_external_accounts
Revises: 0007_add_event_fields
Create Date: 2025-10-27 04:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008_add_external_accounts'
down_revision = '0007_add_event_fields'
branch_labels = None
depends_on = None


def upgrade():
    # create external_accounts table
    op.create_table(
        'external_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    op.create_index('ix_external_accounts_user_id', 'external_accounts', ['user_id'], unique=False)
    op.create_index('ix_external_accounts_provider', 'external_accounts', ['provider'], unique=False)
    op.create_index('ix_external_accounts_external_id', 'external_accounts', ['external_id'], unique=False)

    # create external_event_mappings table
    op.create_table(
        'external_event_mappings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('provider_event_id', sa.String(length=255), nullable=False),
        sa.Column('external_account_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['external_account_id'], ['external_accounts.id'], ),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    )

    op.create_index('ix_external_event_mappings_provider', 'external_event_mappings', ['provider'], unique=False)
    op.create_index('ix_external_event_mappings_provider_event', 'external_event_mappings', ['provider_event_id'], unique=False)
    op.create_index('ix_external_event_mappings_event_id', 'external_event_mappings', ['event_id'], unique=False)

    # create integration_logs table
    op.create_table(
        'integration_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.String(length=16), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['external_accounts.id'], ),
    )

    op.create_index('ix_integration_logs_account_id', 'integration_logs', ['account_id'], unique=False)


def downgrade():
    op.drop_index('ix_integration_logs_account_id', table_name='integration_logs')
    op.drop_table('integration_logs')

    op.drop_index('ix_external_event_mappings_event_id', table_name='external_event_mappings')
    op.drop_index('ix_external_event_mappings_provider_event', table_name='external_event_mappings')
    op.drop_index('ix_external_event_mappings_provider', table_name='external_event_mappings')
    op.drop_table('external_event_mappings')

    op.drop_index('ix_external_accounts_external_id', table_name='external_accounts')
    op.drop_index('ix_external_accounts_provider', table_name='external_accounts')
    op.drop_index('ix_external_accounts_user_id', table_name='external_accounts')
    op.drop_table('external_accounts')
