"""Việc nền của trip trong tab_job_queue (worker/jobs/queue.py HANDLERS):
trip_import -> run_import, trip_evaluate -> run_evaluate."""

from app.modules.trip import service


def run_import(session, job) -> dict:
    return service.run_import(session, job)


def run_evaluate(session, job) -> dict:
    return service.run_evaluate(session, job)
