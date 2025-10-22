"""add location column to events

Revision ID: 0006_add_event_location
Revises: 0005_add_2fa_columns
Create Date: 2025-10-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_add_event_location'
down_revision = '0005_add_2fa_columns'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('location', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('events', 'location')

