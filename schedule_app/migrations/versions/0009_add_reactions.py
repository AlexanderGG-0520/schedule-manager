"""add reactions table

Revision ID: 0009_add_reactions
Revises: 0008_add_external_accounts
Create Date: 2025-10-29 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009_add_reactions'
down_revision = '0008_add_external_accounts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('emoji', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_reactions_event_id', 'reactions', ['event_id'], unique=False)
    op.create_index('ix_reactions_user_id', 'reactions', ['user_id'], unique=False)
    op.create_index('ix_reactions_event_emoji', 'reactions', ['event_id', 'emoji'], unique=False)


def downgrade():
    op.drop_index('ix_reactions_event_emoji', table_name='reactions')
    op.drop_index('ix_reactions_user_id', table_name='reactions')
    op.drop_index('ix_reactions_event_id', table_name='reactions')
    op.drop_table('reactions')
