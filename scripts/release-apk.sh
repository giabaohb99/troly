#!/usr/bin/env bash
# Build, ký và đăng APK bản phát hành từ máy cá nhân (QĐ-32, docs/50-ha-tang mục 3.7).
#
#   bash scripts/release-apk.sh 1.0.0 ["ghi chú phát hành"]          build, ký, đẩy APK + releases/latest.json lên R2
#   bash scripts/release-apk.sh 1.0.0 "" --no-upload                  chỉ build và ký, không đăng
#
# Cần Docker và thư mục bí mật ngoài kho (mặc định D:/giabao/troly-secrets, đổi bằng TROLY_SECRETS):
#   troly-release.jks, keystore.env, cert-sha256.txt   do scripts/make-keystore.sh tạo
#   r2.env   R2_ENDPOINT, R2_BUCKET=assistant, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (QĐ-31)
# Đặt FORCE=1 để build khi cây làm việc còn thay đổi (chỉ để thử).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION_NAME="${1:?Cần số phiên bản dạng X.Y.Z}"
NOTES="${2:-}"
UPLOAD=1
[ "${3:-}" = "--no-upload" ] && UPLOAD=0
[[ "$VERSION_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Phiên bản phải dạng X.Y.Z"; exit 2; }
IFS=. read -r X Y Z <<< "$VERSION_NAME"
VERSION_CODE=$(( X * 10000 + Y * 100 + Z ))

SECRETS="${TROLY_SECRETS:-D:/giabao/troly-secrets}"
for f in troly-release.jks keystore.env cert-sha256.txt; do
  [ -f "$SECRETS/$f" ] || { echo "Thiếu $SECRETS/$f (chạy scripts/make-keystore.sh)."; exit 1; }
done
if [ "$UPLOAD" = 1 ] && [ ! -f "$SECRETS/r2.env" ]; then
  echo "Thiếu $SECRETS/r2.env (mã R2 dùng chung của Gamebar, QĐ-31)."; exit 1
fi
if [ "${FORCE:-0}" != 1 ] && [ -n "$(git status --porcelain)" ]; then
  echo "Cây làm việc còn thay đổi chưa commit; bản phát hành phải build từ mã đã commit (FORCE=1 để thử)."; exit 1
fi

MOUNT="$SECRETS"
if command -v cygpath >/dev/null 2>&1; then MOUNT="$(cygpath -w "$SECRETS")"; fi

echo "Build $VERSION_NAME (versionCode $VERSION_CODE), đăng lên R2: $UPLOAD"
MSYS_NO_PATHCONV=1 docker compose -f infra/docker-compose.test.yml --profile android run --rm \
  -v "$MOUNT:/secrets:ro" \
  -e VERSION_NAME="$VERSION_NAME" -e VERSION_CODE="$VERSION_CODE" -e NOTES="$NOTES" -e UPLOAD="$UPLOAD" \
  android-test build-release-apk
