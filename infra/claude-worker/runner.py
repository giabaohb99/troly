#!/usr/bin/env python3
"""Trình chạy Claude Code trên VPS (QĐ-60). Chạy bằng người dùng `claude` (systemd claude-worker).

Vòng lặp: hỏi api troly lấy việc (`/internal/claude/jobs/claim`), chạy `claude -p` toàn quyền trong ~/work, báo kết
quả (`/finish`). Mỗi lần một việc. Chỉ dùng thư viện chuẩn của Python.

Biến môi trường (tệp /etc/claude-worker/env): TROLY_API (mặc định http://127.0.0.1:8200/api/v1),
CLAUDE_WORKER_TOKEN (khóa nội bộ, trùng với .env của troly), CLAUDE_CODE_OAUTH_TOKEN (token gói đăng ký, tạo bằng
`claude setup-token`), CLAUDE_MAX_TURNS (mặc định 150), CLAUDE_TIMEOUT_SECONDS (mặc định 7200).
"""

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

API = os.environ.get("TROLY_API", "http://127.0.0.1:8200/api/v1").rstrip("/")
TOKEN = os.environ.get("CLAUDE_WORKER_TOKEN", "")
MAX_TURNS = os.environ.get("CLAUDE_MAX_TURNS", "150")
TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "7200"))
WORKDIR = os.path.expanduser(os.environ.get("CLAUDE_WORKDIR", "~/work"))
IDLE_SECONDS = 10
OUTBOX_ROOT = os.path.join(WORKDIR, "outbox")
MAX_FILES = 10
MAX_FILE_BYTES = 25 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("claude-worker")


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body or {}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["data"]


def outbox_of(job_id: int) -> str:
    path = os.path.join(OUTBOX_ROOT, str(job_id))
    os.makedirs(path, exist_ok=True)
    return path


def upload_outbox(job_id: int, path: str) -> None:
    """Tải tệp thành phẩm trong hộp ra lên app (thẻ tệp trong tin báo), rồi dọn hộp ra."""
    files = sorted(
        (os.path.join(root, name) for root, _, names in os.walk(path) for name in names),
        key=os.path.getmtime,
    )[:MAX_FILES]
    for f in files:
        size = os.path.getsize(f)
        if not size or size > MAX_FILE_BYTES:
            log.warning("Bỏ tệp %s (%d byte)", os.path.basename(f), size)
            continue
        with open(f, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        mime = mimetypes.guess_type(f)[0] or "application/octet-stream"
        try:
            call(f"/internal/claude/jobs/{job_id}/files", {"name": os.path.basename(f), "mime": mime, "data_b64": data})
        except (urllib.error.URLError, OSError) as exc:
            log.warning("Tải tệp %s lỗi: %s", os.path.basename(f), exc)
    shutil.rmtree(path, ignore_errors=True)


def run_claude(job: dict) -> dict:
    cmd = [
        "claude", "-p", job["prompt"],
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--max-turns", str(MAX_TURNS),
        "--append-system-prompt", job.get("system_append") or "",
    ]  # fmt: skip
    if job.get("resume_session_id"):
        cmd += ["--resume", job["resume_session_id"]]
    env = {**os.environ, "TROLY_OUTBOX": outbox_of(job["id"])}
    try:
        proc = subprocess.run(cmd, cwd=WORKDIR, env=env, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Quá {TIMEOUT // 60} phút chưa xong, đã dừng."}
    except FileNotFoundError:
        return {"ok": False, "error": "Chưa cài Claude Code trên VPS."}
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        out = {}
    base = {
        "session_id": out.get("session_id"),
        "cost_usd": out.get("total_cost_usd"),
        "turns": out.get("num_turns"),
    }
    if out.get("subtype") == "error_max_turns":
        return {**base, "ok": False, "error": f"Hết {MAX_TURNS} bước mà chưa xong; nhắn tiếp để em làm nốt."}
    if proc.returncode != 0 or out.get("is_error") or not out:
        detail = (out.get("result") or proc.stderr or proc.stdout or "").strip()[-800:]
        return {**base, "ok": False, "error": detail or f"Claude thoát mã {proc.returncode}."}
    return {**base, "ok": True, "result": out.get("result") or ""}


def main() -> None:
    os.makedirs(WORKDIR, exist_ok=True)
    if not TOKEN:
        log.error("Thiếu CLAUDE_WORKER_TOKEN")
    while not TOKEN or not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        log.warning("Chưa có CLAUDE_CODE_OAUTH_TOKEN hoặc CLAUDE_WORKER_TOKEN, chờ cấu hình")
        time.sleep(300)
    try:
        log.info("Trả việc chạy dở về hàng chờ: %s", call("/internal/claude/jobs/reset"))
    except (urllib.error.URLError, OSError) as exc:
        log.warning("Không gọi được api lúc khởi động: %s", exc)
    while True:
        try:
            job = call("/internal/claude/jobs/claim").get("job")
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            log.warning("Lấy việc lỗi: %s", exc)
            time.sleep(60)
            continue
        if not job:
            time.sleep(IDLE_SECONDS)
            continue
        log.info("Bắt đầu việc #%s", job["id"])
        started = time.monotonic()
        result = run_claude(job)
        log.info("Xong việc #%s sau %ds, ok=%s", job["id"], time.monotonic() - started, result.get("ok"))
        upload_outbox(job["id"], outbox_of(job["id"]))
        for attempt in range(5):
            try:
                call(f"/internal/claude/jobs/{job['id']}/finish", result)
                break
            except (urllib.error.URLError, OSError) as exc:
                log.warning("Báo kết quả lỗi (lần %d): %s", attempt + 1, exc)
                time.sleep(30)


if __name__ == "__main__":
    main()
