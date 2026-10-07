"""Tests for the media library service and download queue management (Phase 4A).

The suite runs against a real in-memory SQLite database and a real temporary
directory, so assertions cover actual SQL and actual filesystem behaviour. Only
the two genuinely external boundaries are faked: Redis (no broker in CI) and the
Celery dispatcher (no worker in CI).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import redis_client
from app.models.download import Download, DownloadStatus
from app.models.download_queue import QueueItem
from app.schemas.library import ImportResult, LibraryPage, LibraryStats
from app.services.downloader.download_orchestrator import (
    DownloadOrchestrator,
    InvalidTransition,
)
from app.services.storage.file_manager import FileAccessError, FileManager
from app.services.storage.library_service import (
    DownloadNotFound,
    LibraryPathError,
    LibraryService,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def make_download(
    db,
    *,
    title: str = "Sample Video",
    platform: str = "youtube",
    status: DownloadStatus = DownloadStatus.COMPLETED,
    file_path: str | None = None,
    file_size: int | None = None,
    completed_at: datetime | None = None,
    metadata: dict | None = None,
    content_type: str = "video",
) -> Download:
    """Stage a download row with a pre-assigned ID and return it.

    The ID is generated here rather than relying on the column default because this
    helper is synchronous while the session is async: no ``await commit()`` runs, so
    a column default would only be applied later during an autoflush. The row is
    added but not flushed, which makes the returned object safe to reference
    immediately and lets the next query autoflush it.

    Args:
        db: Active session.
        title: Media title.
        platform: Source platform.
        status: Row status; defaults to completed so library queries include it.
        file_path: Path stored on the record.
        file_size: Size recorded at download time.
        completed_at: Completion timestamp; defaults to now.
        metadata: Extracted metadata blob (used for creator attribution).
        content_type: ``"video"`` or ``"audio"``.

    Returns:
        The pending :class:`Download`, with ``id`` already populated.
    """
    download = Download(
        id=str(uuid.uuid4()),
        url=f"https://example.com/{title}",
        platform=platform,
        content_type=content_type,
        title=title,
        status=status,
        progress=100.0 if status == DownloadStatus.COMPLETED else 0.0,
        file_path=file_path,
        file_size=file_size,
        is_watermark_free=True,
        completed_at=completed_at if completed_at is not None else datetime.utcnow(),
        metadata_json=metadata,
    )
    db.add(download)
    return download


def make_media_file(root: Path, relative: str, size: int = 1024) -> Path:
    """Create a media file of ``size`` bytes under ``root`` and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size)
    return path


@pytest.fixture
def file_manager(download_dir) -> FileManager:
    """A :class:`FileManager` rooted at the temporary download directory."""
    return FileManager(download_dir)


@pytest.fixture
def library(db_session, file_manager) -> LibraryService:
    """A library service bound to the test database and temporary directory."""
    return LibraryService(db_session, file_manager)


# --------------------------------------------------------------------------- #
# Task 1: scan_library
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scan_library_returns_only_completed_downloads_present_on_disk(
    library, db_session, download_dir
):
    """Only completed downloads whose file exists are listed as present.

    A completed record with a missing file, a still-pending record and a file on
    disk with no record must all be excluded from the "exists" set.
    """
    present = make_media_file(Path(download_dir), "youtube/good.mp4", size=2048)
    make_download(db_session, title="Good", file_path=str(present), file_size=2048)

    # Completed, but the file was deleted outside the application.
    make_download(db_session, title="Vanished", file_path=str(Path(download_dir) / "youtube/gone.mp4"))

    # Never finished, and has a partial file on disk.
    partial = make_media_file(Path(download_dir), "youtube/wip.mp4")
    make_download(db_session, title="Pending", status=DownloadStatus.PENDING, file_path=str(partial))

    # Failed download, no file at all.
    make_download(db_session, title="Failed", status=DownloadStatus.FAILED)

    page = await library.scan_library(page=1, limit=24)

    assert isinstance(page, LibraryPage)
    assert page.total == 2, "Only the two completed records are counted"
    by_title = {item.title: item for item in page.items}
    assert set(by_title) == {"Good", "Vanished"}
    assert by_title["Good"].exists_on_disk is True
    assert by_title["Good"].file_size == 2048, "Size is read from disk, not the stale column"
    assert by_title["Vanished"].exists_on_disk is False
    assert by_title["Vanished"].file_size == 0
    assert page.page == 1
    assert page.limit == 24
    assert page.has_next is False


@pytest.mark.asyncio
async def test_scan_library_paginates_filters_and_searches(library, db_session, download_dir):
    """Pagination, platform filtering and title search all narrow the result set."""
    for index in range(7):
        path = make_media_file(Path(download_dir), f"youtube/clip_{index}.mp4")
        make_download(db_session, title=f"Video {index}", file_path=str(path))

    tiktok_path = make_media_file(Path(download_dir), "tiktok/dance.mp4")
    make_download(db_session, title="Dance", platform="tiktok", file_path=str(tiktok_path))

    first = await library.scan_library(page=1, limit=3)
    assert len(first.items) == 3
    assert first.total == 8
    assert first.total_pages == 3
    assert first.has_next is True

    last = await library.scan_library(page=3, limit=3)
    assert last.has_next is False

    only_youtube = await library.scan_library(page=1, limit=24, platform="youtube")
    assert only_youtube.total == 7
    assert {item.platform for item in only_youtube.items} == {"youtube"}

    searched = await library.scan_library(page=1, limit=24, search="Video 5")
    assert searched.total == 1
    assert searched.items[0].title == "Video 5"


