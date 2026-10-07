"""Download schedule CRUD and network status endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.models.schedule import DownloadSchedule, ScheduleTriggerType
from app.services.network.network_monitor import get_network_status
from app.services.scheduler.download_scheduler import download_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Schedules"])


class ScheduleCreate(BaseModel):
    profile_id: Optional[str] = None
    url: Optional[str] = None
    trigger_type: str = "cron"
    cron_expression: Optional[str] = None
    run_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    quality_preference: str = "best"


class ScheduleUpdate(BaseModel):
    profile_id: Optional[str] = None
    url: Optional[str] = None
    trigger_type: Optional[str] = None
    cron_expression: Optional[str] = None
    run_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    is_active: Optional[bool] = None
    quality_preference: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: str
    profile_id: Optional[str]
    url: Optional[str]
    trigger_type: str
    cron_expression: Optional[str]
    run_time: Optional[str]
    days_of_week: Optional[List[int]]
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    quality_preference: str


def _to_response(schedule: DownloadSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(schedule.id),
        profile_id=str(schedule.profile_id) if schedule.profile_id else None,
        url=schedule.url,
        trigger_type=schedule.trigger_type.value if hasattr(schedule.trigger_type, "value") else str(schedule.trigger_type),
        cron_expression=schedule.cron_expression,
        run_time=schedule.run_time.strftime("%H:%M") if schedule.run_time else None,
        days_of_week=schedule.days_of_week,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        quality_preference=schedule.quality_preference,
    )


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(db: AsyncSession = Depends(get_db)) -> List[ScheduleResponse]:
    result = await db.execute(select(DownloadSchedule).order_by(DownloadSchedule.created_at.desc()))
    schedules = result.scalars().all()
    return [_to_response(s) for s in schedules]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(payload: ScheduleCreate, db: AsyncSession = Depends(get_db)) -> ScheduleResponse:
    if not payload.profile_id and not payload.url:
        raise HTTPException(status_code=422, detail="Either profile_id or url must be provided")

    if payload.trigger_type == "cron" and not payload.cron_expression:
        raise HTTPException(status_code=422, detail="cron_expression is required for cron trigger_type")

    schedule = DownloadSchedule(
        profile_id=payload.profile_id,
        url=payload.url,
        trigger_type=ScheduleTriggerType.CRON if payload.trigger_type == "cron" else ScheduleTriggerType.RUN_TIME,
        cron_expression=payload.cron_expression,
        run_time=datetime.strptime(payload.run_time, "%H:%M").time() if payload.run_time else None,
        days_of_week=payload.days_of_week,
        quality_preference=payload.quality_preference,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    download_scheduler.add_schedule(schedule)
    return _to_response(schedule)


@router.put("/schedules/{id}", response_model=ScheduleResponse)
async def update_schedule(id: str, payload: ScheduleUpdate, db: AsyncSession = Depends(get_db)) -> ScheduleResponse:
    result = await db.execute(select(DownloadSchedule).where(DownloadSchedule.id == id))
    schedule = result.scalars().first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if payload.profile_id is not None:
        schedule.profile_id = payload.profile_id
    if payload.url is not None:
        schedule.url = payload.url
    if payload.trigger_type is not None:
        schedule.trigger_type = (
            ScheduleTriggerType.CRON if payload.trigger_type == "cron" else ScheduleTriggerType.RUN_TIME
        )
    if payload.cron_expression is not None:
        schedule.cron_expression = payload.cron_expression
    if payload.run_time is not None:
        try:
            schedule.run_time = datetime.strptime(payload.run_time, "%H:%M").time()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="run_time must be in HH:MM format") from exc
    if payload.days_of_week is not None:
        schedule.days_of_week = payload.days_of_week
    if payload.is_active is not None:
        schedule.is_active = payload.is_active
    if payload.quality_preference is not None:
        schedule.quality_preference = payload.quality_preference

    await db.commit()
    await db.refresh(schedule)
    download_scheduler.update_schedule(schedule)
    return _to_response(schedule)


@router.delete("/schedules/{id}", status_code=204)
async def delete_schedule(id: str, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(DownloadSchedule).where(DownloadSchedule.id == id))
    schedule = result.scalars().first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()
    download_scheduler.remove_schedule(id)


@router.get("/system/network")
async def get_system_network() -> Dict[str, Any]:
    return get_network_status()
