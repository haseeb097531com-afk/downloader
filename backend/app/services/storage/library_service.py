"""Media library service.

Backs the library grid, the dashboard statistics, and the file-management actions
(rename, delete, reveal in the file manager). All filesystem access is delegated to
:class:`~app.services.storage.file_manager.FileManager` so path sanitisation and
containment checks exist in exactly one place.
"""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.models.user import User
from app.api.deps_auth import OwnerFilter
from app.schemas.library import (
    CreatorStat,
    DailyDownloadCount,
    ImportResult,
    LibraryItem,
    LibraryPage,
    LibraryStats,
    PlatformStat,
    UntrackedFile,
)
from app.services.storage.file_manager import (
    FileAccessError,
    FileManager,
    FileManagerError,
    FileNotFoundOnDisk,
)

logger = logging.getLogger(__name__)

__all__ = ["LibraryService", "LibraryError", "DownloadNotFound", "LibraryPathError"]


class LibraryError(Exception):
    """Base class for library operation failures."""


class DownloadNotFound(LibraryError):
    """Raised when no download record exists for the supplied ID."""


class LibraryPathError(LibraryError):
    """Raised when a stored or supplied path is missing, unsafe or not a media file."""


# Metadata keys searched, in order, when ranking top creators. The download flow
# stores extractor metadata under ``metadata_json``; imported files have none, so
# they fall back to the "Unknown" bucket rather than being dropped from the chart.
_CREATOR_KEYS: Tuple[str, ...] = (
    "uploader_name",
    "uploader",
    "username",
    "creator",
    "channel",
    "author",
)

_UNKNOWN_CREATOR = "Unknown"


