"""Cài FileStore của integrations/google/stores.py trên tab_file (registry.register_integrations)."""

from sqlalchemy import select, update

from app.modules.file import service
from app.modules.file.models import File


class FileStore:
    def file_bytes(self, session, user_id, file_id):
        return service.read_file_bytes(session, user_id, file_id)

    def drive_file_id(self, session, user_id, file_id):
        return session.scalar(select(File.drive_file_id).where(File.id == file_id, File.user_id == user_id))

    def save_drive_result(self, session, user_id, file_id, drive_file_id, web_view_link):
        session.execute(
            update(File)
            .where(File.id == file_id, File.user_id == user_id)
            .values(drive_file_id=drive_file_id, drive_web_view_link=web_view_link)
        )


STORE = FileStore()
