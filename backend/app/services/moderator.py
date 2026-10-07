"""Content moderation service for safe mode and parental controls."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModerationResult:
    """Result of a content moderation check."""

    flagged: bool = False
    reasons: List[str] = field(default_factory=list)
    score: float = 0.0


class ContentModerator:
    """Moderate downloaded content against a keyword blacklist and optional LLM signal."""

    def __init__(
        self,
        blacklist: Optional[List[str]] = None,
        sensitivity: float = 0.5,
    ) -> None:
        self.blacklist = [kw.strip() for kw in (blacklist or settings.KEYWORD_BLACKLIST) if kw.strip()]
        self.sensitivity = sensitivity

    def check_content(
        self,
        title: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        transcript: Optional[str] = None,
    ) -> ModerationResult:
        """Check whether the supplied content should be flagged.

        The score combines keyword hits (title is weighted 2x) with an optional
        local Ollama signal when ``settings.USE_LLM_CATEGORIZE`` is enabled and
        the host is reachable.
        """
        reasons: List[str] = []
        keyword_score = self._keyword_score(title, description, tags, transcript)

        llm_score = 0.0
        if getattr(settings, "USE_LLM_CATEGORIZE", False):
            llm_score = self._ollama_signal(title, description, transcript)

        raw_score = max(keyword_score, llm_score)
        flagged = raw_score > self.sensitivity
        if flagged:
            reasons = self._reasons_from_score(keyword_score, llm_score)

        return ModerationResult(flagged=flagged, reasons=reasons, score=raw_score)

    # ------------------------------------------------------------------ #
    # Keyword scoring
    # ------------------------------------------------------------------ #

    def _keyword_score(self, title: str, description: str, tags: Optional[List[str]], transcript: Optional[str]) -> float:
        """Return a 0..1 score from blacklist keyword matches."""
        haystacks = []
        if title:
            haystacks.append((title.lower(), 2.0))
        if description:
            haystacks.append((description.lower(), 1.0))
        if tags:
            for tag in tags:
                haystacks.append((str(tag).lower(), 0.5))
        if transcript:
            haystacks.append((transcript.lower(), 1.0))

        if not haystacks or not self.blacklist:
            return 0.0

        max_score = 0.0
        for keyword in self.blacklist:
            escaped = re.escape(keyword.lower())
            for text, weight in haystacks:
                if re.search(escaped, text):
                    max_score = max(max_score, weight)
                    break

        # Normalise to 0..1 using the highest possible weight (2.0) as the ceiling.
        return min(max_score / 2.0, 1.0)

    def _reasons_from_score(self, keyword_score: float, llm_score: float) -> List[str]:
        reasons: List[str] = []
        if keyword_score > 0:
            reasons.append("matched_keyword_blacklist")
        if llm_score > 0:
            reasons.append("llm_moderation_signal")
        return reasons

    # ------------------------------------------------------------------ #
    # Ollama secondary signal
    # ------------------------------------------------------------------ #

    def _ollama_signal(self, title: str, description: str, transcript: Optional[str]) -> float:
        """Ask the local Ollama model whether the content is family-appropriate."""
        host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        model = getattr(settings, "OLLAMA_MODEL", "llama3")
        prompt_parts = [
            "Is the following content appropriate for a family audience?",
            "Reply with YES or NO followed by a short reason.",
            "",
        ]
        if title:
            prompt_parts.append(f"Title: {title}")
        if description:
            prompt_parts.append(f"Description: {description[:500]}")
        if transcript:
            prompt_parts.append(f"Transcript: {transcript[:1000]}")

        prompt = "\n".join(prompt_parts)
        try:
            response = httpx.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
                timeout=10,
            )
            response.raise_for_status()
            text = response.json().get("response", "").strip().upper()
            if text.startswith("NO"):
                return 0.8
        except Exception as exc:
            logger.debug("Ollama moderation signal failed: %s", exc)
        return 0.0

    # ------------------------------------------------------------------ #
    # PIN helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def hash_pin(pin: str) -> str:
        """Return a deterministic hash for a 4-digit PIN."""
        pin = pin.strip()
        if not re.fullmatch(r"\d{4}", pin):
            raise ValueError("PIN must be exactly 4 digits")
        salt = b"mediavault-salt"
        return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000).hex()

    @staticmethod
    def verify_pin(pin: str, pin_hash: str) -> bool:
        """Return True when the PIN matches the stored hash."""
        try:
            return ContentModerator.hash_pin(pin) == pin_hash
        except ValueError:
            return False
