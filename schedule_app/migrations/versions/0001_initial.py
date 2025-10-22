"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-10-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated ###
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    op.create_index('ix_users_username', 'users', ['username'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False, server_default='#4287f5'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    op.create_index('ix_events_user_id', 'events', ['user_id'], unique=False)
    op.create_index('ix_events_start_at', 'events', ['start_at'], unique=False)
    op.create_index('ix_events_end_at', 'events', ['end_at'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated ###
    op.drop_index('ix_events_end_at', table_name='events')
    op.drop_index('ix_events_start_at', table_name='events')
    op.drop_index('ix_events_user_id', table_name='events')
    op.drop_table('events')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###
