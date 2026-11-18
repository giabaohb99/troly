"""Khung tối thiểu do agent hạ tầng dựng (việc 0-06): vòng chạy nền chưa có job nào.

Agent kiến trúc thay bằng vòng worker thật (docs/10-backend/10-kien-truc-backend.md mục 3.9).
"""

import logging
import os
import signal
import threading

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

stop_event = threading.Event()


def handle_stop(signum, frame) -> None:
    log.info("Nhận tín hiệu dừng, worker thoát.")
    stop_event.set()


def run() -> None:
    poll_seconds = int(os.environ.get("WORKER_POLL_SECONDS", "30"))
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    log.info("Worker khung đã chạy, chu kỳ %s giây.", poll_seconds)
    while not stop_event.wait(poll_seconds):
        log.debug("Vòng worker: chưa có job.")


if __name__ == "__main__":
    run()