class LibraryService:
    """Read and manage the user's downloaded media.

    Args:
        db: Active database session for the request.
        file_manager: Filesystem gateway. Defaults to a :class:`FileManager`
            rooted at ``settings.DOWNLOAD_DIR``; tests inject one pointed at a
            temporary directory.
    """

    def __init__(self, db: AsyncSession, file_manager: Optional[FileManager] = None, current_user: Optional[User] = None) -> None:
        self.db = db
        self.file_manager = file_manager or FileManager()
        self.current_user = current_user

    async def _owner_query(self, query):
        """Apply owner scoping to ``query`` when auth is enabled."""
        if self.current_user is not None:
            from app.api.deps_auth import OwnerFilter, visible_users
            visible = await visible_users(self.current_user, self.db)
            return OwnerFilter.apply(self.current_user, query, Download, visible_user_ids=visible)
        return query

    # ------------------------------------------------------------------ #
    # Library listing
    # ------------------------------------------------------------------ #
    async def scan_library(
        self,
        page: int = 1,
        limit: int = 24,
        platform: str = None,
        search: str = None,
        category: str = None,
    ) -> LibraryPage:
        """Return one page of completed downloads, verified against disk.

        Every returned row is checked with :meth:`FileManager.exists`. A record
        whose file was deleted outside the application is still returned but flagged
        with ``exists_on_disk=False`` and a size read from disk being unavailable -
        hiding it would leave the user with no way to clean it up.

        Args:
            page: 1-based page number. Values below 1 are clamped.
            limit: Items per page, capped at 200 so a crafted query cannot ask for
                the entire table.
            platform: Optional exact platform filter, e.g. ``"youtube"``.
            search: Optional case-insensitive substring match against the title.
                ``%`` and ``_`` are escaped so user input cannot turn into a
                wildcard scan.
            category: Optional exact category filter.

        Returns:
            A :class:`LibraryPage` with items ordered newest completion first.
        """
        page = max(1, int(page or 1))
        limit = max(1, min(int(limit or 24), 200))

        filters = [Download.status == DownloadStatus.COMPLETED, Download.quarantined.is_(False)]
        if platform:
            filters.append(Download.platform == platform)
        if category:
            filters.append(Download.category == category)
        if search and search.strip():
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Download.title.ilike(f"%{escaped}%", escape="\\"))

        total = await self.db.scalar(await self._owner_query(select(func.count(Download.id)).where(*filters)))
        total = int(total or 0)

        result = await self.db.execute(
            await self._owner_query(
                select(Download)
                .where(*filters)
                .order_by(Download.completed_at.desc().nullslast(), Download.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        downloads: Sequence[Download] = result.scalars().all()

        items = [self._to_library_item(download) for download in downloads]
        total_pages = (total + limit - 1) // limit if total else 0

        return LibraryPage(
            items=items,
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
        )

    def _to_library_item(self, download: Download) -> LibraryItem:
        """Project a download row into a :class:`LibraryItem`, checking the disk."""
        file_path = download.file_path
        exists = False
        size = 0

        if file_path:
            try:
                if self.file_manager.exists(file_path):
                    exists = True
                    size = self.file_manager.get_size(file_path)
            except FileAccessError:
                # The record points outside the managed directory. Report the row
                # as missing rather than refusing the whole page.
                logger.warning("Download %s references a path outside the library: %s", download.id, file_path)
            except FileManagerError as exc:  # pragma: no cover - defensive
                logger.warning("Could not stat file for download %s: %s", download.id, exc)

        return LibraryItem.from_download(download, exists_on_disk=exists, file_size=size)

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #
    async def get_library_stats(self) -> LibraryStats:
        """Aggregate library metrics for the dashboard.

        Completed downloads are fetched once and aggregated in Python. That is
        deliberate: the breakdown is grouped by platform, the 7-day chart needs
        per-day bucketing that SQLite cannot express portably, and top creators
        live inside a JSON column - so three separate SQL queries would either be
        database-specific or unable to reach the data at all. A personal media
        library is bounded (thousands of rows, not millions), so the in-memory
        aggregation costs less than the portability tax.

        Sizes are read from disk when the file exists and fall back to the size
        recorded at download time otherwise, which keeps totals stable when a user
        deletes files outside the app.

        Returns:
            A :class:`LibraryStats` with platform counts and sizes, a daily
            download chart covering the last 7 days, and the top 5 creators.
        """
        result = await self.db.execute(
            await self._owner_query(select(Download).where(Download.status == DownloadStatus.COMPLETED))
        )
        downloads: Sequence[Download] = result.scalars().all()

        platform_counts: Counter[str] = Counter()
        platform_sizes: Dict[str, int] = defaultdict(int)
        creator_counts: Counter[str] = Counter()
        daily_counts: Counter[str] = Counter()
        total_size = 0
        missing_files = 0

        today = datetime.utcnow().date()
        window_start = today - timedelta(days=6)

        for download in downloads:
            exists = False
            size = 0
            if download.file_path:
                try:
                    if self.file_manager.exists(download.file_path):
                        exists = True
                        size = self.file_manager.get_size(download.file_path)
                except FileAccessError:
                    pass
                except FileManagerError as exc:  # pragma: no cover - defensive
                    logger.warning("Could not stat file for download %s: %s", download.id, exc)

            if not exists:
                missing_files += 1
                size = int(download.file_size or 0)

            platform = download.platform or "unknown"
            platform_counts[platform] += 1
            platform_sizes[platform] += size
            total_size += size

            creator_counts[self._extract_creator(download) or _UNKNOWN_CREATOR] += 1

            completed_at = download.completed_at
            if completed_at is None:
                completed_at = download.created_at
            if completed_at is not None:
                day = completed_at.date()
                if window_start <= day <= today:
                    daily_counts[day.isoformat()] += 1

        breakdown = [
            PlatformStat(platform=platform, count=count, total_size=platform_sizes[platform])
            for platform, count in sorted(
                platform_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]

        # Always emit all seven days so the mini chart has a stable x-axis and
        # renders gaps as zero rather than collapsing them.
        chart: List[DailyDownloadCount] = []
        for offset in range(7):
            day = (window_start + timedelta(days=offset)).isoformat()
            chart.append(DailyDownloadCount(date=day, count=daily_counts.get(day, 0)))

        # Counter.most_common breaks ties by insertion order, which follows the
        # newest-first query order; sorting on the name keeps the result stable
        # across calls.
        top_creators = [
            CreatorStat(username=name, count=count)
            for name, count in sorted(
                creator_counts.most_common(5), key=lambda item: (-item[1], item[0].lower())
            )
        ]

        return LibraryStats(
            total_files=len(downloads),
            total_size_bytes=total_size,
            missing_files=missing_files,
            platform_breakdown=breakdown,
            downloads_last_7_days=chart,
            top_creators=top_creators,
        )

    @staticmethod
    def _extract_creator(download: Download) -> Optional[str]:
        """Return the uploader name recorded in ``metadata_json``, if any."""
        metadata = download.metadata_json
        if not isinstance(metadata, dict):
            return None
        for key in _CREATOR_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    # ------------------------------------------------------------------ #
    # File management
    # ------------------------------------------------------------------ #
    async def rename_file(self, download_id: str, new_name: str) -> LibraryItem:
        """Rename a media file on disk and update the record title.

        The new name is sanitised by the FileManager, so ``"../../evil.mp4"``
        becomes a plain filename in the same directory rather than a path.

        Args:
            download_id: Download whose file should be renamed.
            new_name: Desired filename. An extension is not required; if omitted the
                original extension is preserved.

        Returns:
            The updated :class:`LibraryItem`.

        Raises:
            DownloadNotFound: If the record does not exist.
            LibraryPathError: If the record has no usable file path, the file is
                missing from disk, or the sanitised name is empty or collides with
                an existing file.
        """
        download = await self._get_download(download_id)
        file_path = self._require_file_path(download)

        # Preserve the extension when the user supplies a bare title, since
        # renaming "clip.mp4" to "clip" should not strip the container.
        if not os.path.splitext(new_name or "")[1]:
            new_name = f"{new_name}{Path(file_path).suffix}"

        try:
            renamed = self.file_manager.rename(file_path, new_name)
        except FileNotFoundOnDisk as exc:
            raise LibraryPathError(f"File is missing from disk: {exc}") from exc
        except FileAccessError as exc:
            raise LibraryPathError(str(exc)) from exc
        except FileManagerError as exc:
            raise LibraryPathError(str(exc)) from exc

        download.file_path = str(renamed)
        download.title = self._title_from_filename(renamed.name)
        await self.db.commit()
        await self.db.refresh(download)

        return LibraryItem.from_download(download, exists_on_disk=True, file_size=self.file_manager.get_size(renamed))

    async def delete_media(self, download_id: str) -> None:
        """Delete a media file from disk and remove its database record.

        The disk delete happens first so a database failure cannot leave a record
        pointing at a file the user believes is gone. A file that is already absent
        is not an error - the record is still cleaned up.

        Args:
            download_id: Download to remove.

        Raises:
            DownloadNotFound: If the record does not exist.
            LibraryPathError: If the stored path is unsafe or the file cannot be
                removed from disk.
        """
        download = await self._get_download(download_id)

        if download.file_path:
            try:
                removed = self.file_manager.delete(download.file_path)
            except FileAccessError as exc:
                raise LibraryPathError(str(exc)) from exc
            except FileManagerError as exc:
                raise LibraryPathError(str(exc)) from exc
            if removed:
                logger.info("Deleted media file %s", download.file_path)

        await self.db.delete(download)
        await self.db.commit()

    async def open_folder(self, download_id: str) -> None:
        """Reveal a media file in the operating system file manager.

        Args:
            download_id: Download whose file should be revealed.

        Raises:
            DownloadNotFound: If the record does not exist.
            LibraryPathError: If the record has no usable file path, the file is
                missing, or the file manager could not be launched.
        """
        download = await self._get_download(download_id)
        file_path = self._require_file_path(download)

        try:
            self.file_manager.open_in_explorer(file_path)
        except FileNotFoundOnDisk as exc:
            raise LibraryPathError(f"File is missing from disk: {exc}") from exc
        except FileAccessError as exc:
            raise LibraryPathError(str(exc)) from exc
        except FileManagerError as exc:
            raise LibraryPathError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Untracked file detection and import
    # ------------------------------------------------------------------ #
    async def detect_untracked_files(self) -> List[UntrackedFile]:
        """Find media files on disk that have no matching download record.

        Walks the download directory recursively and compares the result against
        every ``file_path`` recorded in the database. A single walk of the database
        is used instead of one query per file, since the directory scan can turn up
        thousands of entries.

        Returns:
            Untracked files sorted by modification time, newest first, so the most
            likely candidates for import appear first.

        Raises:
            LibraryPathError: If the download directory cannot be created or read.
        """
        try:
            self.file_manager.ensure_dir()
        except FileManagerError as exc:
            raise LibraryPathError(str(exc)) from exc

        try:
            disk_files = list(self.file_manager.iter_media_files())
        except FileAccessError as exc:
            raise LibraryPathError(str(exc)) from exc

        result = await self.db.execute(
            select(Download.file_path).where(Download.file_path.is_not(None))
        )
        tracked: Set[str] = set()
        for raw_path in result.scalars().all():
            tracked.add(self._comparable_path(raw_path))

        untracked: List[UntrackedFile] = []
        for path in disk_files:
            if self._comparable_path(str(path)) in tracked:
                continue
            untracked.append(self._to_untracked_file(path))

        untracked.sort(key=lambda item: item.modified_at or datetime.min, reverse=True)
        return untracked

    async def import_untracked(self, file_paths: List[str]) -> int:
        """Create completed download records for files that are not yet tracked.

        Args:
            file_paths: Absolute paths supplied by the user. Each one is validated
                for containment inside the download directory, for a media
                extension, and against the existing records - a path that fails any
                check is counted as skipped rather than aborting the whole import,
                because a batch is expected to contain a few stale entries.

        Returns:
            The number of download records created.
        """
        if not file_paths:
            return 0

        try:
            self.file_manager.ensure_dir()
        except FileManagerError as exc:
            raise LibraryPathError(str(exc)) from exc

        result = await self._import_untracked(file_paths)
        if result.imported:
            await self.db.commit()
        return result.imported

    async def import_untracked_detailed(self, file_paths: List[str]) -> ImportResult:
        """Import untracked files and report per-path outcomes.

        Behaves exactly like :meth:`import_untracked` but returns the skipped count,
        the imported byte total and a reason per rejected path, which the
        ``POST /library/import`` endpoint surfaces to the user.

        Args:
            file_paths: Absolute paths supplied by the user.

        Returns:
            An :class:`ImportResult` describing the outcome.
        """
        if not file_paths:
            return ImportResult()

        try:
            self.file_manager.ensure_dir()
        except FileManagerError as exc:
            raise LibraryPathError(str(exc)) from exc

        result = await self._import_untracked(file_paths)
        if result.imported:
            await self.db.commit()
        return result

    async def _import_untracked(self, file_paths: Iterable[str]) -> ImportResult:
        """Validate paths, create records, and stage them without committing."""
        result = ImportResult()

        tracked_result = await self.db.execute(
            select(Download.file_path).where(Download.file_path.is_not(None))
        )
        tracked = {self._comparable_path(p) for p in tracked_result.scalars().all()}

        seen_in_batch: Set[str] = set()

        for raw_path in file_paths:
            key = self._comparable_path(raw_path)
            if key in seen_in_batch:
                result.skipped += 1
                result.errors.append(f"{raw_path}: duplicated in the same request")
                continue
            seen_in_batch.add(key)

            try:
                resolved = self.file_manager.resolve(raw_path)
            except FileAccessError:
                result.skipped += 1
                result.errors.append(f"{raw_path}: outside the managed download directory")
                continue

            if not self.file_manager.is_media_file(resolved):
                result.skipped += 1
                result.errors.append(f"{raw_path}: not a recognised media file")
                continue

            if not resolved.is_file():
                result.skipped += 1
                result.errors.append(f"{raw_path}: file does not exist")
                continue

            if key in tracked:
                result.skipped += 1
                result.errors.append(f"{raw_path}: already tracked by an existing download")
                continue

            stat = resolved.stat()
            platform = self._platform_from_path(resolved)
            download = Download(
                url=f"file://{resolved.as_posix()}",
                platform=platform,
                content_type=self.file_manager.content_type_for(resolved),
                title=self._title_from_filename(resolved.name),
                status=DownloadStatus.COMPLETED,
                progress=100.0,
                file_path=str(resolved),
                file_size=int(stat.st_size),
                is_watermark_free=True,
                completed_at=datetime.utcnow(),
                metadata_json={
                    "imported": True,
                    "original_filename": resolved.name,
                    "platform_inferred_from": resolved.parent.name,
                },
            )
            self.db.add(download)
            tracked.add(key)
            result.imported += 1
            result.total_size_bytes += int(stat.st_size)

        return result

    def _to_untracked_file(self, path: Path) -> UntrackedFile:
        """Project an on-disk file into an :class:`UntrackedFile`."""
        stat = path.stat()
        return UntrackedFile(
            path=str(path),
            filename=path.name,
            extension=path.suffix.lower(),
            file_size=int(stat.st_size),
            modified_at=datetime.utcfromtimestamp(stat.st_mtime),
            platform=self._platform_from_path(path),
            content_type=self.file_manager.content_type_for(path),
            modified_since_sync=False,
        )

    def _platform_from_path(self, path: Path) -> str:
        """Infer the platform from the parent directory name.

        Downloads are written to ``DOWNLOAD_DIR/<platform>/...``, so the immediate
        parent carries the platform. Files sitting directly in the download root are
        reported as ``"imported"``.
        """
        try:
            parent = self.file_manager.resolve(path).parent
        except FileAccessError:  # pragma: no cover - callers pre-validate
            return "imported"
        if parent == self.file_manager.base_dir:
            return "imported"
        candidate = parent.name.lower()
        return candidate if candidate in settings.ALLOWED_PLATFORMS else "imported"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _get_download(self, download_id: str) -> Download:
        """Fetch a download row or raise :class:`DownloadNotFound`."""
        result = await self.db.execute(
            await self._owner_query(select(Download).where(Download.id == download_id))
        )
        download = result.scalars().first()
        if download is None:
            raise DownloadNotFound(f"Download not found: {download_id}")
        return download

    def _require_file_path(self, download: Download) -> str:
        """Return the download's file path, validating it is usable."""
        if not download.file_path:
            raise LibraryPathError(f"Download {download.id} has no associated file")
        try:
            return str(self.file_manager.resolve(download.file_path))
        except FileAccessError as exc:
            raise LibraryPathError(str(exc)) from exc

    @staticmethod
    def _comparable_path(path: str) -> str:
        """Return a normalised, case-folded path for comparison.

        Windows and macOS both treat paths case-insensitively, so two records
        differing only in case must not both look untracked. ``normcase`` applies
        the platform's own rule rather than hardcoding one.
        """
        try:
            return os.path.normcase(os.path.normpath(str(path)))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return str(path).lower()

    @staticmethod
    def _title_from_filename(filename: str) -> str:
        """Derive a display title from a filename by dropping the extension."""
        return Path(filename).stem or filename