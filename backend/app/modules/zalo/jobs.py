"""Job tải ảnh, video, tệp của tin Zalo về R2 (link CDN của Zalo hết hạn sau vài giờ nên tải ngay)."""

import logging

from app.core.db import SessionLocal
from app.integrations.zalo_bridge import client as bridge
from app.modules.inbox import zalo as inbox_zalo

log = logging.getLogger("troly.zalo.jobs")

BATCH = 10


def fetch_media_due() -> int:
    done = 0
    with SessionLocal() as session:
        for m in inbox_zalo.pending_media(session, BATCH):
            inbox_zalo.fetch_media_for(session, m, bridge.fetch_media)
            session.commit()
            done += 1
    return done
