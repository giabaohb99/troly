#!/usr/bin/env bash
# Khôi phục DB từ một bản sao lưu dạng pg_dump custom (docs/50-ha-tang/50-ha-tang-trien-khai.md mục 3.9).
#
# Lấy tệp: tải từ bucket R2 troly-backup (trang Cloudflare, hoặc aws s3 cp --endpoint-url <R2_ENDPOINT>).
#
#   bash scripts/restore-db.sh <tệp.dump>                       diễn tập: khôi phục vào container tạm rồi xóa
#   bash scripts/restore-db.sh <tệp.dump> --target production   khôi phục đè DB đang chạy (chạy trong /opt/troly trên VPS)
set -euo pipefail
cd "$(dirname "$0")/.."

FILE="${1:?Cần đường dẫn tệp .dump}"
TARGET=drill
if [ "${2:-}" = "--target" ]; then TARGET="${3:?Thiếu giá trị sau --target}"; fi
[ -f "$FILE" ] || { echo "Không thấy tệp $FILE"; exit 1; }

count_rows() {
  # In số dòng ước của mọi bảng tab_* để so với tab_job_run.detail.
  docker exec "$1" psql -U troly -d "$2" -At -c \
    "SELECT relname || ' ' || n_live_tup FROM pg_stat_user_tables WHERE relname LIKE 'tab_%' ORDER BY relname;"
}

if [ "$TARGET" = drill ]; then
  NAME=troly-db-drill
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker run -d --name "$NAME" --memory 384m -e POSTGRES_USER=troly -e POSTGRES_PASSWORD=drill \
    -e POSTGRES_DB=troly postgres:16-alpine >/dev/null
  trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 30); do docker exec "$NAME" pg_isready -U troly -d troly >/dev/null 2>&1 && break; sleep 1; done
  START=$(date +%s)
  docker exec -i "$NAME" pg_restore -U troly -d troly --no-owner --exit-on-error < "$FILE"
  docker exec "$NAME" psql -U troly -d troly -c "ANALYZE;" >/dev/null
  echo "Khôi phục xong trong $(( $(date +%s) - START )) giây. Số dòng các bảng:"
  count_rows "$NAME" troly
  docker exec "$NAME" psql -U troly -d troly -At -c "SELECT 'alembic ' || version_num FROM alembic_version;" 2>/dev/null || true
  echo "Ghi kết quả vào docs/90-quan-ly/nhat-ky-viec.md."
  exit 0
fi

[ "$TARGET" = production ] || { echo "--target chỉ nhận drill hoặc production"; exit 2; }
[ "$(pwd)" = /opt/troly ] || { echo "Chỉ chạy --target production trong /opt/troly trên VPS."; exit 1; }
read -r -p "Gõ lại tên tệp $(basename "$FILE") để khôi phục đè DB đang chạy: " CONFIRM
[ "$CONFIRM" = "$(basename "$FILE")" ] || { echo "Không khớp, dừng."; exit 1; }

docker compose stop api worker
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "backups/premigrate-$STAMP-before-restore.dump"
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < "$FILE"
docker compose up -d api worker
echo "Đã khôi phục. Bản DB trước khi khôi phục: backups/premigrate-$STAMP-before-restore.dump"
