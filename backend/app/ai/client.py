"""Gọi Claude qua SDK `anthropic` (đồng bộ): stream, gọi thường, parse; đo token, tính tiền, ghi tab_ai_run.

Mọi lần gọi Claude trong backend đi qua lớp này để không lần nào lọt khỏi `tab_ai_run`.
SDK được nạp lười, nên bài kiểm dùng FakeClaude không cần cài `anthropic`.
"""

import logging
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from app.ai.pricing import UsageCount, compute_cost_usd, usage_from_response
from app.ai.router import supports_fallbacks
from app.ai.schemas import AiError, AiRequestError
from app.ai.settings import AiSettings, get_ai_settings

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MCP_BETA = "mcp-client-2026-09-15"  # trùng ai.mcp.MCP_BETA; client không import mcp để khỏi vòng
MSG_BUSY = "Claude đang quá tải, thử lại sau ít phút."
MSG_DOWN = "Không gọi được Claude, thử lại sau ít phút."
MSG_KEY = "Khóa Claude sai, đã bị thu hồi hoặc chưa đặt trong .env."


@dataclass
class RunRecord:
    user_id: int | None
    purpose: str
    model: str
    mode: str | None
    effort: str | None
    conversation_id: int | None
    usage: UsageCount
    cost_usd: Decimal
    rate_card: str | None
    stop_reason: str | None
    refusal_category: str | None
    latency_ms: int
    request_id: str | None
    error_code: str | None
    fallback_used: bool
    mcp_servers_used: list[str] | None = None  # máy chủ MCP gắn vào lần gọi (QĐ-53), để đo chi phí


class RunRecorder(Protocol):
    def record(self, rec: RunRecord) -> int | None: ...


class NullRecorder:
    def __init__(self):
        self.records: list[RunRecord] = []

    def record(self, rec: RunRecord) -> int | None:
        self.records.append(rec)
        return len(self.records)


@dataclass
class ClaudeResult:
    message: Any
    content: list[dict]
    model: str
    stop_reason: str | None
    refusal_category: str | None
    usage: UsageCount
    cost_usd: Decimal
    run_id: int | None
    fallback_used: bool = False
    parsed: Any = None
    extra: dict = field(default_factory=dict)


def block_to_dict(block: Any) -> dict:
    if isinstance(block, dict):
        return block
    if hasattr(block, "to_dict"):
        return block.to_dict()
    return block.model_dump(exclude_none=True)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _map_error(exc: Exception) -> AiError:
    if isinstance(exc, AiError):
        return exc
    try:
        import anthropic
    except ImportError:  # pragma: no cover - chỉ khi chưa cài SDK
        return AiError("AI_UNAVAILABLE", MSG_DOWN)
    if isinstance(exc, anthropic.BadRequestError):
        return AiRequestError("AI_UNAVAILABLE", str(getattr(exc, "message", exc)))
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return AiError("AI_UNAVAILABLE", MSG_KEY)
    if isinstance(exc, anthropic.RateLimitError):
        return AiError("AI_UNAVAILABLE", MSG_BUSY)
    return AiError("AI_UNAVAILABLE", MSG_DOWN)


