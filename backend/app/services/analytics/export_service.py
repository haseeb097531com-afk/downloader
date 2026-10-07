"""Data export service for Phase 15A."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.download import Download, DownloadStatus
from app.schemas.analytics import ExportFilters

logger = logging.getLogger(__name__)

__all__ = ["ExportService"]


class ExportService:
    """Generate CSV and PDF exports from download analytics data."""

    def __init__(self, db: AsyncSession, visible_user_ids: Optional[List[str]] = None) -> None:
        self.db = db
        self.visible_user_ids = visible_user_ids

    # ------------------------------------------------------------------ #
    # CSV export
    # ------------------------------------------------------------------ #
    async def export_csv(self, filters: Optional[ExportFilters] = None) -> bytes:
        """Generate a CSV export of downloads matching the supplied filters.

        Args:
            filters: Optional date range, platform, status, and category filters.

        Returns:
            Raw CSV bytes.
        """
        query = select(Download).where(Download.status == DownloadStatus.COMPLETED)

        if self.visible_user_ids is not None:
            query = query.where(Download.owner_id.in_(self.visible_user_ids))

        if filters:
            if filters.date_from:
                query = query.where(Download.completed_at >= filters.date_from)
            if filters.date_to:
                query = query.where(Download.completed_at <= filters.date_to)
            if filters.platform:
                query = query.where(Download.platform == filters.platform)
            if filters.status:
                query = query.where(Download.status == DownloadStatus(filters.status))
            if filters.category:
                query = query.where(Download.category == filters.category)

        query = query.order_by(Download.completed_at.desc().nullslast())
        result = await self.db.execute(query)
        downloads = result.scalars().all()

        rows = []
        for dl in downloads:
            metadata = dl.metadata_json or {}
            uploader = "Unknown"
            if isinstance(metadata, dict):
                for key in ("uploader_name", "uploader", "username", "creator", "channel", "author"):
                    value = metadata.get(key)
                    if isinstance(value, str) and value.strip():
                        uploader = value.strip()
                        break

            rows.append({
                "Date": dl.completed_at.strftime("%Y-%m-%d") if dl.completed_at else "",
                "Title": dl.title,
                "Platform": dl.platform,
                "Uploader": uploader,
                "Quality": dl.quality or "",
                "Size": dl.file_size or 0,
                "Status": dl.status.value if isinstance(dl.status, DownloadStatus) else str(dl.status),
                "Category": dl.category or "",
            })

        columns = [
            "Date",
            "Title",
            "Platform",
            "Uploader",
            "Quality",
            "Size",
            "Status",
            "Category",
        ]
        df = pd.DataFrame(rows, columns=columns)
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8")

    # ------------------------------------------------------------------ #
    # PDF export
    # ------------------------------------------------------------------ #
    async def export_pdf(self, report_type: str = "overview") -> bytes:
        """Generate a branded PDF analytics report.

        Args:
            report_type: ``"overview"`` for summary stats, ``"full"`` for
                an extended report including creators and storage breakdown.

        Returns:
            Raw PDF bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        brand_primary = colors.HexColor("#6C5CE7")
        brand_secondary = colors.HexColor("#00D2FF")
        text_color = colors.HexColor("#1A1A2E")

        story: list = []

        # Header
        title_style = styles["Heading1"].clone("BrandTitle")
        title_style.textColor = brand_primary
        title_style.fontSize = 24
        title_style.spaceAfter = 6
        story.append(Paragraph("MediaVault Pro Analytics", title_style))
        story.append(Spacer(1, 4))

        subtitle = styles["Normal"].clone("BrandSubtitle")
        subtitle.textColor = colors.HexColor("#6C6C7C")
        subtitle.fontSize = 10
        story.append(Paragraph(f"Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", subtitle))
        story.append(Spacer(1, 16))

        # Fetch overview stats.
        overview = await self._build_overview()

        # Summary section
        section_style = styles["Heading2"].clone("SectionHeader")
        section_style.textColor = brand_secondary
        section_style.fontSize = 14
        section_style.spaceAfter = 8
        story.append(Paragraph("Summary", section_style))

        summary_data = [
            ["Metric", "Value"],
            ["Total Downloads", str(overview["total_downloads"])],
            ["Total Storage", self._format_bytes(overview["total_storage"])],
            ["Success Rate", f"{overview['success_rate']}%"],
        ]
        summary_table = Table(summary_data, colWidths=[200, 200])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
            ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Platform breakdown
        story.append(Paragraph("Platform Breakdown", section_style))
        platform_data = [["Platform", "Count", "Total Size"]]
        for pb in overview["platform_breakdown"]:
            platform_data.append([pb.platform, str(pb.count), self._format_bytes(pb.total_size)])

        if len(platform_data) == 1:
            platform_data.append(["No data", "", ""])

        platform_table = Table(platform_data, colWidths=[150, 100, 150])
        platform_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
            ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ]))
        story.append(platform_table)
        story.append(Spacer(1, 20))

        # Full report extras.
        if report_type == "full":
            story.append(Paragraph("Top Creators", section_style))
            creators = overview.get("top_creators", [])
            creator_data = [["Rank", "Creator", "Platform", "Count", "Total Size"]]
            for idx, c in enumerate(creators, 1):
                creator_data.append([
                    str(idx), c.username, c.platform, str(c.count), self._format_bytes(c.total_size)
                ])
            if len(creator_data) == 1:
                creator_data.append(["", "No data", "", "", ""])

            creator_table = Table(creator_data, colWidths=[50, 130, 100, 70, 100])
            creator_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
                ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
            ]))
            story.append(creator_table)
            story.append(Spacer(1, 20))

            story.append(Paragraph("Storage by Category", section_style))
            categories = overview.get("category_storage", [])
            cat_data = [["Category", "Files", "Total Size"]]
            for cs in categories:
                cat_data.append([cs.category, str(cs.file_count), self._format_bytes(cs.total_size)])
            if len(cat_data) == 1:
                cat_data.append(["No data", "", ""])

            cat_table = Table(cat_data, colWidths=[180, 100, 170])
            cat_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
                ("TEXTCOLOR", (0, 1), (-1, -1), text_color),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
            ]))
            story.append(cat_table)

        doc.build(story)
        return buffer.getvalue()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #
    async def _build_overview(self) -> Dict[str, Any]:
        """Fetch all stats needed for a PDF report in one go."""
        from app.services.analytics.analytics_service import AnalyticsService

        analytics = AnalyticsService(self.db, visible_user_ids=self.visible_user_ids)
        overview_stats = await analytics.get_overview()
        top_creators = await analytics.get_top_creators(limit=10)
        category_storage = await analytics.get_storage_heatmap()

        return {
            "total_downloads": overview_stats.total_downloads,
            "total_storage": overview_stats.total_storage_bytes,
            "success_rate": overview_stats.success_rate,
            "platform_breakdown": overview_stats.platform_breakdown,
            "top_creators": top_creators,
            "category_storage": category_storage,
        }

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format a byte count as a human-readable string."""
        if size == 0:
            return "0 B"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
