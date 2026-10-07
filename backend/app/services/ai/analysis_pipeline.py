"""AI analysis pipeline for completed downloads."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.download import Download
from app.models.user import User
from app.models.video_analysis import AnalysisStatus, VideoAnalysis
from app.services.ai.summarizer import AnalysisError, SummaryResult, Summarizer
from app.services.ai.transcriber import AnalysisError as TranscriptionError, Segment, Transcriber
from app.services.ai.translator import AnalysisError as TranslationError, Translator

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Run transcription, summarization, and translation for one download."""

    def __init__(self, current_user: Optional[User] = None) -> None:
        self.current_user = current_user
        self._transcriber = Transcriber()
        self._summizer = Summarizer()
        self._translator = Translator()

    def _owner_query(self, query, model):
        from app.api.deps_auth import OwnerFilter
        if self.current_user is not None:
            return OwnerFilter.apply(self.current_user, query, model)
        return query

    async def analyze_download(self, download_id: str) -> Optional[VideoAnalysis]:
        """Run the full AI analysis pipeline for ``download_id``.

        Creates a ``VideoAnalysis`` row, updates it in place through every step,
        and never propagates an exception to the caller: failures are recorded
        in ``status`` and ``error`` so the download itself stays completed.

        Args:
            download_id: Primary key of the download to analyze.

        Returns:
            The updated :class:`VideoAnalysis` row, or ``None`` if the download
            does not exist.
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                self._owner_query(select(Download).where(Download.id == download_id), Download)
            )
            download = result.scalars().first()
            if download is None:
                logger.warning("Analysis skipped: download %s not found", download_id)
                return None

            if not download.file_path or not Path(download.file_path).exists():
                analysis = VideoAnalysis(
                    download_id=download_id,
                    status=AnalysisStatus.FAILED,
                    error="Media file not found for analysis",
                    owner_id=self.current_user.id if self.current_user else None,
                )
                db.add(analysis)
                await db.commit()
                await db.refresh(analysis)
                return analysis

            analysis = VideoAnalysis(
                download_id=download_id,
                status=AnalysisStatus.PROCESSING,
                owner_id=self.current_user.id if self.current_user else None,
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            subtitles_dir = Path(settings.DOWNLOAD_DIR) / "subtitles"
            subtitles_dir.mkdir(parents=True, exist_ok=True)
            base_name = Path(download.file_path).stem

            try:
                # 1) Transcribe
                transcription = self._transcriber.transcribe(download.file_path)
                analysis.language = transcription.language
                analysis.transcript_text = transcription.text
                srt_name = f"{analysis.id}.srt"
                srt_path = subtitles_dir / srt_name
                self._transcriber.write_srt(transcription.segments, str(srt_path))
                analysis.srt_path = str(srt_path)
                await db.commit()

                # 2) Summarize
                summary: SummaryResult = self._summarizer.summarize(transcription.text, transcription.language)
                analysis.summary_text = summary.summary
                analysis.keywords = [str(k) for k in summary.keywords][:10]
                summary_path = Path(download.file_path).with_name(f"{base_name}.summary.md")
                try:
                    summary_path.write_text(
                        f"# Summary\n\n{summary.summary}\n\n## Keywords\n\n" + ", ".join(analysis.keywords or []),
                        encoding="utf-8",
                    )
                except OSError as exc:
                    logger.warning("Failed to write summary file: %s", exc)
                await db.commit()

                # 3) Translate
                auto_translate_langs = getattr(settings, "auto_translate_langs", []) or []
                translated: dict = {}
                for lang in auto_translate_langs:
                    try:
                        lang_srt = subtitles_dir / f"{analysis.id}_{lang}.srt"
                        self._translator.translate_srt(str(srt_path), lang, str(lang_srt))
                        translated[lang] = str(lang_srt)
                    except Exception as exc:
                        logger.warning("Translation to %s failed: %s", lang, exc)
                analysis.translated = translated

                analysis.status = AnalysisStatus.COMPLETED
                analysis.error = None
                await db.commit()
                await db.refresh(analysis)
                logger.info("Analysis complete for download %s", download_id)
                return analysis

            except Exception as exc:
                logger.warning("Analysis failed for download %s: %s", download_id, exc)
                analysis.status = AnalysisStatus.FAILED
                analysis.error = str(exc)[:2000]
                await db.commit()
                await db.refresh(analysis)
                return analysis
