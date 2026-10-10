"""Encrypted API key store for integrations.

Provides Fernet-encrypted key-value storage for API keys and secrets.
Keys are NEVER persisted in plain text.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - optional dependency guard
    Fernet = None  # type: ignore[misc,assignment]
    InvalidToken = Exception  # type: ignore[misc,assignment]


class KeyStore:
    """Encrypted key persistence backed by ``DATA_DIR/api_keys.json``.

    The file is encrypted with Fernet. The key is derived from
    ``settings.SECRET_KEY`` via SHA-256 + base64url so the same secret can be
    reused across restarts without storing the raw Fernet key separately.
    """

    _CACHE: Optional[dict[str, dict[str, Any]]] = None

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
        return Path(settings.DATA_DIR) / "api_keys.json"

    @classmethod
    def load(cls) -> dict[str, dict[str, Any]]:
        """Return the decrypted key map, or an empty dict when the file is absent/corrupt."""
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
            logger.warning("Failed to load API keys: %s", exc)
            cls._CACHE = {}
            return cls._CACHE

    @classmethod
    def save(cls, keys: dict[str, dict[str, Any]]) -> None:
        """Encrypt and persist the key map atomically."""
        cls._CACHE = dict(keys)
        path = cls._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            if Fernet is None:
                raise RuntimeError("cryptography package is not installed")
            f = Fernet(cls._key())
            plaintext = json.dumps(keys, indent=2).encode("utf-8")
            tmp.write_bytes(f.encrypt(plaintext))
            tmp.replace(path)
        except (InvalidToken, OSError, RuntimeError) as exc:
            logger.error("Failed to save API keys: %s", exc)
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @classmethod
    def get(cls, name: str) -> Optional[dict[str, Any]]:
        """Get a key by name (returns decrypted value)."""
        return cls.load().get(name)

    @classmethod
    def get_decrypted_value(cls, name: str) -> Optional[str]:
        """Get just the decrypted value string for a key."""
        key = cls.get(name)
        if key and "value" in key:
            return key["value"]
        return None

    @classmethod
    def set(cls, name: str, value: str, category: str = "other", metadata: Optional[dict] = None) -> dict[str, Any]:
        """Set a key with encryption."""
        keys = cls.load()
        now = datetime.utcnow().isoformat()
        keys[name] = {
            "value": value,
            "category": category,
            "metadata": metadata or {},
            "is_set": True,
            "created_at": keys.get(name, {}).get("created_at", now),
            "updated_at": now,
            "last_test_status": "untested",
            "last_test_at": None,
        }
        cls.save(keys)
        return keys[name]

    @classmethod
    def delete(cls, name: str) -> bool:
        """Delete a key."""
        keys = cls.load()
        if name in keys:
            del keys[name]
            cls.save(keys)
            return True
        return False

    @classmethod
    def list_all(cls) -> dict[str, dict[str, Any]]:
        """List all keys with masked values."""
        keys = cls.load()
        result = {}
        for name, data in keys.items():
            masked = cls._mask_value(data.get("value", ""))
            result[name] = {
                **data,
                "value": masked,  # Never return raw value
            }
        return result

    @classmethod
    def _mask_value(cls, value: str) -> str:
        """Mask a value showing only last 4 characters."""
        if not value:
            return ""
        if len(value) <= 4:
            return "•" * len(value)
        return "•" * (len(value) - 4) + value[-4:]

    @classmethod
    def update_test_status(cls, name: str, status: str) -> bool:
        """Update the last test status for a key."""
        keys = cls.load()
        if name not in keys:
            return False
        keys[name]["last_test_status"] = status
        keys[name]["last_test_at"] = datetime.utcnow().isoformat()
        cls.save(keys)
        return True

    @classmethod
    def get_raw_ciphertext(cls, name: str) -> Optional[str]:
        """Get the raw encrypted blob for verification (first 12 chars only)."""
        path = cls._path()
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            if not data.strip():
                return None
            return data[:12].hex()  # First 12 bytes as hex for verification
        except Exception:
            return None