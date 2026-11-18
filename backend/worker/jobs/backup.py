"""Sao lưu DB lên R2 (QĐ-16, QĐ-27, QĐ-31): pg_dump định dạng custom, không mã hóa.

Khóa: backups/weekly/<thời điểm>.dump (job chủ nhật 02:00), backups/premigrate/<thời điểm>[-nhãn].dump
(trước migration), backups/manual/<thời điểm>.dump (nút Sao lưu ngay hoặc chạy tay).
Giữ BACKUP_KEEP bản cả ba loại; xóa bản không phải weekly cũ trước, luôn còn ít nhất 1 bản weekly.

Chạy tay trước migration: python -m worker.jobs.backup --reason predeploy [--label <sha>]
"""

import argparse
import hashlib
import re
import subprocess
import sys

from sqlalchemy import text

from app.core import clock, storage
from app.core.config import get_settings
from app.core.db import SessionLocal

PREFIX = "backups/"
FOLDERS = {"weekly": "weekly", "predeploy": "premigrate", "premigrate": "premigrate", "manual": "manual"}
MAIN_TABLES = ("tab_user", "tab_message", "tab_note", "tab_expense", "tab_file")


class _HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.sha = hashlib.sha256()
        self.size = 0

    def read(self, n: int = -1) -> bytes:
        chunk = self.stream.read(n)
        self.sha.update(chunk)
        self.size += len(chunk)
        return chunk


def _libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _row_counts() -> dict:
    """Số dòng bảng chính để đối chiếu khi khôi phục; bảng chưa có (DB trống) thì bỏ qua."""
    counts = {}
    with SessionLocal() as s:
        for table in MAIN_TABLES:
            if s.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is not None:
                counts[table] = s.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    return counts


def backup_key(reason: str, label: str | None = None) -> str:
    folder = FOLDERS.get(reason, "manual")
    suffix = f"-{re.sub(r'[^A-Za-z0-9._-]', '', label)[:40]}" if label else ""
    return f"{PREFIX}{folder}/{clock.now():%Y%m%d-%H%M%S}{suffix}.dump"


def backup_database(reason: str = "weekly", label: str | None = None) -> tuple[int, dict]:
    settings = get_settings()
    key = backup_key(reason, label)
    proc = subprocess.Popen(
        [
            "nice",
            "-n",
            "10",
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--dbname",
            _libpq_url(settings.database_url),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    reader = _HashingReader(proc.stdout)
    storage.upload_fileobj(settings.r2_bucket, key, reader)
    stderr = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        storage.delete(settings.r2_bucket, key)
        raise RuntimeError(f"pg_dump lỗi: {stderr[:300]}")
    removed = prune(settings.r2_bucket, settings.backup_keep)
    detail = {
        "key": key,
        "size_bytes": reader.size,
        "sha256": reader.sha.hexdigest(),
        "reason": reason,
        "row_counts": _row_counts(),
        "removed": removed,
    }
    return 1, detail


def choose_to_delete(keys: list[str], keep: int) -> list[str]:
    """Hàm thuần: chọn bản cần xóa để còn `keep` bản; bản không phải weekly cũ bị xóa trước,
    bản weekly mới nhất không bao giờ bị xóa."""

    def stamp(key: str) -> str:
        return key.rsplit("/", 1)[-1]

    if len(keys) <= keep:
        return []
    weekly = sorted((k for k in keys if k.startswith(f"{PREFIX}weekly/")), key=stamp)
    others = sorted((k for k in keys if not k.startswith(f"{PREFIX}weekly/")), key=stamp)
    protected = {weekly[-1]} if weekly else set()
    excess = len(keys) - keep
    candidates = others + [k for k in weekly if k not in protected]
    return candidates[:excess]


def prune(bucket: str, keep: int) -> list[str]:
    keys = [o["key"] for o in storage.list_keys(bucket, PREFIX) if o["key"].endswith(".dump")]
    old = choose_to_delete(keys, keep)
    for key in old:
        storage.delete(bucket, key)
    return old


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m worker.jobs.backup")
    parser.add_argument("--reason", default="manual", choices=["weekly", "predeploy", "premigrate", "manual"])
    parser.add_argument("--label", help="Nhãn thêm vào tên tệp, ví dụ mã commit")
    args = parser.parse_args()
    _, detail = backup_database(args.reason, args.label)
    print(f"Đã sao lưu {detail['key']} ({detail['size_bytes']} byte).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
