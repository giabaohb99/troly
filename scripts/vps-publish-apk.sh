#!/usr/bin/env bash
# Đẩy một APK đã ký và releases/latest.json lên R2, dùng mã R2 trong .env của troly (không cần mã R2 trên máy cá nhân).
# Chạy trên VPS trong /opt/troly (hoặc ở máy cá nhân với bộ compose dev để thử, xem biến DC, TROLY_DIR):
#
#   bash scripts/vps-publish-apk.sh <tệp.apk> <X.Y.Z> ["ghi chú"]
#
# Biến tùy chọn: MIN_SUPPORTED (mặc định 0) ép cập nhật bản cũ hơn; TROLY_DIR (mặc định /opt/troly);
# DC (mặc định "docker compose").
# Ghi releases/troly-X.Y.Z.apk, ghi đè releases/latest.json, giữ 10 APK mới nhất (docs/50-ha-tang mục 3.7).
set -euo pipefail

APK="${1:?Cần đường dẫn tệp APK}"
VERSION_NAME="${2:?Cần số phiên bản X.Y.Z}"
NOTES="${3:-}"
[[ "$VERSION_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Phiên bản phải dạng X.Y.Z"; exit 2; }
[ -f "$APK" ] || { echo "Không thấy $APK"; exit 1; }
IFS=. read -r X Y Z <<< "$VERSION_NAME"
VERSION_CODE=$(( X * 10000 + Y * 100 + Z ))
APK_ABS="$(cd "$(dirname "$APK")" && pwd)/$(basename "$APK")"
if command -v cygpath >/dev/null 2>&1; then APK_ABS="$(cygpath -w "$APK_ABS")"; fi

cd "${TROLY_DIR:-/opt/troly}"
DC=${DC:-docker compose}

MSYS_NO_PATHCONV=1 $DC run --rm -T --no-deps \
  -v "$APK_ABS:/upload/app.apk:ro" \
  -e VERSION_NAME="$VERSION_NAME" -e VERSION_CODE="$VERSION_CODE" \
  -e NOTES="$NOTES" -e MIN_SUPPORTED="${MIN_SUPPORTED:-0}" \
  worker python - <<'PY'
import hashlib, json, os
from datetime import datetime, timezone

from app.core import storage
from app.core.config import get_settings

bucket = get_settings().r2_bucket
name, code = os.environ["VERSION_NAME"], int(os.environ["VERSION_CODE"])
key = f"releases/troly-{name}.apk"
path = "/upload/app.apk"
sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
size = os.path.getsize(path)

with open(path, "rb") as f:
    storage.upload_fileobj(bucket, key, f)
latest = {
    "version_code": code,
    "version_name": name,
    "apk_key": key,
    "sha256": sha,
    "size_bytes": size,
    "min_supported_version_code": int(os.environ["MIN_SUPPORTED"]),
    "notes": os.environ["NOTES"],
    "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
storage.put_bytes(bucket, "releases/latest.json", json.dumps(latest, ensure_ascii=False).encode(), "application/json")

apks = sorted(
    (o for o in storage.list_keys(bucket, "releases/troly-") if o["key"].endswith(".apk")),
    key=lambda o: o["modified"],
)
for old in apks[:-10]:
    storage.delete(bucket, old["key"])
print(f"Đã đăng {name} (versionCode {code}, {size} byte, sha256 {sha[:12]}...) lên {bucket}/{key}")
PY
