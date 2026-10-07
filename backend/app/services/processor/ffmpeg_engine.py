"""FFmpeg/FFprobe wrapper for post-processing.

All subprocess calls use ``asyncio.create_subprocess_exec`` with ``shell=False``.
A 300-second timeout guards against hanging conversions on corrupt media.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    size: int


class FFmpegEngine:
    """Wrapper around ffmpeg/ffprobe binaries."""

    def __init__(self, ffmpeg_path: Optional[str] = None, ffprobe_path: Optional[str] = None) -> None:
        self.ffmpeg_path = ffmpeg_path or getattr(settings, "FFMPEG_PATH", "ffmpeg") or "ffmpeg"
        self.ffprobe_path = ffprobe_path or (shutil.which("ffprobe") or "ffprobe")

    async def check_available(self) -> bool:
        """Return ``True`` when both ffmpeg and ffprobe binaries are on PATH."""
        return shutil.which(self.ffmpeg_path) is not None and shutil.which(self.ffprobe_path) is not None

    async def get_media_info(self, file_path: str) -> MediaInfo:
        """Probe ``file_path`` and return media metadata."""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {file_path}: {stderr.decode().strip()}")

        data = json.loads(stdout.decode() or "{}")
        fmt = data.get("format", {})
        size = int(fmt.get("size", 0))
        duration = float(fmt.get("duration", 0.0))

        video_codec = ""
        audio_codec = ""
        width = 0
        height = 0

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and not video_codec:
                video_codec = stream.get("codec_name", "")
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
            elif codec_type == "audio" and not audio_codec:
                audio_codec = stream.get("codec_name", "")

        return MediaInfo(
            duration=duration,
            width=width,
            height=height,
            video_codec=video_codec,
            audio_codec=audio_codec,
            size=size,
        )

    async def merge_streams(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Merge separate video and audio streams into ``output_path`` using stream copy."""
        tmp_path = f"{output_path}.tmpmerge"
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c", "copy",
            tmp_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        if proc.returncode != 0:
            Path(tmp_path).unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg merge failed: {stderr.decode().strip()}")

        try:
            Path(video_path).unlink(missing_ok=True)
        except OSError:
            pass
        try:
            Path(audio_path).unlink(missing_ok=True)
        except OSError:
            pass
        Path(tmp_path).rename(output_path)
        return output_path

    async def embed_metadata(self, file_path: str, meta: dict) -> str:
        """Embed metadata into ``file_path`` without re-encoding.

        Writes to a temporary file first and replaces the original only on success,
        because ffmpeg cannot safely overwrite its input in-place.
        """
        tmp_path = f"{file_path}.tmpmeta"
        cmd = [self.ffmpeg_path, "-y", "-i", file_path]

        if meta.get("title"):
            cmd.extend(["-metadata", f"title={meta['title']}"])
        if meta.get("artist"):
            cmd.extend(["-metadata", f"artist={meta['artist']}"])
        if meta.get("date"):
            cmd.extend(["-metadata", f"date={meta['date']}"])
        if meta.get("comment"):
            comment = str(meta["comment"])[:500]
            cmd.extend(["-metadata", f"comment={comment}"])

        cmd.extend(["-c", "copy", tmp_path])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        if proc.returncode != 0:
            Path(tmp_path).unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg metadata embed failed: {stderr.decode().strip()}")

        Path(file_path).unlink(missing_ok=True)
        Path(tmp_path).rename(file_path)
        return file_path

    async def generate_thumbnail(self, video_path: str, output_path: str, at_second: int = 2) -> str:
        """Extract a JPEG thumbnail at ``at_second`` seconds."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", video_path,
            "-ss", str(at_second),
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg thumbnail failed: {stderr.decode().strip()}")

        return output_path

    async def normalize_to_mp4(self, input_path: str, output_path: str) -> str:
        """Re-encode ``.webm`` or ``.mkv`` sources to H.264 + AAC MP4."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg normalize failed: {stderr.decode().strip()}")

        return output_path
