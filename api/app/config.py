from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_mode: str = Field(default="demo", validation_alias="PROOFMARK_DATA_MODE")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="PROOFMARK_CORS_ORIGINS",
    )
    supabase_url: str = Field(
        default="https://zxjaccusnmunjgktzkme.supabase.co",
        validation_alias="SUPABASE_URL",
    )
    supabase_secret_key: str = Field(default="", validation_alias="SUPABASE_SECRET_KEY")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash-lite", validation_alias="GEMINI_MODEL")
    gemini_claim_model: str = Field(default="", validation_alias="GEMINI_CLAIM_MODEL")
    gemini_casemap_model: str = Field(default="gemini-3.6-flash", validation_alias="GEMINI_CASEMAP_MODEL")
    gemini_timeout_seconds: float = Field(default=8.0, validation_alias="GEMINI_TIMEOUT_SECONDS")
    audit_retention_days: int = Field(default=30, ge=1, le=3650, validation_alias="PROOFMARK_AUDIT_RETENTION_DAYS")
    refresh_interval_hours: int = Field(default=24, ge=0, le=720, validation_alias="PROOFMARK_REFRESH_INTERVAL_HOURS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def claim_model(self) -> str:
        return self.gemini_claim_model or self.gemini_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
