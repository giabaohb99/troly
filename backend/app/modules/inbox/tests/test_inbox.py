"""Hộp tin: chống trùng lịch sử MessagingStyle, conversation_key, luật, riêng tư (11 mục 3.10)."""

from datetime import datetime, timedelta

from app.modules.inbox import service

AT = datetime.fromisoformat("2026-11-18T10:00:00+07:00")


def zalo(user, db, messages, **payload):
    return service.ingest_notification(
        db,
        user,
        parser="zalo",
        app_package="com.zing.zalo",
        payload={
            "title": payload.pop("title", "Lan"),
            "text": payload.pop("text", None),
            "messages": messages,
            **payload,
        },
        posted_at=payload.pop("posted_at", AT),
    )


def msg(sender, text, minutes):
    return {"sender": sender, "text": text, "at": (AT + timedelta(minutes=minutes)).isoformat()}


def test_messaging_style_history_is_deduped(db, user):
    first = zalo(user, db, [msg("Lan", "Chào anh", 0), msg("Lan", "Chiều rảnh không", 1)])
    again = zalo(
        user, db, [msg("Lan", "Chào anh", 0), msg("Lan", "Chiều rảnh không", 1), msg("Lan", "3h nhé", 2)]
    )
    assert first["created"] == 2 and again["created"] == 1
    page = service.list_conversations(db, user.user_id, {}, None)
    [conv] = page["items"]
    assert conv["unread_count"] == 3 and conv["last_text"] == "3h nhé" and conv["title"] == "Lan"


def test_conversation_key_one_to_one_vs_group(db, user):
    zalo(user, db, [msg("Lan", "a", 0)])
    zalo(user, db, [msg("Lan", "b", 1)], conversation_title="Lan")
    zalo(
        user,
        db,
        [msg("Lan", "c", 2), msg("Minh", "d", 3)],
        conversation_title="Nhóm Gia Đình",
        is_group_conversation=True,
    )
    items = service.list_conversations(db, user.user_id, {}, None)["items"]
    assert sorted((c["title"], c["is_group"]) for c in items) == [("Lan", False), ("Nhóm Gia Đình", True)]


def test_rules_vip_urgent_and_muted(db, user):
    service.create_rule(db, user.user_id, "vip_sender", "Mẹ", None)
    service.create_rule(db, user.user_id, "urgent_keyword", "gấp", "zalo")
    service.create_rule(db, user.user_id, "muted_sender", "Quảng cáo", None)
    service.create_rule(db, user.user_id, "muted_keyword", "khuyến mãi", None)

    zalo(user, db, [msg("Me", "Con ăn cơm chưa", 0)])
    zalo(user, db, [msg("Sếp", "Gửi báo cáo GAP nhé", 1)])
    zalo(user, db, [msg("Quang cao", "Giảm giá", 2)])
    zalo(user, db, [msg("Shop", "Khuyen mai 50%", 3)])
    out = zalo(user, db, [msg("Bạn", "đi cafe", 4)])

    assert out["status"] == "done"
    items = service.list_conversations(db, user.user_id, {}, None)["items"]
    assert [c["title"] for c in items] == ["Sếp", "Me", "Bạn"]  # tin quan trọng chưa xong đứng đầu
    assert [c["importance"] for c in items] == ["important", "important", "normal"]
    service.mark_conversation(db, user.user_id, items[0]["conversation_key"], "done")
    items = service.list_conversations(db, user.user_id, {}, None)["items"]
    assert [c["title"] for c in items] == ["Me", "Bạn", "Sếp"]


def test_muted_app_skips_everything(db, user):
    service.create_rule(db, user.user_id, "muted_app", "zalo", None)
    assert zalo(user, db, [msg("Lan", "a", 0)])["status"] == "ignored"


def test_hidden_content_and_plain_notification(db, user):
    out = service.ingest_notification(
        db,
        user,
        parser="sms",
        app_package="com.samsung.android.messaging",
        payload={"title": "0912345678", "text": "", "messages": [], "hidden_content": True},
        posted_at=AT,
    )
    assert out["status"] == "done"
    [m] = service.list_messages(
        db,
        user.user_id,
        service.list_conversations(db, user.user_id, {}, None)["items"][0]["conversation_key"],
        None,
    )["items"]
    assert m["hidden_content"] and m["text"] == service.HIDDEN_TEXT and m["sender"] == "0912345678"


def test_ai_listing_skips_private_and_masks_phone(db, user):
    service.ingest_notification(
        db,
        user,
        parser="sms",
        app_package="com.google.android.apps.messaging",
        payload={"title": "0912345678", "text": "Goi lai so 0987654321 nhe"},
        posted_at=AT,
    )
    zalo(user, db, [msg("Bí mật", "chuyện riêng", 0)])
    secret_key = next(
        c["conversation_key"]
        for c in service.list_conversations(db, user.user_id, {}, None)["items"]
        if c["title"] == "Bí mật"
    )
    service.create_rule(db, user.user_id, "private_conversation", secret_key, None)

    out = service.list_messages_for_ai(db, user.user_id)
    assert out["total"] == 1
    [item] = out["items"]
    assert item["sender"] == "xxxxxxx678" and "0987654321" not in item["text"] and "321" in item["text"]
    assert any(c["is_private"] for c in service.list_conversations(db, user.user_id, {}, None)["items"])


def test_api_paging_mark_and_rules(auth_client, db, user):
    for i in range(3):
        zalo(user, db, [msg(f"Người {i}", "xin chào", i)])
    first = auth_client.get("/api/v1/inbox/conversations", params={"limit": 2}).json()["data"]
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = auth_client.get(
        "/api/v1/inbox/conversations", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()["data"]
    assert [c["title"] for c in rest["items"]] == ["Người 0"] and rest["next_cursor"] is None

    key = first["items"][0]["conversation_key"]
    msgs = auth_client.get(f"/api/v1/inbox/conversations/{key}/messages").json()["data"]["items"]
    resp = auth_client.post("/api/v1/inbox/messages/mark", json={"ids": [msgs[0]["id"]], "status": "seen"})
    assert resp.json()["data"] == {"updated": 1}
    assert (
        auth_client.patch(f"/api/v1/inbox/messages/{msgs[0]['id']}", json={"status": "done"}).json()["data"][
            "status"
        ]
        == "done"
    )
    assert auth_client.post(f"/api/v1/inbox/conversations/{key}/mark", json={"status": "done"}).json()[
        "data"
    ] == {"updated": 0}

    rule = {"kind": "vip_sender", "value": "Mẹ", "app": "zalo"}
    created = auth_client.post("/api/v1/inbox/rules", json=rule)
    assert created.status_code == 201
    assert auth_client.post("/api/v1/inbox/rules", json={**rule, "value": "mẹ"}).status_code == 409
    assert len(auth_client.get("/api/v1/inbox/rules").json()["data"]["items"]) == 1
    assert auth_client.delete(f"/api/v1/inbox/rules/{created.json()['data']['id']}").status_code == 200


def test_search_finds_inbox_without_accents_and_hides_private_from_ai(db, user):
    from app.modules.search import service as search

    zalo(user, db, [msg("Lan", "Hẹn đi Đà Lạt cuối tuần", 0)])
    hits = search.search(db, user.user_id, "da lat", ["inbox"])
    assert hits and hits[0]["open"]["screen"] == "inbox_conversation"
    key = hits[0]["open"]["params"]["conversation_key"]
    service.create_rule(db, user.user_id, "private_conversation", key, None)
    assert search.search(db, user.user_id, "da lat", ["inbox"]) == []
    assert search.search(db, user.user_id, "da lat", ["inbox"], include_private=True)
