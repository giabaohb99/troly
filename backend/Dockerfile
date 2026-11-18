# Ảnh backend dùng chung cho api, worker, migrate, test (docs/50-ha-tang mục 3.3).
# Ba đích: base (phụ thuộc chạy thật), dev (thêm công cụ phát triển, mã gắn bằng volume), prod (chép mã).

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# Bản client của Debian (17) dump và restore được máy chủ PostgreSQL 16; cần cho job sao lưu.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
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
