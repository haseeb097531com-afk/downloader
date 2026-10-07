"""Celery task for AI video analysis."""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app
from app.services.ai.analysis_pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.ai_tasks.analysis_task")
def analysis_task(download_id: str) -> dict:
    """Run transcription, summarization, and optional translation for a download.

    Args:
        download_id: Primary key of the download to analyze.

    Returns:
        A result dict with ``status`` and either ``analysis_id`` or ``error``.
    """
    pipeline = AnalysisPipeline()
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, pipeline.analyze_download(download_id))
                analysis = future.result(timeout=600)
        else:
            analysis = loop.run_until_complete(pipeline.analyze_download(download_id))
    except RuntimeError:
        analysis = asyncio.run(pipeline.analyze_download(download_id))
    except Exception as exc:
        logger.warning("Analysis task error: %s", exc)
        return {"status": "failed", "error": str(exc)}

    if analysis is None:
        return {"status": "failed", "error": "Download not found"}

    return {"status": analysis.status.value, "analysis_id": str(analysis.id), "error": analysis.error}


@celery_app.task(name="app.workers.ai_tasks.translation_task")
def translation_task(download_id: str, target_lang: str) -> dict:
    """Translate an existing SRT into ``target_lang``.

    Args:
        download_id: Primary key of the download whose analysis to update.
        target_lang: Target language code, e.g. ``"ur"``.

    Returns:
        Result dict with status and output path.
    """
    import asyncio
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.video_analysis import VideoAnalysis
    from app.services.ai.translator import AnalysisError, Translator

    async def _translate() -> dict:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(VideoAnalysis).where(VideoAnalysis.download_id == download_id))
            analysis = result.scalars().first()
            if analysis is None or not analysis.srt_path:
                return {"status": "failed", "error": "Analysis or SRT not found"}

            subtitles_dir = Path(analysis.srt_path).parent
            output_path = subtitles_dir / f"{analysis.id}_{target_lang}.srt"
            translator = Translator()
            try:
                output = translator.translate_srt(analysis.srt_path, target_lang, str(output_path))
                translated = dict(analysis.translated or {})
                translated[target_lang] = output
                analysis.translated = translated
                await db.commit()
                await db.refresh(analysis)
                return {"status": "completed", "analysis_id": str(analysis.id), "path": output}
            except AnalysisError as exc:
                return {"status": "failed", "error": str(exc)}

    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _translate())
                return future.result(timeout=300)
        return loop.run_until_complete(_translate())
    except RuntimeError:
        return asyncio.run(_translate())
    except Exception as exc:
        logger.warning("Translation task error: %s", exc)
        return {"status": "failed", "error": str(exc)}
