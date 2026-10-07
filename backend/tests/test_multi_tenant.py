"""Tests for Part 1 of multi-tenant architecture."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.download import Download, DownloadStatus
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole, TenantRole


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def _auto_enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)


def make_user(db: AsyncSession, *, username="testuser", password="StrongPass1!", role=UserRole.USER, tenant_role=None, tenant_id=None, is_active=True):
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        must_change_password=False,
        failed_login_count=0,
        locked_until=None,
        token_version=0,
        tenant_role=tenant_role,
        tenant_id=tenant_id,
    )
    db.add(user)
    return user


async def login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "username_or_email": username,
        "password": password,
    })
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()["access_token"]


# ------------------------------------------------------------------ #
# Test 1: Default tenant backfill - legacy mode returns all downloads
# ------------------------------------------------------------------ #

class TestDefaultTenantBackfill:
    @pytest.mark.asyncio
    async def test_legacy_mode_returns_all_downloads(self, async_client: AsyncClient, db_session):
        """With AUTH_ENABLED=False, app still works and all downloads are visible."""
        from app.models.download import Download, DownloadStatus

        # Create a default tenant explicitly
        tenant = Tenant(
            id="default-tenant",
            name="Primary Workspace",
            slug="primary",
            plan=TenantPlan.PRO,
            status=TenantStatus.ACTIVE,
        )
        db_session.add(tenant)
        await db_session.commit()

        user_a = make_user(db_session, username="usera", password="UserAPass1!", tenant_role=TenantRole.TENANT_OWNER, tenant_id="default-tenant")
        user_b = make_user(db_session, username="userb", password="UserBPass1!", tenant_role=TenantRole.TENANT_OWNER, tenant_id="default-tenant")

        dl_a = Download(
            id=str(uuid.uuid4()),
            url="https://example.com/a",
            platform="youtube",
            content_type="video",
            title="User A Video",
            status=DownloadStatus.COMPLETED,
            file_size=1000,
            owner_id=user_a.id,
            tenant_id="default-tenant",
        )
        dl_b = Download(
            id=str(uuid.uuid4()),
            url="https://example.com/b",
            platform="youtube",
            content_type="video",
            title="User B Video",
            status=DownloadStatus.COMPLETED,
            file_size=2000,
            owner_id=user_b.id,
            tenant_id="default-tenant",
        )
        db_session.add_all([dl_a, dl_b])
        await db_session.commit()

        original_auth = settings.AUTH_ENABLED
        settings.AUTH_ENABLED = False
        try:
            resp = await async_client.get("/api/v1/library")
            assert resp.status_code == status.HTTP_200_OK, resp.text
            items = resp.json()["items"]
            titles = [item["title"] for item in items]
            assert "User A Video" in titles
            assert "User B Video" in titles
        finally:
            settings.AUTH_ENABLED = original_auth


# ------------------------------------------------------------------ #
# Test 2: Member isolation
# ------------------------------------------------------------------ #

class TestMemberIsolation:
    @pytest.mark.asyncio
    async def test_tenant_member_isolation(self, async_client: AsyncClient, db_session, fake_redis):
        """Member in tenant A cannot see downloads in tenant B."""
        from app.models.download import Download, DownloadStatus

        tenant_a = Tenant(
            id=str(uuid.uuid4()),
            name="Tenant A",
            slug="tenant-a",
            plan=TenantPlan.STARTER,
            status=TenantStatus.ACTIVE,
        )
        tenant_b = Tenant(
            id=str(uuid.uuid4()),
            name="Tenant B",
            slug="tenant-b",
            plan=TenantPlan.STARTER,
            status=TenantStatus.ACTIVE,
        )
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        owner_a = make_user(db_session, username="ownera", password="OwnerAPass1!", role=UserRole.OWNER, tenant_role=TenantRole.TENANT_OWNER, tenant_id=tenant_a.id)
        member_b = make_user(db_session, username="memberb", password="MemberBPass1!", role=UserRole.USER, tenant_role=TenantRole.MEMBER, tenant_id=tenant_b.id)

        dl_a = Download(
            id=str(uuid.uuid4()),
            url="https://example.com/a",
            platform="youtube",
            content_type="video",
            title="Tenant A Video",
            status=DownloadStatus.COMPLETED,
            file_size=1000,
            owner_id=owner_a.id,
            tenant_id=tenant_a.id,
        )
        db_session.add(dl_a)
        await db_session.commit()

        token = await login(async_client, "memberb", "MemberBPass1!")

        resp = await async_client.get(
            "/api/v1/library",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Member should not see tenant A's downloads
        assert resp.status_code == status.HTTP_200_OK, resp.text
        items = resp.json()["items"]
        titles = [item["title"] for item in items]
        assert "Tenant A Video" not in titles


# ------------------------------------------------------------------ #
# Test 3: Super admin impersonation
# ------------------------------------------------------------------ #

class TestSuperAdminImpersonation:
    @pytest.mark.asyncio
    async def test_super_admin_can_switch_tenant_via_header(self, async_client: AsyncClient, db_session, fake_redis):
        """Super admin can switch tenant via X-Tenant-Id header and sees tenant A's data."""
        from app.models.download import Download, DownloadStatus

        tenant_a = Tenant(
            id=str(uuid.uuid4()),
            name="Tenant A",
            slug="tenant-a-imp",
            plan=TenantPlan.PRO,
            status=TenantStatus.ACTIVE,
        )
        db_session.add(tenant_a)
        await db_session.commit()

        # Create super_admin user
        super_admin = make_user(
            db_session,
            username="superadmin",
            password="SuperAdminPass1!",
            role=UserRole.OWNER,
            tenant_role=TenantRole.SUPER_ADMIN,
            tenant_id=None,
        )
        owner_a = make_user(
            db_session,
            username="ownera",
            password="OwnerAPass1!",
            role=UserRole.OWNER,
            tenant_role=TenantRole.TENANT_OWNER,
            tenant_id=tenant_a.id,
        )

        dl_a = Download(
            id=str(uuid.uuid4()),
            url="https://example.com/a",
            platform="youtube",
            content_type="video",
            title="Tenant A Secret Video",
            status=DownloadStatus.COMPLETED,
            file_size=5000,
            owner_id=owner_a.id,
            tenant_id=tenant_a.id,
        )
        db_session.add(dl_a)
        await db_session.commit()

        token = await login(async_client, "superadmin", "SuperAdminPass1!")

        # Without impersonation, super_admin sees nothing (no tenant_id filter applied but library may not show)
        resp_no_imp = await async_client.get(
            "/api/v1/library",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_no_imp.status_code == status.HTTP_200_OK

        # With impersonation header, super_admin sees tenant A data
        resp_with_imp = await async_client.get(
            "/api/v1/library",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_a.id},
        )
        assert resp_with_imp.status_code == status.HTTP_200_OK, resp_with_imp.text
        items = resp_with_imp.json()["items"]
        titles = [item["title"] for item in items]
        assert "Tenant A Secret Video" in titles


