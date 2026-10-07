"""Analytics aggregation service for Phase 15A."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.download import Download, DownloadStatus
from app.schemas.analytics import (
    CategoryStorage,
    CreatorStat,
    OverviewStats,
    PlatformBreakdown,
    QualityBreakdown,
    TimelineEntry,
)

logger = logging.getLogger(__name__)

__all__ = ["AnalyticsService"]


class AnalyticsService:
    """Aggregate download statistics for the analytics dashboard.

    All methods are read-only and run inside the caller's transaction scope.
    """

    def __init__(
        self,
        db: AsyncSession,
        visible_user_ids: Optional[List[str]] = None,
    ) -> None:
        self.db = db
        self.visible_user_ids = visible_user_ids

    def _scoped(self, query):
        """Apply visible_user_ids scoping to a query if provided."""
        if self.visible_user_ids is None:
            return query
        return query.where(Download.owner_id.in_(self.visible_user_ids))

    # ------------------------------------------------------------------ #
    # Overview
    # ------------------------------------------------------------------ #
    async def get_overview(self) -> OverviewStats:
        """Return high-level library metrics."""
        completed_filters = [Download.status == DownloadStatus.COMPLETED]
        failed_filters = [Download.status == DownloadStatus.FAILED]

        total_downloads = await self.db.scalar(
            self._scoped(select(func.count(Download.id)))
        )
        total_downloads = int(total_downloads or 0)

        total_storage = await self.db.scalar(
            self._scoped(select(func.coalesce(func.sum(Download.file_size), 0)))
        )
        total_storage = int(total_storage or 0)

        completed_count = await self.db.scalar(
            self._scoped(select(func.count(Download.id)).where(*completed_filters))
        )
        completed_count = int(completed_count or 0)

        failed_count = await self.db.scalar(
            self._scoped(select(func.count(Download.id)).where(*failed_filters))
        )
        failed_count = int(failed_count or 0)

        success_rate = 0.0
        denominator = completed_count + failed_count
        if denominator > 0:
            success_rate = round((completed_count / denominator) * 100, 2)

        platform_rows = await self.db.execute(
            self._scoped(
                select(Download.platform, func.count(Download.id), func.coalesce(func.sum(Download.file_size), 0))
                .where(Download.status == DownloadStatus.COMPLETED)
                .group_by(Download.platform)
            )
        )
        platform_breakdown = [
            PlatformBreakdown(platform=row[0], count=int(row[1]), total_size=int(row[2]))
            for row in platform_rows.all()
        ]

        quality_rows = await self.db.execute(
            self._scoped(
                select(Download.quality, func.count(Download.id))
                .where(Download.status == DownloadStatus.COMPLETED)
                .where(Download.quality.is_not(None))
                .group_by(Download.quality)
            )
        )
        quality_breakdown = [
            QualityBreakdown(quality=row[0] or "unknown", count=int(row[1]))
            for row in quality_rows.all()
        ]

        return OverviewStats(
            total_downloads=total_downloads,
            total_storage_bytes=total_storage,
            success_rate=success_rate,
            platform_breakdown=platform_breakdown,
            quality_breakdown=quality_breakdown,
        )

    # ------------------------------------------------------------------ #
    # Timeline
    # ------------------------------------------------------------------ #
    async def get_timeline(self, days: int = 30) -> List[TimelineEntry]:
        """Return daily download counts for the last N days, filling gaps with zero."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        rows = await self.db.execute(
            self._scoped(
                select(
                    func.date(Download.completed_at).label("day"),
                    func.count(Download.id),
                    func.coalesce(func.sum(Download.file_size), 0),
                )
                .where(Download.status == DownloadStatus.COMPLETED)
                .where(Download.completed_at >= start_dt)
                .where(Download.completed_at <= end_dt)
                .group_by(func.date(Download.completed_at))
            )
        )
        data: Dict[str, TimelineEntry] = {}
        for row in rows.all():
            day_str = str(row[0])
            data[day_str] = TimelineEntry(
                date=day_str,
                count=int(row[1]),
                total_size=int(row[2]),
            )

        timeline: List[TimelineEntry] = []
        current = start_date
        while current <= end_date:
            day_str = current.isoformat()
            if day_str in data:
                timeline.append(data[day_str])
            else:
                timeline.append(TimelineEntry(date=day_str, count=0, total_size=0))
            current += timedelta(days=1)

        return timeline

    # ------------------------------------------------------------------ #
    # Top creators
    # ------------------------------------------------------------------ #
    async def get_top_creators(self, limit: int = 10) -> List[CreatorStat]:
        """Return the most-downloaded creators grouped by uploader metadata."""
        _CREATOR_KEYS = ("uploader_name", "uploader", "username", "creator", "channel", "author")

        result = await self.db.execute(
            self._scoped(
                select(Download.metadata_json, Download.platform, Download.file_size)
                .where(Download.status == DownloadStatus.COMPLETED)
            )
        )
        rows = result.all()

        creator_counter: Counter = Counter()
        creator_platform: Dict[str, str] = {}
        creator_size: Dict[str, int] = defaultdict(int)

        for metadata, platform, file_size in rows:
            name = "Unknown"
            if isinstance(metadata, dict):
                for key in _CREATOR_KEYS:
                    value = metadata.get(key)
                    if isinstance(value, str) and value.strip():
                        name = value.strip()
                        break
            creator_counter[name] += 1
            creator_platform.setdefault(name, platform or "unknown")
            creator_size[name] += int(file_size or 0)

        top = creator_counter.most_common(limit)
        return [
            CreatorStat(
                username=name,
                platform=creator_platform.get(name, "unknown"),
                count=count,
                total_size=creator_size.get(name, 0),
            )
            for name, count in top
        ]

    # ------------------------------------------------------------------ #
    # Storage heatmap
    # ------------------------------------------------------------------ #
    async def get_storage_heatmap(self) -> List[CategoryStorage]:
        """Return storage usage grouped by category."""
        rows = await self.db.execute(
            self._scoped(
                select(Download.category, func.count(Download.id), func.coalesce(func.sum(Download.file_size), 0))
                .where(Download.status == DownloadStatus.COMPLETED)
                .where(Download.category.is_not(None))
                .group_by(Download.category)
                .order_by(func.sum(Download.file_size).desc())
            )
        )
        return [
            CategoryStorage(
                category=row[0] or "Other",
                total_size=int(row[2]),
                file_count=int(row[1]),
            )
            for row in rows.all()
        ]
