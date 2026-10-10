"""Helper to read secrets from the encrypted key store.

Provides graceful fallback when keys are missing or tests failed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import settings
from app.services.integrations.key_store import KeyStore

logger = logging.getLogger(__name__)


async def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get a decrypted secret from the key store.

    Returns default if key not set or test failed.
    """
    key_data = KeyStore.get(name)
    if not key_data:
        return default
    
    # Check if key is set and test passed
    if not key_data.get("is_set", False):
        logger.debug("Key %s not set, returning default", name)
        return default
    
    test_status = key_data.get("last_test_status", "untested")
    if test_status == "fail":
        logger.warning("Key %s test failed, returning default", name)
        return default
    
    value = key_data.get("value")
    if value is None:
        return default
    
    return value


async def get_secret_or_env(name: str, env_var: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Get secret from store, falling back to environment variable."""
    # Try key store first
    value = await get_secret(name)
    if value is not None:
        return value
    
    # Fall back to environment variable
    if env_var:
        import os
        env_value = os.getenv(env_var)
        if env_value:
            logger.debug("Using environment variable %s for %s", env_var, name)
            return env_value
    
    return default


async def is_feature_enabled(feature: str) -> bool:
    """Check if a feature has all required keys configured and tested."""
    from app.services.integrations.registry import get_required_keys_for_feature
    
    required_keys = get_required_keys_for_feature(feature)
    if not required_keys:
        return True  # No keys required
    
    for key_name in required_keys:
        key_data = KeyStore.get(key_name)
        if not key_data or not key_data.get("is_set", False):
            return False
        test_status = key_data.get("last_test_status", "untested")
        if test_status == "fail":
            return False
    return True


def get_disabled_response(feature: str) -> dict[str, Any]:
    """Return a standard disabled response for a feature."""
    from app.services.integrations.registry import get_required_keys_for_feature
    
    required_keys = get_required_keys_for_feature(feature)
    return {
        "disabled": True,
        "reason": f"Feature requires keys: {', '.join(required_keys)}. Configure in Settings → Integrations & API Keys",
        "required_keys": required_keys,
    }