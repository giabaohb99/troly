"""Cài BookingStore của integrations/google/stores.py (registry.register_integrations)."""

from app.modules.booking import service


class BookingStore:
    def seen(self, session, user_id, message_ids):
        return service.seen(session, user_id, message_ids)

    def handle_booking_mail(self, session, user_id, mail):
        return service.handle_mail(session, user_id, mail)


STORE = BookingStore()
