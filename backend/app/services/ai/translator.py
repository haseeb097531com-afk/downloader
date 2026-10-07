"""SRT subtitle translation service using deep-translator."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when an AI analysis step fails."""


class Translator:
    """Translate SRT subtitle text while preserving timing structure."""

    def translate_srt(self, srt_path: str, target_lang: str, output_path: str) -> str:
        """Translate ``srt_path`` into ``target_lang`` and write to ``output_path``.

        Args:
            srt_path: Source SRT file.
            target_lang: BCP-47-like language code, e.g. ``"ur"`` or ``"es"``.
            output_path: Destination SRT file path.

        Returns:
            The ``output_path`` on success.

        Raises:
            AnalysisError: On read/write failure or translation API failure.
        """
        source = Path(srt_path)
        if not source.exists():
            raise AnalysisError(f"SRT file not found: {srt_path}")

        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise AnalysisError(f"Cannot read SRT: {exc}") from exc

        blocks = self._parse_blocks(raw)
        translated_blocks = self._translate_blocks(blocks, target_lang)

        dest = Path(output_path)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AnalysisError(f"Cannot create subtitle directory: {exc}") from exc

        try:
            lines: List[str] = []
            for idx, block in enumerate(translated_blocks, start=1):
                lines.append(str(idx))
                lines.append(block["timing"])
                lines.append(block["text"])
                lines.append("")
            dest.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            raise AnalysisError(f"Cannot write translated SRT: {exc}") from exc

        return str(dest)

    @staticmethod
    def _parse_blocks(raw: str) -> List[dict]:
        blocks: List[dict] = []
        parts = re.split(r"\n\s*\n", raw.strip())
        for part in parts:
            lines = [line.strip() for line in part.splitlines() if line.strip() != ""]
            if len(lines) < 3:
                continue
            timing = lines[1] if len(lines) > 1 else ""
            text = " ".join(lines[2:])
            blocks.append({"timing": timing, "text": text})
        return blocks

    def _translate_blocks(self, blocks: List[dict], target_lang: str) -> List[dict]:
        try:
            from deep_translator import GoogleTranslator
        except ImportError as exc:
            raise AnalysisError("deep-translator is not installed") from exc

        translated: List[dict] = []
        batch_size = 20
        for start in range(0, len(blocks), batch_size):
            batch = blocks[start:start + batch_size]
            texts = [block["text"] for block in batch]
            try:
                results = GoogleTranslator(target=target_lang).translate_batch(texts)
            except Exception as exc:
                raise AnalysisError(f"Translation failed for batch: {exc}") from exc
            for block, text in zip(batch, results):
                translated.append({"timing": block["timing"], "text": text or block["text"]})
        return translated
