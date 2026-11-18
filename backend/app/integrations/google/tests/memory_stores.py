"""Store trong bộ nhớ thay module calendar, task khi kiểm phần đồng bộ (module thật cài cùng giao diện)."""

from dataclasses import asdict
from datetime import datetime

from app.integrations.google.stores import LocalEvent, LocalRef, LocalTask, RemoteEvent


class MemoryCalendarStore:
    def __init__(self):
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.disconnected: list[bool] = []

    # tiện ích bài kiểm
    def add_local(self, **fields) -> int:
        local_id = self.next_id
        self.next_id += 1
        row = {
            "id": local_id,
            "title": "Sự kiện",
            "google_event_id": None,
            "google_etag": None,
            "google_calendar_id": "primary",
            "all_day": False,
            "start_at": None,
            "end_at": None,
            "status": "confirmed",
            "attendees": [],
            "remind_minutes": [15],
            "remind_source": "app",
            "source": "app",
            "deleted": False,
            "sync_status": "pending",
        }
        row.update(fields)
        self.rows[local_id] = row
        return local_id

    def by_google(self, google_event_id: str) -> dict | None:
        return next((r for r in self.rows.values() if r.get("google_event_id") == google_event_id), None)

    # giao diện CalendarStore
    def find_by_google_id(self, session, user_id, calendar_id, google_event_id):
        row = self.by_google(google_event_id)
        return LocalRef(row["id"], row.get("google_etag")) if row else None

    def write_remote(self, session, user_id, account_id, calendar_id, event: RemoteEvent, local_id):
        data = asdict(event)
        data["google_etag"] = data.pop("etag")
        data["google_updated_at"] = data.pop("updated")
        data["deleted"] = event.status == "cancelled"
        if local_id is None:
            local_id = self.add_local(source="google", remind_source="google", google_calendar_id=calendar_id)
        self.rows[local_id].update(data)
        self.rows[local_id]["sync_status"] = "synced"
        return local_id

    def mark_remote_cancelled(self, session, user_id, local_id):
        self.rows[local_id]["deleted"] = True
        self.rows[local_id]["sync_status"] = "synced"

    def snapshot(self, session, user_id, local_id):
        row = self.rows[local_id]
        return {k: row.get(k) for k in ("title", "description", "location", "start_at", "end_at")}

    def restore_snapshot(self, session, user_id, local_id, data):
        self.rows[local_id].update(data)

    def delete_remote_rows(self, session, user_id, account_id, keep_ids):
        doomed = [i for i, r in self.rows.items() if r["source"] == "google" and i not in keep_ids]
        for i in doomed:
            del self.rows[i]
        return len(doomed)

    def get_for_push(self, session, user_id, local_id):
        row = self.rows.get(local_id)
        if row is None:
            return None
        fields = {k: row.get(k) for k in LocalEvent.__dataclass_fields__ if k in row}
        return LocalEvent(**fields)

    def save_push_result(self, session, user_id, local_id, google_event_id, etag, updated: datetime | None):
        self.rows[local_id].update(
            google_event_id=google_event_id, google_etag=etag, google_updated_at=updated, sync_status="synced"
        )

    def set_sync_status(self, session, user_id, local_id, status, error=None):
        self.rows[local_id]["sync_status"] = status
        self.rows[local_id]["sync_error"] = error

    def on_disconnect(self, session, user_id, keep_data):
        self.disconnected.append(keep_data)


class MemoryTaskStore:
    def __init__(self):
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.disconnected: list[bool] = []

    def add_local(self, **fields) -> int:
        local_id = self.next_id
        self.next_id += 1
        row = {
            "id": local_id,
            "title": "Việc",
            "note": None,
            "status": "todo",
            "priority": "normal",
            "due_date": None,
            "due_at": None,
            "google_task_id": None,
            "google_tasklist_id": None,
            "google_etag": None,
            "google_updated_at": None,
            "deleted": False,
            "sync_status": "pending",
            "completed_source": None,
        }
        row.update(fields)
        self.rows[local_id] = row
        return local_id

    def get_for_push(self, session, user_id, local_id):
        row = self.rows.get(local_id)
        if row is None:
            return None
        return LocalTask(**{k: row[k] for k in LocalTask.__dataclass_fields__})

    def save_push_result(self, session, user_id, local_id, google_task_id, tasklist_id, etag, updated):
        self.rows[local_id].update(
            google_task_id=google_task_id,
            google_tasklist_id=tasklist_id,
            google_etag=etag,
            google_updated_at=updated,
            sync_status="synced" if google_task_id else "local_only",
        )

    def find_by_google_id(self, session, user_id, google_task_id):
        row = next((r for r in self.rows.values() if r["google_task_id"] == google_task_id), None)
        return LocalRef(row["id"], row["google_etag"], row["google_updated_at"]) if row else None

    def apply_remote_status(self, session, user_id, local_id, completed, completed_at, etag, updated):
        row = self.rows[local_id]
        if completed and row["status"] != "done":
            row.update(status="done", completed_at=completed_at, completed_source="google")
        elif not completed and row["status"] == "done":
            row.update(status="todo", completed_at=None, completed_source=None)
        row.update(google_etag=etag, google_updated_at=updated)

    def mark_remote_deleted(self, session, user_id, local_id):
        self.rows[local_id]["sync_status"] = "remote_deleted"

    def set_sync_status(self, session, user_id, local_id, status, error=None):
        self.rows[local_id]["sync_status"] = status

    def list_unlinked(self, session, user_id):
        return [
            i
            for i, r in self.rows.items()
            if not r["google_task_id"] and not r["due_at"] and not r["deleted"]
        ]

    def on_disconnect(self, session, user_id, keep_data):
        self.disconnected.append(keep_data)
