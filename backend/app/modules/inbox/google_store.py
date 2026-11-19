"""Cài MailStore của integrations/google/stores.py: thư Gmail hộp Chính vào hộp tin (QĐ-43)."""

from app.modules.inbox import mail


class MailStore:
    def save_gmail_messages(self, session, user_id, mails):
        return mail.save_gmail_messages(session, user_id, mails)


STORE = MailStore()
