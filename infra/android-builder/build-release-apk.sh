#!/usr/bin/env bash
# Build, ký, kiểm và đăng APK bản phát hành (QĐ-32). Chạy trong ảnh troly-android-builder,
# do scripts/release-apk.sh gọi. Cần /secrets (chỉ đọc): troly-release.jks, keystore.env, cert-sha256.txt,
# và r2.env khi đăng lên R2.
set -euo pipefail
: "${VERSION_NAME:?}" "${VERSION_CODE:?}"
source /secrets/keystore.env
source /usr/local/bin/prepare-android

if [ "$GENERATED" = 1 ]; then
  sed -i -E "s/versionCode [0-9]+/versionCode $VERSION_CODE/; s/versionName \"[^\"]*\"/versionName \"$VERSION_NAME\"/" android/app/build.gradle
fi

cd android
# Dự án Android thật đọc phiên bản từ hai thuộc tính này (trolyVersionCode, trolyVersionName).
./gradlew --no-daemon testReleaseUnitTest assembleRelease \
  -PtrolyVersionCode="$VERSION_CODE" -PtrolyVersionName="$VERSION_NAME" \
  -Pandroid.injected.signing.store.file=/secrets/troly-release.jks \
  -Pandroid.injected.signing.store.password="$ANDROID_KEYSTORE_PASSWORD" \
  -Pandroid.injected.signing.key.alias="$ANDROID_KEY_ALIAS" \
  -Pandroid.injected.signing.key.password="$ANDROID_KEYSTORE_PASSWORD"

APK_SRC=$(ls app/build/outputs/apk/release/*.apk | grep -v unsigned | head -1)
BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
GOT=$("$BT/apksigner" verify --print-certs "$APK_SRC" | sed -n 's/.*certificate SHA-256 digest: //p' | head -1)
WANT=$(tr -d ': \n' < /secrets/cert-sha256.txt | tr 'A-F' 'a-f')
[ "$GOT" = "$WANT" ] || { echo "Dấu vân tay chứng chỉ không khớp cert-sha256.txt (được: $GOT)."; exit 1; }

mkdir -p /out
APK=/out/troly-$VERSION_NAME.apk
cp "$APK_SRC" "$APK"
echo "APK đã ký: infra/android-builder/build/troly-$VERSION_NAME.apk"

[ "${UPLOAD:-1}" = 1 ] || { echo "Bỏ qua đăng lên R2 (--no-upload)."; exit 0; }

source /secrets/r2.env
export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" AWS_DEFAULT_REGION=auto
S3=(aws s3 --endpoint-url "$R2_ENDPOINT")
KEY="releases/troly-$VERSION_NAME.apk"
MIN=$(jq -r '.troly.minSupportedVersionCode // 0' /work/package.json)

"${S3[@]}" cp "$APK" "s3://$R2_BUCKET/$KEY"
jq -n \
  --argjson version_code "$VERSION_CODE" --arg version_name "$VERSION_NAME" --arg apk_key "$KEY" \
  --arg sha256 "$(sha256sum "$APK" | cut -d' ' -f1)" --argjson size_bytes "$(stat -c %s "$APK")" \
  --argjson min_supported_version_code "$MIN" --arg notes "${NOTES:-}" --arg published_at "$(date -u +%FT%TZ)" \
  '{version_code:$version_code, version_name:$version_name, apk_key:$apk_key, sha256:$sha256,
    size_bytes:$size_bytes, min_supported_version_code:$min_supported_version_code,
    notes:$notes, published_at:$published_at}' > /out/latest.json
"${S3[@]}" cp /out/latest.json "s3://$R2_BUCKET/releases/latest.json" --content-type application/json

# Giữ 10 APK mới nhất.
aws s3api list-objects-v2 --endpoint-url "$R2_ENDPOINT" --bucket "$R2_BUCKET" --prefix releases/troly- \
  --query 'sort_by(Contents, &LastModified)[].Key' --output text | tr '\t' '\n' | grep . \
  | head -n -10 | while read -r OLD; do "${S3[@]}" rm "s3://$R2_BUCKET/$OLD"; done

echo "Đã đăng $VERSION_NAME (versionCode $VERSION_CODE) lên s3://$R2_BUCKET/releases/."
