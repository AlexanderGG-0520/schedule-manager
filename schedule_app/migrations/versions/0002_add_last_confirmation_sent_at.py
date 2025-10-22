"""add last_confirmation_sent_at column

Revision ID: 0002_add_last_confirmation_sent_at
Revises: 0001_initial
Create Date: 2025-10-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_last_confirmation_sent_at'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('last_confirmation_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'last_confirmation_sent_at')
