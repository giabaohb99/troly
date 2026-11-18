"""Biến môi trường của tích hợp Google (10 mục 3.6). Đọc riêng như ai/settings.py, không đụng core/config."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CALLBACK_PATH = "/api/v1/google/oauth/callback"
WEBHOOK_PATH = "/api/v1/webhooks/google/calendar"


class GoogleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    public_base_url: str = "http://localhost:8200"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    google_sync_min_seconds: int = 300
    google_maps_api_key: str = ""
    google_timeout_seconds: float = 10.0

    @property
    def redirect_uri(self) -> str:
        return self.google_redirect_uri or self.public_base_url.rstrip("/") + CALLBACK_PATH

    @property
    def webhook_url(self) -> str | None:
        """Google chỉ nhận webhook HTTPS có chứng chỉ hợp lệ; máy dựng (http) thì không tạo kênh."""
        base = self.public_base_url.rstrip("/")
        return base + WEBHOOK_PATH if base.startswith("https://") else None

    @property
    def configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_google_settings() -> GoogleSettings:
    return GoogleSettings()
