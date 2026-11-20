"""Cài MailStore của integrations/google/stores.py: thư Gmail vào hộp tin (QĐ-43); mục Gmail lấy theo khóa
`gmail.categories`, đổi khóa thì quét lại 7 ngày."""

from app.modules.inbox import mail
from app.modules.setting import service as setting_service


class MailStore:
    def save_gmail_messages(self, session, user_id, mails):
        return mail.save_gmail_messages(session, user_id, mails)

    def gmail_categories(self, session, user_id) -> str:
        return setting_service.get_value(session, user_id, "gmail.categories")

    def on_account_removed(self, session, user_id, email, delete_messages) -> None:
        mail.remove_account_messages(session, user_id, email, delete_messages)


STORE = MailStore()
setting_service.on_change("gmail.categories", mail.rescan_after_categories_change)
