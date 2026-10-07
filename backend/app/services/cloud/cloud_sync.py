"""Cloud backup service for Phase 9A.

Provides encrypted token storage and provider-specific clients for Google Drive
and Dropbox. Tokens are NEVER persisted in plain text.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - optional dependency guard
    Fernet = None  # type: ignore[misc,assignment]
    InvalidToken = Exception  # type: ignore[misc,assignment]


class CloudTokenStore:
    """Encrypted token persistence backed by ``DATA_DIR/cloud_tokens.json``.

    The file is encrypted with Fernet. The key is derived from
    ``settings.SECRET_KEY`` via SHA-256 + base64url so the same secret can be
    reused across restarts without storing the raw Fernet key separately.
    """

    _CACHE: Optional[dict[str, str]] = None

    @classmethod
    def _key(cls) -> bytes:
        """Derive a stable Fernet key from ``settings.SECRET_KEY``."""
        import hashlib
        import base64

        raw = getattr(settings, "SECRET_KEY", "") or "mediavault-default-secret"
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @classmethod
    def _path(cls) -> Path:
        return Path(settings.CLOUD_TOKENS_FILE)

    @classmethod
    def load(cls) -> dict[str, str]:
        """Return the decrypted token map, or an empty dict when the file is absent/corrupt."""
        if cls._CACHE is not None:
            return cls._CACHE

        path = cls._path()
        if not path.exists():
            cls._CACHE = {}
            return cls._CACHE

        try:
            if Fernet is None:
                raise RuntimeError("cryptography package is not installed")
            data = path.read_bytes()
            if not data.strip():
                cls._CACHE = {}
                return cls._CACHE
            f = Fernet(cls._key())
            decrypted = f.decrypt(data)
            cls._CACHE = json.loads(decrypted.decode("utf-8"))
            return cls._CACHE
        except (InvalidToken, json.JSONDecodeError, OSError, RuntimeError) as exc:
            logger.warning("Failed to load cloud tokens: %s", exc)
            cls._CACHE = {}
            return cls._CACHE

    @classmethod
    def save(cls, tokens: dict[str, str]) -> None:
        """Encrypt and persist the token map atomically."""
        cls._CACHE = dict(tokens)
        path = cls._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            if Fernet is None:
                raise RuntimeError("cryptography package is not installed")
            f = Fernet(cls._key())
            plaintext = json.dumps(tokens).encode("utf-8")
            tmp.write_bytes(f.encrypt(plaintext))
            tmp.replace(path)
        except (InvalidToken, OSError, RuntimeError) as exc:
            logger.error("Failed to save cloud tokens: %s", exc)
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @classmethod
    def get(cls, provider: str) -> Optional[str]:
        return cls.load().get(provider)

    @classmethod
    def set(cls, provider: str, token: str) -> None:
        tokens = cls.load()
        tokens[provider] = token
        cls.save(tokens)

    @classmethod
    def delete(cls, provider: str) -> None:
        tokens = cls.load()
        tokens.pop(provider, None)
        cls.save(tokens)

    @classmethod
    def clear(cls) -> None:
        cls._CACHE = {}
        cls.save({})


class GoogleDriveClient:
    """Minimal Google Drive client using OAuth2 access tokens."""

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    BASE_URL = "https://www.googleapis.com/drive/v3"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    def __init__(self) -> None:
        self._access_token: Optional[str] = None

    def build_auth_url(self) -> str:
        """Return a Google OAuth2 consent URL."""
        client_id = settings.GOOGLE_DRIVE_CLIENT_ID
        if not client_id:
            raise ValueError("GOOGLE_DRIVE_CLIENT_ID is not configured")
        params = (
            f"client_id={client_id}"
            f"&redirect_uri={settings.PUBLIC_BASE_URL}/api/v1/cloud/google/callback"
            f"&response_type=code"
            f"&scope={' '.join(self.SCOPES)}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return f"{self.AUTH_URL}?{params}"

    def exchange_code(self, code: str) -> None:
        """Exchange an authorization code for tokens and persist them."""
        import requests as req

        client_id = settings.GOOGLE_DRIVE_CLIENT_ID
        client_secret = settings.GOOGLE_DRIVE_CLIENT_SECRET
        if not client_id or not client_secret:
            raise ValueError("Google Drive OAuth credentials are not configured")

        resp = req.post(
            self.TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": f"{settings.PUBLIC_BASE_URL}/api/v1/cloud/google/callback",
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("No access_token in Google OAuth response")
        self._access_token = access_token
        CloudTokenStore.set("google", access_token)

    def is_connected(self) -> bool:
        token = self._access_token or CloudTokenStore.get("google")
        if not token:
            return False
        try:
            return bool(self._get("about?fields=id") and self._access_token is not None)
        except Exception:
            return False

    def _get(self, path: str) -> Optional[dict]:
        import requests as req

        token = self._access_token or CloudTokenStore.get("google")
        if not token:
            return None
        resp = req.get(
            f"{self.BASE_URL}/{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code == 401:
            self._access_token = None
            return None
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict, params: Optional[dict] = None) -> Optional[dict]:
        import requests as req

        token = self._access_token or CloudTokenStore.get("google")
        if not token:
            return None
        resp = req.post(
            f"{self.BASE_URL}/{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params or {},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 401:
            self._access_token = None
            return None
        resp.raise_for_status()
        return resp.json()

    def upload_file(self, file_path: str, folder_path: str) -> Optional[str]:
        """Upload ``file_path`` into ``folder_path`` under ``MediaVault/`` and return a web link."""
        import requests as req

        token = self._access_token or CloudTokenStore.get("google")
        if not token:
            raise ConnectionError("Google Drive is not connected")

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        folder_id = self._find_or_create_folder(folder_path)
        if folder_id is None:
            raise RuntimeError("Failed to resolve Google Drive folder")

        file_name = path.name
        mime_type = self._guess_mime(path)
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "name": file_name,
            "parents": [folder_id],
            "fields": "id, webViewLink",
        }
        with path.open("rb") as handle:
            resp = req.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers=headers,
                params=params,
                files={
                    "metadata": (None, json.dumps(params), "application/json"),
                    "file": (file_name, handle, mime_type),
                },
                timeout=120,
            )
        if resp.status_code == 401:
            self._access_token = None
            raise ConnectionError("Google Drive token expired")
        resp.raise_for_status()
        data = resp.json()
        return data.get("webViewLink") or f"https://drive.google.com/file/d/{data.get('id')}"

    def _find_or_create_folder(self, folder_path: str) -> Optional[str]:
        """Create/reuse nested folders and return the deepest folder ID."""
        parts = [p for p in folder_path.replace("\\", "/").split("/") if p]
        parent_id = "root"
        for part in parts:
            query = (
                f"name = '{part}' and mimeType = 'application/vnd.google-apps.folder'"
                f" and '{parent_id}' in parents and trashed = false"
            )
            existing = self._get(f"files?q={urllib.parse.quote(query)}&fields=files(id)")
            files = existing.get("files", []) if existing else []
            if files:
                parent_id = files[0]["id"]
            else:
                created = self._post(
                    "files",
                    {
                        "name": part,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [parent_id],
                    },
                    {"fields": "id"},
                )
                if not created:
                    return None
                parent_id = created["id"]
        return parent_id

    def disconnect(self) -> None:
        self._access_token = None
        CloudTokenStore.delete("google")

    def __repr__(self) -> str:
        return "GoogleDriveClient()"


try:
    import urllib.parse as reqs
except ImportError:  # pragma: no cover
    import urllib as reqs  # type: ignore[no-redef]


class DropboxClient:
    """Minimal Dropbox client using long-lived access tokens."""

    BASE_URL = "https://api.dropboxapi.com/2"

    def __init__(self) -> None:
        self._access_token: Optional[str] = None

    def connect(self, access_token: str) -> None:
        """Validate ``access_token`` and persist it."""
        import requests as req

        resp = req.post(
            f"{self.BASE_URL}/users/get_current_account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        self._access_token = access_token
        CloudTokenStore.set("dropbox", access_token)

    def is_connected(self) -> bool:
        token = self._access_token or CloudTokenStore.get("dropbox")
        if not token:
            return False
        try:
            import requests as req

            resp = req.post(
                f"{self.BASE_URL}/users/get_current_account",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            if resp.status_code == 401:
                self._access_token = None
                return False
            return resp.ok
        except Exception:
            return False

    def upload_file(self, file_path: str, folder_path: str) -> Optional[str]:
        """Upload ``file_path`` into ``/MediaVault/{folder_path}/`` and return a shared link."""
        import requests as req

        token = self._access_token or CloudTokenStore.get("dropbox")
        if not token:
            raise ConnectionError("Dropbox is not connected")

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        dropbox_path = f"/MediaVault/{folder_path}/{path.name}"
        with path.open("rb") as handle:
            resp = req.post(
                f"{self.BASE_URL}/files/upload",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                    "Dropbox-API-Arg": json.dumps({"path": dropbox_path, "mode": "add", "autorename": True}),
                },
                data=handle.read(),
                timeout=120,
            )
        if resp.status_code == 401:
            self._access_token = None
            raise ConnectionError("Dropbox token expired")
        resp.raise_for_status()

        try:
            link_resp = req.post(
                f"{self.BASE_URL}/sharing/create_shared_link_with_settings",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"path": dropbox_path, "settings": {"requested_visibility": "public"}},
                timeout=30,
            )
            if link_resp.status_code == 200:
                return link_resp.json().get("url")
        except Exception:
            pass
        return f"https://www.dropbox.com/home{dropbox_path}"

    def disconnect(self) -> None:
        self._access_token = None
        CloudTokenStore.delete("dropbox")

    def __repr__(self) -> str:
        return "DropboxClient()"


def get_client(provider: str) -> Optional[GoogleDriveClient | DropboxClient]:
    """Return a cloud client for ``provider`` if it appears connected.

    Args:
        provider: ``"google"`` or ``"dropbox"``.

    Returns:
        A connected client instance, or ``None`` when no provider is configured
        or connected.
    """
    provider = (provider or "").strip().lower()
    if provider == "google":
        client = GoogleDriveClient()
        if client.is_connected():
            return client
        return None
    if provider == "dropbox":
        client = DropboxClient()
        if client.is_connected():
            return client
        return None
    return None
