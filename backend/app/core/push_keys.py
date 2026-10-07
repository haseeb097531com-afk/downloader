"""VAPID key pair management for web push notifications."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_KEYS_FILE: Path = Path(settings.DATA_DIR) / "vapid_keys.json"


def _generate_keypair() -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return {"private_key": private_pem, "public_key": public_pem}


def _load_keys() -> dict:
    if not _KEYS_FILE.exists():
        return {}
    try:
        with _KEYS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "private_key" not in data or "public_key" not in data:
            return {}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read VAPID keys: %s", exc)
        return {}


def _persist_keys(data: dict) -> None:
    _KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _KEYS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(_KEYS_FILE)


def get_public_key() -> str:
    data = _load_keys()
    if not data:
        data = _generate_keypair()
        _persist_keys(data)
    return data["public_key"]


def get_private_key() -> str:
    data = _load_keys()
    if not data:
        data = _generate_keypair()
        _persist_keys(data)
    return data["private_key"]


def get_claims(sub: str) -> dict:
    return {
        "sub": sub,
        "typ": "push",
    }
