#!/usr/bin/env bash
# Chạy trên VPS trong /opt/troly, do scripts/deploy.sh gọi qua SSH. Không chạy tay ở máy cá nhân.
# Bước 3 tới 7 của docs/50-ha-tang/50-ha-tang-trien-khai.md mục 3.8.
set -euo pipefail
SHA="$1"
VERSION="${2:-$1}"
cd /opt/troly

test -f .env || { echo "Thiếu /opt/troly/.env: chép từ .env.example, quyền 600, điền giá trị thật rồi chạy lại."; exit 1; }

set_tag() {
  if grep -q '^TROLY_IMAGE_TAG=' .env; then
    sed -i "s/^TROLY_IMAGE_TAG=.*/TROLY_IMAGE_TAG=$1/" .env
  else
    echo "TROLY_IMAGE_TAG=$1" >> .env
  fi
}

wait_healthy() {
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8200/api/health >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

PREV_TAG=$(grep '^TROLY_IMAGE_TAG=' .env | cut -d= -f2 || true)

# Bước 3: dựng ảnh, bản đang chạy không bị đụng.
nice -n 10 docker build --target prod \
  --build-arg GIT_SHA="$SHA" --build-arg APP_VERSION="$VERSION" \
  --label com.troly.image=1 -t "troly-backend:$SHA" backend

# Bước 4 và 5: sao lưu trước migration, rồi migrate (chỉ khi đã có Alembic).
if [ -f backend/alembic.ini ]; then
  STATE=$(TROLY_IMAGE_TAG="$SHA" docker compose --profile migrate run --rm -T migrate \
    sh -c 'echo "current=$(alembic current 2>/dev/null | awk "{print \$1}")"; echo "head=$(alembic heads | awk "{print \$1}")"')
  CURRENT=$(echo "$STATE" | sed -n 's/^current=//p')
  HEAD=$(echo "$STATE" | sed -n 's/^head=//p')
  if [ "$CURRENT" != "$HEAD" ]; then
    echo "Có migration mới ($CURRENT -> $HEAD): sao lưu trước migration."
    mkdir -p backups
    STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
      > "backups/premigrate-$STAMP-$SHA.dump"
    # Khi job sao lưu (backup_database) có lệnh đẩy lên R2, đổi đoạn này sang lệnh đó; tạm giữ 3 bản trên VPS.
    ls -1t backups/premigrate-*.dump | tail -n +4 | xargs -r rm -f
    TROLY_IMAGE_TAG="$SHA" docker compose --profile migrate run --rm migrate
  fi
fi

# Bước 6: đổi api, worker sang ảnh mới.
set_tag "$SHA"
docker compose up -d db api worker
if ! wait_healthy; then
  echo "api không khỏe sau 60 giây, quay về ${PREV_TAG:-không có}."
  if [ -n "$PREV_TAG" ]; then set_tag "$PREV_TAG"; docker compose up -d api worker; fi
  exit 1
fi

# Bước 7: ghi nhật ký, dọn ảnh cũ (giữ 3 thẻ), dọn bộ đệm build cũ hơn 3 ngày.
echo "$(date -u +%FT%TZ) $SHA $VERSION ok" >> releases.log
docker images troly-backend --format '{{.Tag}}' | grep -v -e latest -e dev -e "^$SHA$" \
  | tail -n +3 | xargs -r -I{} docker rmi "troly-backend:{}" || true
docker builder prune -f --filter until=72h >/dev/null || true
df -h / | tail -1
echo "Xong: troly-backend:$SHA"
