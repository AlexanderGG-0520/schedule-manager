"""Add notifications and participants tables

Revision ID: 0012
Revises: 0011
Create Date: 2025-11-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    # Create notifications table
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=32), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(), nullable=False),
    sa.Column('sent', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_event_id'), 'notifications', ['event_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_scheduled_at'), 'notifications', ['scheduled_at'], unique=False)

    # Create event_participants table
    op.create_table('event_participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('invited_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_event_participants_event_id'), 'event_participants', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_participants_user_id'), 'event_participants', ['user_id'], unique=False)
    op.create_index(op.f('ix_event_participants_email'), 'event_participants', ['email'], unique=False)

    # Create event_comments table
    op.create_table('event_comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_event_comments_event_id'), 'event_comments', ['event_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_event_comments_event_id'), table_name='event_comments')
    op.drop_table('event_comments')
    op.drop_index(op.f('ix_event_participants_email'), table_name='event_participants')
    op.drop_index(op.f('ix_event_participants_user_id'), table_name='event_participants')
    op.drop_index(op.f('ix_event_participants_event_id'), table_name='event_participants')
    op.drop_table('event_participants')
    op.drop_index(op.f('ix_notifications_scheduled_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_event_id'), table_name='notifications')
    op.drop_table('notifications')
