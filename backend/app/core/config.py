"""Cấu hình đọc một lần từ biến môi trường của container (10 mục 3.6)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    env: str = "dev"
    app_timezone: str = "Asia/Ho_Chi_Minh"
    cors_origins: str = "https://localhost,http://localhost:5190"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8200"
    app_version: str = "dev"
    git_sha: str = "dev"

    database_url: str
    jwt_secret: str = ""
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 365
    token_encryption_keys: str = ""

    anthropic_api_key: str = ""
    ai_model_chat: str = "claude-haiku-5-5"
    ai_model_extract: str = "claude-haiku-5-5"
    ai_model_smart: str = "claude-sonnet-5-5"
    ai_model_max: str = "claude-opus-5-5"
    ai_effort_chat: str = "low"
    ai_compact_tokens: int = 30000
    ai_max_tool_rounds: int = 8
    ai_user_hourly_turns: int = 60
    ai_monthly_usd: float = 200.0
    ai_inbox_max_items: int = 200

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_endpoint: str = ""
    r2_bucket: str = "assistant"  # một bucket, chia tiền tố files/, backups/, releases/ (QĐ-31)
    r2_presign_seconds: int = 300

    backup_weekday: int = 6
    backup_hour: int = 2
    backup_minute: int = 0
    backup_keep: int = 5

    worker_poll_seconds: int = 30
    worker_batch_size: int = 200

    inbox_retention_days: int = 180
    device_event_retention_days: int = 180
    third_party_chat_retention_days: int = 180
    chat_retention_days: int = 365
    client_log_retention_days: int = 30

    disk_warn_percent: int = 15
    disk_stop_percent: int = 8

    rate_login_per_15min: int = 10
    rate_device_events_per_min: int = 120
    rate_chat_per_min: int = 20
    rate_user_per_min: int = 300

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def r2_endpoint_url(self) -> str:
        if self.r2_endpoint:
            return self.r2_endpoint
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
