#!/usr/bin/env bash
# Đẩy bản main hiện tại lên VPS và dựng lại troly (docs/50-ha-tang/50-ha-tang-trien-khai.md mục 3.8).
#
# Dùng (chạy ở máy cá nhân, Git Bash hoặc Linux):
#   VPS_HOST=root@<ip> SSH_KEY=<đường dẫn khóa> bash scripts/deploy.sh             deploy
#   VPS_HOST=... bash scripts/deploy.sh --dry-run                                  chỉ in các bước
#   VPS_HOST=... bash scripts/deploy.sh --rollback                                 quay về thẻ ảnh trước
# Biến tùy chọn: SKIP_CI_CHECK=1 bỏ bước kiểm CI (khi chưa có kho trên GitHub).
#
# Chỉ đụng /opt/troly và các container troly-*. Không đụng /opt/gamebar, /opt/gymcanhan, cloudflared.
# Lần đầu: script dừng vì thiếu /opt/troly/.env; tạo tệp đó từ .env.example (quyền 600) rồi chạy lại.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=deploy
case "${1:-}" in
  --dry-run) MODE=dry ;;
  --rollback) MODE=rollback ;;
  "") ;;
  *) echo "Không hiểu tham số: $1"; exit 2 ;;
esac

: "${VPS_HOST:?Đặt VPS_HOST, ví dụ VPS_HOST=root@<ip>}"
SSH_OPTS=(-o BatchMode=yes)
if [ -n "${SSH_KEY:-}" ]; then SSH_OPTS+=(-i "$SSH_KEY" -o IdentitiesOnly=yes); fi
REMOTE_DIR=/opt/troly

remote() {
  if [ "$MODE" = dry ]; then
    echo "[ssh $VPS_HOST] $*"
  else
    ssh "${SSH_OPTS[@]}" "$VPS_HOST" "$@"
  fi
}

if [ "$MODE" = rollback ]; then
  remote "cd $REMOTE_DIR && bash scripts/vps-rollback.sh"
  exit 0
fi

# Bước 1: kiểm ở máy.
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = main ] || { echo "Phải ở nhánh main (đang ở $BRANCH)."; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Cây làm việc còn thay đổi chưa commit."; exit 1; }
SHA=$(git rev-parse --short=12 HEAD)
VERSION=$(git describe --tags --always 2>/dev/null || echo "$SHA")
if [ "${SKIP_CI_CHECK:-0}" != 1 ]; then
  CI=$(gh run list --workflow backend-test.yml --commit "$(git rev-parse HEAD)" --json conclusion --jq '.[0].conclusion' 2>/dev/null || true)
  [ "$CI" = success ] || { echo "backend-test chưa xanh cho commit $SHA (kết quả: ${CI:-không có}). Đặt SKIP_CI_CHECK=1 nếu chắc chắn."; exit 1; }
fi
echo "Deploy $SHA ($VERSION) lên $VPS_HOST"

# Bước 2: chép tệp cần dựng ảnh; .env trên VPS giữ nguyên.
if [ "$MODE" = dry ]; then
  echo "[local] git archive HEAD docker-compose.yml .env.example backend infra scripts | ssh $VPS_HOST tar -xf - -C $REMOTE_DIR"
else
  remote "mkdir -p $REMOTE_DIR"
  git archive --format=tar HEAD docker-compose.yml .env.example backend infra scripts \
    | ssh "${SSH_OPTS[@]}" "$VPS_HOST" "tar -xf - -C $REMOTE_DIR"
fi

# Bước 3 tới 7 chạy trên VPS.
remote "cd $REMOTE_DIR && bash scripts/vps-deploy.sh '$SHA' '$VERSION'"
