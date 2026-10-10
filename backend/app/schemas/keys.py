"""Schemas for API key management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KeyCreate(BaseModel):
    """Request to create/update a key."""
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1)
    category: str = Field(default="other", max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KeyUpdate(BaseModel):
    """Request to update a key (value optional for partial updates)."""
    value: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, max_length=50)
    metadata: Optional[dict[str, Any]] = Field(default=None)


class KeyResponse(BaseModel):
    """Response for a single key (masked value)."""
    name: str
    value: str  # Always masked
    category: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_set: bool
    created_at: str
    updated_at: str
    last_test_status: str  # ok | fail | untested
    last_test_at: Optional[str] = None


class KeyListResponse(BaseModel):
    """Response for listing keys."""
    keys: dict[str, KeyResponse]


class KeyRegistryResponse(BaseModel):
    """Response for the key registry."""
    keys: list[dict[str, Any]]
    categories: list[str]


class KeyTestRequest(BaseModel):
    """Request to test a key (optional extra params for provider-specific tests)."""
    extra: dict[str, Any] = Field(default_factory=dict)


class KeyTestResponse(BaseModel):
    """Response for key test."""
    name: str
    status: str  # ok | fail
    message: str
    tested_at: str


class KeyCiphertextResponse(BaseModel):
    """Response showing raw ciphertext prefix for verification."""
    name: str
    ciphertext_prefix: str  # First 12 bytes as hex