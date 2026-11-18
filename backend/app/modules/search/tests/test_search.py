import uuid

from app.core import clock
from app.modules.chat import repo as chat_repo
from app.modules.chat.models import Message
from app.modules.file.models import File, FileText
from app.modules.memory import service as memory
from app.modules.search import service


def test_unaccented_query_finds_note_chat_and_file(db, user):
    memory.create_note(db, user.user_id, "Hợp đồng nhà", "Thuê nhà ở Phước Hải, hết hạn tháng 6", ["nha"])
    conv = chat_repo.get_or_create_conversation(db, user.user_id, clock.now().date(), clock.now())
    db.add(
        Message(
            user_id=user.user_id,
            conversation_id=conv.id,
            turn_id=uuid.uuid4(),
            role="user",
            content=[{"type": "text", "text": "nhắc anh gia hạn hợp đồng nhà"}],
            text="nhắc anh gia hạn hợp đồng nhà",
        )
    )
    db.add(
        Message(
            user_id=user.user_id,
            conversation_id=conv.id,
            turn_id=uuid.uuid4(),
            role="system",
            content="hợp đồng nhà (ẩn)",
            text="hợp đồng nhà (ẩn)",
            hidden=True,
        )
    )
    f = File(
        user_id=user.user_id,
        r2_key=f"u/{user.user_id}/x.pdf",
        original_name="hd.pdf",
        mime="application/pdf",
        size_bytes=10,
        purpose="document",
        status="ready",
    )
    db.add(f)
    db.flush()
    db.add(
        FileText(
            file_id=f.id,
            user_id=user.user_id,
            content="Điều 1: Bên A cho thuê nhà...",
            method="pdf_text",
            extracted_at=clock.now(),
        )
    )
    db.flush()

    hits = service.search(db, user.user_id, "hop dong nha")

    sources = sorted(h["source"] for h in hits)
    assert sources == ["chat", "note"]  # tin ẩn không ra
    file_hits = service.search(db, user.user_id, "cho thue nha", ["file"])
    assert [h["source"] for h in file_hits] == ["file"]
    assert "<b>" in hits[0]["snippet"]
    assert hits[0]["open"]["type"] == "open_screen"


def test_results_filtered_by_user(db, user):
    memory.create_note(db, user.user_id, "Bí mật", "chỉ của người này", [])
    assert service.search(db, user.user_id + 999, "bi mat") == []
    assert [h["source"] for h in service.search(db, user.user_id, "bi mat")] == ["note"]
