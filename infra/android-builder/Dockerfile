# Ảnh build APK debug và chạy JUnit trên máy cá nhân (docs/50-ha-tang mục 3.11).
# Bản phát hành vẫn chỉ build trên GitHub Actions. Dùng qua dịch vụ android-test của infra/docker-compose.test.yml.
FROM node:24-bookworm-slim AS node

FROM eclipse-temurin:21-jdk

# Node 24 lấy từ ảnh node chính thức (cùng bản với node:24-alpine của dịch vụ web).
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip git rsync \
    && rm -rf /var/lib/apt/lists/*

# Android command-line tools; Gradle tự tải thêm thành phần SDK còn thiếu (giấy phép đã chấp nhận).
ARG CMDLINE_TOOLS_BUILD=13114758
ARG ANDROID_PLATFORM=android-36
ARG BUILD_TOOLS=36.0.0
ENV ANDROID_HOME=/opt/android-sdk ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH=$PATH:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools
RUN mkdir -p /opt/android-sdk/cmdline-tools \
    && cd /tmp \
    && curl -fsSLo tools.zip "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_BUILD}_latest.zip" \
    && unzip -q tools.zip \
    && mv cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && rm tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;${ANDROID_PLATFORM}" "build-tools;${BUILD_TOOLS}" >/dev/null

# awscli và jq cho bước đăng APK lên R2 (scripts/release-apk.sh).
RUN apt-get update \
    && apt-get install -y --no-install-recommends awscli jq \
    && rm -rf /var/lib/apt/lists/*

COPY prepare-android.sh /usr/local/bin/prepare-android
COPY build-debug-apk.sh /usr/local/bin/build-debug-apk
COPY build-release-apk.sh /usr/local/bin/build-release-apk
RUN chmod +x /usr/local/bin/prepare-android /usr/local/bin/build-debug-apk /usr/local/bin/build-release-apk
WORKDIR /work
CMD ["build-debug-apk"]
