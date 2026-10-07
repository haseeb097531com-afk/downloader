"""Tests for the FFmpeg post-processing engine, pipeline, resource guard, and settings."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import redis_client
from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.schemas.settings import ProcessingSettings
from app.services.processor.ffmpeg_engine import FFmpegEngine, MediaInfo
from app.services.processor.pipeline import ProcessingPipeline
from app.services.processor.resource_guard import ResourceGuard
from app.workers.monitor_tasks import system_monitor_task


# --------------------------------------------------------------------------- #
# FFmpeg engine
# --------------------------------------------------------------------------- #


def _mock_process(returncode=0, stdout_data=b"", stderr_data=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout_data, stderr_data))
    return proc


@pytest.fixture
def ffmpeg():
    engine = FFmpegEngine(ffmpeg_path="ffmpeg", ffprobe_path="ffprobe")
    return engine


@pytest.mark.asyncio
async def test_check_available_true(ffmpeg, monkeypatch):
    monkeypatch.setattr("app.services.processor.ffmpeg_engine.shutil.which", lambda x: "/usr/bin/" + x)
    assert await ffmpeg.check_available() is True


@pytest.mark.asyncio
async def test_check_available_false(ffmpeg, monkeypatch):
    monkeypatch.setattr("app.services.processor.ffmpeg_engine.shutil.which", lambda x: None)
    assert await ffmpeg.check_available() is False


@pytest.mark.asyncio
async def test_get_media_info_parses_ffprobe_json(ffmpeg):
    probe_output = json.dumps({
        "format": {"duration": "120.5", "size": "1048576"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }).encode()

    async def fake_subprocess(*args, **kwargs):
        return _mock_process(stdout_data=probe_output)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        info = await ffmpeg.get_media_info("/tmp/video.mp4")

    assert isinstance(info, MediaInfo)
    assert info.duration == 120.5
    assert info.width == 1920
    assert info.height == 1080
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.size == 1048576


@pytest.mark.asyncio
async def test_merge_streams_uses_stream_copy_and_cleanup(ffmpeg, tmp_path):
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.m4a"
    output = tmp_path / "merged.mp4"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    captured: list = []

    async def fake_subprocess(*args, **kwargs):
        captured.extend(args)
        proc = _mock_process(returncode=0)
        Path(args[-1]).write_bytes(b"merged")
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        result = await ffmpeg.merge_streams(str(video), str(audio), str(output))

    assert "-c" in captured
    assert "copy" in captured
    assert result == str(output)
    assert not video.exists(), "Input video must be deleted after successful merge"
    assert not audio.exists(), "Input audio must be deleted after successful merge"


@pytest.mark.asyncio
async def test_merge_streams_does_not_delete_on_failure(ffmpeg, tmp_path):
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.m4a"
    output = tmp_path / "merged.mp4"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    async def fake_subprocess(*args, **kwargs):
        return _mock_process(returncode=1, stderr_data=b"boom")

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        with pytest.raises(RuntimeError, match="merge failed"):
            await ffmpeg.merge_streams(str(video), str(audio), str(output))

    assert video.exists(), "Input video must survive a failed merge"
    assert audio.exists(), "Input audio must survive a failed merge"


@pytest.mark.asyncio
async def test_embed_metadata_includes_flags(ffmpeg, tmp_path):
    target = tmp_path / "vid.mp4"
    target.write_bytes(b"data")
    captured: list = []

    async def fake_subprocess(*args, **kwargs):
        captured.extend(args)
        proc = _mock_process(returncode=0)
        tmp_path = str(target) + ".tmpmeta"
        Path(tmp_path).write_bytes(b"meta")
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        result = await ffmpeg.embed_metadata(str(target), {"title": "T", "artist": "A", "date": "2024", "comment": "C" * 600})

    assert result == str(target)
    assert "-metadata" in captured
    assert "title=T" in captured
    assert "artist=A" in captured
    assert "date=2024" in captured
    assert "comment=" + "C" * 500 in captured, "Comment must be truncated to 500 chars"
    assert "-c" in captured
    assert "copy" in captured


@pytest.mark.asyncio
async def test_generate_thumbnail_includes_ss_and_frames(ffmpeg, tmp_path):
    target = tmp_path / "vid.mp4"
    target.write_bytes(b"data")
    out = tmp_path / "thumb.jpg"
    captured: list = []

    async def fake_subprocess(*args, **kwargs):
        captured.extend(args)
        return _mock_process(returncode=0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        result = await ffmpeg.generate_thumbnail(str(target), str(out), at_second=5)

    assert result == str(out)
    assert "-ss" in captured
    assert "5" in captured
    assert "-frames:v" in captured
    assert "1" in captured


@pytest.mark.asyncio
async def test_normalize_to_mp4_uses_h264_aac(ffmpeg, tmp_path):
    src = tmp_path / "src.webm"
    dst = tmp_path / "dst.mp4"
    src.write_bytes(b"data")
    captured: list = []

    async def fake_subprocess(*args, **kwargs):
        captured.extend(args)
        return _mock_process(returncode=0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        result = await ffmpeg.normalize_to_mp4(str(src), str(dst))

    assert result == str(dst)
    assert "-c:v" in captured
    assert "libx264" in captured
    assert "-c:a" in captured
    assert "aac" in captured


# --------------------------------------------------------------------------- #
# Processing pipeline
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def pipeline(monkeypatch, tmp_path, db_session):
    engine = MagicMock()
    monkeypatch.setattr("app.services.processor.pipeline.FFmpegEngine", lambda: engine)
    monkeypatch.setattr(settings, "DOWNLOAD_DIR", str(tmp_path))
    return ProcessingPipeline(db_session=db_session), engine


def _make_download(db_session, **kwargs):
    download = Download(
        id=str(uuid.uuid4()),
        title=kwargs.get("title", "Test"),
        platform="youtube",
        content_type="video",
        url="https://example.com/video",
        status=DownloadStatus.COMPLETED,
        progress=100.0,
        file_path=kwargs.get("file_path"),
        metadata_json=kwargs.get("metadata_json", {}),
        is_watermark_free=True,
    )
    db_session.add(download)
    return download


@pytest.mark.asyncio
async def test_pipeline_sets_processed_true_on_success(db_session, pipeline, tmp_path):
    pl, engine = pipeline
    target = tmp_path / "video.mp4"
    target.write_bytes(b"video")
    download = _make_download(db_session, file_path=str(target))
    await db_session.commit()
    Path(settings.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    engine.merge_streams.return_value = None
    engine.embed_metadata.return_value = None
    engine.generate_thumbnail.return_value = None

    await pl.process_download(download.id)

    result = await db_session.execute(select(Download).where(Download.id == download.id))
    refreshed = result.scalars().first()
    assert refreshed.processed is True
    assert refreshed.processing_error is None
    assert refreshed.status == DownloadStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_sets_processed_false_on_failure(db_session, pipeline, tmp_path):
    pl, engine = pipeline
    target = tmp_path / "video.mp4"
    target.write_bytes(b"video")
    engine.embed_metadata.side_effect = RuntimeError("boom")
    download = _make_download(db_session, file_path=str(target))
    await db_session.commit()

    await pl.process_download(download.id)

    result = await db_session.execute(select(Download).where(Download.id == download.id))
    refreshed = result.scalars().first()
    assert refreshed.processed is False
    assert refreshed.processing_error is not None
    assert refreshed.status == DownloadStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_merges_separate_streams_when_enabled(db_session, pipeline, tmp_path, monkeypatch):
    pl, engine = pipeline
    monkeypatch.setattr(settings, "AUTO_MERGE", True)

    video = tmp_path / "clip.mp4"
    audio = tmp_path / "clip.m4a"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    download = _make_download(db_session, file_path=str(video))
    await db_session.commit()

    engine.merge_streams.return_value = str(video)

    await pl.process_download(download.id)

    engine.merge_streams.assert_called_once()
    args = engine.merge_streams.call_args[0]
    assert args[0] == str(video)
    assert args[1] == str(audio)


# --------------------------------------------------------------------------- #
# Resource guard
# --------------------------------------------------------------------------- #


def test_resource_guard_concurrency_math(monkeypatch):
    monkeypatch.setattr("psutil.cpu_count", lambda logical=True: 8)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=16 * 1024 ** 3))
    assert ResourceGuard.get_recommended_concurrency() == max(1, min(7, 8))


def test_resource_guard_minimum_is_one(monkeypatch):
    monkeypatch.setattr("psutil.cpu_count", lambda logical=True: 1)
    monkeypatch.setattr("psutil.virtual_memory", lambda: MagicMock(total=1 * 1024 ** 3))
    assert ResourceGuard.get_recommended_concurrency() == 1


@pytest.mark.asyncio
async def test_resource_guard_throttle_flag(monkeypatch):
    store: dict = {}
    monkeypatch.setattr("app.services.processor.resource_guard.psutil.cpu_percent", lambda interval=1: 100.0)
    monkeypatch.setattr("app.services.processor.resource_guard.psutil.virtual_memory", lambda: MagicMock(percent=50.0))
    monkeypatch.setattr(redis_client, "set_throttle", lambda client=None: store.__setitem__("throttle", "1") or True)
    monkeypatch.setattr(redis_client, "clear_throttle", lambda client=None: store.pop("throttle", None) is not None)
    monkeypatch.setattr(redis_client, "is_throttled", lambda client=None: "throttle" in store)

    system_monitor_task()
    assert redis_client.is_throttled() is True

    system_monitor_task()
    assert redis_client.is_throttled() is True

    monkeypatch.setattr("app.services.processor.resource_guard.psutil.cpu_percent", lambda interval=1: 10.0)
    system_monitor_task()
    assert redis_client.is_throttled() is False


# --------------------------------------------------------------------------- #
# Settings endpoints
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def client(db_session, download_dir, monkeypatch):
    import app.main as main_module
    from app.db.database import get_db

    async def override_get_db():
        yield db_session

    monkeypatch.setattr(settings, "DATA_DIR", str(download_dir))
    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_settings_get_returns_defaults(client):
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["auto_merge"] is True
    assert body["max_cpu_percent"] == 90


@pytest.mark.asyncio
async def test_settings_put_persists_and_returns_updated(client, download_dir):
    response = await client.put("/api/v1/settings", json={"auto_merge": False, "max_cpu_percent": 50})
    assert response.status_code == 200
    body = response.json()
    assert body["auto_merge"] is False
    assert body["max_cpu_percent"] == 50

    persisted = (Path(download_dir) / "settings.json").read_text()
    assert "auto_merge" in persisted
