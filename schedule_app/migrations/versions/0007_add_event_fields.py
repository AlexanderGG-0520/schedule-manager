"""add participants, category, rrule, timezone to events

Revision ID: 0007_add_event_fields
Revises: 0006_add_event_location
Create Date: 2025-10-23 00:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007_add_event_fields'
down_revision = '0006_add_event_location'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('participants', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('category', sa.String(length=64), nullable=True))
    op.add_column('events', sa.Column('rrule', sa.String(length=512), nullable=True))
    op.add_column('events', sa.Column('timezone', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('events', 'timezone')
    op.drop_column('events', 'rrule')
    op.drop_column('events', 'category')
    op.drop_column('events', 'participants')
