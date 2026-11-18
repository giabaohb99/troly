# Ảnh backend dùng chung cho api, worker, migrate, test (docs/50-ha-tang mục 3.3).
# Ba đích: base (phụ thuộc chạy thật), dev (thêm công cụ phát triển, mã gắn bằng volume), prod (chép mã).

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# pg_dump phải đúng bản 16 như máy chủ: bản 17 của Debian ghi định dạng và lệnh (transaction_timeout)
# mà pg_restore, máy chủ 16 không đọc được. Lấy postgresql-client-16 từ kho chính thức apt.postgresql.org.
# fonts-dejavu-core: font Unicode đủ dấu tiếng Việt cho tệp PDF bot xuất (QĐ-41), không tải lúc chạy.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSLo /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 fonts-dejavu-core \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN pip install .

FROM base AS dev
RUN pip install ".[dev]"
# Mã gắn vào /app bằng volume (docker-compose.dev.yml, infra/docker-compose.test.yml).

FROM base AS prod
ARG GIT_SHA=unknown
ARG APP_VERSION=unknown
ENV GIT_SHA=${GIT_SHA} APP_VERSION=${APP_VERSION}
COPY . .
RUN useradd --uid 10001 --create-home troly && chown -R troly:troly /app
USER troly
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
