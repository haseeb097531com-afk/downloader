"""Bulk import endpoints for Phase 16A.

Exposes:
- POST /api/v1/bulk/links
- POST /api/v1/bulk/profiles
- GET /api/v1/bulk/{job_id}
- WS /ws/bulk/{job_id}
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user
from app.db.database import get_db
from app.models.bulk_import import BulkJob, BulkItem, BulkJobType, BulkItemStatus
from app.services.downloader.bulk_import import BulkImportService

router = APIRouter(prefix="/bulk", tags=["Bulk Import"])
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Request / Response Models
# ------------------------------------------------------------------ #

class LinksRequest(BaseModel):
    urls: List[str]


class ProfilesRequest(BaseModel):
    urls: List[str]
    limit: int = 50


class BulkProgressResponse(BaseModel):
    job_id: str
    total: int
    processed: int
    failed: int
    percent: float
    status: str
    items: List[dict]


# ------------------------------------------------------------------ #
# REST endpoints
# ------------------------------------------------------------------ #

@router.post("/links", status_code=202, response_model=dict)
async def bulk_import_links(req: LinksRequest, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    service = BulkImportService(db, current_user=current_user)
    job = await service.import_links(req.urls)
    await db.commit()
    return {"job_id": job.id}


@router.post("/profiles", status_code=202, response_model=dict)
async def bulk_import_profiles(req: ProfilesRequest, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    service = BulkImportService(db, current_user=current_user)
    job = await service.import_profiles(req.urls, limit=req.limit)
    await db.commit()
    return {"job_id": job.id}


@router.get("/{job_id}", response_model=BulkProgressResponse)
async def get_bulk_job(job_id: str, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    service = BulkImportService(db, current_user=current_user)
    progress = await service.get_job_progress(job_id)
    return BulkProgressResponse(**progress)


# ------------------------------------------------------------------ #
# WebSocket live progress
# ------------------------------------------------------------------ #

@router.websocket("/ws/bulk/{job_id}")
async def bulk_progress_socket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    stop = asyncio.Event()
    reader = asyncio.create_task(_relay_bulk_progress(websocket, job_id, stop))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Bulk progress socket for %s ended: %s", job_id, exc)
        try:
            await websocket.send_json({"status": "error", "error": "Progress stream unavailable"})
        except Exception:
            pass
    finally:
        stop.set()
        reader.cancel()
        try:
            await reader
        except (asyncio.CancelledError, WebSocketDisconnect):
            pass
        except Exception as exc:
            logger.debug("Error closing bulk progress relay: %s", exc)


async def _relay_bulk_progress(websocket: WebSocket, job_id: str, stop: asyncio.Event) -> None:
    from app.db.database import AsyncSessionLocal
    from app.services.downloader.bulk_import import BulkImportService
    while not stop.is_set():
        try:
            async with AsyncSessionLocal() as db:
                service = BulkImportService(db)
                progress = await service.get_job_progress(job_id)
                await websocket.send_json(progress)
        except Exception as exc:
            logger.debug("Bulk progress relay error: %s", exc)
        await asyncio.sleep(2)
