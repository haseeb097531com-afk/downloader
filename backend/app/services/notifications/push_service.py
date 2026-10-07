"""Web push notification service."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.core.push_keys import get_private_key
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush
except ImportError:
    webpush = None


class PushService:
    """Manage web push subscriptions and send notifications."""

    def __init__(self) -> None:
        self._debounce: dict[str, float] = {}
        self._debounce_ttl = 5.0

    def _debounce_key(self, user_id: str, tag: str) -> str:
        return f"{user_id}:{tag}"

    def _is_debounced(self, user_id: str, tag: str) -> bool:
        key = self._debounce_key(user_id, tag)
        now = time.monotonic()
        if key in self._debounce and now - self._debounce[key] < self._debounce_ttl:
            return True
        self._debounce[key] = now
        return False

    async def subscribe(self, db, user_id: str, payload: dict) -> None:
        endpoint = payload.get("endpoint")
        if not endpoint:
            return
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        sub = result.scalars().first()
        if sub:
            sub.user_id = user_id
            sub.p256dh = payload.get("p256dh", "")
            sub.auth = payload.get("auth", "")
            sub.user_agent = payload.get("user_agent")
        else:
            sub = PushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                p256dh=payload.get("p256dh", ""),
                auth=payload.get("auth", ""),
                user_agent=payload.get("user_agent"),
            )
            db.add(sub)
        try:
            await db.commit()
            await db.refresh(sub)
        except Exception:
            await db.rollback()
            raise

    async def unsubscribe(self, db, endpoint: str) -> None:
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        sub = result.scalars().first()
        if sub:
            await db.delete(sub)
            await db.commit()

    async def send_to_user(
        self, db, user_id: str, title: str, body: str, tag: str, url: str
    ) -> None:
        if not getattr(settings, "PUSH_ENABLED", True):
            return
        if self._is_debounced(user_id, tag):
            return

        result = await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        subs = result.scalars().all()

        for sub in subs:
            await self._send_push(db, sub, title, body, tag, url)

    async def _send_push(self, db, sub: PushSubscription, title: str, body: str, tag: str, url: str) -> None:
        if webpush is None:
            return
        payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url})
        vapid_claims = {"sub": "mailto:admin@example.com"}
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=get_private_key(),
                vapid_claims=vapid_claims,
                ttl=24 * 60 * 60,
            )
            sub.last_sent_at = datetime.utcnow()
            sub.failure_count = 0
            await db.commit()
        except Exception as exc:
            sub.failure_count = (sub.failure_count or 0) + 1
            permanent = _is_permanent(exc)
            if sub.failure_count >= 3 or permanent:
                await db.delete(sub)
            else:
                sub.last_sent_at = datetime.utcnow()
            try:
                await db.commit()
            except Exception:
                await db.rollback()
            logger.warning("Push failed for %s: %s", sub.endpoint, exc)

    async def broadcast_admin(self, db, title: str, body: str, tag: str, url: str) -> None:
        result = await db.execute(
            select(PushSubscription.user_id).distinct().where(PushSubscription.user_id.is_not(None))
        )
        user_ids = [row[0] for row in result.scalars().all()]
        for uid in user_ids:
            try:
                await self.send_to_user(db, uid, title, body, tag, url)
            except Exception as exc:
                logger.warning("Broadcast to %s failed: %s", uid, exc)


def _is_permanent(exc: Exception) -> bool:
    status = getattr(exc, "response", None)
    if status is not None:
        code = getattr(status, "status_code", None)
        return code in (404, 410)
    return False