class ClaudeClient:
    def __init__(
        self, sdk: Any = None, recorder: RunRecorder | None = None, settings: AiSettings | None = None
    ):
        self._sdk = sdk
        self.recorder = recorder or NullRecorder()
        self.settings = settings or get_ai_settings()

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            if not self.settings.anthropic_api_key:
                raise AiError("AI_UNAVAILABLE", MSG_KEY)
            import anthropic

            self._sdk = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                timeout=self.settings.ai_timeout_seconds,
                max_retries=2,
            )
        return self._sdk

    def _api_and_params(self, params: dict, timeout: float | None = None) -> tuple[Any, dict]:
        """Sonnet, Opus đi đường beta có dự phòng phía máy chủ; lượt có MCP connector cũng đi beta; còn lại
        (Haiku không MCP) đi đường thường."""
        sdk = self.sdk.with_options(timeout=timeout) if timeout else self.sdk
        betas, extra = [], {}
        if params.get("mcp_servers"):
            betas.append(MCP_BETA)
        if supports_fallbacks(params["model"]):
            betas.append(FALLBACK_BETA)
            extra["fallbacks"] = "default"
        if betas:
            return sdk.beta.messages, {**params, "betas": betas, **extra}
        return sdk.messages, params

    def _finish(self, message: Any, meta: dict, started: float, parsed: Any = None) -> ClaudeResult:
        usage = usage_from_response(_get(message, "usage"))
        model = _get(message, "model") or meta["model"]
        cost, card = compute_cost_usd(model, usage)
        content = [block_to_dict(b) for b in (_get(message, "content") or [])]
        iterations = _get(_get(message, "usage"), "iterations") or []
        fallback_used = any(b.get("type") == "fallback" for b in content) or any(
            _get(it, "type") == "fallback_message" for it in iterations
        )
        stop_reason = _get(message, "stop_reason")
        refusal = _get(_get(message, "stop_details"), "category") if stop_reason == "refusal" else None
        run_id = self._record(
            meta,
            model=model,
            usage=usage,
            cost=cost,
            card=card,
            stop_reason=stop_reason,
            refusal=refusal,
            started=started,
            request_id=_get(message, "_request_id"),
            error=None,
            fallback=fallback_used,
        )
        return ClaudeResult(
            message=message,
            content=content,
            model=model,
            stop_reason=stop_reason,
            refusal_category=refusal,
            usage=usage,
            cost_usd=cost,
            run_id=run_id,
            fallback_used=fallback_used,
            parsed=parsed,
        )

    def _record(
        self,
        meta: dict,
        *,
        model,
        usage,
        cost,
        card,
        stop_reason,
        refusal,
        started,
        request_id,
        error,
        fallback,
    ):
        try:
            return self.recorder.record(
                RunRecord(
                    user_id=meta.get("user_id"),
                    purpose=meta["purpose"],
                    model=model,
                    mode=meta.get("mode"),
                    effort=meta.get("effort"),
                    conversation_id=meta.get("conversation_id"),
                    usage=usage,
                    cost_usd=cost,
                    rate_card=card,
                    stop_reason=stop_reason,
                    refusal_category=refusal,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    request_id=request_id,
                    error_code=error,
                    fallback_used=fallback,
                    mcp_servers_used=meta.get("mcp_servers_used"),
                )
            )
        except Exception:  # ghi sổ hỏng không được làm hỏng lượt chat
            log.exception("Không ghi được tab_ai_run")
            return None

    def _fail(self, meta: dict, exc: Exception, started: float) -> AiError:
        err = _map_error(exc)
        log.warning("Gọi Claude lỗi (%s): %s", meta["purpose"], type(exc).__name__)
        self._record(
            meta,
            model=meta["model"],
            usage=UsageCount(),
            cost=Decimal(0),
            card=None,
            stop_reason=None,
            refusal=None,
            started=started,
            request_id=None,
            error=type(exc).__name__,
            fallback=False,
        )
        return err

    @staticmethod
    def _meta(params: dict, purpose: str, **kw) -> dict:
        effort = (params.get("output_config") or {}).get("effort")
        mcp = sorted(s["name"] for s in params.get("mcp_servers") or []) or None
        return {"purpose": purpose, "model": params["model"], "effort": effort, "mcp_servers_used": mcp, **kw}

    def stream_text(self, params: dict, *, purpose: str, **meta_kw) -> Generator[str, None, ClaudeResult]:
        """Sinh từng đoạn chữ; giá trị trả về (qua StopIteration) là ClaudeResult."""
        meta = self._meta(params, purpose, **meta_kw)
        started = time.monotonic()
        try:
            api, full = self._api_and_params(params)
            with api.stream(**full) as stream:
                yield from stream.text_stream
                message = stream.get_final_message()
        except Exception as exc:
            raise self._fail(meta, exc, started) from exc
        return self._finish(message, meta, started)

    def create(self, params: dict, *, purpose: str, **meta_kw) -> ClaudeResult:
        meta = self._meta(params, purpose, **meta_kw)
        started = time.monotonic()
        try:
            api, full = self._api_and_params(params)
            message = api.create(**full)
        except Exception as exc:
            raise self._fail(meta, exc, started) from exc
        return self._finish(message, meta, started)

    def parse(
        self,
        params: dict,
        output_format: type,
        *,
        purpose: str,
        timeout: float | None = None,
        stream: bool = False,
        **meta_kw,
    ) -> ClaudeResult:
        """Đầu ra có cấu trúc bằng `messages.parse`; `result.parsed` là đối tượng Pydantic hoặc None.
        `timeout` (giây) cho việc dài như bóc tách cả tệp lịch trình; mặc định theo AI_TIMEOUT_SECONDS."""
        meta = self._meta(params, purpose, **meta_kw)
        started = time.monotonic()
        try:
            api, full = self._api_and_params(params, timeout)
            if stream:  # SDK đòi stream khi max_tokens lớn (đầu ra dài như bóc tách cả tệp lịch trình)
                with api.stream(**full, output_format=output_format) as s:
                    message = s.get_final_message()
            else:
                message = api.parse(**full, output_format=output_format)
        except Exception as exc:
            raise self._fail(meta, exc, started) from exc
        parsed = _get(message, "parsed_output")
        return self._finish(message, meta, started, parsed=parsed)


_client: ClaudeClient | None = None


def get_client() -> ClaudeClient:
    """Client dùng chung của tiến trình, ghi tab_ai_run bằng phiên DB riêng."""
    global _client
    if _client is None:
        from app.ai.models import DbRunRecorder

        _client = ClaudeClient(recorder=DbRunRecorder())
    return _client
