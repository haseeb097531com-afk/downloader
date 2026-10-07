from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel

from app.api.deps_auth import get_current_user, require_feature, OwnerFilter, visible_users
from app.db.database import get_db
from app.models.profile import Profile, ProfileVideo
from app.models.user import User
from app.workers.scrape_tasks import scrape_profile_task
from app.services.downloader.bulk_orchestrator import BulkOrchestrator

router = APIRouter(prefix="/profiles", tags=["Profiles"], dependencies=[Depends(require_feature("profiles"))])

class ScrapeRequest(BaseModel):
    url: str
    limit: int = 50

class DownloadRequest(BaseModel):
    video_ids: Optional[List[str]] = None
    quality: str = "best"

@router.post("/scrape", status_code=202)
async def scrape_profile(req: ScrapeRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = scrape_profile_task.delay(req.url, req.limit)
    return {"message": "Scraping started", "task_id": task.id}


@router.get("/")
async def list_profiles(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    visible = await visible_users(current_user, db)
    query = select(Profile)
    query = OwnerFilter.apply(current_user, query, Profile, visible_user_ids=visible)
    result = await db.execute(query)
    profiles = result.scalars().all()
    return profiles


@router.get("/{id}")
async def get_profile(id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    visible = await visible_users(current_user, db)
    query = select(Profile).where(Profile.id == id)
    query = OwnerFilter.apply(current_user, query, Profile, visible_user_ids=visible)
    result = await db.execute(query)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    v_query = select(ProfileVideo).where(ProfileVideo.profile_id == id)
    v_query = OwnerFilter.apply(current_user, v_query, ProfileVideo, visible_user_ids=visible)
    v_result = await db.execute(v_query)
    videos = v_result.scalars().all()
    
    return {"profile": profile, "videos": videos}


@router.post("/{id}/download", status_code=202)
async def bulk_download(id: str, req: DownloadRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    orchestrator = BulkOrchestrator(db, current_user=current_user)
    result = await orchestrator.enqueue_profile_videos(id, req.video_ids, req.quality)
    return result

@router.delete("/{id}")
async def delete_profile(id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(Profile).where(Profile.id == id), Profile, visible_user_ids=visible)
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    await db.delete(profile)
    await db.commit()
    return {"message": "Profile deleted"}
