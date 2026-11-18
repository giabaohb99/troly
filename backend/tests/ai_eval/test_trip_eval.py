"""Bóc tách thật tệp mẫu Phước Hải – Trà Vinh (41 mục 9). Chỉ chạy tay: pytest -m ai_eval.

Đặt TRIP_SAMPLE_DOCX trỏ tới tệp mẫu (gắn vào container). Trình đọc Word ở đây chỉ để thử phần AI;
module trip có trình đọc riêng (41 mục 3.1).
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.ai_eval
HERE = Path(__file__).parent


def docx_to_text(path: str) -> str:
    """Đoạn văn và bảng theo thứ tự; link thành [chữ](url)."""
    import docx
    from docx.table import Table
    from docx.text.hyperlink import Hyperlink

    def para_text(p) -> str:
        parts = []
        for item in p.iter_inner_content():
            if isinstance(item, Hyperlink):
                url = item.url
                parts.append(f"[{item.text}]({url})" if url else item.text)
            else:
                parts.append(item.text)
        text = "".join(parts).strip()
        style = (p.style.name or "") if p.style is not None else ""
        if text and style.startswith("Heading"):
            return "#" * (int(style[-1]) if style[-1].isdigit() else 1) + " " + text
        if text and style == "Title":
            return "# " + text
        return text

    lines = []
    for block in docx.Document(path).iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = [" ".join(filter(None, (para_text(p) for p in c.paragraphs))) for c in row.cells]
                lines.append(" | ".join(cells))
        else:
            text = para_text(block)
            if text:
                lines.append(text)
    return "\n".join(lines)


def test_phuoc_hai_tra_vinh():
    from app.ai.client import ClaudeClient, NullRecorder
    from app.ai.trip_ai import extract_trip

    path = os.environ.get("TRIP_SAMPLE_DOCX", "")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Chưa có ANTHROPIC_API_KEY")
    if not Path(path).exists():
        pytest.skip("Chưa có TRIP_SAMPLE_DOCX")
    text = docx_to_text(path)
    client = ClaudeClient(recorder=NullRecorder())
    result = extract_trip(1, text=text, client=client)
    assert result is not None
    stops = [s for d in result.days for s in d.stops]
    places = [p for s in stops for p in s.places]
    facts = {(f.kind, f.value_time or f.value_text) for f in result.facts}
    rec = client.recorder.records[-1]
    summary = {
        "days": len(result.days),
        "stops": len(stops),
        "places_with_url": sum(1 for p in places if p.url),
        "roles": sorted({p.role for p in places}),
        "optional": sum(1 for s in stops if s.optional),
        "facts": sorted(facts),
        "map_links": len(result.map_links),
        "hotels": [h.label for h in result.hotels],
        "cost_usd": float(rec.cost_usd),
        "latency_ms": rec.latency_ms,
        "tokens": [rec.usage.prompt_tokens, rec.usage.output_tokens],
    }
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / f"{datetime.now(UTC):%Y-%m-%d}-trip.json").write_text(
        json.dumps({"summary": summary, "extract": result.model_dump()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert len(result.days) == 3
    assert 25 <= len(stops) <= 40
    assert summary["places_with_url"] >= 30
    assert {"generic", "main"} <= set(summary["roles"]) and summary["optional"] >= 1
    kinds = {k for k, _ in facts}
    assert {"checkin", "checkout", "ferry_last"} <= kinds
    assert any("17:00" in v for k, v in facts if k == "ferry_last")
    assert any(
        "bảo tàng" in s.title.lower() or any("bảo tàng" in p.label.lower() for p in s.places)
        for s in result.days[2].stops
    )
