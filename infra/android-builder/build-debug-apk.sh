#!/usr/bin/env bash
# Build APK debug và chạy JUnit (chạy trong ảnh troly-android-builder). APK ra /out/troly-debug.apk.
set -euo pipefail
source /usr/local/bin/prepare-android

if [ "$GENERATED" = 1 ] && ! grep -q 'applicationIdSuffix' android/app/build.gradle; then
  # Bản thử cài song song bản chính: đuôi .debug cho mã gói.
  sed -i 's/buildTypes {/buildTypes {\n        debug {\n            applicationIdSuffix ".debug"\n            versionNameSuffix "-debug"\n        }/' android/app/build.gradle
fi

cd android
./gradlew --no-daemon testDebugUnitTest assembleDebug

mkdir -p /out
cp "$(ls app/build/outputs/apk/debug/*.apk | head -1)" /out/troly-debug.apk
echo "APK debug: infra/android-builder/build/troly-debug.apk ($(du -h /out/troly-debug.apk | cut -f1))"
