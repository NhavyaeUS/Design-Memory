"""add_fts5_virtual_table

Revision ID: a0b906867b16
Revises: 700a9ec74e4c
Create Date: 2026-11-02 20:05:24.650404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0b906867b16'
down_revision: Union[str, Sequence[str], None] = '700a9ec74e4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create and populate FTS5 virtual table."""
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            item_id UNINDEXED,
            title,
            domain,
            notes,
            reason_for_saving,
            tags,
            meta_description,
            tokenize = 'unicode61 remove_diacritics 2'
        );
    """)

    # Populate with existing items and their tags
    op.execute("""
        INSERT INTO items_fts(item_id, title, domain, notes, reason_for_saving, tags, meta_description)
        SELECT
            i.id,
            COALESCE(i.title, ''),
            COALESCE(i.domain, ''),
            COALESCE(i.notes, ''),
            COALESCE(i.reason_for_saving, ''),
            COALESCE((
                SELECT GROUP_CONCAT(t.name, ' ')
                FROM item_tag it
                JOIN tags t ON it.tag_id = t.id
                WHERE it.item_id = i.id
            ), ''),
            COALESCE(i.meta_description, '')
        FROM items i;
    """)


def downgrade() -> None:
    """Downgrade schema: drop FTS5 table."""
    op.execute("DROP TABLE IF EXISTS items_fts;")
