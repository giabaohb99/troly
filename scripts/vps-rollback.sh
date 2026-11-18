#!/usr/bin/env bash
# Chạy trên VPS trong /opt/troly, do scripts/deploy.sh --rollback gọi. Đặt lại thẻ ảnh của lần deploy thành công trước.
set -euo pipefail
cd /opt/troly
CURRENT=$(grep '^TROLY_IMAGE_TAG=' .env | cut -d= -f2)
PREV=$(awk '$4=="ok"{print $2}' releases.log | grep -v "^$CURRENT$" | tail -1)
[ -n "$PREV" ] || { echo "Không có bản trước trong releases.log."; exit 1; }
docker image inspect "troly-backend:$PREV" >/dev/null || { echo "Ảnh troly-backend:$PREV đã bị dọn."; exit 1; }
sed -i "s/^TROLY_IMAGE_TAG=.*/TROLY_IMAGE_TAG=$PREV/" .env
docker compose up -d api worker
echo "$(date -u +%FT%TZ) $PREV rollback-from-$CURRENT rollback" >> releases.log
echo "Đã quay về troly-backend:$PREV"
