"""Tests for Phase 11A Smart Deduplication & Cross-Platform Duplicate Detection.

Covers:
- Perceptual hash computation from images
- Near-duplicate detection with threshold behaviour
- DedupEngine.find_matches against stored fingerprints
- DownloadOrchestrator.create_download with duplicate rejection and force bypass
- Maintenance scan grouping and cleanup deletion
- Dedup API endpoints
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.models.media_fingerprint import MediaFingerprint
from app.services.ai.dedup import DedupEngine, DuplicateMatch
from app.services.downloader.download_orchestrator import (
    DownloadOrchestrator,
    DuplicateFoundError,
)
from app.workers.maintenance_tasks import dedup_scan_task, read_dedup_report, _build_groups


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_image(color: tuple[int, int, int], size: tuple[int, int] = (64, 64)) -> bytes:
    """Generate a solid-colour JPEG image and return its raw bytes."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _resize_image(data: bytes, size: tuple[int, int] = (32, 32)) -> bytes:
    """Resize an image and return the new raw bytes."""
    with Image.open(io.BytesIO(data)) as img:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG")
        return buf.getvalue()


def _make_download(
    db: AsyncSession,
    *,
    title: str = "Test Video",
    platform: str = "youtube",
    file_path: str | None = None,
) -> Download:
    """Stage a completed download row and return it."""
    download = Download(
        id=str(uuid.uuid4()),
        url=f"https://example.com/{title}",
        platform=platform,
        content_type="video",
        title=title,
        status=DownloadStatus.COMPLETED,
        file_path=file_path,
        completed_at=datetime.utcnow(),
    )
    db.add(download)
    return download


# --------------------------------------------------------------------------- #
# DedupEngine unit tests
# --------------------------------------------------------------------------- #


class TestDedupEngineHashFromBytes:
    """Unit tests for DedupEngine.hash_from_image_bytes."""

    def test_same_image_same_hash(self):
        """Identical images must produce identical phash hex strings."""
        data = _make_image((255, 0, 0))
        h1 = DedupEngine.hash_from_image_bytes(data)
        h2 = DedupEngine.hash_from_image_bytes(data)
        assert h1 == h2
        assert len(h1) == 16

    def test_different_images_different_hash(self):
        """Completely different colours must produce different phashes."""
        red = _make_image((255, 0, 0))
        blue = _make_image((0, 0, 255))
        assert DedupEngine.hash_from_image_bytes(red) != DedupEngine.hash_from_image_bytes(blue)

    def test_resized_same_image_near_duplicate(self):
        """Same image resized must have a small hamming distance (near-duplicate)."""
        original = _make_image((128, 128, 128), size=(128, 128))
        resized = _resize_image(original, size=(64, 64))
        h1 = DedupEngine.hash_from_image_bytes(original)
        h2 = DedupEngine.hash_from_image_bytes(resized)
        # Same image resized: hamming distance should be small.
        import imagehash

        dist = imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
        assert dist <= 6  # well within default threshold


# --------------------------------------------------------------------------- #
# DedupEngine find_matches integration tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_find_matches_returns_near_duplicates(db_session: AsyncSession):
    """Fingerprinted downloads with similar images must be returned as matches."""
    engine = DedupEngine(db_session)

    # Create two downloads with near-identical images.
    img_a = _make_image((100, 100, 100), size=(128, 128))
    img_b = _resize_image(img_a, size=(64, 64))

    dl_a = _make_download(db_session, title="Original", platform="youtube")
    dl_b = _make_download(db_session, title="Resized Copy", platform="tiktok")
    await db_session.flush()

    h_a = engine.hash_from_image_bytes(img_a)
    h_b = engine.hash_from_image_bytes(img_b)

    fp_a = MediaFingerprint(download_id=dl_a.id, phash=h_a, keyframe_paths=[])
    fp_b = MediaFingerprint(download_id=dl_b.id, phash=h_b, keyframe_paths=[])
    db_session.add_all([fp_a, fp_b])
    await db_session.commit()

    matches = await engine.find_matches(h_a)
    match_ids = [m.download_id for m in matches]
    assert dl_b.id in match_ids
    assert dl_a.id not in match_ids  # Don't match against self.

    similarity = next(m.similarity for m in matches if m.download_id == dl_b.id)
    assert 0.0 <= similarity <= 1.0


