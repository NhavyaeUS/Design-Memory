"""
SQLite FTS5 Full-Text Search Service — Milestone 1B.5.

Provides:
- Schema initialization and synchronization for items_fts virtual table.
- Safe query sanitization preventing FTS5 syntax errors or SQL injection.
- Prefix matching on title, domain, notes, reason_for_saving, tags, and meta_description.
- Resilient fallback if FTS5 is not available or query fails.
"""
import re
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

_CLEAN_WORDS_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def init_fts5(db: Session) -> bool:
    """
    Ensure the items_fts virtual table exists in the current database.
    Safe to call repeatedly across sessions or test database setups.
    """
    try:
        db.execute(text("""
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
        """))
        return True
    except Exception:
        return False


def build_safe_fts5_query(user_query: str) -> Optional[str]:
    """
    Sanitize and construct a safe FTS5 query string from arbitrary user input.
    Prevents syntax errors from unbalanced quotes, colons, wildcards, or operators.
    Each word is wrapped as a prefix token: '"word"*'
    """
    if not user_query or not isinstance(user_query, str):
        return None

    # Strip FTS5 operators and punctuation
    cleaned = _CLEAN_WORDS_RE.sub(" ", user_query)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    if not words:
        return None

    # Filter out bare boolean words if solitary
    safe_tokens = []
    for w in words:
        # Quote individual token and add prefix wildcard
        clean_word = w.replace('"', '""')
        safe_tokens.append(f'"{clean_word}"*')

    return " ".join(safe_tokens) if safe_tokens else None


def sync_item_fts(db: Session, item_id: int) -> None:
    """Synchronize an item and its tags into the items_fts virtual table."""
    try:
        # Delete existing entry if present
        db.execute(
            text("DELETE FROM items_fts WHERE item_id = :item_id"),
            {"item_id": item_id},
        )

        # Re-insert fresh row with aggregated tags
        db.execute(
            text("""
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
                FROM items i
                WHERE i.id = :item_id;
            """),
            {"item_id": item_id},
        )
        db.flush()
    except Exception:
        pass


def remove_item_fts(db: Session, item_id: int) -> None:
    """Remove an item from the items_fts virtual table upon deletion."""
    try:
        db.execute(
            text("DELETE FROM items_fts WHERE item_id = :item_id"),
            {"item_id": item_id},
        )
        db.flush()
    except Exception:
        pass


def search_fts5(db: Session, query: str) -> Optional[List[int]]:
    """
    Execute full-text search using FTS5.
    Returns a list of matching item IDs, or None if query is empty or FTS5 is not available.
    """
    safe_q = build_safe_fts5_query(query)
    if not safe_q:
        return None

    try:
        init_fts5(db)
        stmt = text("SELECT item_id FROM items_fts WHERE items_fts MATCH :match_q ORDER BY rank")
        rows = db.execute(stmt, {"match_q": safe_q}).fetchall()
        return [int(r[0]) for r in rows]
    except Exception:
        db.rollback()
        return None
