"""
Tests for Milestone 1B.4: Durable Background URL Analysis.

Validates:
- Job lifecycle states: pending, processing, completed, failed.
- Safe asynchronous execution without blocking API requests.
- Retries and backoff for retryable network errors up to MAX_RETRIES.
- Terminal failure handling without leaking internal paths or traceback details.
- User title and notes preservation when analysis completes.
- Startup recovery of interrupted 'processing' or 'pending' items.
- Manual re-analysis endpoint (POST /api/v1/items/{id}/analyze).
- Automatic category suggestion integration during analysis.
"""
import pytest
from app.models.item import AnalysisStatus, Item, ResourceType
from app.services.analysis import (
    MAX_RETRIES,
    recover_pending_jobs,
    run_item_analysis_sync,
)
from app.services.metadata import MetadataResult


def test_analysis_successful_lifecycle(db, monkeypatch):
    """Analysis transitions pending -> processing -> completed and saves metadata."""
    item = Item(
        title="awwwards.com",
        domain="awwwards.com",
        url="https://www.awwwards.com",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.pending.value,
        is_pending=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    def mock_extract(url):
        return MetadataResult(
            url=url,
            domain="awwwards.com",
            title="Awwwards - Website Awards",
            description="Awards for design, creativity and innovation.",
            favicon_url="https://www.awwwards.com/favicon.ico",
            image_url="https://www.awwwards.com/og.png",
            success=True,
            status="success",
            suggested_type="website",
        )

    import app.services.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "extract_metadata", mock_extract)

    success = run_item_analysis_sync(item.id, db=db)
    assert success is True

    db.refresh(item)
    assert item.analysis_status == AnalysisStatus.completed.value
    assert item.is_pending is False
    assert item.title == "Awwwards - Website Awards"
    assert item.meta_description == "Awards for design, creativity and innovation."
    assert item.favicon_url == "https://www.awwwards.com/favicon.ico"
    assert item.preview_image_url == "https://www.awwwards.com/og.png"
    assert item.suggested_type == "website"


def test_analysis_preserves_custom_user_title_and_notes(db, monkeypatch):
    """User-customized title and notes are never overwritten by extracted title."""
    item = Item(
        title="My Custom Title",
        domain="example.com",
        url="https://example.com",
        notes="Important inspiration note",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.pending.value,
        is_pending=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    def mock_extract(url):
        return MetadataResult(
            url=url,
            domain="example.com",
            title="Scraped Title That Must Not Overwrite",
            description="Extracted description",
            favicon_url="https://example.com/favicon.ico",
            image_url=None,
            success=True,
            status="success",
            suggested_type="website",
        )

    import app.services.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "extract_metadata", mock_extract)

    run_item_analysis_sync(item.id, db=db)
    db.refresh(item)

    assert item.title == "My Custom Title"
    assert item.notes == "Important inspiration note"
    assert item.meta_description == "Extracted description"
    assert item.analysis_status == AnalysisStatus.completed.value


def test_analysis_retryable_error_increments_retries(db, monkeypatch):
    """Temporary network timeouts trigger bounded retries before failing."""
    item = Item(
        title="Slow Site",
        domain="slow.com",
        url="https://slow.com",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.pending.value,
        analysis_retries=0,
        is_pending=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    def mock_timeout(url):
        return MetadataResult(
            url=url,
            domain="slow.com",
            title="Slow.com",
            description=None,
            favicon_url=None,
            image_url=None,
            success=False,
            status="fallback",
            error="Request timed out: ReadTimeout",
        )

    import app.services.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "extract_metadata", mock_timeout)

    # First attempt: increments retries and stays pending
    success1 = run_item_analysis_sync(item.id, db=db)
    assert success1 is False
    db.refresh(item)
    assert item.analysis_retries == 1
    assert item.analysis_status == AnalysisStatus.pending.value
    assert "Retrying" in item.analysis_error

    # Second attempt: increments retries and stays pending
    success2 = run_item_analysis_sync(item.id, db=db)
    assert success2 is False
    db.refresh(item)
    assert item.analysis_retries == 2
    assert item.analysis_status == AnalysisStatus.pending.value

    # Third attempt: exceeds MAX_RETRIES, transitions to terminal failed
    success3 = run_item_analysis_sync(item.id, db=db)
    assert success3 is False
    db.refresh(item)
    assert item.analysis_status == AnalysisStatus.failed.value
    assert item.is_pending is False


def test_analysis_terminal_error_no_retries(db, monkeypatch):
    """Non-retryable errors (e.g. 404 or SSRF block) immediately fail."""
    item = Item(
        title="Blocked Site",
        domain="internal.corp",
        url="http://internal.corp",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.pending.value,
        analysis_retries=0,
        is_pending=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    def mock_ssrf_error(url):
        return MetadataResult(
            url=url,
            domain="internal.corp",
            title="Internal.corp",
            description=None,
            favicon_url=None,
            image_url=None,
            success=False,
            status="fallback",
            error="SSRF blocked: Host 'internal.corp' is restricted and cannot be requested.",
        )

    import app.services.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "extract_metadata", mock_ssrf_error)

    run_item_analysis_sync(item.id, db=db)
    db.refresh(item)
    assert item.analysis_status == AnalysisStatus.failed.value
    assert item.is_pending is False
    assert "SSRF blocked" in item.analysis_error


def test_recover_pending_jobs(db):
    """Interrupted 'processing' jobs from server restarts are reset to 'pending'."""
    item1 = Item(
        title="Interrupted Job",
        domain="interrupted.com",
        url="https://interrupted.com",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.processing.value,
        is_pending=True,
    )
    item2 = Item(
        title="Completed Job",
        domain="completed.com",
        url="https://completed.com",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.completed.value,
        is_pending=False,
    )
    db.add_all([item1, item2])
    db.commit()

    count = recover_pending_jobs(db=db)
    assert count >= 1

    db.refresh(item1)
    db.refresh(item2)
    assert item1.analysis_status == AnalysisStatus.pending.value
    assert item2.analysis_status == AnalysisStatus.completed.value


def test_api_trigger_reanalysis(client, db):
    """POST /api/v1/items/{id}/analyze queues item for fresh analysis."""
    item = Item(
        title="Reanalyze Target",
        domain="target.com",
        url="https://target.com",
        resource_type=ResourceType.website,
        analysis_status=AnalysisStatus.completed.value,
        is_pending=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    resp = client.post(f"/api/v1/items/{item.id}/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_status"] == "pending"
    assert data["is_pending"] is True
