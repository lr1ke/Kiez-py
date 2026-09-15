from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "postgresql+psycopg://kiez:kiez@127.0.0.1:5432/kiez"
    environment: str = "development"
    public_origin: str = "http://localhost:3000"
    session_secret: str = ""
    cron_secret: str = ""
    admin_secret: str = ""
    demo_data: bool = True
    demo_anchor_date: str = ""
    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-3.6-flash"
    gemini_transcription_model: str = "gemini-3.6-flash"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_voice: str = "Kore"
    openai_api_key: str = ""
    openai_chronicle_model: str = "gpt-4.1"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    transcription_provider: str = "gemini"
    translation_provider: str = "gemini"
    detection_provider: str = "gemini"
    chronicle_provider: str = "openai"
    tts_provider: str = "auto"
    enabled_audio_languages: str = "en,de,tr,ar,es"
    provider_timeout_seconds: float = 90
    worker_poll_seconds: float = 1
    job_lease_seconds: int = 120
    job_ttl_seconds: int = 900
    job_max_attempts: int = 3
    interactive_concurrency: int = 4
    chronicle_concurrency: int = 1
    ai_daily_task_limit: int = 2000
    scheduler_interval_seconds: int = 300

    @model_validator(mode="after")
    def validate_runtime(self):
        if not self.session_secret:
            if self.environment == "production":
                raise ValueError("SESSION_SECRET is required in production")
            # Stable across local API/worker processes, never used in production.
            self.session_secret = "kiez-py-local-development-only-change-before-deployment"
        for field in (
            "job_lease_seconds",
            "job_ttl_seconds",
            "job_max_attempts",
            "interactive_concurrency",
            "chronicle_concurrency",
            "ai_daily_task_limit",
        ):
            if getattr(self, field) < 1:
                raise ValueError(f"{field} must be positive")
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self

    @property
    def languages(self):
        return list(
            dict.fromkeys(
                x.strip()
                for x in self.enabled_audio_languages.split(",")
                if x.strip() in {"en", "de", "tr", "ar", "es"}
            )
        )


@lru_cache
def get_settings():
    return Settings()