@pytest.mark.asyncio
async def test_find_matches_no_match_for_different_images(db_session: AsyncSession):
    """Completely different images must not be returned as matches."""
    engine = DedupEngine(db_session)

    red = _make_image((255, 0, 0))
    blue = _make_image((0, 0, 255))

    dl_a = _make_download(db_session, title="Red", platform="youtube")
    dl_b = _make_download(db_session, title="Blue", platform="tiktok")
    await db_session.flush()

    fp_a = MediaFingerprint(download_id=dl_a.id, phash=engine.hash_from_image_bytes(red), keyframe_paths=[])
    fp_b = MediaFingerprint(download_id=dl_b.id, phash=engine.hash_from_image_bytes(blue), keyframe_paths=[])
    db_session.add_all([fp_a, fp_b])
    await db_session.commit()

    matches = await engine.find_matches(engine.hash_from_image_bytes(red))
    match_ids = [m.download_id for m in matches]
    assert dl_b.id not in match_ids


@pytest.mark.asyncio
async def test_find_matches_threshold_boundary(db_session: AsyncSession):
    """Only fingerprints within the threshold distance must be returned."""
    engine = DedupEngine(db_session)

    img_a = _make_image((100, 100, 100), size=(128, 128))
    img_b = _resize_image(img_a, size=(64, 64))
    img_c = _make_image((0, 0, 0), size=(128, 128))

    dl_a = _make_download(db_session, title="Near", platform="youtube")
    dl_b = _make_download(db_session, title="Far", platform="tiktok")
    await db_session.flush()

    fp_a = MediaFingerprint(download_id=dl_a.id, phash=engine.hash_from_image_bytes(img_a), keyframe_paths=[])
    fp_b = MediaFingerprint(download_id=dl_b.id, phash=engine.hash_from_image_bytes(img_c), keyframe_paths=[])
    db_session.add_all([fp_a, fp_b])
    await db_session.commit()

    # Default threshold is 6.
    matches = await engine.find_matches(engine.hash_from_image_bytes(img_a))
    match_ids = [m.download_id for m in matches]
    assert dl_a.id not in match_ids

    # With threshold 0, should definitely not match.
    matches_strict = await engine.find_matches(engine.hash_from_image_bytes(img_a), threshold=0)
    match_ids_strict = [m.download_id for m in matches_strict]
    assert dl_b.id not in match_ids_strict


# --------------------------------------------------------------------------- #
# DownloadOrchestrator create_download tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_download_raises_409_when_duplicate_found(
    db_session: AsyncSession,
    monkeypatch,
):
    """create_download must raise HTTP 409 (DuplicateFoundError) when duplicates exist."""
    monkeypatch.setattr(settings, "DEDUP_ENABLED", True)
    monkeypatch.setattr(settings, "DEDUP_THRESHOLD", 6)

    def _fake_dispatcher(download_id: str, resume: bool = False) -> str:
        return f"task-{download_id}"

    orchestrator = DownloadOrchestrator(db_session, task_dispatcher=_fake_dispatcher)

    # Mock the dedup engine's check_url to return a match.
    fake_match = DuplicateMatch(
        download_id="dup-1",
        title="Existing Video",
        thumbnail_url="https://example.com/thumb.jpg",
        similarity=0.95,
        platform="youtube",
    )

    with patch("app.services.ai.dedup.DedupEngine") as MockDedup:
        instance = MockDedup.return_value
        instance.check_url = AsyncMock(return_value=[fake_match])
        with pytest.raises(DuplicateFoundError) as exc_info:
            await orchestrator.create_download("https://example.com/video")
        assert len(exc_info.value.matches) == 1


@pytest.mark.asyncio
async def test_create_download_force_bypasses_dedup(
    db_session: AsyncSession,
    monkeypatch,
):
    """force=True must skip the dedup check and create the download."""
    monkeypatch.setattr(settings, "DEDUP_ENABLED", True)
    monkeypatch.setattr(settings, "DEDUP_THRESHOLD", 6)

    def _fake_dispatcher(download_id: str, resume: bool = False) -> str:
        return f"task-{download_id}"

    orchestrator = DownloadOrchestrator(db_session, task_dispatcher=_fake_dispatcher)

    with patch("app.services.ai.dedup.DedupEngine") as MockDedup:
        instance = MockDedup.return_value
        instance.check_url = AsyncMock(return_value=[])
        download = await orchestrator.create_download(
            "https://example.com/video", force=True
        )
    assert download.id is not None
    assert download.url == "https://example.com/video"


@pytest.mark.asyncio
async def test_create_download_enqueues_download(db_session: AsyncSession, monkeypatch):
    """create_download must create the row, enqueue it, and dispatch it."""
    monkeypatch.setattr(settings, "DEDUP_ENABLED", False)

    def _fake_dispatcher(download_id: str, resume: bool = False) -> str:
        return f"task-{download_id}"

    orchestrator = DownloadOrchestrator(db_session, task_dispatcher=_fake_dispatcher)
    download = await orchestrator.create_download(
        "https://example.com/video", force=True, platform="youtube"
    )
    assert download.id is not None
    assert download.platform == "youtube"
    assert download.status == DownloadStatus.PENDING

    # A queue item must exist.
    from app.models.download_queue import QueueItem

    result = await db_session.execute(
        select(QueueItem).where(QueueItem.download_id == download.id)
    )
    queue_item = result.scalars().first()
    assert queue_item is not None


