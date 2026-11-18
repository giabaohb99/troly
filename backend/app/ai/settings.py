"""Biến môi trường của tầng AI, tên theo docs/10-backend/10-kien-truc-backend.md mục 3.6."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    anthropic_api_key: str = ""
    ai_model_chat: str = "claude-haiku-5-5"
    ai_model_extract: str = "claude-haiku-5-5"
    ai_model_smart: str = "claude-sonnet-5-5"
    ai_model_max: str = "claude-opus-5-5"
    ai_effort_chat: str = "low"
    ai_compact_tokens: int = 30000
    ai_max_tool_rounds: int = 8
    ai_monthly_usd: float = 200.0
    ai_inbox_max_items: int = 200
    ai_timeout_seconds: float = 60.0


@lru_cache
def get_ai_settings() -> AiSettings:
    return AiSettings()
