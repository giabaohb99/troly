#!/usr/bin/env bash
# Phần chung của build-debug-apk và build-release-apk: chép app/ (gắn chỉ đọc ở /src) ra /work,
# dựng giao diện, chuẩn bị dự án Android. Không ghi gì vào kho.
set -euo pipefail

rsync -a --delete --exclude node_modules --exclude dist --exclude 'android/**/build' --exclude 'android/.gradle' /src/ /work/
cd /work
npm ci --no-audit --no-fund
npm run build

GENERATED=0
if [ ! -d android ]; then
  # Kho chưa có dự án Android thật: sinh tạm bằng Capacitor (chỉ trong /work).
  npx cap add android
  GENERATED=1
fi
npx cap sync android
# gradlew tạo trên Windows có thể mang CRLF; đổi về LF trên bản chép rồi mới chạy.
tr -d '\015' < android/gradlew > android/gradlew.lf && mv android/gradlew.lf android/gradlew
chmod +x android/gradlew
export GENERATED
