"""Request/response schemas for download creation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DownloadCreateRequest(BaseModel):
    """Body of ``POST /api/v1/downloads``."""

    url: str = Field(..., description="Source URL to download")
    platform: Optional[str] = Field(None, description="Override platform detection")
    force: bool = Field(False, description="Skip duplicate detection and proceed")


class DownloadCreateResponse(BaseModel):
    """Response body after a download is created."""

    id: str = Field(..., description="Download record ID")
    status: str = Field(..., description="Current download status")
    message: str = Field("", description="Human-readable summary")