@pytest.mark.asyncio
async def test_scan_library_escapes_wildcards_in_search(library, db_session, download_dir):
    """A search containing SQL wildcards is matched literally, not as a pattern."""
    path = make_media_file(Path(download_dir), "youtube/real.mp4")
    make_download(db_session, title="100% cotton", file_path=str(path))
    make_download(db_session, title="a_b", file_path=str(make_media_file(Path(download_dir), "youtube/ab.mp4")))
    make_download(db_session, title="axb", file_path=str(make_media_file(Path(download_dir), "youtube/axb.mp4")))

    result = await library.scan_library(page=1, limit=24, search="100%")
    assert result.total == 1, "'%' must be escaped so it does not match everything"
    assert result.items[0].title == "100% cotton"

    result = await library.scan_library(page=1, limit=24, search="a_b")
    assert result.total == 1, "'_' must be escaped so it does not match 'axb'"
    assert result.items[0].title == "a_b"


# --------------------------------------------------------------------------- #
# Task 1: get_library_stats
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_library_stats_platform_breakdown_math_is_correct(
    library, db_session, download_dir
):
    """Platform counts and byte totals are summed from disk, sorted by count."""
    youtube_a = make_media_file(Path(download_dir), "youtube/a.mp4", size=1000)
    youtube_b = make_media_file(Path(download_dir), "youtube/b.mp4", size=2000)
    tiktok_a = make_media_file(Path(download_dir), "tiktok/a.mp4", size=500)

    make_download(db_session, title="A", platform="youtube", file_path=str(youtube_a))
    make_download(db_session, title="B", platform="youtube", file_path=str(youtube_b))
    make_download(db_session, title="C", platform="tiktok", file_path=str(tiktok_a))

    # Not completed: must not appear anywhere in the stats.
    make_download(db_session, title="D", platform="youtube", status=DownloadStatus.PENDING)

    stats = await library.get_library_stats()

    assert isinstance(stats, LibraryStats)
    assert stats.total_files == 3
    assert stats.total_size_bytes == 3500

    breakdown = {item.platform: item for item in stats.platform_breakdown}
    assert breakdown["youtube"].count == 2
    assert breakdown["youtube"].total_size == 3000
    assert breakdown["tiktok"].count == 1
    assert breakdown["tiktok"].total_size == 500

    # Sorted by count descending.
    assert [item.platform for item in stats.platform_breakdown] == ["youtube", "tiktok"]


@pytest.mark.asyncio
async def test_library_stats_falls_back_to_recorded_size_for_missing_files(
    library, db_session, download_dir
):
    """A deleted file still contributes its recorded size, and is flagged missing."""
    make_download(
        db_session,
        title="Ghost",
        file_path=str(Path(download_dir) / "youtube/ghost.mp4"),
        file_size=4096,
    )
    present = make_media_file(Path(download_dir), "youtube/real.mp4", size=10)
    make_download(db_session, title="Real", file_path=str(present), file_size=999)

    stats = await library.get_library_stats()

    assert stats.missing_files == 1
    assert stats.total_size_bytes == 4096 + 10, "Recorded size is used when disk has no file"


@pytest.mark.asyncio
async def test_library_stats_7_day_chart_always_has_seven_buckets(
    library, db_session, download_dir
):
    """The chart emits one bucket per day for the last 7 days, oldest first."""
    today = datetime.utcnow().date()
    for offset in (0, 1, 6):
        day = datetime.combine(today - timedelta(days=offset), datetime.min.time())
        path = make_media_file(Path(download_dir), f"youtube/day_{offset}.mp4")
        make_download(db_session, title=f"d{offset}", file_path=str(path), completed_at=day)

    # Older than the window: counted in totals, absent from the chart.
    old_day = datetime.combine(today - timedelta(days=30), datetime.min.time())
    old_path = make_media_file(Path(download_dir), "youtube/old.mp4")
    make_download(db_session, title="old", file_path=str(old_path), completed_at=old_day)

    stats = await library.get_library_stats()

    assert len(stats.downloads_last_7_days) == 7
    counts = {bucket.date: bucket.count for bucket in stats.downloads_last_7_days}
    assert counts[today.isoformat()] == 1
    assert counts[(today - timedelta(days=6)).isoformat()] == 1
    assert sum(counts.values()) == 3, "The 30-day-old download is outside the window"
    assert stats.downloads_last_7_days[0].date < stats.downloads_last_7_days[-1].date


@pytest.mark.asyncio
async def test_library_stats_top_creators_from_metadata(library, db_session, download_dir):
    """Creators are ranked by download count, with unknown creators bucketed."""
    alice_path = make_media_file(Path(download_dir), "youtube/a1.mp4")
    alice_path2 = make_media_file(Path(download_dir), "youtube/a2.mp4")
    bob_path = make_media_file(Path(download_dir), "youtube/b1.mp4")

    make_download(db_session, title="a1", file_path=str(alice_path), metadata={"uploader_name": "alice"})
    make_download(db_session, title="a2", file_path=str(alice_path2), metadata={"uploader": "alice"})
    make_download(db_session, title="b1", file_path=str(bob_path), metadata={"username": "bob"})
    make_download(db_session, title="anon", file_path=str(make_media_file(Path(download_dir), "youtube/x.mp4")))

    stats = await library.get_library_stats()
    top = {creator.username: creator.count for creator in stats.top_creators}

    assert top["alice"] == 2
    assert top["bob"] == 1
    assert "Unknown" in top, "Downloads without metadata are still counted"
    assert len(stats.top_creators) <= 5


