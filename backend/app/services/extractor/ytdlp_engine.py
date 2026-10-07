import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError
from app.schemas.media import MediaMetadata, DownloadOption
from app.core.config import settings
from app.core import redis_client

logger = logging.getLogger(__name__)


class YTDLPControlSignal(Exception):
    """
    Base class for exceptions raised from a progress hook to interrupt a transfer.

    A progress callback may need to abort the download (pausing it, for example).
    That is control flow rather than a failure, so it must not be rewritten into a
    ``YTDLPEngineError`` - callers need to receive it unchanged to tell "paused"
    apart from "failed".
    """


class YTDLPEngineError(Exception):
    def __init__(self, message: str, code: str = "EXTRACTOR_ERROR", action: str = "Try again later"):
        self.message = message
        self.code = code
        self.action = action
        super().__init__(self.message)


class YTDLPEngine:
    """
    Robust wrapper around yt-dlp for extracting media metadata and downloading files.

    Turbo mode (``settings.turbo_mode``) activates two performance enhancements when
    the ``aria2c`` binary is present on PATH:

    1. ``external_downloader`` / ``external_downloader_args`` — aria2c handles the
       HTTP download with many parallel connections, which is dramatically faster for
       single-file MP4 downloads.
    2. ``concurrent_fragments`` — yt-dlp parallelizes DASH/HLS segment downloads.

    When aria2c is missing, turbo mode degrades gracefully: only ``concurrent_fragments``
    is applied and the native downloader continues to be used.  No exception is raised
    so the rest of the pipeline is unaffected.
    """

    def __init__(self):
        self.base_options = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "socket_timeout": 30,
            "retries": 3,
            "cachedir": "/tmp/yt-dlp-cache",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
        }

    @staticmethod
    def _aria2_available() -> bool:
        """Return True when the ``aria2c`` binary is on PATH."""
        return shutil.which("aria2c") is not None

    def _turbo_options(self) -> Dict[str, Any]:
        """Return aria2c-related yt-dlp options when turbo mode is active.

        The dictionary is empty when turbo mode is disabled or aria2c is not
        installed, so callers can merge it unconditionally.
        """
        turbo: Dict[str, Any] = {}
        if not getattr(settings, "TURBO_MODE", False):
            return turbo

        connections = getattr(settings, "ARIA2_CONNECTIONS", 16)
        turbo["concurrent_fragments"] = getattr(settings, "CONCURRENT_FRAGMENTS", 16)

        if self._aria2_available():
            turbo["external_downloader"] = "aria2c"
            turbo["external_downloader_args"] = {
                "aria2c": [
                    f"-x{connections}",
                    f"-s{connections}",
                    "-k1M",
                    f"--max-connection-per-server={connections}",
                    "--min-split-size=1M",
                ]
            }
            logger.debug("Turbo mode: aria2c enabled with %d connections", connections)
        else:
            logger.debug("Turbo mode: aria2c not found; using native downloader with concurrent_fragments=%d", turbo["concurrent_fragments"])

        return turbo

    def _handle_yt_dlp_exception(self, e: Exception) -> None:
        """Categorize and raise a domain-specific exception."""
        error_msg = str(e)
        if isinstance(e, DownloadError):
            if "Sign in to confirm your age" in error_msg:
                raise YTDLPEngineError(
                    message="Age restricted content. Authentication required.",
                    code="AGE_RESTRICTED",
                    action="Provide valid cookies or credentials."
                )
            if "Video unavailable" in error_msg or "Private video" in error_msg:
                raise YTDLPEngineError(
                    message="Video is unavailable or private.",
                    code="UNAVAILABLE_OR_PRIVATE",
                    action="Check if the URL is correct and accessible publicly."
                )
            raise YTDLPEngineError(
                message=f"Download failed: {error_msg}",
                code="DOWNLOAD_ERROR",
                action="Verify the URL and network connection."
            )
        elif isinstance(e, ExtractorError):
            if "Geo-restricted" in error_msg or "blocked in your country" in error_msg:
                raise YTDLPEngineError(
                    message="Content is geo-restricted.",
                    code="GEO_RESTRICTED",
                    action="Use a proxy or VPN from an allowed region."
                )
            raise YTDLPEngineError(
                message=f"Extraction failed: {error_msg}",
                code="EXTRACTOR_ERROR",
                action="Check if the platform is supported or if the URL format changed."
            )
        else:
            raise YTDLPEngineError(
                message=f"An unexpected error occurred: {error_msg}",
                code="UNKNOWN_ERROR",
                action="Review system logs."
            )

    @staticmethod
    def _cache_key(url: str) -> str:
        """Build a stable Redis cache key from a URL."""
        import hashlib
        return f"{settings.REDIS_KEY_PREFIX}:extract_cache:{hashlib.sha256(url.encode()).hexdigest()}"

    def _cached_extract_info(self, url: str, download: bool = False) -> Optional[Dict[str, Any]]:
        """Return cached ``extract_info`` result when available and fresh."""
        if download:
            return None
        try:
            client = redis_client.get_redis()
            raw = client.get(self._cache_key(url))
            if raw:
                return redis_client._deserialize_json(raw) if hasattr(redis_client, "_deserialize_json") else __import__("json").loads(raw)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Extraction cache read failed for %s: %s", url, exc)
        return None

    def _write_extract_cache(self, url: str, data: Dict[str, Any]) -> None:
        """Persist ``extract_info`` result to Redis with TTL."""
        ttl = getattr(settings, "NETWORK_SPEED_CACHE_TTL", 600)
        try:
            client = redis_client.get_redis()
            client.set(self._cache_key(url), __import__("json").dumps(data, default=str), ex=ttl)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Extraction cache write failed for %s: %s", url, exc)

    def extract_info(self, url: str, download: bool = False) -> Dict[str, Any]:
        """
        Uses yt-dlp to extract video metadata, with an optional Redis-backed cache.
        """
        cached = self._cached_extract_info(url, download=download)
        if cached is not None:
            logger.debug("Extraction cache hit for %s", url)
            return cached

        options = self.base_options.copy()

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info_dict = ydl.extract_info(url, download=download)

                if not info_dict:
                    raise YTDLPEngineError("No metadata could be extracted.", code="NO_METADATA")

                if 'entries' in info_dict:
                    self._write_extract_cache(url, info_dict)
                    return info_dict

                formats = self._parse_formats(info_dict.get('formats', []), info_dict.get('extractor', ''))

                metadata = MediaMetadata(
                    id=info_dict.get('id', ''),
                    title=info_dict.get('title', 'Unknown Title'),
                    description=info_dict.get('description'),
                    duration=info_dict.get('duration'),
                    thumbnail_url=info_dict.get('thumbnail'),
                    uploader_name=info_dict.get('uploader'),
                    uploader_url=info_dict.get('uploader_url'),
                    upload_date=info_dict.get('upload_date'),
                    view_count=info_dict.get('view_count'),
                    like_count=info_dict.get('like_count'),
                    tags=info_dict.get('tags') or [],
                    platform=self._platform_from_extractor(info_dict.get('extractor', '')),
                    content_type=self._content_type_from_formats(info_dict.get('formats', [])),
                    formats=formats,
                    raw_data=info_dict
                )

                result = metadata.model_dump()
                self._write_extract_cache(url, result)
                return result

        except Exception as e:
            self._handle_yt_dlp_exception(e)

    def _parse_formats(self, raw_formats: List[Dict[str, Any]], extractor: str) -> List[DownloadOption]:
        """
        Parse raw yt-dlp formats into normalized DownloadOption schemas,
        applying platform-specific logic.
        """
        options = []
        for f in raw_formats:
            if f.get('acodec') == 'none' and f.get('vcodec') == 'none':
                continue
            if not f.get('url'):
                continue

            has_video = f.get('vcodec') != 'none'
            has_audio = f.get('acodec') != 'none'
            height = None

            if has_video:
                height = f.get('height')
                quality = f"{height}p" if height else "unknown"
            elif has_audio and not has_video:
                quality = "audio_only"
            else:
                quality = "unknown"

            watermarked = False
            format_note = f.get('format_note', '').lower()

            if 'tiktok' in extractor.lower():
                if 'watermark' in format_note:
                    watermarked = True

            elif 'youtube' in extractor.lower():
                dynamic_range = f.get('dynamic_range', '').lower()
                if dynamic_range in ['hdr', 'sdr']:
                    quality += f" ({dynamic_range.upper()})"

            option = DownloadOption(
                format_id=f.get('format_id', ''),
                quality=quality,
                extension=f.get('ext', 'mp4'),
                url=f.get('url', ''),
                file_size_estimate=f.get('filesize') or f.get('filesize_approx'),
                is_watermark_free=not watermarked,
                resolution=str(height) if height else None,
                codec=self._codec_label(f)
            )
            options.append(option)

        return options

    @staticmethod
    def _platform_from_extractor(extractor: str) -> str:
        """Map a yt-dlp extractor key onto a MediaVault platform name."""
        return (extractor or "unknown").strip().lower()

    @staticmethod
    def _content_type_from_formats(raw_formats: List[Dict[str, Any]]) -> str:
        """Return ``"audio"`` only when every offered format is audio-only."""
        usable = [
            f for f in raw_formats
            if f.get('url') and not (f.get('vcodec') == 'none' and f.get('acodec') == 'none')
        ]
        if usable and all(f.get('vcodec') == 'none' for f in usable):
            return "audio"
        return "video"

    @staticmethod
    def _codec_label(fmt: Dict[str, Any]) -> Optional[str]:
        """Return a human-readable codec label combining the video and audio codecs."""
        vcodec = fmt.get('vcodec')
        acodec = fmt.get('acodec')
        parts = [c for c in (vcodec, acodec) if c and c != 'none']
        return "+".join(parts) if parts else None

    def get_best_format(self, url: str, quality_preference: str = "best") -> Optional[Dict[str, Any]]:
        """
        Analyzes available formats and selects the best one based on preference.
        """
        metadata = self.extract_info(url, download=False)
        formats: List[Dict[str, Any]] = metadata.get("formats", [])

        if not formats:
            return None

        clean_formats = [f for f in formats if f.get('is_watermark_free', True)]
        target_formats = clean_formats if clean_formats else formats

        audio_renditions = [f for f in target_formats if f.get('quality') == 'audio_only']
        video_renditions = [f for f in target_formats if f.get('quality') != 'audio_only']

        if quality_preference == "audio_only":
            if audio_renditions:
                return sorted(audio_renditions, key=lambda x: x.get('file_size_estimate') or 0, reverse=True)[0]
            return None

        if quality_preference == "best":
            if video_renditions:
                return sorted(video_renditions, key=lambda x: x.get('file_size_estimate') or 0, reverse=True)[0]
            if audio_renditions:
                return sorted(audio_renditions, key=lambda x: x.get('file_size_estimate') or 0, reverse=True)[0]
            return None

        res_formats = [f for f in video_renditions if f['quality'].startswith(quality_preference)]
        if res_formats:
            return sorted(res_formats, key=lambda x: x.get('file_size_estimate') or 0, reverse=True)[0]

        return target_formats[-1] if target_formats else None

    def download_media(
        self,
        url: str,
        output_path: str,
        format_id: str = None,
        progress_callback: Callable = None,
        extra_options: Dict[str, Any] = None,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit_rate_mbps: Optional[int] = None,
        auto_adjust_quality: bool = False,
        download_archive: Optional[str] = None,
    ) -> str:
        """
        Downloads media to the specified path with progress monitoring.

        Args:
            url: Source URL to download.
            output_path: yt-dlp output template, e.g. ``".../%(title)s.%(ext)s"``.
            format_id: Optional explicit format selector.
            progress_callback: Called with a single progress dict on each chunk.
            extra_options: Additional yt-dlp options merged last, so a caller can
                override anything in ``base_options``. Used by the download worker
                to set ``continuedl`` when resuming a partial ``.part`` file.
            start_time: Optional trim start time as ``"HH:MM:SS"`` or seconds.
            end_time: Optional trim end time as ``"HH:MM:SS"`` or seconds.
            limit_rate_mbps: Optional bandwidth cap in megabits per second. When
                set, yt-dlp receives ``--limit-rate`` in a human-readable form.
            auto_adjust_quality: When True, ignore the caller's quality preference
                and use :func:`app.services.network.network_monitor.get_recommended_quality`
                based on the cached network speed.
            download_archive: Optional path to a yt-dlp download archive file.
                When provided, yt-dlp skips URLs already recorded in the archive.

        Returns:
            The final prepared filename, or an empty string if extraction failed.
        """
        options = self.base_options.copy()
        options['outtmpl'] = output_path

        if download_archive:
            options['download_archive'] = download_archive

        # Turbo mode: aria2c external downloader + concurrent fragments.
        turbo_opts = self._turbo_options()
        options.update(turbo_opts)

        if auto_adjust_quality:
            from app.services.network.network_monitor import get_current_speed, get_recommended_quality
            recommended = get_recommended_quality(get_current_speed())
            if recommended == "best":
                pass
            else:
                options['format'] = recommended
        elif format_id:
            options['format'] = format_id

        if limit_rate_mbps and limit_rate_mbps > 0:
            if limit_rate_mbps >= 1000:
                options['limit_rate'] = f"{limit_rate_mbps // 1000}G"
            else:
                options['limit_rate'] = f"{limit_rate_mbps}M"

        if start_time or end_time:
            start = start_time or "0"
            end = end_time or "9999"
            options['download_sections'] = [f"*{start}-{end}"]

        if extra_options:
            options.update(extra_options)

        if progress_callback:
            def yt_dlp_hook(d: dict):
                if d['status'] == 'downloading':
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    payload = {
                        "status": "downloading",
                        "downloaded_bytes": downloaded_bytes,
                        "total_bytes": total_bytes,
                        "speed": d.get('speed'),
                        "eta": d.get('eta'),
                    }
                    if total_bytes and total_bytes > 0:
                        payload["progress"] = round((downloaded_bytes / total_bytes) * 100, 2)
                    progress_callback(payload)
                elif d['status'] == 'finished':
                    progress_callback({
                        "status": "finished",
                        "progress": 100.0,
                        "downloaded_bytes": d.get('downloaded_bytes'),
                        "total_bytes": d.get('total_bytes') or d.get('total_bytes_estimate')
                    })

            options['progress_hooks'] = [yt_dlp_hook]

        if '+' in options.get('format', '') and not shutil.which('ffmpeg'):
            raise YTDLPEngineError(
                message="High-res download needs ffmpeg (separate video+audio streams). Install ffmpeg and retry.",
                code="FFMPEG_MISSING",
                action="Install ffmpeg: https://ffmpeg.org/download.html",
            )

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(info)
                if start_time or end_time:
                    stem = Path(final_filename).stem
                    suffix = Path(final_filename).suffix
                    segment = f"[{start_time or '0'}-{end_time or 'end'}]"
                    final_filename = str(Path(final_filename).parent / f"{stem} {segment}{suffix}")
                return final_filename
        except YTDLPControlSignal:
            raise
        except Exception as e:
            self._handle_yt_dlp_exception(e)
            return ""

    def get_subtitles(self, url: str, languages: list = ["en"]) -> Dict[str, str]:
        """
        Extracts available subtitles for the video.
        """
        options = self.base_options.copy()
        options['skip_download'] = True
        options['writesubtitles'] = True
        options['writeautomaticsub'] = True
        options['subtitleslangs'] = languages

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                subs = {}
                req_subs = info.get('requested_subtitles', {})
                for lang, sub_info in req_subs.items():
                    subs[lang] = sub_info.get('url', '')

                if not subs:
                    all_subs = info.get('subtitles', {})
                    for lang in languages:
                        if lang in all_subs and len(all_subs[lang]) > 0:
                            subs[lang] = all_subs[lang][0].get('url', '')

                return subs
        except Exception as e:
            logger.error(f"Failed to fetch subtitles: {str(e)}")
            return {}