# ------------------------------------------------------------------ #
# Test 4: Tenant owner invite
# ------------------------------------------------------------------ #

class TestTenantOwnerInvite:
    @pytest.mark.asyncio
    async def test_tenant_owner_can_invite_member(self, async_client: AsyncClient, db_session, fake_redis):
        """Tenant owner invites member, member appears in tenant roster."""
        from app.models.download import Download, DownloadStatus

        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Test Tenant",
            slug="test-tenant",
            plan=TenantPlan.STARTER,
            status=TenantStatus.ACTIVE,
        )
        db_session.add(tenant)
        await db_session.commit()

        owner = make_user(db_session, username="tenantowner", password="OwnerPass1!", role=UserRole.OWNER, tenant_role=TenantRole.TENANT_OWNER, tenant_id=tenant.id)
        await db_session.commit()

        owner_token = await login(async_client, "tenantowner", "OwnerPass1!")

        # Owner creates a download in the tenant
        dl = Download(
            id=str(uuid.uuid4()),
            url="https://example.com/tenant-vid",
            platform="youtube",
            content_type="video",
            title="Tenant Video",
            status=DownloadStatus.COMPLETED,
            file_size=3000,
            owner_id=owner.id,
            tenant_id=tenant.id,
        )
        db_session.add(dl)
        await db_session.commit()

        # Invite a new member with explicit password
        invite_resp = await async_client.post(
            f"/api/v1/tenants/{tenant.id}/members",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"username": "newmember", "email": "new@example.com", "password": "NewMemberStr0ng!"},
        )
        assert invite_resp.status_code == status.HTTP_201_CREATED, invite_resp.text
        member_username = invite_resp.json()["username"]
        assert invite_resp.json()["tenant_role"] == "member"
        assert invite_resp.json()["tenant_id"] == tenant.id

        # Verify member can login
        member_token = await login(async_client, member_username, "NewMemberStr0ng!")

        # Verify member appears in tenant roster
        members_resp = await async_client.get(
            f"/api/v1/tenants/{tenant.id}/members",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert members_resp.status_code == status.HTTP_200_OK
        members = members_resp.json()
        assert any(m["username"] == member_username for m in members)
