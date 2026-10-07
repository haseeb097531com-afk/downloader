"""Tests for Phase 17A Authentication, Authorization & Security Hardening."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import PasswordStrengthError, hash_password, validate_password_strength, verify_password
from app.models.user import User, UserRole


# ------------------------------------------------------------------ #
# Auto-enable auth for every test in this module
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def _auto_enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_user(db, *, username="testuser", password="StrongPass1!", role=UserRole.USER, is_active=True, failed_login_count=0, locked_until=None, must_change_password=False):
    user = User(
        id=str(__import__("uuid").uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        must_change_password=must_change_password,
        failed_login_count=failed_login_count,
        locked_until=locked_until,
    )
    db.add(user)
    return user


# --------------------------------------------------------------------------- #
# Password strength tests
# --------------------------------------------------------------------------- #

class TestPasswordStrength:
    def test_rejects_short_password(self):
        with pytest.raises(PasswordStrengthError, match="at least 10 characters"):
            validate_password_strength("Short1!")

    def test_rejects_no_uppercase(self):
        with pytest.raises(PasswordStrengthError, match="uppercase"):
            validate_password_strength("nouppercase1!")

    def test_rejects_no_lowercase(self):
        with pytest.raises(PasswordStrengthError, match="lowercase"):
            validate_password_strength("NOLOWERCASE1!")

    def test_rejects_no_digit(self):
        with pytest.raises(PasswordStrengthError, match="digit"):
            validate_password_strength("NoDigitsHere!")

    def test_rejects_no_special(self):
        with pytest.raises(PasswordStrengthError, match="special"):
            validate_password_strength("NoSpecial123")

    def test_accepts_strong_password(self):
        validate_password_strength("Str0ng!Pass")


# --------------------------------------------------------------------------- #
# Password hashing tests
# --------------------------------------------------------------------------- #

class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "MyStr0ng!Pass"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass")
        assert not verify_password("WrongPass", hashed)


# --------------------------------------------------------------------------- #
# Auth endpoint tests
# --------------------------------------------------------------------------- #

class TestAuthEndpoints:
    def setup_method(self):
        self._original_auth = settings.AUTH_ENABLED
        settings.AUTH_ENABLED = True

    def teardown_method(self):
        settings.AUTH_ENABLED = self._original_auth

    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="alice", password="AlicePass1!")
        await db_session.commit()

        resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "alice",
            "password": "AlicePass1!",
        })
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "alice"

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="bob", password="BobPass1!")
        await db_session.commit()

        resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "bob",
            "password": "WrongPass",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_locks_after_max_failures(self, async_client: AsyncClient, db_session, fake_redis, monkeypatch):
        monkeypatch.setattr(settings, "MAX_FAILED_LOGINS", 3)
        monkeypatch.setattr(settings, "LOCK_MINUTES", 5)

        make_user(db_session, username="charlie", password="CharliePass1!", failed_login_count=2)
        await db_session.commit()

        for _ in range(2):
            await async_client.post("/api/v1/auth/login", json={
                "username_or_email": "charlie",
                "password": "WrongPass",
            })

        resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "charlie",
            "password": "WrongPass",
        })
        assert resp.status_code == status.HTTP_423_LOCKED

    @pytest.mark.asyncio
    async def test_refresh_rotates_access_token(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="dave", password="DavePass1!")
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "dave",
            "password": "DavePass1!",
        })
        assert login_resp.status_code == status.HTTP_200_OK
        tokens = login_resp.json()

        refresh_resp = await async_client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert refresh_resp.status_code == status.HTTP_200_OK
        new_tokens = refresh_resp.json()
        assert "access_token" in new_tokens
        assert new_tokens["access_token"] != tokens["access_token"]

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="eve", password="EvePass1!")
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "eve",
            "password": "EvePass1!",
        })
        tokens = login_resp.json()

        logout_resp = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert logout_resp.status_code == status.HTTP_200_OK

        refresh_resp = await async_client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_me_returns_profile(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="frank", password="FrankPass1!")
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "frank",
            "password": "FrankPass1!",
        })
        tokens = login_resp.json()

        resp = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["username"] == "frank"

    @pytest.mark.asyncio
    async def test_change_password(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="grace", password="GracePass1!")
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "grace",
            "password": "GracePass1!",
        })
        tokens = login_resp.json()

        resp = await async_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"old_password": "GracePass1!", "new_password": "NewStr0ng!Pass"},
        )
        assert resp.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_admin_can_create_user(self, async_client: AsyncClient, db_session, fake_redis):
        admin = make_user(db_session, username="admin", password="AdminPass1!", role=UserRole.OWNER)
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "admin",
            "password": "AdminPass1!",
        })
        tokens = login_resp.json()

        resp = await async_client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"username": "newuser", "password": "NewUserStr0ng!Pass", "role": "user"},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_user(self, async_client: AsyncClient, db_session, fake_redis):
        viewer = make_user(db_session, username="viewer", password="ViewerPass1!", role=UserRole.USER)
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "viewer",
            "password": "ViewerPass1!",
        })
        tokens = login_resp.json()

        resp = await async_client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"username": "newuser", "password": "NewUserStr0ng!Pass", "role": "user"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# --------------------------------------------------------------------------- #
# Data isolation tests
# --------------------------------------------------------------------------- #

class TestDataIsolation:
    @pytest.mark.asyncio
    async def test_user_a_sees_own_downloads_only(self, async_client: AsyncClient, db_session, fake_redis):
        from app.models.download import Download, DownloadStatus

        user_a = make_user(db_session, username="usera", password="UserAPass1!")
        user_b = make_user(db_session, username="userb", password="UserBPass1!")

        dl_a = Download(
            id=str(__import__("uuid").uuid4()),
            url="https://example.com/a",
            platform="youtube",
            content_type="video",
            title="User A Video",
            status=DownloadStatus.COMPLETED,
            file_size=1000,
            owner_id=user_a.id,
        )
        dl_b = Download(
            id=str(__import__("uuid").uuid4()),
            url="https://example.com/b",
            platform="youtube",
            content_type="video",
            title="User B Video",
            status=DownloadStatus.COMPLETED,
            file_size=2000,
            owner_id=user_b.id,
        )
        db_session.add_all([dl_a, dl_b])
        await db_session.commit()

        # Enable auth for this test.
        original_auth = settings.AUTH_ENABLED
        settings.AUTH_ENABLED = True
        try:
            login_resp = await async_client.post("/api/v1/auth/login", json={
                "username_or_email": "usera",
                "password": "UserAPass1!",
            })
            tokens = login_resp.json()

            resp = await async_client.get(
                "/api/v1/library",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            items = resp.json()["items"]
            titles = [item["title"] for item in items]
            assert "User A Video" in titles
            assert "User B Video" not in titles
        finally:
            settings.AUTH_ENABLED = original_auth

    @pytest.mark.asyncio
    async def test_legacy_mode_returns_all_downloads(self, async_client: AsyncClient, db_session, fake_redis):
        from app.models.download import Download, DownloadStatus

        user_a = make_user(db_session, username="usera", password="UserAPass1!")
        user_b = make_user(db_session, username="userb", password="UserBPass1!")

        dl_a = Download(
            id=str(__import__("uuid").uuid4()),
            url="https://example.com/a",
            platform="youtube",
            content_type="video",
            title="User A Video",
            status=DownloadStatus.COMPLETED,
            file_size=1000,
            owner_id=user_a.id,
        )
        dl_b = Download(
            id=str(__import__("uuid").uuid4()),
            url="https://example.com/b",
            platform="youtube",
            content_type="video",
            title="User B Video",
            status=DownloadStatus.COMPLETED,
            file_size=2000,
            owner_id=user_b.id,
        )
        db_session.add_all([dl_a, dl_b])
        await db_session.commit()

        original_auth = settings.AUTH_ENABLED
        settings.AUTH_ENABLED = False
        try:
            resp = await async_client.get("/api/v1/library")
            assert resp.status_code == status.HTTP_200_OK
            items = resp.json()["items"]
            titles = [item["title"] for item in items]
            assert "User A Video" in titles
            assert "User B Video" in titles
        finally:
            settings.AUTH_ENABLED = original_auth


# --------------------------------------------------------------------------- #
# Rate limiter tests
# --------------------------------------------------------------------------- #

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_login_rate_limiter_blocks_excess_attempts(self, async_client: AsyncClient, db_session, fake_redis, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)

        for i in range(5):
            make_user(db_session, username=f"ratelimituser{i}", password="RatePass1!")
        await db_session.commit()

        for i in range(5):
            await async_client.post("/api/v1/auth/login", json={
                "username_or_email": "ratelimituser0",
                "password": "WrongPass",
            })

        resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "ratelimituser0",
            "password": "WrongPass",
        })
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# --------------------------------------------------------------------------- #
# Audit log tests
# --------------------------------------------------------------------------- #

class TestAuditLog:
    def setup_method(self):
        self._original_auth = settings.AUTH_ENABLED
        settings.AUTH_ENABLED = True

    def teardown_method(self):
        settings.AUTH_ENABLED = self._original_auth

    @pytest.mark.asyncio
    async def test_login_failure_writes_audit_log(self, async_client: AsyncClient, db_session, fake_redis):
        make_user(db_session, username="audituser", password="AuditPass1!")
        await db_session.commit()

        resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "audituser",
            "password": "WrongPass",
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        from app.models.audit_log import AuditLog, AuditAction
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILURE)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1

    @pytest.mark.asyncio
    async def test_user_create_writes_audit_log(self, async_client: AsyncClient, db_session, fake_redis):
        admin = make_user(db_session, username="admin2", password="AdminPass1!", role=UserRole.OWNER)
        await db_session.commit()

        login_resp = await async_client.post("/api/v1/auth/login", json={
            "username_or_email": "admin2",
            "password": "AdminPass1!",
        })
        tokens = login_resp.json()

        await async_client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"username": "auditnewuser", "password": "NewUserStr0ng!Pass", "role": "user"},
        )

        from app.models.audit_log import AuditLog, AuditAction
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.USER_CREATE)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert logs[0].resource == "auditnewuser"
