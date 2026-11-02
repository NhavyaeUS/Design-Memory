"""add_analysis_status_and_metadata_columns

Revision ID: 700a9ec74e4c
Revises: 70d84b2fa6db
Create Date: 2026-11-02 19:49:46.814737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '700a9ec74e4c'
down_revision: Union[str, Sequence[str], None] = '70d84b2fa6db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'items',
        sa.Column('analysis_status', sa.String(length=30), nullable=False, server_default='completed')
    )
    op.create_index('ix_items_analysis_status', 'items', ['analysis_status'])
    op.add_column('items', sa.Column('analysis_error', sa.String(length=500), nullable=True))
    op.add_column('items', sa.Column('analysis_retries', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('items', sa.Column('suggested_type', sa.String(length=50), nullable=True))
    op.add_column('items', sa.Column('meta_description', sa.Text(), nullable=True))
    op.add_column('items', sa.Column('favicon_url', sa.String(length=2048), nullable=True))
    op.add_column('items', sa.Column('preview_image_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_items_analysis_status', table_name='items')
    with op.batch_alter_table('items') as batch_op:
        batch_op.drop_column('preview_image_url')
        batch_op.drop_column('favicon_url')
        batch_op.drop_column('meta_description')
        batch_op.drop_column('suggested_type')
        batch_op.drop_column('analysis_retries')
        batch_op.drop_column('analysis_error')
        batch_op.drop_column('analysis_status')
