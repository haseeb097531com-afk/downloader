"""Safe filesystem access for MediaVault Pro.

Every path that reaches the disk passes through :class:`FileManager`, which owns
three responsibilities:

1. **Sanitisation** - user-supplied names are stripped of characters that are
   illegal on any of the supported platforms and of Windows reserved device names.
2. **Containment** - every resolved path is asserted to live inside the configured
   download directory, so a malicious ``file_path`` stored in the database (or a
   crafted ``file_paths`` entry from ``POST /library/import``) cannot read or
   delete ``C:\\Windows\\System32``.
3. **OS integration** - revealing a file in the platform file explorer.

The class is deliberately stateless apart from its base directory, so the library
service, the download workers and the tests can all share one implementation
instead of each rolling their own path handling.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "FileManagerError",
    "FileAccessError",
    "FileNotFoundOnDisk",
    "FileManager",
]


class FileManagerError(Exception):
    """Base class for recoverable filesystem problems."""


class FileAccessError(FileManagerError):
    """Raised when a path escapes the managed download directory."""


class FileNotFoundOnDisk(FileManagerError):
    """Raised when an expected media file is missing from disk."""


# Characters that are illegal in a filename on Windows or POSIX. NUL is handled
# separately because Python string handling truncates at it.
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Windows refuses to create files named after these DOS devices, with or without
# an extension.
_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

# Extension -> logical content type, used to fill ``Download.content_type`` for
# files imported from disk where the original metadata is unknown.
_CONTENT_TYPES: Dict[str, str] = {
    ".mp4": "video",
    ".webm": "video",
    ".mkv": "video",
    ".mp3": "audio",
    ".m4a": "audio",
}


class FileManager:
    """Path-safe wrapper around the media download directory.

    Args:
        base_dir: Root directory that all managed files must live under.
            Defaults to ``settings.DOWNLOAD_DIR`` resolved to an absolute path so
            containment checks stay correct regardless of the process CWD.

    Raises:
        FileManagerError: If ``base_dir`` cannot be created.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir or settings.DOWNLOAD_DIR).expanduser().resolve()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @property
    def media_extensions(self) -> set[str]:
        """Return the media extensions considered part of the library."""
        return {ext.lower() for ext in settings.MEDIA_EXTENSIONS}

    @property
    def video_extensions(self) -> set[str]:
        """Return the recognised video extensions."""
        return {ext.lower() for ext in settings.VIDEO_EXTENSIONS}

    @property
    def audio_extensions(self) -> set[str]:
        """Return the recognised audio extensions."""
        return {ext.lower() for ext in settings.AUDIO_EXTENSIONS}

    def content_type_for(self, path: Path) -> str:
        """Return ``"video"`` or ``"audio"`` for ``path``, defaulting to ``"video"``."""
        return _CONTENT_TYPES.get(path.suffix.lower(), "video")

    def is_media_file(self, path: Path) -> bool:
        """Return whether ``path`` has a recognised media extension."""
        return Path(path).suffix.lower() in self.media_extensions

    # ------------------------------------------------------------------ #
    # Sanitisation
    # ------------------------------------------------------------------ #
    def sanitize_filename(self, name: str, fallback: str = "untitled") -> str:
        """Turn arbitrary user input into a safe single path component.

        Strips path separators and illegal characters, normalises unicode,
        collapses whitespace, strips trailing dots and spaces (illegal on
        Windows), escapes Windows reserved device names, and truncates to
        ``settings.MAX_FILENAME_LENGTH`` while preserving the extension.

        Args:
            name: Raw, untrusted input. May contain separators or be empty.
            fallback: Name to use when sanitising leaves nothing behind.

        Returns:
            A filename safe to pass to :func:`os.path.join`. Never contains a
            path separator and is never empty.
        """
        if not name or not str(name).strip():
            return fallback

        # Normalise first so decomposed unicode cannot smuggle separators past the
        # character filter, then drop any directory component a caller may have
        # supplied ("../../etc/passwd" must not survive).
        candidate = unicodedata.normalize("NFKC", str(name))
        candidate = candidate.replace("/", "_").replace("\\", "_")
        candidate = _ILLEGAL_CHARS.sub("_", candidate)
        candidate = "".join(ch for ch in candidate if unicodedata.category(ch)[0] != "C")
        candidate = re.sub(r"\s+", " ", candidate).strip()
        # Collapse dot runs. Separators are already gone at this point, so ".." can
        # no longer traverse, but collapsing it keeps a traversal attempt such as
        # "../../etc/passwd" from producing a filename that merely looks like one.
        candidate = re.sub(r"\.{2,}", "_", candidate)
        # Leading dots would create hidden files; strip them but keep ".tar"-style
        # names from being reduced to nothing.
        candidate = candidate.lstrip(". ")
        candidate = candidate.rstrip(". ")
        if not candidate:
            return fallback

        stem, dot, suffix = candidate.rpartition(".")
        if not dot:
            # No extension: the whole string is the stem.
            stem, suffix = candidate, ""

        if stem.lower() in _RESERVED_NAMES:
            stem = f"{stem}_file"

        if len(stem) > settings.MAX_FILENAME_LENGTH:
            stem = stem[: settings.MAX_FILENAME_LENGTH].rstrip(". ")

        candidate = f"{stem}.{suffix}" if suffix else stem
        return candidate or fallback

    def sanitize_subpath(self, relative_path: str) -> Path:
        """Sanitise each component of a relative path and rejoin it safely.

        The result is relative to :attr:`base_dir`. Absolute inputs and ``..``
        segments are dropped rather than rejected so that a slightly odd stored
        path can still be represented inside the library.
        """
        raw = Path(str(relative_path))
        parts: List[str] = []
        for part in raw.parts:
            if part in ("..", "."):
                continue
            # A Windows drive prefix such as "C:" loses its colon to the illegal
            # character filter and becomes an ordinary directory name, which is the
            # desired behaviour - the path is re-rooted under base_dir either way.
            cleaned = self.sanitize_filename(part)
            if cleaned:
                parts.append(cleaned)
        return Path(*parts) if parts else Path("untitled")

    def build_path(self, *parts: str) -> Path:
        """Build a sanitised absolute path under :attr:`base_dir`."""
        relative = self.sanitize_subpath(Path(*[str(p) for p in parts]).as_posix())
        return self.resolve(self.base_dir / relative)

    # ------------------------------------------------------------------ #
    # Containment
    # ------------------------------------------------------------------ #
    def resolve(self, path: os.PathLike | str) -> Path:
        """Resolve ``path`` and assert it stays inside :attr:`base_dir`.

        Symlinks are resolved before the containment check, so a link planted
        inside the download directory cannot be used to escape it.

        Args:
            path: Absolute or relative candidate path.

        Returns:
            The resolved absolute :class:`~pathlib.Path`.

        Raises:
            FileAccessError: If the resolved path is outside :attr:`base_dir`.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.base_dir / candidate

        resolved = candidate.resolve()
        # Path.resolve() is non-strict, so a missing file still yields an absolute
        # path; containment is therefore checkable before touching the disk.
        try:
            resolved.relative_to(self.base_dir)
        except ValueError as exc:
            raise FileAccessError(
                f"Path escapes the managed download directory: {path}"
            ) from exc
        return resolved

    def is_contained(self, path: os.PathLike | str) -> bool:
        """Return whether ``path`` resolves inside :attr:`base_dir`."""
        try:
            self.resolve(path)
        except FileAccessError:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Directory management
    # ------------------------------------------------------------------ #
    def ensure_dir(self) -> Path:
        """Create :attr:`base_dir` if needed and return it.

        Raises:
            FileManagerError: If the directory cannot be created.
        """
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FileManagerError(
                f"Could not create download directory {self.base_dir}: {exc}"
            ) from exc
        return self.base_dir

    def ensure_parent_dir(self, path: os.PathLike | str) -> Path:
        """Create the parent directory of ``path`` and return the resolved path."""
        resolved = self.resolve(path)
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FileManagerError(
                f"Could not create directory {resolved.parent}: {exc}"
            ) from exc
        return resolved

    def unique_path(self, directory: os.PathLike | str, filename: str) -> Path:
        """Return a non-colliding path for ``filename`` inside ``directory``.

        Appends ``" (2)"``, ``" (3)"`` ... before the extension until the path is
        free, so importing files that collide with existing media never overwrites
        anything.
        """
        safe_name = self.sanitize_filename(filename)
        target_dir = self.resolve(directory)
        candidate = target_dir / safe_name

        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        counter = 2
        while True:
            candidate = target_dir / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def build_output_template(self, platform: str, ext: str = "mp4") -> str:
        """Return a yt-dlp output template under ``platform``.

        The template ends in ``.%(ext)s`` so yt-dlp can pick the real container
        after merging, and the platform segment is sanitised because it comes from
        user-supplied URLs.

        Args:
            platform: Platform name, e.g. ``"youtube"``. Sanitised.
            ext: Fallback extension when the template is already fully resolved.
        """
        safe_platform = self.sanitize_filename(platform or "unknown", fallback="unknown")
        directory = self.ensure_dir() / safe_platform
        directory.mkdir(parents=True, exist_ok=True)
        # The %(title)s/%(ext)s placeholders must survive verbatim: yt-dlp expands
        # them itself once it knows the real title and container.
        return str(directory / "%(title)s.%(ext)s")

    # ------------------------------------------------------------------ #
    # Inspection
    # ------------------------------------------------------------------ #
    def exists(self, path: os.PathLike | str) -> bool:
        """Return whether ``path`` resolves to an existing file inside the base dir."""
        try:
            return self.resolve(path).is_file()
        except FileAccessError:
            return False

    def get_size(self, path: os.PathLike | str) -> int:
        """Return the size of ``path`` in bytes.

        Returns:
            ``0`` when the file is missing, so library stats degrade gracefully when
            a user deletes files outside the application.
        """
        try:
            return self.resolve(path).stat().st_size
        except (FileAccessError, OSError):
            return 0

    def iter_media_files(self, root: Optional[os.PathLike | str] = None) -> Iterator[Path]:
        """Recursively yield every media file under ``root`` (default: the base dir).

        Extension filtering happens on the resolved path, and directories that
        cannot be read are skipped with a warning rather than aborting the scan.

        Yields:
            Absolute :class:`~pathlib.Path` objects inside :attr:`base_dir`.
        """
        try:
            scan_root = self.resolve(root) if root is not None else self.base_dir
        except FileAccessError as exc:
            logger.warning("Refusing to scan out-of-tree path: %s", exc)
            return

        if not scan_root.is_dir():
            return

        for dirpath, dirnames, filenames in os.walk(scan_root, followlinks=False):
            # Skip hidden and temp trees: yt-dlp leaves ".part" files and editors
            # leave lock files that would pollute the untracked-file report.
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in ("__pycache__", "node_modules")
            ]
            for filename in filenames:
                if filename.startswith(".") or filename.endswith((".part", ".ytdl", ".temp")):
                    continue
                candidate = Path(dirpath) / filename
                if self.is_media_file(candidate):
                    yield candidate

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #
    def rename(self, path: os.PathLike | str, new_name: str) -> Path:
        """Rename a file inside the base directory to a sanitised ``new_name``.

        The file keeps its original parent directory, so renaming never moves media
        between platform folders.

        Args:
            path: Current file path.
            new_name: Desired new filename; sanitised before use.

        Returns:
            The resolved path of the renamed file.

        Raises:
            FileAccessError: If ``path`` is outside the managed directory.
            FileNotFoundOnDisk: If the source file does not exist.
            FileManagerError: If the sanitised name is empty, collides with another
                file, or the rename fails.
        """
        source = self.resolve(path)
        if not source.is_file():
            raise FileNotFoundOnDisk(f"File does not exist: {source}")

        safe_name = self.sanitize_filename(new_name, fallback="")
        if not safe_name:
            raise FileManagerError("The new name is empty after sanitisation")

        target = self.resolve(source.parent / safe_name)
        if target == source:
            return source
        if target.exists():
            raise FileManagerError(f"A file named '{safe_name}' already exists in {source.parent}")

        try:
            source.rename(target)
        except OSError as exc:
            raise FileManagerError(f"Could not rename {source.name} to '{safe_name}': {exc}") from exc
        return target

    def delete(self, path: os.PathLike | str) -> bool:
        """Delete a file inside the base directory.

        Returns:
            ``True`` if a file was removed, ``False`` if it was already gone.

        Raises:
            FileAccessError: If ``path`` is outside the managed directory.
            FileManagerError: If the file exists but could not be removed.
        """
        target = self.resolve(path)
        if not target.exists():
            return False
        try:
            target.unlink()
        except OSError as exc:
            raise FileManagerError(f"Could not delete {target}: {exc}") from exc
        return True

    def delete_quietly(self, path: os.PathLike | str) -> bool:
        """Delete a file, swallowing errors and logging them instead.

        Used on cleanup paths (for example clearing a partially written download)
        where a failure must not abort the caller's transaction.
        """
        try:
            return self.delete(path)
        except FileManagerError as exc:
            logger.warning("Ignoring delete failure: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    # OS integration
    # ------------------------------------------------------------------ #
    def open_in_explorer(self, path: os.PathLike | str) -> None:
        """Reveal ``path`` in the native file manager.

        Uses ``subprocess`` with an argument list and ``shell=False`` throughout -
        the path is never interpolated into a shell string, so names containing
        quotes, semicolons or spaces cannot execute anything.

        Platform behaviour:

        * Windows - ``explorer /select,<path>`` selects the file.
        * macOS - ``open -R <path>`` reveals the file.
        * Linux - ``xdg-open <parent dir>`` opens the containing directory, since
          no standard "reveal" verb exists.

        Args:
            path: File to reveal.

        Raises:
            FileAccessError: If ``path`` is outside the managed directory.
            FileNotFoundOnDisk: If the file is missing.
            FileManagerError: If the platform is unsupported or the command cannot
                be started.
        """
        target = self.resolve(path)
        if not target.is_file():
            raise FileNotFoundOnDisk(f"File does not exist: {target}")

        command = self._explorer_command(target)
        try:
            # start_new_session detaches the explorer shell process on POSIX so it
            # does not keep a zombie tied to the API process.
            subprocess.Popen(  # noqa: S603 - argument list, shell=False by construction
                command,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=(sys.platform != "win32"),
            )
        except (OSError, ValueError) as exc:
            raise FileManagerError(f"Could not open the file manager: {exc}") from exc

    def _explorer_command(self, target: Path) -> List[str]:
        """Return the argument list used to reveal ``target`` on this platform."""
        if sys.platform == "win32":
            # explorer.exe requires /select with a comma and no space after it.
            return ["explorer", f"/select,{target}"]
        if sys.platform == "darwin":
            return ["open", "-R", str(target)]
        return ["xdg-open", str(target.parent)]

    # ------------------------------------------------------------------ #
    # Housekeeping
    # ------------------------------------------------------------------ #
    def cleanup_partials(self, directory: Optional[os.PathLike | str] = None) -> List[Path]:
        """Remove orphaned ``.part``/``.ytdl`` temp files and return what was removed.

        Called on startup: a crashed worker can leave fragments behind, and they
        would otherwise show up as noise in the library.
        """
        removed: List[Path] = []
        try:
            scan_root = self.resolve(directory) if directory is not None else self.base_dir
        except FileAccessError:
            return removed

        if not scan_root.is_dir():
            return removed

        for dirpath, _dirnames, filenames in os.walk(scan_root, followlinks=False):
            for filename in filenames:
                if not filename.endswith((".part", ".ytdl")):
                    continue
                candidate = Path(dirpath) / filename
                try:
                    candidate.unlink()
                    removed.append(candidate)
                except OSError as exc:  # pragma: no cover - platform dependent
                    logger.warning("Could not remove partial file %s: %s", candidate, exc)
        return removed

    def free_space_bytes(self) -> int:
        """Return free space on the volume holding :attr:`base_dir`, or 0 if unknown."""
        try:
            usage = shutil.disk_usage(self.base_dir)
        except OSError:  # pragma: no cover - platform dependent
            return 0
        return int(usage.free)