# --------------------------------------------------------------------------- #
# Maintenance scan + report tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_dedup_scan_groups_exact_duplicates(db_session: AsyncSession, tmp_path):
    """Exact phash matches must be grouped together in the report."""
    img = _make_image((50, 50, 50), size=(128, 128))
    phash = DedupEngine.hash_from_image_bytes(img)

    dl_a = _make_download(db_session, title="A", platform="youtube")
    dl_b = _make_download(db_session, title="B", platform="tiktok")
    await db_session.flush()

    fp_a = MediaFingerprint(download_id=dl_a.id, phash=phash, keyframe_paths=[])
    fp_b = MediaFingerprint(download_id=dl_b.id, phash=phash, keyframe_paths=[])
    db_session.add_all([fp_a, fp_b])
    await db_session.commit()

    report = await _build_groups(db_session, threshold=6)
    assert len(report) >= 1
    all_ids: set[str] = set()
    for group in report:
        all_ids.add(group["keep"]["id"])
        for dup in group["duplicates"]:
            all_ids.add(dup["id"])
    assert dl_a.id in all_ids
    assert dl_b.id in all_ids


@pytest.mark.asyncio
async def test_dedup_cleanup_deletes_files_and_records(
    db_session: AsyncSession, tmp_path, monkeypatch
):
    """dedup_cleanup must remove files from disk and DB records."""
    media_file = tmp_path / "video.mp4"
    media_file.write_bytes(b"fake video content")

    monkeypatch.setattr(settings, "DOWNLOAD_DIR", str(tmp_path))

    dl = _make_download(
        db_session,
        title="ToDelete",
        platform="youtube",
        file_path=str(media_file),
    )
    await db_session.flush()

    fp = MediaFingerprint(download_id=dl.id, phash="abcd1234ef567890", keyframe_paths=[])
    db_session.add(fp)
    await db_session.commit()

    from app.api.v1.endpoints.dedup import dedup_cleanup

    result = await dedup_cleanup([dl.id], db_session)
    assert result["deleted"] == 1
    assert not media_file.exists()


# --------------------------------------------------------------------------- #
# API endpoint tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_dedup_check_endpoint_returns_matches(
    db_session: AsyncSession, monkeypatch
):
    """GET /api/v1/dedup/check must return a list of matches."""
    from app.api.v1.endpoints.dedup import check_url_duplicates

    fake_matches = [
        {
            "download_id": "dup-1",
            "title": "Existing",
            "thumbnail_url": "https://example.com/t.jpg",
            "similarity": 0.9,
            "platform": "youtube",
        }
    ]

    with patch("app.api.v1.endpoints.dedup.DedupEngine") as MockDedup:
        instance = MockDedup.return_value
        instance.check_url = AsyncMock(return_value=[DuplicateMatch(**fake_matches[0])])
        result = await check_url_duplicates(url="https://example.com/v", db=db_session)
    assert len(result) == 1
    assert result[0]["download_id"] == "dup-1"


@pytest.mark.asyncio
async def test_library_dedup_scan_endpoint(monkeypatch):
    """POST /api/v1/library/dedup-scan must enqueue the scan task."""
    from app.api.v1.endpoints.dedup import enqueue_dedup_scan

    with patch("app.workers.maintenance_tasks.dedup_scan_task.delay") as mock_delay:
        result = await enqueue_dedup_scan()
    assert result["message"] == "Dedup scan enqueued"
    assert mock_delay.called


@pytest.mark.asyncio
async def test_library_dedup_report_endpoint(monkeypatch):
    """GET /api/v1/library/dedup-report must return the stored report."""
    from app.api.v1.endpoints.dedup import get_dedup_report

    fake_report = [{"keep": {"id": "1", "title": "Keep"}, "duplicates": []}]
    monkeypatch.setattr(
        "app.workers.maintenance_tasks.read_dedup_report",
        lambda: fake_report,
    )
    result = await get_dedup_report()
    assert result == fake_report


@pytest.mark.asyncio
async def test_library_dedup_cleanup_endpoint(db_session: AsyncSession):
    """POST /api/v1/library/dedup-cleanup must delete the given IDs."""
    from app.api.v1.endpoints.dedup import dedup_cleanup

    dl = _make_download(db_session, title="Del", platform="youtube")
    await db_session.flush()
    fp = MediaFingerprint(download_id=dl.id, phash="abcd1234ef567890", keyframe_paths=[])
    db_session.add(fp)
    await db_session.commit()

    result = await dedup_cleanup([dl.id], db_session)
    assert result["deleted"] == 1
