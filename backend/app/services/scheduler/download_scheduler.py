"""APScheduler-based download scheduler for MediaVault Pro.

Integrates with FastAPI lifespan so active schedules are loaded on startup and
stopped cleanly on shutdown.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.db.database import AsyncSessionLocal
from app.models.schedule import DownloadSchedule, ScheduleTriggerType

logger = logging.getLogger(__name__)


class DownloadScheduler:
    """Manage APScheduler jobs that enqueue downloads on a cron or fixed-time basis."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._jobs: Dict[str, str] = {}

    async def start(self) -> None:
        """Load all active schedules from the database and register them."""
        await self.refresh()
        logger.info("DownloadScheduler started with %d active job(s)", len(self._jobs))

    async def stop(self) -> None:
        """Shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._jobs.clear()
        logger.info("DownloadScheduler stopped")

    async def refresh(self) -> None:
        """Reload all active schedules from the database, replacing existing jobs."""
        self._scheduler.remove_all_jobs()
        self._jobs.clear()

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DownloadSchedule).where(DownloadSchedule.is_active.is_(True))
            )
            schedules = result.scalars().all()

        for schedule in schedules:
            self._register(schedule)

    def _register(self, schedule: DownloadSchedule) -> None:
        """Add a single schedule to APScheduler."""
        job_id = str(schedule.id)
        if schedule.trigger_type == ScheduleTriggerType.CRON:
            trigger = CronTrigger.from_crontab(schedule.cron_expression or "* * * * *")
        else:
            # run_time trigger: fire at a fixed wall-clock time on the configured days.
            days = schedule.days_of_week or [0, 1, 2, 3, 4, 5, 6]
            trigger = CronTrigger(
                hour=schedule.run_time.hour if schedule.run_time else 0,
                minute=schedule.run_time.minute if schedule.run_time else 0,
                day_of_week=",".join(str(d) for d in days),
            )

        self._scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=job_id,
            args=[str(schedule.id)],
            replace_existing=True,
            misfire_grace_time=60,
        )
        self._jobs[job_id] = str(schedule.id)
        logger.debug("Registered schedule %s", job_id)

    async def _fire(self, schedule_id: str) -> None:
        """APScheduler callback: enqueue work when the schedule triggers."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DownloadSchedule).where(DownloadSchedule.id == schedule_id)
            )
            schedule = result.scalars().first()
            if schedule is None or not schedule.is_active:
                return

            schedule.last_run_at = datetime.utcnow()
            await db.commit()

        if schedule.profile_id:
            celery_app.send_task(
                "app.workers.scrape_tasks.scrape_profile_task",
                args=[str(schedule.profile_id)],
            )
        elif schedule.url:
            celery_app.send_task(
                "app.workers.download_tasks.download_media_task",
                args=[str(schedule.url)],
            )

    def add_schedule(self, schedule: DownloadSchedule) -> None:
        self._register(schedule)

    def remove_schedule(self, schedule_id: str) -> None:
        job_id = str(schedule_id)
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
        self._jobs.pop(job_id, None)

    def update_schedule(self, schedule: DownloadSchedule) -> None:
        self.remove_schedule(str(schedule.id))
        if schedule.is_active:
            self._register(schedule)

    def get_schedules(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": job.id,
                "schedule_id": self._jobs.get(job.id),
                "next_run_time": (
                    getattr(job, "next_run_time", None).isoformat()
                    if getattr(job, "next_run_time", None)
                    else None
                ),
            }
            for job in self._scheduler.get_jobs()
        ]


download_scheduler = DownloadScheduler()
