"""Hồ sơ lõi và ghi chú (11 mục 3.6). Hàm công khai cũng dùng cho công cụ AI."""

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.memory.models import PROFILE_MAX_CHARS, Note, ProfileMemory, ProfileMemoryRevision

KEEP_REVISIONS = 50
UNDO_DAYS = 30

# ---------- Hồ sơ lõi ----------


def _get_or_create_profile(session: Session, user_id: int, lock: bool = False) -> ProfileMemory:
    stmt = select(ProfileMemory).where(ProfileMemory.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    profile = session.scalar(stmt)
    if profile is None:
        profile = ProfileMemory(user_id=user_id, content="", version=1, updated_by="user")
        session.add(profile)
        session.flush()
    return profile


def serialize_profile(p: ProfileMemory) -> dict:
    return {
        "content": p.content,
        "version": p.version,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at,
    }


def get_profile(session: Session, user_id: int) -> dict:
    return serialize_profile(_get_or_create_profile(session, user_id))


def get_profile_markdown(session: Session, user_id: int) -> str:
    content = session.scalar(select(ProfileMemory.content).where(ProfileMemory.user_id == user_id))
    return content or ""


def update_profile(
    session: Session,
    user_id: int,
    content: str,
    expected_version: int | None,
    changed_by: str = "user",
    reason: str | None = "manual_edit",
) -> dict:
    """Ghi hồ sơ mới, lưu bản cũ vào lịch sử. `expected_version` lệch thì CONFLICT."""
    if len(content) > PROFILE_MAX_CHARS:
        raise ValidationError(
            f"Hồ sơ lõi tối đa {PROFILE_MAX_CHARS} ký tự.", fields={"content": "Quá 8.000 ký tự."}
        )
    profile = _get_or_create_profile(session, user_id, lock=True)
    if expected_version is not None and expected_version != profile.version:
        raise ConflictError()
    session.add(
        ProfileMemoryRevision(
            user_id=user_id,
            version=profile.version,
            content=profile.content,
            changed_by=changed_by,
            reason=reason,
        )
    )
    profile.content = content
    profile.version += 1
    profile.updated_by = changed_by
    session.flush()
    _trim_revisions(session, user_id)
    return serialize_profile(profile)


def apply_ai_changes(session: Session, user_id: int, changes: list[dict], reason: str) -> dict | None:
    """Ghi các thay đổi do lượt rút trí nhớ đề xuất (QĐ-59), lưu bản cũ để người dùng quay lại; không đổi thì None."""
    from app.modules.memory.tools import apply_changes

    if not changes:
        return None
    profile = _get_or_create_profile(session, user_id, lock=True)
    content = apply_changes(profile.content or "", changes)
    if content is None or len(content) > PROFILE_MAX_CHARS:
        return None
    return update_profile(session, user_id, content, profile.version, changed_by="ai", reason=reason[:200])


def _trim_revisions(session: Session, user_id: int) -> None:
    keep_from = session.scalar(
        select(ProfileMemoryRevision.version)
        .where(ProfileMemoryRevision.user_id == user_id)
        .order_by(ProfileMemoryRevision.version.desc())
        .offset(KEEP_REVISIONS - 1)
        .limit(1)
    )
    if keep_from is not None:
        session.execute(
            delete(ProfileMemoryRevision).where(
                ProfileMemoryRevision.user_id == user_id, ProfileMemoryRevision.version < keep_from
            )
        )


def list_revisions(session: Session, user_id: int, before_version: int | None, limit: int) -> dict:
    stmt = select(ProfileMemoryRevision).where(ProfileMemoryRevision.user_id == user_id)
    if before_version is not None:
        stmt = stmt.where(ProfileMemoryRevision.version < before_version)
    rows = list(session.scalars(stmt.order_by(ProfileMemoryRevision.version.desc()).limit(limit + 1)))
    items = rows[:limit]
    return {
        "items": [
            {
                "version": r.version,
                "changed_by": r.changed_by,
                "reason": r.reason,
                "created_at": r.created_at,
                "preview": r.content[:200],
            }
            for r in items
        ],
        "next_cursor": str(items[-1].version) if len(rows) > limit else None,
    }


def get_revision(session: Session, user_id: int, version: int) -> dict:
    r = session.scalar(
        select(ProfileMemoryRevision).where(
            ProfileMemoryRevision.user_id == user_id, ProfileMemoryRevision.version == version
        )
    )
    if r is None:
        raise NotFoundError()
    return {
        "version": r.version,
        "content": r.content,
        "changed_by": r.changed_by,
        "reason": r.reason,
        "created_at": r.created_at,
    }


def restore_revision(session: Session, user_id: int, version: int, current_version: int | None) -> dict:
    revision = get_revision(session, user_id, version)
    return update_profile(session, user_id, revision["content"], current_version, "user", "restore")


# ---------- Ghi chú ----------


def serialize_note(n: Note, full: bool = True) -> dict:
    body = n.body if full or len(n.body) <= 300 else n.body[:300]
    return {
        "id": n.id,
        "title": n.title,
        "body": body,
        "body_truncated": not full and len(n.body) > 300,
        "tags": n.tags,
        "source": n.source,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
    }


def _get_note(session: Session, user_id: int, note_id: int, include_deleted: bool = False) -> Note:
    stmt = select(Note).where(Note.id == note_id, Note.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Note.deleted_at.is_(None))
    note = session.scalar(stmt)
    if note is None:
        raise NotFoundError()
    return note


def _clean_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in tags:
        tag = tag.strip().lower()[:40]
        if tag and tag not in seen:
            seen.append(tag)
    return seen[:20]


def create_note(
    session: Session, user_id: int, title: str, body: str, tags: list[str], source: str = "user"
) -> dict:
    note = Note(user_id=user_id, title=title.strip()[:200], body=body, tags=_clean_tags(tags), source=source)
    session.add(note)
    session.flush()
    return serialize_note(note)


def update_note(session: Session, user_id: int, note_id: int, changes: dict) -> dict:
    note = _get_note(session, user_id, note_id)
    if "title" in changes and changes["title"] is not None:
        note.title = changes["title"].strip()[:200]
    if "body" in changes and changes["body"] is not None:
        note.body = changes["body"]
    if "tags" in changes and changes["tags"] is not None:
        note.tags = _clean_tags(changes["tags"])
    session.flush()
    return serialize_note(note)


def get_note(session: Session, user_id: int, note_id: int) -> dict:
    return serialize_note(_get_note(session, user_id, note_id))


def delete_note(session: Session, user_id: int, note_id: int) -> None:
    _get_note(session, user_id, note_id).deleted_at = clock.now()


def restore_note(session: Session, user_id: int, note_id: int) -> dict:
    note = _get_note(session, user_id, note_id, include_deleted=True)
    if note.deleted_at is None or note.deleted_at < clock.now() - timedelta(days=UNDO_DAYS):
        raise NotFoundError()
    note.deleted_at = None
    return serialize_note(note)


def list_notes(
    session: Session, user_id: int, q: str | None, tag: str | None, cursor: str | None, limit: int
) -> dict:
    stmt = select(Note).where(Note.user_id == user_id, Note.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Note.search_vector.op("@@")(func.websearch_to_tsquery("troly_vn", q)))
    if tag:
        stmt = stmt.where(Note.tags.any(tag.strip().lower()))
    if cursor:
        stmt = stmt.where(Note.id < int(cursor))
    rows = list(session.scalars(stmt.order_by(Note.id.desc()).limit(limit + 1)))
    items = rows[:limit]
    return {
        "items": [serialize_note(n, full=False) for n in items],
        "next_cursor": str(items[-1].id) if len(rows) > limit else None,
    }
