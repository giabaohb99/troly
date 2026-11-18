"""Bóc tách có cấu trúc một lần gọi (20 mục 3.10): không công cụ, không lịch sử, đầu ra theo Pydantic."""

from pydantic import BaseModel

from app.ai.client import ClaudeClient, get_client
from app.ai.settings import get_ai_settings


def extract_structured[T: BaseModel](
    *,
    user_id: int | None,
    purpose: str,
    output_model: type[T],
    content: str | list[dict],
    system: str | None = None,
    model: str | None = None,
    effort: str = "low",
    max_tokens: int = 1024,
    client: ClaudeClient | None = None,
) -> T | None:
    """Trả đối tượng đã kiểm, hoặc None khi bị từ chối, bị cắt hoặc không đọc được."""
    client = client or get_client()
    params = {
        "model": model or get_ai_settings().ai_model_extract,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": effort},
    }
    if system:
        params["system"] = system
    res = client.parse(params, output_model, purpose=purpose, user_id=user_id)
    if res.stop_reason in ("refusal", "max_tokens") or res.parsed is None:
        return None
    parsed = res.parsed
    return parsed if isinstance(parsed, output_model) else output_model.model_validate(parsed)
