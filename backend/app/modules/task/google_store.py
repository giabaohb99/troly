"""Cài TaskStore của integrations/google/stores.py trên tab_task (registry.register_integrations)."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.integrations.google.stores import LocalRef, LocalTask
from app.modules.task.models import Task


def _row(session: Session, user_id: int, local_id: int) -> Task | None:
    return session.scalar(select(Task).where(Task.id == local_id, Task.user_id == user_id))


class TaskStore:
    def get_for_push(self, session, user_id, local_id):
        t = _row(session, user_id, local_id)
        if t is None:
            return None
        return LocalTask(
            id=t.id,
            title=t.title,
            note=t.note,
            status=t.status,
            priority=t.priority,
            due_date=t.due_date,
            due_at=t.due_at,
            google_task_id=t.google_task_id,
            google_tasklist_id=t.google_tasklist_id,
            google_etag=t.google_etag,
            deleted=t.deleted_at is not None,
        )

    def save_push_result(self, session, user_id, local_id, google_task_id, tasklist_id, etag, updated):
        """`google_task_id = None`: việc đã có giờ, gỡ khỏi Google Tasks, đi Calendar qua sự kiện."""
        session.execute(
            update(Task)
            .where(Task.id == local_id, Task.user_id == user_id)
            .values(
                google_task_id=google_task_id,
                google_tasklist_id=tasklist_id,
                google_etag=etag,
                google_updated_at=updated,
                sync_status="synced" if google_task_id else "local_only",
                sync_error=None,
            )
        )

    def find_by_google_id(self, session, user_id, google_task_id):
        t = session.scalar(select(Task).where(Task.user_id == user_id, Task.google_task_id == google_task_id))
        return LocalRef(t.id, t.google_etag, t.google_updated_at) if t else None

    def apply_remote_status(self, session, user_id, local_id, completed, completed_at, etag, updated):
        t = _row(session, user_id, local_id)
        if t is None:
            return
        if completed and t.status != "done":
            t.status, t.completed_at, t.completed_source = "done", completed_at, "google"
        elif not completed and t.status == "done":
            t.status, t.completed_at, t.completed_source = "todo", None, None
        t.google_etag, t.google_updated_at = etag, updated
        if t.sync_status != "remote_deleted":
            t.sync_status = "synced"
        session.flush()

    def mark_remote_deleted(self, session, user_id, local_id):
        t = _row(session, user_id, local_id)
        if t is not None and t.deleted_at is None:
            t.sync_status = "remote_deleted"
            session.flush()

    def set_sync_status(self, session, user_id, local_id, status, error=None):
        session.execute(
            update(Task)
            .where(Task.id == local_id, Task.user_id == user_id)
            .values(sync_status=status, sync_error=error)
        )

    def list_unlinked(self, session, user_id):
        return list(
            session.scalars(
                select(Task.id).where(
                    Task.user_id == user_id,
                    Task.google_task_id.is_(None),
                    Task.due_at.is_(None),
                    Task.deleted_at.is_(None),
                    Task.status != "cancelled",
                )
            )
        )

    def on_disconnect(self, session, user_id, keep_data):
        """Việc luôn là của app (nguồn app, chat): ngắt Google chỉ gỡ liên kết, không xóa."""
        session.execute(
            update(Task)
            .where(Task.user_id == user_id, Task.google_task_id.is_not(None))
            .values(
                google_task_id=None,
                google_tasklist_id=None,
                google_etag=None,
                google_updated_at=None,
                sync_status="local_only",
                sync_error=None,
            )
        )


STORE = TaskStore()
