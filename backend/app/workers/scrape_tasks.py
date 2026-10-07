import asyncio
import logging

from app.core.celery_app import celery_app
from app.services.scraper.profile_scraper import ProfileScraper
from app.db.database import AsyncSessionLocal
from app.services.downloader.bulk_orchestrator import BulkOrchestrator
from app.services.downloader.bulk_import import BulkImportService
from app.models.bulk_import import BulkJobStatus, BulkItemStatus

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.scrape_tasks.scrape_profile_task")
def scrape_profile_task(profile_url: str, limit: int = 50, bulk_job_id: str | None = None):
    scraper = ProfileScraper()
    
    async def run_scrape():
        async with AsyncSessionLocal() as db:
            result = await scraper.scrape_profile(db, profile_url, limit)
            profile = result.profile_info
            profile_id = None
            if bulk_job_id:
                profile_row = await _get_profile_by_url(db, profile_url)
                if profile_row:
                    profile_id = profile_row.id
                    await BulkImportService(db).import_profiles([profile_url], limit=limit, bulk_job_id=bulk_job_id)
                    await _advance_bulk_job(db, bulk_job_id)
            
            try:
                from app.services.notifications.push_service import PushService
                if result.new_count > 0 and profile_id:
                    await PushService().send_to_user(
                        db, "00000000-0000-0000-0000-000000000000",
                        f"{result.new_count} new videos found",
                        f"Profile {profile_url} has {result.new_count} new videos",
                        "scrape",
                        f"/profiles/{profile_id}",
                    )
            except Exception as exc:
                logger.warning("Push notification failed for scrape: %s", exc)
            
            return {
                "profile_info": profile.model_dump(),
                "total_discovered": result.total_discovered,
                "new_count": result.new_count,
                "skipped_count": result.skipped_count,
                "videos": result.videos,
                "profile_id": profile_id,
            }
             
    return asyncio.run(run_scrape())


async def _get_profile_by_url(db, profile_url: str):
    from app.models.profile import Profile
    from sqlalchemy import select
    result = await db.execute(select(Profile).where(Profile.profile_url == profile_url))
    return result.scalars().first()


async def _advance_bulk_job(db, bulk_job_id: str):
    from sqlalchemy import select, func
    from app.models.bulk_import import BulkJob, BulkItem, BulkItemStatus
    result = await db.execute(select(BulkItem).where(BulkItem.job_id == bulk_job_id))
    items = result.scalars().all()
    job = await db.get(BulkJob, bulk_job_id)
    if not job:
        return
    completed = sum(1 for i in items if i.status in (BulkItemStatus.COMPLETED, BulkItemStatus.QUEUED, BulkItemStatus.DOWNLOADING))
    failed = sum(1 for i in items if i.status == BulkItemStatus.FAILED)
    job.processed_items = completed
    job.failed_items = failed
    if failed == 0 and completed == job.total_items:
        job.status = BulkJobStatus.COMPLETED
    elif completed > 0:
        job.status = BulkJobStatus.PARTIAL
    await db.commit()
