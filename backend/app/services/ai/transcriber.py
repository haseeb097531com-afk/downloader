"""AI transcription service using faster-whisper."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when an AI analysis step fails."""


@dataclass
class Segment:
    """One transcribed time span."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Result of a transcription run."""

    language: Optional[str]
    segments: List[Segment]
    text: str


class Transcriber:
    """Lazy-loading Whisper transcription wrapper.

    The underlying WhisperModel is created on first use so importing this module
    never triggers the heavier model download or GPU initialization.
    """

    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise AnalysisError("faster-whisper is not installed") from exc
            model_name = getattr(settings, "whisper_model", "base") or "base"
            try:
                self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
            except Exception as exc:
                raise AnalysisError(f"Failed to load Whisper model: {exc}") from exc
        return self._model

    def transcribe(self, file_path: str) -> TranscriptionResult:
        """Transcribe ``file_path`` and return segments.

        Args:
            file_path: Absolute path to a media file.

        Returns:
            A :class:`TranscriptionResult` with detected language, segments, and full text.

        Raises:
            AnalysisError: On missing file, model load failure, or transcription failure.
        """
        path = Path(file_path)
        if not path.exists():
            raise AnalysisError(f"Media file not found: {file_path}")

        model = self._ensure_model()

        segments: List[Segment] = []
        full_text_parts: List[str] = []
        detected_language: Optional[str] = None

        try:
            segments_iter, info = model.transcribe(str(path), beam_size=5)
            detected_language = getattr(info, "language", None)
            for segment in segments_iter:
                seg = Segment(start=float(segment.start), end=float(segment.end), text=segment.text.strip())
                segments.append(seg)
                full_text_parts.append(seg.text)
        except Exception as exc:
            raise AnalysisError(f"Transcription failed: {exc}") from exc

        return TranscriptionResult(
            language=detected_language,
            segments=segments,
            text=" ".join(full_text_parts).strip(),
        )

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Format seconds as ``HH:MM:SS,mmm`` for SRT files."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def write_srt(self, segments: List[Segment], output_path: str) -> str:
        """Write an SRT file from ``segments`` to ``output_path``.

        Args:
            segments: Ordered list of transcribed segments.
            output_path: Target SRT file path.

        Returns:
            The ``output_path`` on success.

        Raises:
            AnalysisError: If the output directory cannot be created or the file cannot be written.
        """
        dest = Path(output_path)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AnalysisError(f"Cannot create subtitle directory: {exc}") from exc

        try:
            lines: List[str] = []
            for idx, segment in enumerate(segments, start=1):
                start = self.format_timestamp(segment.start)
                end = self.format_timestamp(segment.end)
                lines.append(str(idx))
                lines.append(f"{start} --> {end}")
                lines.append(segment.text or "")
                lines.append("")
            dest.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            raise AnalysisError(f"Cannot write SRT file: {exc}") from exc

        return str(dest)