# --------------------------------------------------------------------------- #
# Task 1: rename / delete / open_folder
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_rename_file_updates_disk_and_database(library, db_session, download_dir):
    """Renaming moves the file on disk and rewrites the stored path and title."""
    original = make_media_file(Path(download_dir), "youtube/old name.mp4", size=64)
    download = make_download(db_session, title="Old Name", file_path=str(original))

    renamed = await library.rename_file(download.id, "new name.mp4")

    assert original.exists() is False
    assert Path(renamed.file_path).exists()
    assert Path(renamed.file_path).name == "new name.mp4"
    assert renamed.title == "new name", "Title follows the new filename"
    assert renamed.file_size == 64

    refreshed = (await db_session.execute(select(Download).where(Download.id == download.id))).scalars().first()
    assert refreshed.file_path == str(renamed.file_path)
    assert refreshed.title == "new name"


@pytest.mark.asyncio
async def test_rename_file_preserves_extension_when_omitted(library, db_session, download_dir):
    """A bare new title keeps the original container extension."""
    original = make_media_file(Path(download_dir), "youtube/clip.mp4")
    download = make_download(db_session, title="Clip", file_path=str(original))

    renamed = await library.rename_file(download.id, "Renamed Clip")

    assert Path(renamed.file_path).name == "Renamed Clip.mp4"


@pytest.mark.asyncio
async def test_rename_file_sanitises_path_traversal_input(library, db_session, download_dir):
    """A traversal attempt is flattened to a filename inside the original folder."""
    original = make_media_file(Path(download_dir), "youtube/clip.mp4")
    download = make_download(db_session, title="Clip", file_path=str(original))

    renamed = await library.rename_file(download.id, "../../../etc/passwd")

    new_path = Path(renamed.file_path)
    assert new_path.parent == original.parent, "The file must stay in its own directory"
    assert ".." not in new_path.name, "Traversal dots must not survive into the filename"
    assert new_path.exists(), "The file is renamed, not moved or deleted"
    assert new_path.parent == Path(download_dir) / "youtube"


@pytest.mark.asyncio
async def test_rename_file_rejects_collisions_and_missing_files(library, db_session, download_dir):
    """Renaming onto an existing name, or renaming a vanished file, raises."""
    first = make_media_file(Path(download_dir), "youtube/one.mp4")
    make_media_file(Path(download_dir), "youtube/two.mp4")
    download = make_download(db_session, title="One", file_path=str(first))

    with pytest.raises(LibraryPathError):
        await library.rename_file(download.id, "two.mp4")

    missing = make_download(
        db_session, title="Ghost", file_path=str(Path(download_dir) / "youtube/ghost.mp4")
    )
    with pytest.raises(LibraryPathError):
        await library.rename_file(missing.id, "whatever.mp4")

    with pytest.raises(DownloadNotFound):
        await library.rename_file("does-not-exist", "whatever.mp4")


@pytest.mark.asyncio
async def test_delete_media_removes_file_and_record(library, db_session, download_dir):
    """Deleting removes the file from disk and the row from the database."""
    target = make_media_file(Path(download_dir), "youtube/bye.mp4", size=128)
    download = make_download(db_session, title="Bye", file_path=str(target))

    await library.delete_media(download.id)

    assert target.exists() is False
    remaining = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert remaining is None


@pytest.mark.asyncio
async def test_delete_media_cleans_up_record_when_file_already_gone(library, db_session, download_dir):
    """A record whose file is missing is still removed, not left orphaned."""
    download = make_download(
        db_session, title="Ghost", file_path=str(Path(download_dir) / "youtube/ghost.mp4")
    )

    await library.delete_media(download.id)

    remaining = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert remaining is None


@pytest.mark.asyncio
async def test_delete_media_refuses_paths_outside_the_library(library, db_session, download_dir):
    """A record pointing outside the download directory is rejected, not deleted."""
    outside = Path(download_dir).parent / "outside.mp4"
    outside.write_bytes(b"data")
    download = make_download(db_session, title="Outside", file_path=str(outside))

    with pytest.raises(LibraryPathError):
        await library.delete_media(download.id)

    assert outside.exists(), "The file outside the library must be untouched"
    still_there = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert still_there is not None


@pytest.mark.asyncio
async def test_open_folder_launches_explorer_with_select_flag(library, db_session, download_dir):
    """The file manager is launched with an argument list, never a shell string."""
    target = make_media_file(Path(download_dir), "youtube/show me.mp4")
    download = make_download(db_session, title="Show Me", file_path=str(target))

    with patch("app.services.storage.file_manager.subprocess.Popen") as mock_popen:
        await library.open_folder(download.id)

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert kwargs["shell"] is False, "The path must never be interpolated into a shell command"
    command = args[0]
    assert isinstance(command, list), "subprocess must receive an argument list"
    assert command[0] in {"explorer", "open", "xdg-open"}
    assert any(str(target) in part for part in command[1:])


# --------------------------------------------------------------------------- #
# Task 1: untracked detection and import
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_detect_untracked_files_finds_only_orphans(library, db_session, download_dir):
    """Files without a matching record are reported; tracked ones are not."""
    tracked = make_media_file(Path(download_dir), "youtube/tracked.mp4", size=100)
    make_download(db_session, title="Tracked", file_path=str(tracked))

    orphan_video = make_media_file(Path(download_dir), "youtube/orphan.mp4", size=200)
    orphan_audio = make_media_file(Path(download_dir), "tiktok/orphan.mp3", size=50)

    # Neither an unknown extension nor an in-progress fragment is a library file.
    make_media_file(Path(download_dir), "youtube/notes.txt", size=10)
    (Path(download_dir) / "youtube" / "inflight.mp4.part").write_bytes(b"0" * 20)

    untracked = await library.detect_untracked_files()
    paths = {item.path for item in untracked}

    assert str(orphan_video) in paths
    assert str(orphan_audio) in paths
    assert str(tracked) not in paths, "A tracked file is not untracked"
    assert not any(p.endswith("notes.txt") for p in paths)
    assert not any(p.endswith(".part") for p in paths)

    audio = next(item for item in untracked if item.filename == "orphan.mp3")
    assert audio.content_type == "audio"
    assert audio.file_size == 50
    assert audio.platform == "tiktok", "Platform is inferred from the parent directory"


