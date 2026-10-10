"""API endpoints for encrypted API key management."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps_auth import get_current_user, require_role
from app.core.config import settings
from app.schemas.keys import (
    KeyCreate,
    KeyCiphertextResponse,
    KeyListResponse,
    KeyRegistryResponse,
    KeyResponse,
    KeyTestRequest,
    KeyTestResponse,
    KeyUpdate,
)
from app.services.integrations.key_store import KeyStore
from app.services.integrations.registry import (
    CATEGORIES,
    KNOWN_KEYS,
    get_registry,
    is_key_optional,
)
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings/keys", tags=["Settings - API Keys"])


def require_owner(user: User = Depends(require_role(UserRole.OWNER))) -> User:
    """Ensure only owner can manage API keys."""
    if user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can manage API keys",
        )
    return user


def require_owner_or_subadmin(user: User = Depends(get_current_user)) -> User:
    """Allow owner and sub_admin to view keys."""
    if user.role not in (UserRole.OWNER, UserRole.SUB_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return user


@router.get("/registry", response_model=KeyRegistryResponse)
async def get_key_registry(
    current_user: User = Depends(require_owner_or_subadmin),
) -> KeyRegistryResponse:
    """Return the key registry for dynamic UI rendering."""
    return KeyRegistryResponse(keys=KNOWN_KEYS, categories=CATEGORIES)


@router.get("", response_model=KeyListResponse)
async def list_keys(
    current_user: User = Depends(require_owner_or_subadmin),
) -> KeyListResponse:
    """List all keys with masked values and status."""
    keys_data = KeyStore.list_all()
    keys = {}
    for name, data in keys_data.items():
        keys[name] = KeyResponse(**data)
    return KeyListResponse(keys=keys)


@router.get("/{name}", response_model=KeyResponse)
async def get_key(
    name: str,
    current_user: User = Depends(require_owner_or_subadmin),
) -> KeyResponse:
    """Get a single key (masked)."""
    key_data = KeyStore.get(name)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not found",
        )
    return KeyResponse(**key_data)


@router.put("/{name}", response_model=KeyResponse)
async def set_key(
    name: str,
    payload: KeyCreate,
    current_user: User = Depends(require_owner),
) -> KeyResponse:
    """Create or update a key (encrypts on write)."""
    if payload.name != name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name in path must match name in body",
        )
    
    # Validate key exists in registry
    key_def = next((k for k in KNOWN_KEYS if k["name"] == name), None)
    if not key_def:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown key '{name}'. Use /registry to see valid keys.",
        )
    
    key_data = KeyStore.set(
        name=name,
        value=payload.value,
        category=payload.category,
        metadata=payload.metadata,
    )
    return KeyResponse(**key_data)


@router.patch("/{name}", response_model=KeyResponse)
async def update_key(
    name: str,
    payload: KeyUpdate,
    current_user: User = Depends(require_owner),
) -> KeyResponse:
    """Partially update a key (value, category, metadata)."""
    existing = KeyStore.get(name)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not found",
        )
    
    # Build updated data
    value = payload.value if payload.value is not None else existing.get("value", "")
    category = payload.category if payload.category is not None else existing.get("category", "other")
    metadata = payload.metadata if payload.metadata is not None else existing.get("metadata", {})
    
    key_data = KeyStore.set(
        name=name,
        value=value,
        category=category,
        metadata=metadata,
    )
    return KeyResponse(**key_data)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    name: str,
    current_user: User = Depends(require_owner),
) -> None:
    """Delete a key."""
    if not KeyStore.delete(name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not found",
        )


@router.post("/{name}/test", response_model=KeyTestResponse)
async def test_key(
    name: str,
    payload: KeyTestRequest,
    current_user: User = Depends(require_owner),
) -> KeyTestResponse:
    """Run the provider's real health check for a key."""
    key_def = next((k for k in KNOWN_KEYS if k["name"] == name), None)
    if not key_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not found in registry",
        )
    
    if not KeyStore.get(name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not set",
        )
    
    test_status = "fail"
    message = "Test failed"
    
    try:
        if name == "telegram_bot_token":
            # Test Telegram bot token with getMe()
            import httpx
            token = KeyStore.get_decrypted_value(name)
            if not token:
                raise ValueError("Token not found")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        test_status = "ok"
                        message = f"Bot @{data['result'].get('username', 'unknown')} connected"
                    else:
                        message = f"Telegram API error: {data.get('description', 'unknown')}"
                else:
                    message = f"HTTP {resp.status_code}: {resp.text}"
        
        elif name in ("llm_api_key", "llm_provider", "llm_model"):
            # Test AI provider with a 1-token request
            import httpx
            provider = KeyStore.get_decrypted_value("llm_provider") or "openai"
            api_key = KeyStore.get_decrypted_value("llm_api_key")
            model = KeyStore.get_decrypted_value("llm_model") or "gpt-3.5-turbo"
            
            if not api_key:
                raise ValueError("AI API key not set")
            
            if provider == "openai":
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 1},
                    )
                    if resp.status_code == 200:
                        test_status = "ok"
                        message = f"OpenAI connected (model: {model})"
                    else:
                        message = f"OpenAI error: {resp.status_code} - {resp.text}"
            elif provider == "anthropic":
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 1},
                    )
                    if resp.status_code == 200:
                        test_status = "ok"
                        message = f"Anthropic connected (model: {model})"
                    else:
                        message = f"Anthropic error: {resp.status_code} - {resp.text}"
            elif provider == "ollama":
                import httpx
                host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(f"{host}/api/tags")
                    if resp.status_code == 200:
                        test_status = "ok"
                        message = f"Ollama connected ({host})"
                    else:
                        message = f"Ollama error: {resp.status_code}"
            else:
                message = f"Unknown provider: {provider}"
        
        elif name == "cookies_path":
            # Test cookies file exists and is readable
            import os
            path = KeyStore.get_decrypted_value(name)
            if not path:
                raise ValueError("Cookies path not set")
            if os.path.exists(path) and os.access(path, os.R_OK):
                test_status = "ok"
                message = f"Cookies file found and readable: {path}"
            else:
                message = f"Cookies file not found or not readable: {path}"
        
        elif name in ("payment_public_key", "payment_secret_key"):
            # Payment keys - basic validation only
            value = KeyStore.get_decrypted_value(name)
            if value and len(value) > 10:
                test_status = "ok"
                message = "Payment key format appears valid"
            else:
                message = "Payment key missing or too short"
        
        else:
            message = f"No test implemented for key type: {key_def.get('category', 'unknown')}"
    
    except Exception as exc:
        logger.warning("Key test failed for %s: %s", name, exc)
        test_status = "fail"
        message = f"Test error: {exc}"
    
    # Update store with test result
    KeyStore.update_test_status(name, test_status)
    
    from datetime import datetime
    return KeyTestResponse(
        name=name,
        status=test_status,
        message=message,
        tested_at=datetime.utcnow().isoformat(),
    )


@router.get("/{name}/ciphertext", response_model=KeyCiphertextResponse)
async def get_key_ciphertext(
    name: str,
    current_user: User = Depends(require_owner),
) -> KeyCiphertextResponse:
    """Get raw ciphertext prefix for encryption verification (first 12 bytes as hex)."""
    if not KeyStore.get(name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{name}' not found",
        )
    prefix = KeyStore.get_raw_ciphertext(name)
    return KeyCiphertextResponse(name=name, ciphertext_prefix=prefix or "")