"""Thẻ duyệt `send_zalo_message` (QĐ-52): bot gửi Zalo thay người dùng chỉ khi người dùng bấm Duyệt."""

from app.modules.zalo import service

EXECUTORS = {"send_zalo_message": service.execute_approved}