@pytest.mark.asyncio
async def test_detect_untracked_files_is_empty_when_everything_is_tracked(
    library, db_session, download_dir
):
    """A fully-tracked library reports no untracked files."""
    path = make_media_file(Path(download_dir), "youtube/only.mp4")
    make_download(db_session, title="Only", file_path=str(path))

    assert await library.detect_untracked_files() == []


@pytest.mark.asyncio
async def test_import_untracked_creates_completed_records(library, db_session, download_dir):
    """Importing creates completed download rows that then appear in the library."""
    video = make_media_file(Path(download_dir), "youtube/imported.mp4", size=512)
    audio = make_media_file(Path(download_dir), "youtube/imported song.m4a", size=256)

    imported = await library.import_untracked([str(video), str(audio)])

    assert imported == 2

    page = await library.scan_library(page=1, limit=24)
    by_title = {item.title: item for item in page.items}
    assert set(by_title) == {"imported", "imported song"}
    assert by_title["imported song"].content_type == "audio"
    assert by_title["imported"].file_size == 512
    assert all(item.exists_on_disk for item in page.items)

    # The files are now tracked, so detection comes up empty.
    assert await library.detect_untracked_files() == []


@pytest.mark.asyncio
async def test_import_untracked_skips_unsafe_duplicate_and_missing_paths(
    library, db_session, download_dir
):
    """A bad path in a batch is skipped and reported, not fatal to the batch."""
    good = make_media_file(Path(download_dir), "youtube/good.mp4", size=32)
    tracked = make_media_file(Path(download_dir), "youtube/tracked.mp4")
    make_download(db_session, title="Tracked", file_path=str(tracked))

    outside = Path(download_dir).parent / "escape.mp4"
    outside.write_bytes(b"data")

    result = await library.import_untracked_detailed(
        [
            str(good),
            str(outside),           # outside the managed directory
            str(tracked),           # already tracked
            str(good),              # duplicated within the same request
            str(Path(download_dir) / "youtube" / "nope.mp4"),  # missing
            str(Path(download_dir) / "youtube" / "bad.txt"),   # wrong extension
        ]
    )

    assert isinstance(result, ImportResult)
    assert result.imported == 1
    assert result.skipped == 5
    assert result.total_size_bytes == 32
    assert len(result.errors) == 5
    assert outside.exists(), "The file outside the library must not be touched"


@pytest.mark.asyncio
async def test_import_untracked_with_no_paths_is_a_no_op(library, db_session):
    """An empty request imports nothing and does not fail."""
    assert await library.import_untracked([]) == 0


# --------------------------------------------------------------------------- #
# FileManager safety
# --------------------------------------------------------------------------- #


def test_file_manager_sanitises_illegal_and_reserved_names(file_manager):
    """Illegal characters, reserved device names and empty input are handled."""
    assert "/" not in file_manager.sanitize_filename("a/b.mp4")
    assert file_manager.sanitize_filename("a/b.mp4") == "a_b.mp4"
    assert file_manager.sanitize_filename("bad:name?.mp4") == "bad_name_.mp4"
    assert file_manager.sanitize_filename("   ") == "untitled"
    assert file_manager.sanitize_filename("") == "untitled"
    assert file_manager.sanitize_filename("CON").lower().startswith("con_")
    assert not file_manager.sanitize_filename("trailing dots...").endswith(".")
    assert len(file_manager.sanitize_filename("x" * 500 + ".mp4")) <= 190


def test_file_manager_rejects_paths_outside_base_dir(file_manager, tmp_path):
    """Containment checks reject traversal and absolute paths outside the library."""
    with pytest.raises(FileAccessError):
        file_manager.resolve(tmp_path / "outside.mp4")

    with pytest.raises(FileAccessError):
        file_manager.resolve("../../etc/passwd")

    assert file_manager.is_contained(file_manager.base_dir / "youtube" / "ok.mp4") is True
    assert file_manager.is_contained(tmp_path / "nope.mp4") is False


def test_file_manager_unique_path_avoids_overwriting(file_manager):
    """Colliding names get a numeric suffix instead of clobbering the original."""
    first = file_manager.unique_path(file_manager.base_dir, "clip.mp4")
    first.write_bytes(b"first")

    second = file_manager.unique_path(file_manager.base_dir, "clip.mp4")

    assert second.name != first.name
    assert second.suffix == ".mp4"
    assert first.read_bytes() == b"first", "The existing file is untouched"


def test_file_manager_iter_media_files_skips_partials_and_hidden_dirs(file_manager):
    """The recursive scan honours the extension allowlist and skips temp files."""
    (file_manager.base_dir / "youtube").mkdir(parents=True)
    (file_manager.base_dir / "hidden").mkdir(parents=True)
    (file_manager.base_dir / "youtube" / "good.mp4").write_bytes(b"0")
    (file_manager.base_dir / "youtube" / "good.mp4.part").write_bytes(b"0")
    (file_manager.base_dir / "youtube" / ".hidden.mp4").write_bytes(b"0")
    (file_manager.base_dir / "youtube" / "notes.txt").write_text("x")
    (file_manager.base_dir / "hidden" / "nested.mkv").write_bytes(b"0")

    found = {path.name for path in file_manager.iter_media_files()}

    assert found == {"good.mp4", "nested.mkv"}


