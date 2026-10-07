from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import logging
import os
import secrets
from datetime import datetime, timezone

from app.core.config import settings
from app.core.redis_client import close_async_redis
from app.services.storage.file_manager import FileManager, FileManagerError
from app.services.scheduler.download_scheduler import download_scheduler

from app.api.v1.endpoints.profiles import router as profiles_router
from app.api.v1.endpoints.library import router as library_router
from app.api.v1.endpoints.queue import router as queue_router
from app.api.v1.endpoints.downloads import router as downloads_router
from app.api.v1.endpoints.ws import router as ws_router
from app.api.v1.endpoints.settings import router as settings_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.providers import router as providers_router
from app.api.v1.endpoints.desktop import router as desktop_router
from app.api.v1.endpoints.cloud import router as cloud_router
from app.api.v1.endpoints.analysis import router as analysis_router
from app.api.v1.endpoints.schedules import router as schedules_router
from app.api.v1.endpoints.plugins import router as plugins_router
from app.api.v1.endpoints.dedup import dedup_router, lib_router as dedup_lib_router
from app.api.v1.endpoints.moderation import router as moderation_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.bulk import router as bulk_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.audit import router as audit_router
from app.desktop.manager import DesktopManager

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
)


# ------------------------------------------------------------------ #
# Security headers middleware
# ------------------------------------------------------------------ #

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Only send HSTS when not running on localhost (avoids breaking local dev).
    host = request.headers.get("host", "")
    if "localhost" not in host and "127.0.0.1" not in host:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# ------------------------------------------------------------------ #
# Global exception handler (never leak stack traces or secrets)
# ------------------------------------------------------------------ #

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )


# ------------------------------------------------------------------ #
# CORS
# ------------------------------------------------------------------ #

