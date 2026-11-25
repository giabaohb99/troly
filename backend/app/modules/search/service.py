"""Tìm chung toàn văn (QĐ-27 mục 11, 12 mục 5.3). Dùng chung cho GET /search và công cụ search_everything.

Nguồn note, chat, file, inbox; trip (Phase 4) thêm khi bảng có, gọi với nguồn chưa có thì trả rỗng.
Cuộc trò chuyện riêng tư (luật private_conversation) chỉ ra khi `include_private` (API của app),
không bao giờ ra cho công cụ AI (60 mục 3.6).
"""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ValidationError

SOURCES = ("note", "chat", "inbox", "trip", "file")
HEADLINE = "StartSel=<b>, StopSel=</b>, MaxWords=25, MinWords=8, MaxFragments=2, FragmentDelimiter=' ... '"

_QUERIES = {
    "note": """
        SELECT 'note' AS source, n.id, n.title AS title, n.updated_at AS date,
               ts_rank(n.search_vector, q) AS rank,
               ts_headline('troly_vn', n.title || ' ' || n.body, q, :hl) AS snippet,
               NULL::bigint AS conversation_id
        FROM tab_note n, websearch_to_tsquery('troly_vn', :q) q
        WHERE n.user_id = :uid AND n.deleted_at IS NULL AND n.search_vector @@ q
          AND (CAST(:from_ AS timestamptz) IS NULL OR n.updated_at >= :from_)
          AND (CAST(:to_ AS timestamptz) IS NULL OR n.updated_at < :to_)
        ORDER BY rank DESC, n.updated_at DESC LIMIT :limit
    """,
    "chat": """
        SELECT 'chat' AS source, m.id, coalesce(c.title, 'Trò chuyện ' || to_char(c.local_date, 'DD/MM/YYYY')) AS title,
               m.created_at AS date, ts_rank(m.search_vector, q) AS rank,
               ts_headline('troly_vn', m.text, q, :hl) AS snippet, m.conversation_id
        FROM tab_message m JOIN tab_conversation c ON c.id = m.conversation_id,
             websearch_to_tsquery('troly_vn', :q) q
        WHERE m.user_id = :uid AND m.hidden = false AND m.search_vector @@ q
          AND (CAST(:from_ AS timestamptz) IS NULL OR m.created_at >= :from_)
          AND (CAST(:to_ AS timestamptz) IS NULL OR m.created_at < :to_)
        ORDER BY rank DESC, m.created_at DESC LIMIT :limit
    """,
    "file": """
        SELECT 'file' AS source, f.id, coalesce(f.original_name, 'Tệp') AS title, f.created_at AS date,
               ts_rank(t.search_vector, q) AS rank,
               ts_headline('troly_vn', left(t.content, 100000), q, :hl) AS snippet,
               NULL::bigint AS conversation_id
        FROM tab_file_text t JOIN tab_file f ON f.id = t.file_id, websearch_to_tsquery('troly_vn', :q) q
        WHERE t.user_id = :uid AND f.deleted_at IS NULL AND f.status = 'ready' AND t.search_vector @@ q
          AND (CAST(:from_ AS timestamptz) IS NULL OR f.created_at >= :from_)
          AND (CAST(:to_ AS timestamptz) IS NULL OR f.created_at < :to_)
        ORDER BY rank DESC, f.created_at DESC LIMIT :limit
    """,
    "inbox": """
        SELECT 'inbox' AS source, i.id, coalesce(i.conversation_title, i.sender, 'Tin nhắn') AS title,
               i.posted_at AS date, ts_rank(i.search_vector, q) AS rank,
               ts_headline('troly_vn', i.text, q, :hl) AS snippet, NULL::bigint AS conversation_id,
               i.conversation_key
        FROM tab_inbox_message i, websearch_to_tsquery('troly_vn', :q) q
        WHERE i.user_id = :uid AND i.search_vector @@ q
          AND NOT EXISTS (
              SELECT 1 FROM tab_listened_app a WHERE a.user_id = i.user_id AND a.purpose = 'inbox'
                AND a.enabled = false AND a.parser = i.app)
          AND (:include_private OR NOT EXISTS (
              SELECT 1 FROM tab_inbox_rule r WHERE r.user_id = i.user_id
                AND r.kind = 'private_conversation' AND r.value = i.conversation_key))
          AND (CAST(:from_ AS timestamptz) IS NULL OR i.posted_at >= :from_)
          AND (CAST(:to_ AS timestamptz) IS NULL OR i.posted_at < :to_)
        ORDER BY rank DESC, i.posted_at DESC LIMIT :limit
    """,
}

