"""Ngữ cảnh người gọi, truyền từ router xuống service và công cụ AI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserContext:
    user_id: int
    timezone: str


@dataclass(frozen=True)
class DeviceContext:
    device_id: int
    user_id: int
    timezone: str

    @property
    def user(self) -> UserContext:
        return UserContext(user_id=self.user_id, timezone=self.timezone)