if getattr(settings, "AUTH_ENABLED", False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/settings-derived", tags=["Settings"])
async def settings_derived():
    return {"auth_enabled": getattr(settings, "AUTH_ENABLED", False)}


app.include_router(profiles_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1")
app.include_router(queue_router, prefix="/api/v1")
app.include_router(downloads_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(settings_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(providers_router, prefix="/api/v1")
app.include_router(desktop_router, prefix="/api/v1")
app.include_router(cloud_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(schedules_router, prefix="/api/v1")
app.include_router(plugins_router, prefix="/api/v1")
app.include_router(dedup_router, prefix="/api/v1")
app.include_router(dedup_lib_router, prefix="/api/v1")
app.include_router(moderation_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(bulk_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
from app.api.v1.endpoints.push import router as push_router
app.include_router(push_router, prefix="/api/v1")
from app.api.v1.endpoints.remote import router as remote_router
app.include_router(remote_router, prefix="/api/v1")
from app.api.v1.endpoints.bot import router as bot_router
app.include_router(bot_router, prefix="/api/v1")
from app.api.v1.endpoints.tenants import router as tenants_router
app.include_router(tenants_router, prefix="/api/v1")
from app.api.v1.endpoints.billing import router as billing_router
app.include_router(billing_router, prefix="/api/v1")
from app.api.v1.endpoints.media import router as media_router
app.include_router(media_router, prefix="/api/v1")

_desktop_manager = DesktopManager()


# ------------------------------------------------------------------ #
# Startup helpers
# ------------------------------------------------------------------ #

async def _ensure_jwt_secret() -> str:
    """Return the JWT secret, generating and persisting one if empty."""
    secret = getattr(settings, "JWT_SECRET", "") or ""
    if secret:
        return secret

    secret = secrets.token_urlsafe(32)
    data_dir = getattr(settings, "DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    secret_path = os.path.join(data_dir, "jwt_secret.txt")
    try:
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(secret)
        logger.info("Generated new JWT secret and wrote to %s", secret_path)
    except OSError as exc:
        logger.warning("Could not persist JWT secret: %s", exc)

    # Update the settings object in-memory for this process.
    settings.JWT_SECRET = secret
    return secret


async def _seed_default_user(db) -> None:
    """Create or update the default 'local' admin user."""
    from sqlalchemy import select
    from app.models.user import User
    from app.core.security import hash_password

    result = await db.execute(select(User).where(User.username == "local"))
    user = result.scalars().first()

    temp_password = "changeme"
    hashed = hash_password(temp_password)

    if user is None:
        user = User(
            id="00000000-0000-0000-0000-000000000001",
            username="local",
            email=None,
            password_hash=hashed,
            role="owner",
            is_active=True,
            must_change_password=True,
            failed_login_count=0,
            locked_until=None,
            token_version=0,
        )
        db.add(user)
    else:
        user.password_hash = hashed
        user.must_change_password = True
        user.is_active = True
        user.role = "owner"

    await db.commit()

    data_dir = getattr(settings, "DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    creds_path = os.path.join(data_dir, "initial_admin_credentials.txt")
    try:
        with open(creds_path, "w", encoding="utf-8") as f:
            f.write(f"Username: local\nPassword: {temp_password}\n")
        logger.warning("=" * 60)
        logger.warning("DEFAULT ADMIN CREDENTIALS (saved to %s)", creds_path)
        logger.warning("Username: local")
        logger.warning("Password: %s", temp_password)
        logger.warning("CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN")
        logger.warning("=" * 60)
    except OSError as exc:
        logger.warning("Could not write admin credentials file: %s", exc)
        logger.warning("Default admin credentials -> username: local, password: %s", temp_password)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up MediaVault backend...")

    # Ensure JWT secret exists when auth is enabled.
    if getattr(settings, "AUTH_ENABLED", False):
        await _ensure_jwt_secret()

    # Seed default admin user.
    try:
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await _seed_default_user(db)
    except Exception as exc:
        logger.warning("Default user seeding failed: %s", exc)

    # The library and download workers both assume the media directory exists.
    try:
        file_manager = FileManager()
        file_manager.ensure_dir()
        partials = file_manager.cleanup_partials()
        if partials:
            print(f"Cleaned up {len(partials)} orphaned partial download file(s).")
    except FileManagerError as exc:
        print(f"Warning: media directory unavailable: {exc}")

    if settings.CLIPBOARD_ENABLED or settings.TRAY_ENABLED:
        try:
            _desktop_manager.start(
                clipboard=settings.CLIPBOARD_ENABLED,
                tray=settings.TRAY_ENABLED,
            )
        except Exception as exc:
            print(f"Warning: desktop services failed to start: {exc}")

    try:
        await download_scheduler.start()
    except Exception as exc:
        print(f"Warning: download scheduler failed to start: {exc}")

    _telegram_bot_task = None
    if getattr(settings, "TELEGRAM_BOT_ENABLED", False) and getattr(settings, "TELEGRAM_BOT_TOKEN", ""):
        try:
            from app.services.bot.telegram_bot import TelegramBotService
            _telegram_bot_service = TelegramBotService()
            _telegram_bot_service.start(
                settings.TELEGRAM_BOT_TOKEN,
                getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", "") or "",
            )
            if _telegram_bot_service.enabled:
                _telegram_bot_task = asyncio.create_task(_telegram_bot_service.run())
                logger.info("Telegram bot background task started")
        except Exception as exc:
            logger.warning("Telegram bot failed to start: %s", exc)

    yield

    print("Shutting down MediaVault backend...")
    if _telegram_bot_task is not None:
        try:
            from app.services.bot.telegram_bot import TelegramBotService
            await _telegram_bot_service.stop()
            _telegram_bot_task.cancel()
            try:
                await _telegram_bot_task
            except asyncio.CancelledError:
                pass
        except Exception as exc:
            logger.warning("Telegram bot shutdown error: %s", exc)
    try:
        await download_scheduler.stop()
    except Exception as exc:
        print(f"Warning: download scheduler failed to stop: {exc}")
    try:
        _desktop_manager.stop()
    except Exception as exc:
        print(f"Warning: desktop services failed to stop: {exc}")
    await close_async_redis()