# Không ra kết quả toàn văn thì thử gần đúng (pg_trgm) trên tiêu đề.
_FUZZY = {
    "note": """
        SELECT 'note' AS source, n.id, n.title AS title, n.updated_at AS date,
               similarity(unaccent(n.title), unaccent(:q)) AS rank, left(n.body, 160) AS snippet,
               NULL::bigint AS conversation_id
        FROM tab_note n
        WHERE n.user_id = :uid AND n.deleted_at IS NULL AND unaccent(n.title) % unaccent(:q)
        ORDER BY rank DESC LIMIT :limit
    """,
    "file": """
        SELECT 'file' AS source, f.id, coalesce(f.original_name, 'Tệp') AS title, f.created_at AS date,
               similarity(unaccent(coalesce(f.original_name, '')), unaccent(:q)) AS rank, '' AS snippet,
               NULL::bigint AS conversation_id
        FROM tab_file f
        WHERE f.user_id = :uid AND f.deleted_at IS NULL AND f.status = 'ready'
          AND unaccent(coalesce(f.original_name, '')) % unaccent(:q)
        ORDER BY rank DESC LIMIT :limit
    """,
}


def _open_action(hit: dict) -> dict:
    source = hit["source"]
    if source == "chat":
        screen, params = "chat", {"conversation_id": hit["conversation_id"], "message_id": hit["id"]}
    elif source == "note":
        screen, params = "note_detail", {"note_id": hit["id"]}
    elif source == "file":
        screen, params = "file_detail", {"file_id": hit["id"]}
    elif source == "trip":
        screen, params = "trip_detail", {"trip_id": hit["id"]}
    else:
        screen, params = "inbox_conversation", {"conversation_key": hit.get("conversation_key")}
    return {"id": f"s{hit['id']}", "type": "open_screen", "label": "Mở", "screen": screen, "params": params}


def search(
    session: Session,
    user_id: int,
    q: str,
    types: list[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 20,
    include_private: bool = False,
) -> list[dict]:
    q = (q or "").strip()
    if not q:
        raise ValidationError(fields={"q": "Nhập chữ cần tìm."})
    wanted = types or list(SOURCES)
    unknown = [t for t in wanted if t not in SOURCES]
    if unknown:
        raise ValidationError(fields={"types": f"Không có loại: {', '.join(unknown)}."})
    params = {
        "q": q,
        "uid": user_id,
        "from_": start,
        "to_": end,
        "limit": limit,
        "hl": HEADLINE,
        "include_private": include_private,
    }
    hits: list[dict] = []
    for source in wanted:
        sql = _QUERIES.get(source)
        if sql is None:
            continue
        hits.extend(dict(r._mapping) for r in session.execute(text(sql), params))
    if not hits:
        for source in wanted:
            sql = _FUZZY.get(source)
            if sql is not None:
                hits.extend(dict(r._mapping) for r in session.execute(text(sql), params))
    hits.sort(key=lambda h: (-(h["rank"] or 0), -(h["date"].timestamp() if h["date"] else 0)))
    out = []
    for h in hits[:limit]:
        out.append(
            {
                "source": h["source"],
                "id": h["id"],
                "title": h["title"],
                "snippet": h["snippet"] or "",
                "rank": round(float(h["rank"] or 0), 4),
                "date": h["date"],
                "open": _open_action(h),
            }
        )
    return out
