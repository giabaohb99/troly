from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.ai import registry
from app.ai.client import ClaudeClient, NullRecorder
from app.ai.schemas import ToolContext
from app.ai.settings import AiSettings


@dataclass
class FakeUser:
    user_id: int = 1
    timezone: str = "Asia/Ho_Chi_Minh"


class FakeSavepoint:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *rest):
        if exc_type is None:
            self.session.released += 1
        else:
            self.rollback()
        return False

    def rollback(self):
        self.session.rollbacks += 1


class FakeSession:
    def __init__(self):
        self.released = 0
        self.rollbacks = 0

    def begin_nested(self):
        return FakeSavepoint(self)


class FakeStore:
    def __init__(self):
        self.assistant: list[dict] = []
        self.tool_results: list[dict] = []
        self.pending: list[dict] = []
        self.order: list[str] = []

    def save_assistant_message(self, content, ai_run_id, model, text, citations, hidden) -> int:
        self.assistant.append(
            {
                "content": content,
                "ai_run_id": ai_run_id,
                "model": model,
                "text": text,
                "citations": citations,
                "hidden": hidden,
            }
        )
        self.order.append("assistant")
        return len(self.order)

    def save_tool_results(self, content, contains_third_party) -> int:
        self.tool_results.append({"content": content, "contains_third_party": contains_third_party})
        self.order.append("tool_results")
        return len(self.order)

    def create_pending_action(self, tool_name, draft) -> int:
        self.pending.append({"tool_name": tool_name, "draft": draft})
        return 100 + len(self.pending)


@pytest.fixture(autouse=True)
def clean_registry():
    """Bài kiểm của ai/ dùng registry rỗng, xong trả lại công cụ mà app/main.py đã đăng ký."""
    saved = dict(registry._TOOLS)
    registry.clear_tools()
    yield
    registry.clear_tools()
    registry._TOOLS.update(saved)


@pytest.fixture
def settings():
    return AiSettings(anthropic_api_key="test")


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def ctx(session):
    return ToolContext(
        session=session,
        user=FakeUser(),
        conversation_id=7,
        now=datetime(2026, 11, 18, 4, 30, tzinfo=UTC),  # 11:30 giờ Việt Nam
    )


@pytest.fixture
def make_client(settings):
    def make(fake):
        return ClaudeClient(sdk=fake, recorder=NullRecorder(), settings=settings)

    return make
