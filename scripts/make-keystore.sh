#!/usr/bin/env bash
# Tạo khóa ký APK một lần (QĐ-32, docs/60-bao-mat mục 3.3). Chỉ cần Docker.
#
#   bash scripts/make-keystore.sh [thư mục]      mặc định: D:/giabao/troly-secrets (NGOÀI kho mã)
#
# Sinh mật khẩu ngẫu nhiên, không in ra màn hình. Kết quả trong thư mục:
#   troly-release.jks     khóa ký. Người dùng chép hai bản dự phòng (trình quản lý mật khẩu và một ổ khác).
#   keystore.env          ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS (scripts/release-apk.sh đọc).
#   cert-sha256.txt       dấu vân tay SHA-256 của chứng chỉ (không bí mật; ghi vào nhật ký việc).
# Mất troly-release.jks hoặc keystore.env thì không cập nhật đè được app, phải gỡ ra cài lại.
set -euo pipefail

OUT="${1:-D:/giabao/troly-secrets}"
ALIAS=troly
REPO="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT"
case "$(cd "$OUT" && (pwd -W 2>/dev/null || pwd))" in
  "$REPO"*) echo "Không đặt khóa trong kho mã. Chọn thư mục khác."; exit 1 ;;
esac
if [ -e "$OUT/troly-release.jks" ]; then
  echo "Đã có $OUT/troly-release.jks. Khóa ký chỉ tạo một lần; không ghi đè."
  exit 1
fi

PASS=$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)
umask 077
printf 'ANDROID_KEYSTORE_PASSWORD=%s\nANDROID_KEY_ALIAS=%s\n' "$PASS" "$ALIAS" > "$OUT/keystore.env"

MOUNT="$OUT"
if command -v cygpath >/dev/null 2>&1; then MOUNT="$(cygpath -w "$OUT")"; fi

MSYS_NO_PATHCONV=1 docker run --rm -e KS_PASS="$PASS" -v "$MOUNT:/keys" eclipse-temurin:21-jdk \
  keytool -genkeypair \
    -keystore /keys/troly-release.jks -storetype PKCS12 \
    -storepass:env KS_PASS -keypass:env KS_PASS \
    -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10950 \
    -dname "CN=troly, O=baohuynh.io.vn, C=VN" >/dev/null

MSYS_NO_PATHCONV=1 docker run --rm -e KS_PASS="$PASS" -v "$MOUNT:/keys" eclipse-temurin:21-jdk \
  keytool -list -v -keystore /keys/troly-release.jks -storepass:env KS_PASS -alias "$ALIAS" \
  | sed -n 's/.*SHA256: *//p' | head -1 | tr -d ':' | tr 'A-F' 'a-f' > "$OUT/cert-sha256.txt"

echo "Đã tạo khóa ký ở $OUT"
echo "Dấu vân tay SHA-256: $(cat "$OUT/cert-sha256.txt")"
echo "Việc của người dùng: chép cả thư mục $OUT ra hai chỗ dự phòng."
