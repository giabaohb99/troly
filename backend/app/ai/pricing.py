"""Bảng giá Claude và cách tính tiền một lần gọi (20 mục 3.1, 3.12).

Giá lấy từ skill claude-api bản lưu 03/11/2026; đối chiếu trang giá chính thức trước mỗi phase.
"""

from dataclasses import dataclass
from decimal import Decimal

PER_MILLION = Decimal(1_000_000)
WEB_SEARCH_USD = Decimal("0.01")  # 10 USD mỗi 1.000 lần tìm
HAIKU_LONG_PROMPT_TOKENS = 100_000


@dataclass(frozen=True)
class Rate:
    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write_5m: Decimal
    cache_write_1h: Decimal


def _rate(inp: str, out: str, read: str) -> Rate:
    i = Decimal(inp)
    return Rate(i, Decimal(out), Decimal(read), i * Decimal("1.25"), i * 2)


RATES: dict[str, Rate] = {
    "claude-haiku-5-5": _rate("0.10", "0.50", "0.01"),
    "claude-sonnet-5-5": _rate("2", "10", "0.10"),
    "claude-opus-5-5": _rate("4", "20", "0.20"),
}
HAIKU_LONG_RATE = _rate("0.50", "2.50", "0.05")


@dataclass(frozen=True)
class UsageCount:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    web_search_requests: int = 0

    @property
    def prompt_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cache_read_tokens
            + self.cache_write_5m_tokens
            + self.cache_write_1h_tokens
        )


def pick_rate(model: str, prompt_tokens: int) -> tuple[Rate, str]:
    """Trả bảng giá và nhãn rate_card (le_100k, gt_100k)."""
    card = "gt_100k" if prompt_tokens > HAIKU_LONG_PROMPT_TOKENS else "le_100k"
    if model.startswith("claude-haiku-5-5") and card == "gt_100k":
        return HAIKU_LONG_RATE, card
    rate = RATES.get(model) or next((r for name, r in RATES.items() if model.startswith(name)), None)
    if rate is None:
        # Model lạ: tính theo giá cao nhất để không báo thiếu tiền.
        rate = RATES["claude-opus-5-5"]
    return rate, card


def compute_cost_usd(model: str, usage: UsageCount) -> tuple[Decimal, str]:
    rate, card = pick_rate(model, usage.prompt_tokens)
    cost = (
        rate.input * usage.input_tokens
        + rate.output * usage.output_tokens
        + rate.cache_read * usage.cache_read_tokens
        + rate.cache_write_5m * usage.cache_write_5m_tokens
        + rate.cache_write_1h * usage.cache_write_1h_tokens
    ) / PER_MILLION + WEB_SEARCH_USD * usage.web_search_requests
    return cost.quantize(Decimal("0.000001")), card


def usage_from_response(usage) -> UsageCount:
    """Đọc usage của SDK (đối tượng hoặc dict), chịu được trường thiếu."""

    def get(obj, name, default=0):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default) or default
        return getattr(obj, name, default) or default

    creation = get(usage, "cache_creation", None)
    w5 = get(creation, "ephemeral_5m_input_tokens")
    w1 = get(creation, "ephemeral_1h_input_tokens")
    total_write = get(usage, "cache_creation_input_tokens")
    if not (w5 or w1) and total_write:
        w5 = total_write
    server = get(usage, "server_tool_use", None)
    return UsageCount(
        input_tokens=get(usage, "input_tokens"),
        output_tokens=get(usage, "output_tokens"),
        cache_read_tokens=get(usage, "cache_read_input_tokens"),
        cache_write_5m_tokens=w5,
        cache_write_1h_tokens=w1,
        web_search_requests=get(server, "web_search_requests"),
    )
