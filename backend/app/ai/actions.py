"""Hành động trả cho app (20 mục 3.11, vỏ phẳng theo QĐ-26).

Mỗi hàm trả dict phẳng `{type, label, ...}`; `id` do vòng chat gắn khi gom hành động của lượt.
"""

from datetime import datetime
from urllib.parse import urlsplit


def _https(url: str) -> str:
    if urlsplit(url).scheme != "https":
        raise ValueError("Chỉ nhận link https")
    return url


def open_screen(label: str, screen: str, params: dict | None = None) -> dict:
    return {"type": "open_screen", "label": label, "screen": screen, "params": params or {}}


def open_link(label: str, url: str, kind: str) -> dict:
    return {"type": "open_link", "label": label, "url": _https(url), "kind": kind}


def open_map_navigation(
    label: str,
    *,
    lat: float | None,
    lng: float | None,
    query: str | None,
    fallback_url: str,
    mode: str = "l",
    avoid: str | None = "h",
) -> dict:
    return {
        "type": "open_map_navigation",
        "label": label,
        "lat": lat,
        "lng": lng,
        "query": query,
        "mode": mode,
        "avoid": avoid,
        "fallback_url": _https(fallback_url),
    }


def open_map_directions(label: str, urls: list[str], segment_labels: list[str]) -> dict:
    if len(urls) != len(segment_labels):
        raise ValueError("urls và segment_labels phải cùng độ dài")
    return {
        "type": "open_map_directions",
        "label": label,
        "urls": [_https(u) for u in urls],
        "segment_labels": segment_labels,
    }


def open_map_place(label: str, query: str, place_id: str | None) -> dict:
    return {"type": "open_map_place", "label": label, "query": query, "place_id": place_id}


def confirm(
    *,
    pending_action_id: int,
    title: str,
    summary: str,
    details: list[dict],
    danger: bool,
    expires_at: datetime,
    confirm_label: str = "Duyệt",
    cancel_label: str = "Bỏ",
) -> dict:
    return {
        "type": "confirm",
        "label": title,
        "pending_action_id": pending_action_id,
        "title": title,
        "summary": summary,
        "details": details,
        "confirm_label": confirm_label,
        "cancel_label": cancel_label,
        "danger": danger,
        "expires_at": expires_at.isoformat(),
    }


def undo(text: str, resource: str, ids: list[int], expires_at: datetime) -> dict:
    return {
        "type": "undo",
        "label": "Hoàn tác",
        "text": text,
        "resource": resource,
        "ids": ids,
        "expires_at": expires_at.isoformat(),
    }


def memory_changed(text: str, version: int, undo_version: int) -> dict:
    return {
        "type": "memory_changed",
        "label": "Hoàn tác",
        "text": text,
        "version": version,
        "undo_version": undo_version,
    }


def choices(label: str, options: list[tuple[str, str]]) -> dict:
    return {
        "type": "choices",
        "label": label,
        "options": [{"label": lbl, "value": val} for lbl, val in options[:5]],
    }


def file_card(file: dict) -> dict:
    """Thẻ tệp trong tin trả lời (QĐ-41). `file`: {file_id, name, mime, size_bytes}; app mở bằng GET /files/{id}."""
    return {
        "type": "file",
        "label": file["name"],
        "file_id": file["file_id"],
        "name": file["name"],
        "mime": file["mime"],
        "size_bytes": file["size_bytes"],
    }


def connect(
    label: str, connector_id: int | None = None, name: str | None = None, url: str | None = None
) -> dict:
    """Nút kết nối hệ thống ngoài (QĐ-56): có connector_id thì app mở luồng đăng nhập của kết nối đó; chỉ có
    name, url thì app mở form thêm kết nối điền sẵn. Mật khẩu chỉ nhập trên trang của hệ thống, không qua chat."""
    action: dict = {"type": "connect", "label": label}
    if connector_id is not None:
        action["connector_id"] = connector_id
    if name:
        action["name"] = name
    if url:
        action["url"] = _https(url)
    return action
