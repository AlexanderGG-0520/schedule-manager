"""add two-factor auth columns to users

Revision ID: 0005_add_2fa_columns
Revises: 0004_invitations
Create Date: 2025-10-22 14:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_add_2fa_columns'
down_revision = '0004_invitations'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns for TOTP two-factor authentication
    op.add_column('users', sa.Column('two_factor_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('two_factor_secret', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('two_factor_backup_codes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'two_factor_backup_codes')
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_enabled')
