"""Key registry - single source of truth for all known integration keys.

Backend and frontend both read this to render UI dynamically.
Adding a key later = one constant edit, no UI change.
"""

from __future__ import annotations

from typing import Any

KNOWN_KEYS: list[dict[str, Any]] = [
    {
        "name": "llm_provider",
        "label": "AI Provider",
        "category": "ai",
        "required_for": ["ai_search", "transcript", "clip_maker", "analytics_insights"],
        "test": "ping the provider with a 1-token request",
        "optional": True,
        "secret": False,
        "description": "AI provider name (e.g., openai, anthropic, ollama)",
    },
    {
        "name": "llm_api_key",
        "label": "AI API Key",
        "category": "ai",
        "required_for": ["ai_search", "transcript", "clip_maker", "analytics_insights"],
        "test": "ping the provider with a 1-token request",
        "optional": True,
        "secret": True,
        "description": "API key for the AI provider",
    },
    {
        "name": "llm_model",
        "label": "AI Model ID",
        "category": "ai",
        "required_for": ["ai_search", "transcript", "clip_maker", "analytics_insights"],
        "optional": True,
        "secret": False,
        "description": "Model identifier (e.g., gpt-4o, claude-3-sonnet, llama3)",
    },
    {
        "name": "telegram_bot_token",
        "label": "Telegram Bot Token",
        "category": "telegram",
        "required_for": ["telegram_bot"],
        "test": "getMe()",
        "optional": True,
        "secret": True,
        "description": "Bot token from @BotFather",
    },
    {
        "name": "payment_public_key",
        "label": "Payment Public Key",
        "category": "payment",
        "optional": True,
        "secret": False,
        "note": "Only when switching payment_mode to a real gateway",
        "description": "Public key for payment gateway (e.g., Stripe publishable key)",
    },
    {
        "name": "payment_secret_key",
        "label": "Payment Secret Key",
        "category": "payment",
        "optional": True,
        "secret": True,
        "note": "Only when switching payment_mode to a real gateway",
        "description": "Secret key for payment gateway (e.g., Stripe secret key)",
    },
    {
        "name": "cookies_path",
        "label": "Cookies File Path (private videos)",
        "category": "cookies",
        "test": "os.path.exists + readable",
        "optional": True,
        "secret": False,
        "description": "Path to cookies.txt for private/age-restricted videos",
    },
]

CATEGORIES = ["ai", "telegram", "payment", "cookies", "other"]

def get_registry() -> list[dict]:
    """Return the key registry for dynamic UI rendering."""
    return KNOWN_KEYS

def get_keys_by_category(category: str) -> list[dict]:
    """Filter keys by category."""
    return [k for k in KNOWN_KEYS if k["category"] == category]

def get_required_keys_for_feature(feature: str) -> list[str]:
    """Get list of key names required for a specific feature."""
    required = []
    for k in KNOWN_KEYS:
        if feature in k.get("required_for", []):
            required.append(k["name"])
    return required

def is_key_optional(name: str) -> bool:
    """Check if a key is optional."""
    for k in KNOWN_KEYS:
        if k["name"] == name:
            return k.get("optional", True)
    return True