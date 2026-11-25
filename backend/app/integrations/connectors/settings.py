"""Kết nối MCP chung như Claude (QĐ-56). Cờ FEATURE_CONNECTORS mặc định tắt: tắt thì không gắn route."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CALLBACK_PATH = "/api/v1/connectors/oauth/callback"
CLIENT_NAME = "Trợ lý cá nhân"
DEEP_LINK = "troly://settings/connectors"
PRESETS = [
    {"name": "ERP DEGO", "url": "https://erp.degoholding.vn/api/mcp"},
    {"name": "ERP DEGO (thử nghiệm)", "url": "https://deverp.degoholding.vn/api/mcp"},
]


class ConnectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    public_base_url: str = "http://localhost:8200"
    connectors_redirect_uri: str = ""
    feature_connectors: bool = False
    connectors_timeout_seconds: float = 10.0
    connectors_max_response_bytes: int = 1024 * 1024

    @property
    def redirect_uri(self) -> str:
        return self.connectors_redirect_uri or self.public_base_url.rstrip("/") + CALLBACK_PATH


@lru_cache
def get_connector_settings() -> ConnectorSettings:
    return ConnectorSettings()
