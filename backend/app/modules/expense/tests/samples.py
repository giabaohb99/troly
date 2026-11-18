"""Đọc bộ mẫu thông báo ở testdata/bank-notifications (70 mục 3.3)."""

import os
from datetime import datetime
from pathlib import Path

import yaml

PARSERS = {"com.VCB": "vcb", "vn.com.techcombank.bb.app": "tcb", "com.mservice.momotransfer": "momo"}


def fixtures_dir() -> Path:
    return Path(os.environ.get("TESTDATA_DIR") or Path(__file__).resolve().parents[5] / "testdata")


def load_samples() -> list[dict]:
    files = sorted((fixtures_dir() / "bank-notifications").glob("*.yaml"))
    assert files, "Thiếu testdata/bank-notifications"
    return [s for f in files for s in yaml.safe_load(f.read_text(encoding="utf-8"))]


def sample(sample_id: str) -> dict:
    s = next(s for s in load_samples() if s["id"] == sample_id)
    return {**s, "parser": PARSERS[s["package"]], "posted_at": datetime.fromisoformat(s["posted_at"])}