def test_file_manager_cleanup_partials_removes_fragments(file_manager):
    """Orphaned ``.part`` fragments are swept up."""
    (file_manager.base_dir / "youtube").mkdir(parents=True)
    (file_manager.base_dir / "youtube" / "a.mp4.part").write_bytes(b"0")
    (file_manager.base_dir / "youtube" / "b.mp4").write_bytes(b"0")

    removed = file_manager.cleanup_partials()

    assert len(removed) == 1
    assert removed[0].name == "a.mp4.part"
    assert (file_manager.base_dir / "youtube" / "b.mp4").exists()


# --------------------------------------------------------------------------- #
# Task 3: queue management
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_dispatcher():
    """A dispatcher that records calls instead of contacting a Celery broker.

    Returns:
        A ``(dispatcher, calls)`` tuple; ``calls`` is a list of
        ``(download_id, resume)`` tuples.
    """
    calls: list = []

    def dispatch(download_id: str, resume: bool) -> str:
        calls.append((download_id, resume))
        return f"task-{len(calls)}"

    return dispatch, calls


@pytest.fixture
def orchestrator(db_session, fake_redis, fake_dispatcher) -> DownloadOrchestrator:
    """A queue orchestrator wired to the fake Redis and fake dispatcher."""
    dispatcher, _calls = fake_dispatcher
    return DownloadOrchestrator(db_session, task_dispatcher=dispatcher)


@pytest.mark.asyncio
async def test_pause_sets_redis_flag_and_status(orchestrator, db_session, fake_redis, fake_dispatcher):
    """Pausing sets ``pause:{id}`` in Redis and moves the row to ``paused``."""
    _dispatcher, calls = fake_dispatcher
    download = make_download(db_session, title="Running", status=DownloadStatus.DOWNLOADING)

    result = await orchestrator.pause_download(download.id)

    assert result.status == "paused"
    assert result.id == download.id
    assert redis_client.pause_key(download.id) in fake_redis.store, "The pause flag must exist for the worker"
    assert fake_redis.store[redis_client.pause_key(download.id)] == "1"

    refreshed = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert refreshed.status == DownloadStatus.PAUSED
    assert calls == [], "Pausing must not dispatch a new task"


@pytest.mark.asyncio
async def test_pause_flags_every_active_download_for_pause_all(
    orchestrator, db_session, fake_redis
):
    """``pause-all`` signals each active download and pauses queued ones."""
    active_a = make_download(db_session, title="A", status=DownloadStatus.DOWNLOADING)
    active_b = make_download(db_session, title="B", status=DownloadStatus.PROCESSING)
    waiting = make_download(db_session, title="C", status=DownloadStatus.PENDING)
    finished = make_download(db_session, title="D", status=DownloadStatus.COMPLETED)

    result = await orchestrator.pause_all()

    assert result.affected == 3, "Finished downloads are left alone"
    assert redis_client.pause_key(active_a.id) in fake_redis.store
    assert redis_client.pause_key(active_b.id) in fake_redis.store
    assert redis_client.pause_key(waiting.id) not in fake_redis.store, "A queued item needs no worker signal"

    statuses = {
        row.id: row.status
        for row in (await db_session.execute(select(Download))).scalars().all()
    }
    assert statuses[active_a.id] == DownloadStatus.PAUSED
    assert statuses[active_b.id] == DownloadStatus.PAUSED
    assert statuses[waiting.id] == DownloadStatus.PAUSED
    assert statuses[finished.id] == DownloadStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_clears_flag_and_re_enqueues_task(orchestrator, db_session, fake_redis, fake_dispatcher):
    """Resuming clears the pause flag and re-dispatches the task with resume=True."""
    _dispatcher, calls = fake_dispatcher
    download = make_download(db_session, title="Paused", status=DownloadStatus.PAUSED)
    redis_client.request_pause(download.id)
    assert redis_client.pause_key(download.id) in fake_redis.store

    result = await orchestrator.resume_download(download.id)

    assert result.status == "pending"
    assert result.celery_task_id is not None
    assert calls == [(download.id, True)], "Resume must dispatch with continuation enabled"
    assert redis_client.pause_key(download.id) not in fake_redis.store, "The pause flag must be cleared"

    refreshed = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert refreshed.status == DownloadStatus.PENDING
    assert refreshed.celery_task_id == result.celery_task_id


@pytest.mark.asyncio
async def test_resume_rejects_downloads_that_are_not_paused(orchestrator, db_session):
    """A download that is already running cannot be resumed."""
    download = make_download(db_session, title="Running", status=DownloadStatus.DOWNLOADING)

    with pytest.raises(InvalidTransition):
        await orchestrator.resume_download(download.id)


@pytest.mark.asyncio
async def test_pause_rejects_finished_downloads(orchestrator, db_session):
    """A completed download cannot be paused."""
    download = make_download(db_session, title="Done", status=DownloadStatus.COMPLETED)

    with pytest.raises(InvalidTransition):
        await orchestrator.pause_download(download.id)


@pytest.mark.asyncio
async def test_prioritize_moves_item_to_position_zero(orchestrator, db_session):
    """Prioritizing sets position 0 and renumbers the rest to stay dense."""
    first = make_download(db_session, title="First", status=DownloadStatus.PENDING)
    second = make_download(db_session, title="Second", status=DownloadStatus.PENDING)
    third = make_download(db_session, title="Third", status=DownloadStatus.PENDING)

    for index, download in enumerate((first, second, third), start=1):
        db_session.add(QueueItem(download_id=download.id, position=index, priority=0, status="queued"))
    await db_session.commit()

    entry = await orchestrator.prioritize(third.id)

    assert entry.position == 0
    assert entry.id == third.id

    items = {
        item.download_id: item
        for item in (await db_session.execute(select(QueueItem))).scalars().all()
    }
    assert items[third.id].position == 0, "The prioritised item is at the front"
    assert items[first.id].position == 1
    assert items[second.id].position == 2, "Remaining items are renumbered without gaps"
    assert items[third.id].priority == 1, "It also gets the highest priority"


