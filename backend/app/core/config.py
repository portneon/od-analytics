"""Central application configuration, loaded from environment variables.

All tunables that would otherwise be magic numbers (file size limits, page
sizes, anomaly thresholds, risk weights, cache TTLs, retry windows) live here
so they can be changed without touching business logic.
"""
from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "Email Intelligence Platform"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://email_intel:email_intel@localhost:5432/email_intel"

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize provider-issued Postgres URLs for psycopg2 compatibility.

        - Converts ``postgresql://`` to ``postgresql+psycopg2://``.
        - Strips ``channel_binding`` (unsupported by psycopg2-binary).
        """
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://"):]
        parsed = urlparse(v)
        if parsed.query:
            params = parse_qs(parsed.query)
            params.pop("channel_binding", None)
            cleaned_query = urlencode(params, doseq=True)
            v = urlunparse(parsed._replace(query=cleaned_query))
        return v

    # Object storage (S3-compatible / MinIO)
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_BUCKET: str = "email-intel-raw"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_USE_LOCAL_FS: bool = True
    LOCAL_STORAGE_PATH: str = "./data/raw"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174"

    # AI provider abstraction
    LLM_PROVIDER: Literal["anthropic", "openai", "groq", "none"] = "none"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "openai/gpt-oss-120b"

    # Ingestion limits
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 200 * 1024 * 1024  # 200MB
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".csv",)

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # Anomaly detection
    ANOMALY_Z_SCORE_THRESHOLD: float = 2.5
    ANOMALY_MIN_HISTORY_POINTS: int = 7
    ANOMALY_IQR_MULTIPLIER: float = 1.5

    # Recipient risk scoring weights (must sum to ~1.0 across weighted terms)
    RISK_WEIGHT_HARD_BOUNCE: float = 0.35
    RISK_WEIGHT_SOFT_BOUNCE: float = 0.15
    RISK_WEIGHT_FAILURE_RATE: float = 0.25
    RISK_WEIGHT_FAILURE_STREAK: float = 0.15
    RISK_WEIGHT_RECENCY: float = 0.10

    # Retry/duplicate detection
    RETRY_WINDOW_MINUTES: int = 60
    DUPLICATE_TIMESTAMP_BUCKET_SECONDS: int = 60

    # Caching
    CACHE_TTL_SECONDS: int = 300

    # Timezone
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # Bot/automation integrations (e.g. Zoho Cliq): a shared secret the
    # caller must present in the X-Bot-Api-Key header. None/empty disables
    # the endpoint entirely rather than leaving it open with no auth, since
    # it's meant to be reachable from the public internet.
    BOT_API_KEY: str | None = None
    # Optional, used to build a "view full dashboard" link in bot replies.
    FRONTEND_PUBLIC_URL: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.APP_ENV == "development":
            dev_defaults = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:3000"]
            for d in dev_defaults:
                if d not in origins:
                    origins.append(d)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
