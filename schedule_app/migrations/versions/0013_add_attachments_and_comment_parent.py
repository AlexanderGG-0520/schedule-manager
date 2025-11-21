"""Add attachments table and comment parent reference

Revision ID: 0013
Revises: 0012
Create Date: 2025-01-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=True),
        sa.Column('storage_path', sa.String(length=1024), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_event_id'), 'attachments', ['event_id'], unique=False)
    op.create_index(op.f('ix_attachments_uploaded_by'), 'attachments', ['uploaded_by'], unique=False)

    op.add_column('event_comments', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_event_comments_parent_id',
        'event_comments',
        'event_comments',
        ['parent_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    op.drop_constraint('fk_event_comments_parent_id', 'event_comments', type_='foreignkey')
    op.drop_column('event_comments', 'parent_id')

    op.drop_index(op.f('ix_attachments_uploaded_by'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_event_id'), table_name='attachments')
    op.drop_table('attachments')