@pytest.mark.asyncio
async def test_prioritize_rejects_active_downloads(orchestrator, db_session):
    """An in-flight download cannot be requeued."""
    download = make_download(db_session, title="Busy", status=DownloadStatus.DOWNLOADING)

    with pytest.raises(InvalidTransition):
        await orchestrator.prioritize(download.id)


@pytest.mark.asyncio
async def test_get_queue_splits_active_queued_and_paused_with_live_progress(
    orchestrator, db_session, fake_redis
):
    """The snapshot classifies each download and layers Redis metrics on top."""
    active = make_download(db_session, title="Active", status=DownloadStatus.DOWNLOADING)
    waiting = make_download(db_session, title="Waiting", status=DownloadStatus.PENDING)
    paused = make_download(db_session, title="Paused", status=DownloadStatus.PAUSED)
    make_download(db_session, title="Finished", status=DownloadStatus.COMPLETED)

    db_session.add(QueueItem(download_id=waiting.id, position=1, priority=0, status="queued"))
    db_session.add(QueueItem(download_id=paused.id, position=2, priority=0, status="paused"))
    await db_session.commit()

    redis_client.write_progress(
        active.id,
        {"status": "downloading", "progress": 42.5, "speed": 1024.0, "eta": 30, "downloaded_bytes": 512},
    )

    snapshot = await orchestrator.get_queue()

    assert snapshot.active_count == 1
    assert snapshot.queued_count == 1
    assert snapshot.paused_count == 1
    assert snapshot.progress_source == "redis"

    active_entry = snapshot.active[0]
    assert active_entry.id == active.id
    assert active_entry.is_active is True
    assert active_entry.progress == 42.5
    assert active_entry.speed == 1024.0
    assert active_entry.eta == 30
    assert active_entry.downloaded_bytes == 512

    assert snapshot.queued[0].id == waiting.id
    assert snapshot.queued[0].position == 1
    assert snapshot.paused[0].id == paused.id
    assert all(entry.id != "Finished" for entry in snapshot.active + snapshot.queued + snapshot.paused)


@pytest.mark.asyncio
async def test_resume_all_re_enqueues_every_paused_download(orchestrator, db_session, fake_redis, fake_dispatcher):
    """``resume-all`` clears flags and dispatches each paused download."""
    _dispatcher, calls = fake_dispatcher
    paused_a = make_download(db_session, title="A", status=DownloadStatus.PAUSED)
    paused_b = make_download(db_session, title="B", status=DownloadStatus.PAUSED)
    redis_client.request_pause(paused_a.id)
    redis_client.request_pause(paused_b.id)

    result = await orchestrator.resume_all()

    assert result.affected == 2
    assert {call[0] for call in calls} == {paused_a.id, paused_b.id}
    assert all(call[1] is True for call in calls), "Every resume continues the partial file"
    assert redis_client.pause_key(paused_a.id) not in fake_redis.store


# --------------------------------------------------------------------------- #
# Task 3: download task pause behaviour
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_transfer_aborts_as_soon_as_the_pause_flag_is_set(
    db_session, fake_redis, download_dir, monkeypatch
):
    """The progress callback raises on the first chunk once pause is requested."""
    from app.workers import download_tasks

    download = make_download(db_session, title="Pause Me", status=DownloadStatus.PENDING)
    redis_client.request_pause(download.id)

    observed = {}

    class PausingEngine:
        def download_media(self, url, output_path, format_id=None, progress_callback=None, extra_options=None, **kwargs):
            observed["extra_options"] = extra_options
            progress_callback(
                {"status": "downloading", "progress": 10.0, "downloaded_bytes": 10, "total_bytes": 100}
            )
            # Unreachable: the callback above must abort the transfer.
            observed["reached_end"] = True
            return ""

    monkeypatch.setattr(download_tasks, "YTDLPEngine", PausingEngine)

    with pytest.raises(download_tasks.DownloadPausedSignal):
        await download_tasks._transfer(db_session, download, FileManager(download_dir), resume=False)

    assert "reached_end" not in observed, "The transfer must stop at the paused chunk"
    assert observed["extra_options"] == {"continuedl": False}


@pytest.mark.asyncio
async def test_transfer_publishes_progress_and_completes(db_session, fake_redis, download_dir, monkeypatch):
    """A successful transfer persists the file, completes the row and clears the flag."""
    from app.workers import download_tasks

    download = make_download(db_session, title="Finish Me", status=DownloadStatus.PENDING)
    produced = Path(download_dir) / "youtube" / "Finish Me.mp4"
    observed_extra: dict = {}

    class FinishingEngine:
        def download_media(self, url, output_path, format_id=None, progress_callback=None, extra_options=None, **kwargs):
            observed_extra["extra_options"] = extra_options
            progress_callback(
                {"status": "downloading", "progress": 50.0, "downloaded_bytes": 50, "total_bytes": 100}
            )
            produced.parent.mkdir(parents=True, exist_ok=True)
            produced.write_bytes(b"0" * 77)
            progress_callback({"status": "finished", "progress": 100.0})
            return str(produced)

    monkeypatch.setattr(download_tasks, "YTDLPEngine", FinishingEngine)

    result = await download_tasks._transfer(db_session, download, FileManager(download_dir), resume=True)

    assert result["status"] == "completed"
    assert result["file_size"] == 77
    assert observed_extra["extra_options"] == {"continuedl": True}, "Resume enables yt-dlp continuation"

    refreshed = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert refreshed.status == DownloadStatus.COMPLETED
    assert refreshed.progress == 100.0
    assert refreshed.file_path == str(produced)
    assert refreshed.file_size == 77
    assert refreshed.completed_at is not None
    assert redis_client.read_progress(download.id)["status"] == "completed"
    assert redis_client.pause_key(download.id) not in fake_redis.store


