"""Chạy bộ mẫu thông báo ngân hàng với Claude thật (QĐ-35). Chỉ chạy tay: pytest -m ai_eval.

Không cần DB. Ghi kết quả vào results/<ngày>-bank.json. Mỗi mẫu khoảng 0,0002 USD.
"""

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).parent
POSTED = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)
_RESULTS: list[dict] = []

pytestmark = pytest.mark.ai_eval


def _load() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    return yaml.safe_load((HERE / "bank_cases.yaml").read_text(encoding="utf-8"))


CASES = _load()


@pytest.fixture(scope="module", autouse=True)
def write_results():
    yield
    if not _RESULTS:
        return
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    summary = {
        "passed": sum(r["ok"] for r in _RESULTS),
        "total": len(_RESULTS),
        "cost_usd": float(sum((Decimal(str(r["cost_usd"])) for r in _RESULTS), Decimal(0))),
        "cases": _RESULTS,
    }
    path = out / f"{datetime.now(UTC):%Y-%m-%d}-bank.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_bank_case(case):
    from app.ai.bank_extract import classify, extract_bank_notification
    from app.ai.client import ClaudeClient, NullRecorder

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Chưa có ANTHROPIC_API_KEY")
    client = ClaudeClient(recorder=NullRecorder())
    result = extract_bank_notification(1, case["bank"], case["title"], case["text"], POSTED, client=client)
    exp = case["expect"]
    errors: list[str] = []
    got_class = classify(result)
    if got_class != exp["classify"]:
        errors.append(f"classify {got_class}, cần {exp['classify']}")
    if exp.get("no_claude") and client.recorder.records:
        errors.append("đã gửi Claude dù có OTP")
    if result is not None:
        for field in ("is_transaction", "direction", "amount_vnd", "account_last4"):
            if field in exp and getattr(result, field) != exp[field]:
                errors.append(f"{field} = {getattr(result, field)!r}, cần {exp[field]!r}")
        if exp.get("txn_type_in") and result.txn_type not in exp["txn_type_in"]:
            errors.append(f"txn_type = {result.txn_type}, cần một trong {exp['txn_type_in']}")
    cost = sum((r.cost_usd for r in client.recorder.records), Decimal(0))
    _RESULTS.append(
        {
            "id": case["id"],
            "ok": not errors,
            "errors": errors,
            "result": result.model_dump(mode="json") if result else None,
            "classify": got_class,
            "cost_usd": float(cost),
        }
    )
    assert not errors, "; ".join(errors)
