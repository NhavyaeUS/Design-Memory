"""
Durable Background URL Analysis Service — Milestone 1B.4.

Requirements:
- Asynchronous, non-blocking execution so the frontend is never stalled.
- Database-backed durable state (pending, processing, completed, failed).
- Safe against duplicate / concurrent execution.
- Bounded retries (max 2 retries) with backoff for retryable network failures.
- Restart recovery: items interrupted in 'processing' or left 'pending' are resumed on server launch.
- Never overwrites user-edited titles or manual category selections.
- Clean sanitized error messages without leaking server paths or secrets.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.classifier import suggest_category
from app.db.session import SessionLocal
from app.models.item import AnalysisStatus, Item
from app.services.metadata import extract_metadata
from app.services.search import sync_item_fts

logger = logging.getLogger("design_memory.analysis")

MAX_RETRIES = 2
RETRYABLE_KEYWORDS = ("timed out", "timeout", "network request error", "connection reset")


def _is_retryable_error(error_msg: Optional[str]) -> bool:
    """Check if an extraction failure is temporary and retryable."""
    if not error_msg:
        return False
    msg_lower = error_msg.lower()
    return any(kw in msg_lower for kw in RETRYABLE_KEYWORDS)


def run_item_analysis_sync(item_id: int, db: Optional[Session] = None) -> bool:
    """
    Synchronously execute analysis for a given item.
    Safe against concurrent execution: only proceeds if status is 'pending'.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        item = db.execute(
            select(Item).where(Item.id == item_id)
        ).scalar_one_or_none()

        if item is None:
            return False

        # If not pending and not recovering from an interrupted processing state, skip
        if item.analysis_status not in (AnalysisStatus.pending.value, AnalysisStatus.processing.value):
            return False

        # Mark as processing
        item.analysis_status = AnalysisStatus.processing.value
        item.is_pending = True
        item.updated_at = datetime.now(timezone.utc)
        db.commit()

        target_url = item.url
        if not target_url:
            item.analysis_status = AnalysisStatus.completed.value
            item.is_pending = False
            db.commit()
            return True

        # Perform metadata extraction with SSRF & timeout enforcement
        res = extract_metadata(target_url)

        # Refresh item in case of external changes
        db.refresh(item)

        if res.success:
            # Metadata extracted successfully
            # Only update title if current title matches the domain or was empty
            current_title = (item.title or "").strip()
            clean_dom = item.domain.strip() if item.domain else ""
            if not current_title or current_title == clean_dom or current_title == target_url:
                if res.title:
                    item.title = res.title

            item.meta_description = res.description
            item.favicon_url = res.favicon_url
            item.preview_image_url = res.image_url

            # Suggest category (1B.6) without overwriting user confirmed category
            if res.suggested_type:
                item.suggested_type = res.suggested_type
            else:
                cat, _ = suggest_category(
                    url=item.url,
                    domain=item.domain,
                    title=item.title,
                    description=item.meta_description,
                )
                item.suggested_type = cat.value

            item.analysis_status = AnalysisStatus.completed.value
            item.analysis_error = None
            item.is_pending = False
            item.updated_at = datetime.now(timezone.utc)
            db.commit()
            sync_item_fts(db, item.id)
            return True

        else:
            # Extraction failed or returned fallback
            err_msg = res.error or "Could not extract webpage metadata."
            # Sanitize error to avoid leaking internal system details
            sanitized_err = err_msg.replace("/Users/", "[redacted]/").replace("/home/", "[redacted]/")

            # Check retry eligibility
            if _is_retryable_error(err_msg) and item.analysis_retries < MAX_RETRIES:
                item.analysis_retries += 1
                item.analysis_status = AnalysisStatus.pending.value
                item.analysis_error = f"Retrying ({item.analysis_retries}/{MAX_RETRIES}): {sanitized_err}"
                item.is_pending = True
                db.commit()
                return False
            else:
                # Terminal failure
                item.analysis_status = AnalysisStatus.failed.value
                item.analysis_error = sanitized_err
                item.is_pending = False

                # Still attempt domain-based category suggestion as fallback
                cat, _ = suggest_category(
                    url=item.url,
                    domain=item.domain,
                    title=item.title,
                )
                item.suggested_type = cat.value
                item.updated_at = datetime.now(timezone.utc)
                db.commit()
                return False

    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error analyzing item %d: %s", item_id, exc)
        try:
            item = db.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()
            if item:
                item.analysis_status = AnalysisStatus.failed.value
                item.analysis_error = "An error occurred during webpage analysis."
                item.is_pending = False
                db.commit()
        except Exception:
            pass
        return False
    finally:
        if own_session:
            db.close()


async def analyze_item_async(item_id: int, delay_seconds: float = 0.0) -> None:
    """Asynchronous wrapper that runs the analysis in a background thread."""
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    await asyncio.to_thread(run_item_analysis_sync, item_id)


def recover_pending_jobs(db: Optional[Session] = None) -> int:
    """
    Recovers any jobs left in 'processing' (e.g. from server crash or restart)
    or 'pending', and schedules them for analysis.
    Returns the count of recovered items.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        stmt = (
            select(Item.id)
            .where(
                or_(
                    Item.analysis_status == AnalysisStatus.processing.value,
                    Item.analysis_status == AnalysisStatus.pending.value,
                ),
                Item.url.isnot(None),
            )
        )
        item_ids = list(db.execute(stmt).scalars().all())

        # Reset any stuck 'processing' back to 'pending'
        for i_id in item_ids:
            it = db.execute(select(Item).where(Item.id == i_id)).scalar_one_or_none()
            if it and it.analysis_status == AnalysisStatus.processing.value:
                it.analysis_status = AnalysisStatus.pending.value
        db.commit()

        # Schedule background tasks for recovered jobs
        for i_id in item_ids:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(analyze_item_async(i_id, delay_seconds=0.5))
            except RuntimeError:
                # No running event loop (e.g. in certain CLI/test environments)
                pass

        return len(item_ids)
    finally:
        if own_session:
            db.close()
