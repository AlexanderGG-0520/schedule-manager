"""add retros and tasks

Revision ID: 0010_add_retro_and_tasks
Revises: 0009_add_reactions
Create Date: 2025-10-29 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010_add_retro_and_tasks'
down_revision = '0009_add_reactions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'retros',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('q1', sa.Text(), nullable=True),
        sa.Column('q2', sa.Text(), nullable=True),
        sa.Column('q3', sa.Text(), nullable=True),
        sa.Column('next_action', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_retros_event_id', 'retros', ['event_id'], unique=False)
    op.create_index('ix_retros_user_id', 'retros', ['user_id'], unique=False)

    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    )
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'], unique=False)
    op.create_index('ix_tasks_event_id', 'tasks', ['event_id'], unique=False)


def downgrade():
    op.drop_index('ix_tasks_event_id', table_name='tasks')
    op.drop_index('ix_tasks_user_id', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('ix_retros_user_id', table_name='retros')
    op.drop_index('ix_retros_event_id', table_name='retros')
    op.drop_table('retros')
