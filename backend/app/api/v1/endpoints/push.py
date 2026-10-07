"""Web push notification endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps_auth import get_current_user
from app.api.v1.deps import get_db
from app.core.push_keys import get_public_key
from app.models.user import User
from app.services.notifications.push_service import PushService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Push"])


class SubscribeRequest(BaseModel):
    endpoint: str = Field(..., description="Push subscription endpoint URL")
    p256dh: str = Field(..., description="Base64-encoded p256dh public key")
    auth: str = Field(..., description="Base64-encoded auth secret")
    user_agent: str | None = Field(None, description="Client user agent")


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., description="Push subscription endpoint URL to remove")


class TestPushRequest(BaseModel):
    title: str = Field("Test notification", description="Notification title")
    body: str = Field("This is a test", description="Notification body")
    tag: str = Field("test", description="Notification tag for debouncing")
    url: str = Field("/", description="URL to open on click")


@router.get("/push/public-key")
async def get_public_key_endpoint() -> dict:
    return {"public_key": get_public_key()}


@router.post("/push/subscribe")
async def subscribe(
    payload: SubscribeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    await PushService().subscribe(db, current_user.id, payload.model_dump())
    return {"message": "Subscribed"}


@router.post("/push/unsubscribe")
async def unsubscribe(
    payload: UnsubscribeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    await PushService().unsubscribe(db, payload.endpoint)
    return {"message": "Unsubscribed"}


@router.post("/push/test")
async def test_push(
    payload: TestPushRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    await PushService().send_to_user(
        db, current_user.id, payload.title, payload.body, payload.tag, payload.url
    )
    return {"message": "Test push queued"}
