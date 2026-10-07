"""AI summarization service with Ollama primary and extractive fallback."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when an AI analysis step fails."""


@dataclass
class SummaryResult:
    """Summary payload produced by the summarizer."""

    summary: str
    keywords: List[str] = field(default_factory=list)


class Summarizer:
    """Summarize transcripts via Ollama when available, otherwise extractively."""

    def summarize(self, transcript: str, language: Optional[str] = None) -> SummaryResult:
        """Return a short summary and up to 5 keywords.

        Args:
            transcript: Plain text transcript.
            language: Detected language code, optional.

        Returns:
            A :class:`SummaryResult` with summary text and keyword list.
        """
        text = (transcript or "").strip()
        if not text:
            return SummaryResult(summary="", keywords=[])

        ollama_host = getattr(settings, "ollama_host", None)
        if ollama_host:
            ollama_result = self._try_ollama(text)
            if ollama_result is not None:
                return ollama_result

        return self._extractive(text)

    def _try_ollama(self, transcript: str) -> Optional[SummaryResult]:
        host = getattr(settings, "ollama_host", "http://localhost:11434") or "http://localhost:11434"
        model = getattr(settings, "ollama_model", "llama3") or "llama3"
        prompt = (
            "Summarize this transcript in 3-5 sentences. Then list 5 keywords. "
            "Reply JSON only in the form {\"summary\":\"...\",\"keywords\":[\"...\"]}.\n\n"
            f"{transcript[:4000]}"
        )
        try:
            import httpx

            response = httpx.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
                timeout=30,
            )
            if response.status_code != 200:
                return None
            body = response.json()
            raw = (body.get("response") or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group(0))
            summary = str(data.get("summary", "")).strip()
            keywords = [str(k).strip() for k in data.get("keywords", [])][:5]
            if not summary:
                return None
            return SummaryResult(summary=summary, keywords=keywords)
        except Exception as exc:
            logger.debug("Ollama summarization failed: %s", exc)
            return None

    def _extractive(self, transcript: str) -> SummaryResult:
        """Build an extractive summary by sentence word-frequency score."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript) if s.strip()]
        if not sentences:
            return SummaryResult(summary="", keywords=[])

        words = re.findall(r"[A-Za-z]{3,}", transcript.lower())
        stop = {"the", "and", "for", "with", "this", "that", "from", "have", "your", "were", "been", "will", "would", "could", "should", "about", "which", "their", "there"}
        freq = Counter(w for w in words if w not in stop)
        keywords = [word for word, _ in freq.most_common(5)]

        if len(sentences) <= 3:
            return SummaryResult(summary=" ".join(sentences), keywords=keywords)

        scored = []
        for sentence in sentences:
            score = sum(freq.get(w, 0) for w in re.findall(r"[A-Za-z]{3,}", sentence.lower()))
            scored.append((score, sentence))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [sentence for _, sentence in scored[:4]]
        top.sort(key=lambda s: sentences.index(s))
        return SummaryResult(summary=" ".join(top), keywords=keywords)
