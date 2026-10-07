"""Tests for Phase 15A Analytics Dashboard & Data Export."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.download import Download, DownloadStatus
from app.schemas.analytics import ExportFilters
from app.services.analytics.analytics_service import AnalyticsService
from app.services.analytics.export_service import ExportService


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_download(
    db: AsyncSession,
    *,
    title: str = "Sample Video",
    platform: str = "youtube",
    status: DownloadStatus = DownloadStatus.COMPLETED,
    file_path: str | None = None,
    file_size: int | None = None,
    completed_at: datetime | None = None,
    metadata: dict | None = None,
    content_type: str = "video",
    category: str | None = None,
    quality: str | None = None,
) -> Download:
    """Stage a download row with a pre-assigned ID and return it."""
    download = Download(
        id=str(__import__("uuid").uuid4()),
        url=f"https://example.com/{title}",
        platform=platform,
        content_type=content_type,
        title=title,
        status=status,
        progress=100.0 if status == DownloadStatus.COMPLETED else 0.0,
        file_path=file_path,
        file_size=file_size,
        is_watermark_free=True,
        completed_at=completed_at if completed_at is not None else datetime.utcnow(),
        metadata_json=metadata,
        category=category,
        quality=quality,
    )
    db.add(download)
    return download


# --------------------------------------------------------------------------- #
# AnalyticsService tests
# --------------------------------------------------------------------------- #

class TestAnalyticsServiceOverview:
    """Unit tests for AnalyticsService.get_overview."""

    @pytest.mark.asyncio
    async def test_empty_db_returns_zeroes(self, db_session: AsyncSession):
        """An empty database should produce zeroed overview stats."""
        service = AnalyticsService(db_session)
        result = await service.get_overview()

        assert result.total_downloads == 0
        assert result.total_storage_bytes == 0
        assert result.success_rate == 0.0
        assert result.platform_breakdown == []
        assert result.quality_breakdown == []

    @pytest.mark.asyncio
    async def test_overview_counts_and_storage(self, db_session: AsyncSession):
        """Total downloads and storage should match seeded data."""
        make_download(db_session, title="A", platform="youtube", file_size=1000, metadata={"uploader_name": "Alice"})
        make_download(db_session, title="B", platform="tiktok", file_size=2000, metadata={"uploader_name": "Bob"})
        make_download(db_session, title="C", platform="youtube", file_size=3000, status=DownloadStatus.FAILED)
        await db_session.commit()

        service = AnalyticsService(db_session)
        result = await service.get_overview()

        assert result.total_downloads == 3
        assert result.total_storage_bytes == 6000
        # 2 completed / (2 completed + 1 failed) = 66.67%
        assert abs(result.success_rate - (2 / 3 * 100)) < 0.01

    @pytest.mark.asyncio
    async def test_platform_breakdown(self, db_session: AsyncSession):
        """Platform breakdown should aggregate counts and sizes per platform."""
        make_download(db_session, title="A", platform="youtube", file_size=1000)
        make_download(db_session, title="B", platform="youtube", file_size=2000)
        make_download(db_session, title="C", platform="tiktok", file_size=5000)
        await db_session.commit()

        service = AnalyticsService(db_session)
        result = await service.get_overview()

        platforms = {pb.platform: pb for pb in result.platform_breakdown}
        assert "youtube" in platforms
        assert platforms["youtube"].count == 2
        assert platforms["youtube"].total_size == 3000
        assert "tiktok" in platforms
        assert platforms["tiktok"].count == 1
        assert platforms["tiktok"].total_size == 5000

    @pytest.mark.asyncio
    async def test_quality_breakdown(self, db_session: AsyncSession):
        """Quality breakdown should group by quality label."""
        make_download(db_session, title="A", quality="1080p")
        make_download(db_session, title="B", quality="1080p")
        make_download(db_session, title="C", quality="720p")
        await db_session.commit()

        service = AnalyticsService(db_session)
        result = await service.get_overview()

        qualities = {qb.quality: qb for qb in result.quality_breakdown}
        assert qualities["1080p"].count == 2
        assert qualities["720p"].count == 1


class TestAnalyticsServiceTimeline:
    """Unit tests for AnalyticsService.get_timeline."""

    @pytest.mark.asyncio
    async def test_timeline_fills_missing_dates(self, db_session: AsyncSession):
        """Missing days in the range must be filled with zero entries."""
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        make_download(
            db_session,
            title="Yesterday",
            file_size=1000,
            completed_at=datetime.combine(yesterday, datetime.min.time()),
        )
        make_download(
            db_session,
            title="TwoDaysAgo",
            file_size=2000,
            completed_at=datetime.combine(two_days_ago, datetime.min.time()),
        )
        await db_session.commit()

        service = AnalyticsService(db_session)
        timeline = await service.get_timeline(days=3)

        assert len(timeline) == 3
        dates = {entry.date: entry for entry in timeline}
        assert two_days_ago.isoformat() in dates
        assert yesterday.isoformat() in dates
        assert today.isoformat() in dates
        assert dates[two_days_ago.isoformat()].count == 1
        assert dates[two_days_ago.isoformat()].total_size == 2000
        assert dates[today.isoformat()].count == 0
        assert dates[today.isoformat()].total_size == 0

    @pytest.mark.asyncio
    async def test_timeline_empty_db(self, db_session: AsyncSession):
        """An empty DB should return a full timeline of zero entries."""
        service = AnalyticsService(db_session)
        timeline = await service.get_timeline(days=7)

        assert len(timeline) == 7
        for entry in timeline:
            assert entry.count == 0
            assert entry.total_size == 0


class TestAnalyticsServiceTopCreators:
    """Unit tests for AnalyticsService.get_top_creators."""

    @pytest.mark.asyncio
    async def test_top_creators_sorted_by_count(self, db_session: AsyncSession):
        """Creators should be returned sorted by download count descending."""
        make_download(db_session, title="A1", metadata={"uploader_name": "Alice"}, file_size=1000)
        make_download(db_session, title="A2", metadata={"uploader_name": "Alice"}, file_size=2000)
        make_download(db_session, title="B1", metadata={"uploader_name": "Bob"}, file_size=3000)
        make_download(db_session, title="C1", metadata={"uploader_name": "Charlie"}, file_size=4000)
        await db_session.commit()

        service = AnalyticsService(db_session)
        creators = await service.get_top_creators(limit=10)

        assert len(creators) == 3
        assert creators[0].username == "Alice"
        assert creators[0].count == 2
        assert creators[0].total_size == 3000
        assert creators[1].username == "Bob"
        assert creators[1].count == 1

    @pytest.mark.asyncio
    async def test_top_creators_respects_limit(self, db_session: AsyncSession):
        """The limit parameter should cap the number of returned creators."""
        for i in range(5):
            make_download(db_session, title=f"V{i}", metadata={"uploader_name": f"Creator{i}"}, file_size=100)
        await db_session.commit()

        service = AnalyticsService(db_session)
        creators = await service.get_top_creators(limit=3)

        assert len(creators) == 3

    @pytest.mark.asyncio
    async def test_creator_metadata_fallback_keys(self, db_session: AsyncSession):
        """The service should check multiple metadata keys for the creator name."""
        make_download(db_session, title="A", metadata={"creator": "Cathy"})
        make_download(db_session, title="B", metadata={"channel": "ChannelDude"})
        make_download(db_session, title="C", metadata={"author": "AuthorEve"})
        await db_session.commit()

        service = AnalyticsService(db_session)
        creators = await service.get_top_creators(limit=10)

        usernames = {c.username for c in creators}
        assert "Cathy" in usernames
        assert "ChannelDude" in usernames
        assert "AuthorEve" in usernames


class TestAnalyticsServiceStorageHeatmap:
    """Unit tests for AnalyticsService.get_storage_heatmap."""

    @pytest.mark.asyncio
    async def test_storage_grouped_by_category(self, db_session: AsyncSession):
        """Storage should be aggregated by category."""
        make_download(db_session, title="A", category="Gaming", file_size=1000)
        make_download(db_session, title="B", category="Gaming", file_size=2000)
        make_download(db_session, title="C", category="Music", file_size=500)
        make_download(db_session, title="D", category=None, file_size=100)
        await db_session.commit()

        service = AnalyticsService(db_session)
        heatmap = await service.get_storage_heatmap()

        categories = {cs.category: cs for cs in heatmap}
        assert "Gaming" in categories
        assert categories["Gaming"].total_size == 3000
        assert categories["Gaming"].file_count == 2
        assert "Music" in categories
        assert categories["Music"].total_size == 500

    @pytest.mark.asyncio
    async def test_empty_storage_heatmap(self, db_session: AsyncSession):
        """An empty database should return an empty list."""
        service = AnalyticsService(db_session)
        result = await service.get_storage_heatmap()
        assert result == []


# --------------------------------------------------------------------------- #
# ExportService tests
# --------------------------------------------------------------------------- #

class TestExportServiceCsv:
    """Unit tests for ExportService.export_csv."""

    @pytest.mark.asyncio
    async def test_export_csv_returns_valid_csv(self, db_session: AsyncSession):
        """CSV export should return parseable bytes with the expected header."""
        make_download(
            db_session,
            title="My Video",
            platform="youtube",
            file_size=1234,
            category="Gaming",
            metadata={"uploader_name": "UploaderX"},
            completed_at=datetime(2024, 1, 15, 12, 0, 0),
        )
        await db_session.commit()

        service = ExportService(db_session)
        csv_bytes = await service.export_csv()

        assert isinstance(csv_bytes, bytes)
        decoded = csv_bytes.decode("utf-8")
        assert "Date" in decoded
        assert "Title" in decoded
        assert "Platform" in decoded
        assert "Uploader" in decoded
        assert "My Video" in decoded
        assert "UploaderX" in decoded

    @pytest.mark.asyncio
    async def test_export_csv_with_filters(self, db_session: AsyncSession):
        """Filters should restrict the exported rows."""
        make_download(db_session, title="YT Vid", platform="youtube", file_size=1000, completed_at=datetime(2024, 6, 1))
        make_download(db_session, title="TT Vid", platform="tiktok", file_size=2000, completed_at=datetime(2024, 6, 2))
        await db_session.commit()

        service = ExportService(db_session)
        filters = ExportFilters(platform="youtube")
        csv_bytes = await service.export_csv(filters=filters)
        decoded = csv_bytes.decode("utf-8")

        assert "YT Vid" in decoded
        assert "TT Vid" not in decoded

    @pytest.mark.asyncio
    async def test_export_csv_no_results(self, db_session: AsyncSession):
        """An empty result set should still produce a valid CSV with header only."""
        service = ExportService(db_session)
        csv_bytes = await service.export_csv()
        decoded = csv_bytes.decode("utf-8")
        lines = decoded.strip().splitlines()
        assert len(lines) == 1
        assert "Date" in lines[0]


class TestExportServicePdf:
    """Unit tests for ExportService.export_pdf."""

    @pytest.mark.asyncio
    async def test_export_pdf_overview_returns_pdf_bytes(self, db_session: AsyncSession):
        """PDF overview export should return valid PDF bytes."""
        make_download(db_session, title="A", platform="youtube", file_size=1000)
        await db_session.commit()

        service = ExportService(db_session)
        pdf_bytes = await service.export_pdf(report_type="overview")

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_export_pdf_full_includes_extras(self, db_session: AsyncSession):
        """Full PDF should include creator and category tables (longer output)."""
        make_download(db_session, title="A", platform="youtube", file_size=1000, category="Gaming", metadata={"uploader_name": "Alice"})
        await db_session.commit()

        service = ExportService(db_session)
        overview_pdf = await service.export_pdf(report_type="overview")
        full_pdf = await service.export_pdf(report_type="full")

        assert len(full_pdf) > len(overview_pdf)


# --------------------------------------------------------------------------- #
# API endpoint tests
# --------------------------------------------------------------------------- #

class TestAnalyticsEndpoints:
    """Integration tests for /api/v1/analytics endpoints."""

    @pytest.mark.asyncio
    async def test_overview_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """GET /api/v1/analytics/overview should return OverviewStats."""
        make_download(db_session, title="V", platform="youtube", file_size=500)
        await db_session.commit()

        resp = await async_client.get("/api/v1/analytics/overview")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["total_downloads"] == 1
        assert data["total_storage_bytes"] == 500

    @pytest.mark.asyncio
    async def test_timeline_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """GET /api/v1/analytics/timeline should return a list of timeline entries."""
        today = datetime.utcnow().date()
        make_download(
            db_session,
            title="Today",
            completed_at=datetime.combine(today, datetime.min.time()),
            file_size=1000,
        )
        await db_session.commit()

        resp = await async_client.get("/api/v1/analytics/timeline?days=7")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 7
        assert data[-1]["count"] == 1

    @pytest.mark.asyncio
    async def test_creators_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """GET /api/v1/analytics/creators should return ranked creators."""
        make_download(db_session, title="A", metadata={"uploader_name": "Alice"})
        make_download(db_session, title="B", metadata={"uploader_name": "Alice"})
        make_download(db_session, title="C", metadata={"uploader_name": "Bob"})
        await db_session.commit()

        resp = await async_client.get("/api/v1/analytics/creators?limit=10")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data[0]["username"] == "Alice"
        assert data[0]["count"] == 2

    @pytest.mark.asyncio
    async def test_storage_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """GET /api/v1/analytics/storage should return category aggregates."""
        make_download(db_session, title="A", category="Gaming", file_size=1000)
        make_download(db_session, title="B", category="Gaming", file_size=2000)
        await db_session.commit()

        resp = await async_client.get("/api/v1/analytics/storage")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert any(cs["category"] == "Gaming" and cs["total_size"] == 3000 for cs in data)

    @pytest.mark.asyncio
    async def test_export_csv_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """POST /api/v1/analytics/export/csv should return a CSV file response."""
        make_download(db_session, title="Vid", platform="youtube", file_size=500)
        await db_session.commit()

        resp = await async_client.post("/api/v1/analytics/export/csv", json={})
        assert resp.status_code == status.HTTP_200_OK
        assert "text/csv" in resp.headers["content-type"]
        assert b"Vid" in resp.content
        assert b"youtube" in resp.content

    @pytest.mark.asyncio
    async def test_export_pdf_endpoint(self, async_client: AsyncClient, db_session: AsyncSession):
        """POST /api/v1/analytics/export/pdf should return a PDF file response."""
        make_download(db_session, title="Vid", platform="youtube", file_size=500)
        await db_session.commit()

        resp = await async_client.post("/api/v1/analytics/export/pdf", json={"report_type": "overview"})
        assert resp.status_code == status.HTTP_200_OK
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_export_pdf_invalid_report_type(self, async_client: AsyncClient):
        """POST /api/v1/analytics/export/pdf with invalid report_type should 400."""
        resp = await async_client.post("/api/v1/analytics/export/pdf", json={"report_type": "invalid"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