@pytest.mark.asyncio
async def test_transfer_marks_download_failed_on_engine_error(
    db_session, fake_redis, download_dir, monkeypatch
):
    """An engine failure propagates so the caller records it on the row."""
    from app.services.extractor.ytdlp_engine import YTDLPEngineError
    from app.workers import download_tasks

    download = make_download(db_session, title="Doomed", status=DownloadStatus.PENDING)

    class FailingEngine:
        def download_media(self, url, output_path, format_id=None, progress_callback=None, extra_options=None, **kwargs):
            raise YTDLPEngineError(message="gone", code="DOWNLOAD_ERROR", action="retry")

    monkeypatch.setattr(download_tasks, "YTDLPEngine", FailingEngine)

    with pytest.raises(YTDLPEngineError):
        await download_tasks._transfer(db_session, download, FileManager(download_dir), resume=False)


def test_resolve_output_falls_back_to_a_different_container(file_manager):
    """A merge that changes the extension is still found next to the template."""
    from app.workers.download_tasks import _resolve_output

    actual = make_media_file(file_manager.base_dir, "youtube/Clip.webm", size=10)
    template = file_manager.base_dir / "youtube" / "Clip.mp4"

    assert _resolve_output(file_manager, str(template)) == actual


def test_resolve_output_rejects_paths_outside_the_library(file_manager, tmp_path):
    """A filename outside the download directory is never trusted."""
    from app.workers.download_tasks import _resolve_output

    outside = tmp_path / "escape.mp4"
    outside.write_bytes(b"data")

    assert _resolve_output(file_manager, str(outside)) is None


def test_pause_key_and_progress_channel_are_namespaced(fake_redis):
    """Redis keys use the configured prefix so the API and workers agree."""
    assert redis_client.pause_key("abc").startswith("mediavault:pause:abc")
    assert redis_client.progress_key("abc").startswith("mediavault:progress:abc")
    assert redis_client.progress_channel_all().startswith("mediavault:progress:channel:")
    assert redis_client.pause_all_key().startswith("mediavault:pause_all")


def test_write_progress_persists_and_publishes(fake_redis):
    """A progress write is stored and fanned out to both pub/sub channels."""
    redis_client.write_progress("abc", {"status": "downloading", "progress": 12.5, "speed": 99.0})

    snapshot = redis_client.read_progress("abc")
    assert snapshot["progress"] == 12.5
    assert snapshot["download_id"] == "abc"
    assert redis_client.progress_key("abc") in fake_redis.store

    channels = [channel for channel, _payload in fake_redis.published]
    assert redis_client.progress_channel("abc") in channels
    assert redis_client.progress_channel_all() in channels


# --------------------------------------------------------------------------- #
# Task 2: endpoints
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def client(db_session, download_dir, monkeypatch):
    """An HTTP client bound to the app with the database dependency overridden."""
    import app.main as main_module
    from app.db.database import get_db

    async def override_get_db():
        yield db_session

    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_library_endpoints_scan_stats_and_untracked(client, db_session, download_dir):
    """The list, stats and untracked endpoints return their schemas."""
    path = make_media_file(Path(download_dir), "youtube/api.mp4", size=300)
    make_download(db_session, title="Api Video", file_path=str(path))
    make_media_file(Path(download_dir), "youtube/orphan.mp4", size=20)

    listed = await client.get("/api/v1/library", params={"page": 1, "limit": 10})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Api Video"
    assert body["items"][0]["exists_on_disk"] is True

    stats = await client.get("/api/v1/library/stats")
    assert stats.status_code == 200
    assert stats.json()["total_files"] == 1
    assert stats.json()["total_size_bytes"] == 300
    assert len(stats.json()["downloads_last_7_days"]) == 7

    untracked = await client.get("/api/v1/library/untracked")
    assert untracked.status_code == 200
    assert [item["filename"] for item in untracked.json()] == ["orphan.mp4"]


@pytest.mark.asyncio
async def test_library_endpoints_rename_delete_and_open_folder(client, db_session, download_dir):
    """Rename, delete and open-folder all round-trip through the HTTP layer."""
    path = make_media_file(Path(download_dir), "youtube/before.mp4")
    download = make_download(db_session, title="Before", file_path=str(path))

    renamed = await client.post(f"/api/v1/library/{download.id}/rename", json={"new_name": "after.mp4"})
    assert renamed.status_code == 200
    assert Path(renamed.json()["file_path"]).name == "after.mp4"
    assert renamed.json()["title"] == "after"

    with patch("app.services.storage.file_manager.subprocess.Popen") as mock_popen:
        opened = await client.post(f"/api/v1/library/{download.id}/open-folder")
    assert opened.status_code == 200
    assert mock_popen.called

    deleted = await client.delete(f"/api/v1/library/{download.id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    remaining = (
        await db_session.execute(select(Download).where(Download.id == download.id))
    ).scalars().first()
    assert remaining is None


