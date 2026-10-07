"""Response schemas for the analytics and export subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


__all__ = [
    "OverviewStats",
    "PlatformBreakdown",
    "QualityBreakdown",
    "TimelineEntry",
    "CreatorStat",
    "CategoryStorage",
    "ExportFilters",
    "ExportCsvResponse",
    "ExportPdfRequest",
]


class PlatformBreakdown(BaseModel):
    """Per-platform aggregate."""

    platform: str = Field(..., description="Platform name")
    count: int = Field(0, description="Number of downloads")
    total_size: int = Field(0, description="Combined size in bytes")


class QualityBreakdown(BaseModel):
    """Per-quality aggregate."""

    quality: str = Field(..., description="Quality label, e.g. '1080p'")
    count: int = Field(0, description="Number of downloads")


class OverviewStats(BaseModel):
    """High-level library metrics."""

    total_downloads: int = Field(0, description="Total number of downloads")
    total_storage_bytes: int = Field(0, description="Combined file size in bytes")
    success_rate: float = Field(0.0, description="Percentage of completed downloads")
    platform_breakdown: List[PlatformBreakdown] = Field(default_factory=list)
    quality_breakdown: List[QualityBreakdown] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    """One day in the download timeline."""

    date: str = Field(..., description="ISO date YYYY-MM-DD")
    count: int = Field(0, description="Downloads completed on this day")
    total_size: int = Field(0, description="Combined size in bytes")


class CreatorStat(BaseModel):
    """Aggregate stats for one uploader/creator."""

    username: str = Field(..., description="Uploader name")
    platform: str = Field(..., description="Source platform")
    count: int = Field(0, description="Number of downloads")
    total_size: int = Field(0, description="Combined size in bytes")


class CategoryStorage(BaseModel):
    """Storage usage grouped by category."""

    category: str = Field(..., description="Category name")
    total_size: int = Field(0, description="Combined size in bytes")
    file_count: int = Field(0, description="Number of files in this category")


class ExportFilters(BaseModel):
    """Filters applied to CSV export."""

    date_from: Optional[datetime] = Field(None, description="Start of date range")
    date_to: Optional[datetime] = Field(None, description="End of date range")
    platform: Optional[str] = Field(None, description="Platform filter")
    status: Optional[str] = Field(None, description="Status filter")
    category: Optional[str] = Field(None, description="Category filter")


class ExportCsvResponse(BaseModel):
    """Metadata returned alongside the CSV file download."""

    filename: str = Field(..., description="Suggested file name")
    rows: int = Field(0, description="Number of rows exported")


class ExportPdfRequest(BaseModel):
    """Body for ``POST /api/v1/analytics/export/pdf``."""

    report_type: str = Field("overview", description="Report type: 'overview' or 'full'")
