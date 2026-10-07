import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MediaVault"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "An AI-powered, cross-platform social media downloader"
    API_V1_STR: str = "/api/v1"
    
    # Databases
    # Must use an async driver: app/db/database.py builds the engine with
    # create_async_engine, which rejects a plain "sqlite:///" URL outright.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./mediavault.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Paths & Binaries
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "./downloads")
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")
    
    # Application Logic
    ALLOWED_PLATFORMS: List[str] = ["youtube", "tiktok", "instagram", "facebook", "twitter"]
    MAX_CONCURRENT_DOWNLOADS: int = 3
    DEFAULT_QUALITY: str = "best"

    # Media file handling (used by the library scanner / FileManager)
    VIDEO_EXTENSIONS: List[str] = [".mp4", ".webm", ".mkv"]
    AUDIO_EXTENSIONS: List[str] = [".mp3", ".m4a"]
    MEDIA_EXTENSIONS: List[str] = [".mp4", ".webm", ".mkv", ".mp3", ".m4a"]
    MAX_FILENAME_LENGTH: int = 180

    # Redis key namespaces shared by the API, the queue orchestrator and the workers
    REDIS_KEY_PREFIX: str = "mediavault"
    REDIS_PAUSE_FLAG_TTL: int = 60 * 60 * 12
    REDIS_PROGRESS_TTL: int = 60 * 60 * 6
    
    # Third-party configurations
    YT_DLP_DEFAULTS: dict = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(extractor)s/%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0"
    }
    
    # Celery
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    
    # Security / CORS
    BACKEND_CORS_ORIGINS: List[str] = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Data directory for runtime files (settings.json, thumbnails, etc.)
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")

    # Post-processing defaults
    AUTO_MERGE: bool = True
    EMBED_METADATA: bool = True
    GENERATE_THUMBNAILS: bool = True
    MAX_CPU_PERCENT: int = 90
    MAX_RAM_PERCENT: int = 90

    # Fallback extraction defaults
    SCRAPER_API_KEY: str = ""
    SCRAPER_PROVIDER: str = "scraperapi"
    RAPID_API_KEY: str = ""
    PROVIDER_MONTHLY_LIMIT: int = 1000
    FALLBACK_ENABLED: bool = True

    # Desktop integration defaults
    CLIPBOARD_ENABLED: bool = False
    TRAY_ENABLED: bool = False
    CLIPBOARD_POLL_MS: int = 1000

    # AI auto-categorization defaults
    AUTO_CATEGORIZE: bool = True
    MIN_CONFIDENCE: float = 0.3
    USE_LLM_CATEGORIZE: bool = False
    OLLAMA_HOST: str = "http://localhost:11434"

    # Storage guard defaults
    STORAGE_GUARD_ENABLED: bool = True
    MIN_FREE_GB: float = 5.0

    # Cloud backup defaults
    CLOUD_BACKUP_ENABLED: bool = False
    CLOUD_PROVIDER: str = ""
    GOOGLE_DRIVE_CLIENT_ID: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""
    DROPBOX_ACCESS_TOKEN: str = ""
    CLOUD_TOKENS_FILE: str = os.getenv("CLOUD_TOKENS_FILE", "./data/cloud_tokens.json")

    # Smart deduplication defaults
    DEDUP_ENABLED: bool = True
    DEDUP_THRESHOLD: int = 6

    # yt-dlp download archive (URL-level dedup)
    ARCHIVE_DEDUP_ENABLED: bool = True
    ARCHIVE_DEDUP_PATH: str = os.getenv("ARCHIVE_DEDUP_PATH", "")

    # Content moderation / parental controls
    SAFE_MODE: bool = False
    PIN_HASH: str = ""
    KEYWORD_BLACKLIST: List[str] = []
    MODERATION_SENSITIVITY: float = 0.5

    # AI transcription and summarization defaults
    AI_ANALYSIS_ENABLED: bool = False
    WHISPER_MODEL: str = "base"
    OLLAMA_MODEL: str = "llama3"
    AUTO_TRANSLATE_LANGS: List[str] = []

    # Scheduled downloads and network optimization
    BANDWIDTH_LIMIT_MBPS: int = 0
    AUTO_ADJUST_QUALITY: bool = True
    OFF_PEAK_START: str = "23:00"
    OFF_PEAK_END: str = "06:00"
    OFF_PEAK_ENABLED: bool = False

    # Network speed cache TTL (seconds)
    NETWORK_SPEED_CACHE_TTL: int = 600

    # Turbo / performance mode
    TURBO_MODE: bool = True
    CONCURRENT_FRAGMENTS: int = 16
    ARIA2_CONNECTIONS: int = 16

    # Push notification defaults
    PUSH_ENABLED: bool = True

    # Remote control defaults
    REMOTE_ENABLED: bool = True
    PAIRING_TTL_SECONDS: int = 120
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")

    # Dynamic plugin settings
    USER_PLUGINS_DIR: str = os.getenv("USER_PLUGINS_DIR", "./user_plugins")

    # Telegram bot settings
    TELEGRAM_BOT_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_CHAT_IDS: str = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")

    # Billing settings
    BILLING_ENABLED: bool = False
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "stub")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_STARTER: str = os.getenv("STRIPE_PRICE_STARTER", "")
    STRIPE_PRICE_PRO: str = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_ENTERPRISE: str = os.getenv("STRIPE_PRICE_ENTERPRISE", "")

    # Authentication and authorization (Phase 17A)
    AUTH_ENABLED: bool = False
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ACCESS_TTL_MIN: int = 30
    JWT_REFRESH_TTL_DAYS: int = 7
    MAX_FAILED_LOGINS: int = 5
    LOCK_MINUTES: int = 15
    REGISTRATION_OPEN: bool = False
    GLOBAL_RATE_LIMIT: int = 120


settings = Settings()