@pytest.mark.asyncio
async def test_library_endpoints_import_and_report_errors(client, db_session, download_dir):
    """Import creates records and reports rejected paths without failing."""
    good = make_media_file(Path(download_dir), "youtube/import me.mp4", size=10)
    outside = Path(download_dir).parent / "escape.mp4"
    outside.write_bytes(b"x")

    response = await client.post(
        "/api/v1/library/import", json={"file_paths": [str(good), str(outside)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    assert len(body["errors"]) == 1


@pytest.mark.asyncio
async def test_library_endpoint_returns_404_for_unknown_download(client, db_session, download_dir):
    """Unknown IDs produce 404 rather than a 500."""
    response = await client.post("/api/v1/library/nope/rename", json={"new_name": "x.mp4"})
    assert response.status_code == 404

    response = await client.delete("/api/v1/library/nope")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_queue_endpoints_prioritize_pause_and_resume(
    client, db_session, download_dir, fake_redis
):
    """The queue and download routes drive the orchestrator through the HTTP layer."""
    import app.main as main_module
    from app.api.v1.deps import get_orchestrator
    from app.services.downloader.download_orchestrator import DownloadOrchestrator

    calls: list = []

    def dispatch(download_id: str, resume: bool) -> str:
        calls.append((download_id, resume))
        return f"task-{len(calls)}"

    async def override_orchestrator():
        yield DownloadOrchestrator(db_session, task_dispatcher=dispatch)

    # queue.py and downloads.py share one dependency, so one override covers both.
    main_module.app.dependency_overrides[get_orchestrator] = override_orchestrator

    try:
        first = make_download(db_session, title="First", status=DownloadStatus.PENDING)
        second = make_download(db_session, title="Second", status=DownloadStatus.PENDING)
        db_session.add(QueueItem(download_id=first.id, position=1, priority=0, status="queued"))
        db_session.add(QueueItem(download_id=second.id, position=2, priority=0, status="queued"))
        await db_session.commit()

        queue = await client.get("/api/v1/queue")
        assert queue.status_code == 200
        assert queue.json()["queued_count"] == 2

        prioritized = await client.post(f"/api/v1/queue/{second.id}/prioritize")
        assert prioritized.status_code == 200
        assert prioritized.json()["position"] == 0

        paused = await client.post(f"/api/v1/downloads/{first.id}/pause")
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"
        assert redis_client.pause_key(first.id) in fake_redis.store

        resumed = await client.post(f"/api/v1/downloads/{first.id}/resume")
        assert resumed.status_code == 200
        assert resumed.json()["celery_task_id"] is not None
        assert (first.id, True) in calls

        paused_all = await client.post("/api/v1/queue/pause-all")
        assert paused_all.status_code == 200
        assert paused_all.json()["affected"] >= 1

        resumed_all = await client.post("/api/v1/queue/resume-all")
        assert resumed_all.status_code == 200
        assert resumed_all.json()["affected"] >= 1
    finally:
        main_module.app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.asyncio
async def test_resume_reports_503_when_the_broker_is_unreachable(
    client, db_session, download_dir, fake_redis
):
    """A broker outage leaves the download paused and surfaces as a 503."""
    import app.main as main_module
    from app.api.v1.deps import get_orchestrator
    from app.services.downloader.download_orchestrator import (
        DispatchUnavailable,
        DownloadOrchestrator,
    )

    def broken_dispatch(download_id: str, resume: bool) -> str:
        raise DispatchUnavailable("broker down")

    async def override_orchestrator():
        yield DownloadOrchestrator(db_session, task_dispatcher=broken_dispatch)

    main_module.app.dependency_overrides[get_orchestrator] = override_orchestrator
    try:
        paused = make_download(db_session, title="Stranded", status=DownloadStatus.PAUSED)

        response = await client.post(f"/api/v1/downloads/{paused.id}/resume")

        assert response.status_code == 503
        row = (
            await db_session.execute(select(Download).where(Download.id == paused.id))
        ).scalars().first()
        assert row.status == DownloadStatus.PAUSED, "The row must not claim to be running"
    finally:
        main_module.app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.asyncio
async def test_pause_reports_503_when_redis_is_unreachable(
    client, db_session, download_dir, monkeypatch
):
    """A pause that cannot be signalled is a 503, never a silent success."""
    import app.main as main_module
    from app.core import redis_client
    from app.api.v1.deps import get_orchestrator
    from app.services.downloader.download_orchestrator import DownloadOrchestrator

    def failing_request_pause(download_id: str, client=None) -> bool:
        return False

    monkeypatch.setattr(redis_client, "request_pause", failing_request_pause)

    async def override_orchestrator():
        yield DownloadOrchestrator(db_session, task_dispatcher=lambda d, r: "task-1")

    main_module.app.dependency_overrides[get_orchestrator] = override_orchestrator
    try:
        running = make_download(db_session, title="Unpausable", status=DownloadStatus.DOWNLOADING)

        response = await client.post(f"/api/v1/downloads/{running.id}/pause")

        assert response.status_code == 503
        row = (
            await db_session.execute(select(Download).where(Download.id == running.id))
        ).scalars().first()
        assert row.status == DownloadStatus.DOWNLOADING, "Status must not flip without the flag"
    finally:
        main_module.app.dependency_overrides.pop(get_orchestrator, None)


@pytest.mark.asyncio
async def test_download_endpoints_return_409_for_invalid_transitions(client, db_session, download_dir):
    """Resuming a running download and pausing a finished one are conflicts."""
    running = make_download(db_session, title="Running", status=DownloadStatus.DOWNLOADING)
    finished = make_download(db_session, title="Finished", status=DownloadStatus.COMPLETED)

    resumed = await client.post(f"/api/v1/downloads/{running.id}/resume")
    assert resumed.status_code == 409

    paused = await client.post(f"/api/v1/downloads/{finished.id}/pause")
    assert paused.status_code == 409

    missing = await client.post("/api/v1/downloads/nope/pause")
    assert missing.status_code == 404