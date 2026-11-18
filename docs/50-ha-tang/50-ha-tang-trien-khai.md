# Hạ tầng và triển khai

Ngày lập: 18/11/2026. Người giữ: agent hạ tầng. Trạng thái: bản 3, gọn hóa theo QĐ-27 và sửa theo `81-ra-cheo-lan-2.md`.

Nguồn chuẩn (QĐ-25): tệp này là nguồn chuẩn cho **mạng, cổng, compose**. Biến môi trường và danh sách job theo `10-kien-truc-backend.md` (mục 3.6, 3.9); đường dẫn API và giới hạn theo `12-api.md`; bảng theo `11-co-so-du-lieu.md`.

Liên quan: [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md); [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md).

## 1. Mục tiêu

- Chạy api, worker, db của troly trên VPS chung, không làm hỏng gymcanhan; không mở cổng web nào ra Internet, mọi lưu lượng qua Cloudflare Tunnel sẵn có.
- Thử trên VPS hiện tại (2 vCPU, 4 GB RAM). Chạy ổn thì người dùng mua VPS mạnh hơn và chuyển sang bằng bản sao lưu (mục 3.9).
- Build APK trên GitHub Actions; máy cá nhân chỉ cần Docker.
- Deploy một lệnh, quay lui một lệnh, sao lưu trước mỗi lần chạy migration.

## 2. Phạm vi

Trong tệp: Phase 0, mạng và cổng, compose, tài nguyên, Cloudflare, CI, deploy, sao lưu, giám sát, môi trường phát triển, build APK trên máy, tạm dừng Gamebar, trang tĩnh. V3 (Claude CLI) chỉ ghi hướng.

Ngoài tệp: bảo mật ở `60`, kiểm thử ở `70`, mã backend ở `10`, cập nhật APK phía app ở `30-app-android.md`.

Thông tin VPS lấy từ tài liệu và script của gymcanhan và Gamebar, đọc ngày 18/11/2026. Agent không SSH, không chạy lệnh nào lên VPS; mọi lệnh trên VPS trong tệp này do người dùng chạy.

## 3. Thiết kế

### 3.1 VPS hiện tại và Phase 0

| Mục | Hiện trạng |
|---|---|
| Máy | Ubuntu 24.04, 2 vCPU, 4 GB RAM, ổ khoảng 22 GB; tường lửa chỉ mở cổng 22 |
| `cloudflared` | Nằm trong compose của Gamebar (`/opt/gamebar`), `network_mode: host`; gymcanhan dùng chung |
| Gamebar | Container `core-game`, `127.0.0.1:8080`. **Tạm dừng ở Phase 0** (QĐ-24, mục 3.12) |
| gymcanhan | Container `gymcanhan`, `127.0.0.1:8100`; giữ nguyên |

**Phase 0, người dùng làm trước Phase 1 (V1.0, V1.1):**

| Bước | Việc |
|---|---|
| 1 | Kiểm VPS: `ss -ltn` (cổng 8200 trống), `docker stats --no-stream`, `free -m`, `df -h /`. Gửi kết quả cho điều phối |
| 2 | Cloudflare: thêm Public Hostname `troly.baohuynh.io.vn` trỏ `http://localhost:8200` vào tunnel đang có (mục 3.5) |
| 3 | R2: tạo ba bucket riêng tư `troly-files`, `troly-backup`, `troly-release`; một mã R2 cho VPS (quyền trên cả ba), một mã cho CI (chỉ `troly-release`) |
| 4 | Khóa Anthropic; tạo `JWT_SECRET`, `TOKEN_ENCRYPTION_KEYS`, mật khẩu DB; cất bản sao trong trình quản lý mật khẩu |
| 5 | Khóa ký APK: tạo trên máy cá nhân theo `60` mục 3.3, dán vào GitHub Secrets |
| 6 | Tạm dừng Gamebar (mục 3.12), có xác nhận của người dùng |

Google Cloud (OAuth, Maps) để tới Phase 3 (V1.4).

### 3.2 Mạng và cổng

```
 Cloudflare ── tunnel ── cloudflared (của Gamebar, mạng host)
                            ├─ gym.baohuynh.io.vn    -> 127.0.0.1:8100  gymcanhan
                            ├─ game.baohuynh.io.vn   -> 127.0.0.1:8080  core-game (tạm dừng)
                            └─ troly.baohuynh.io.vn  -> 127.0.0.1:8200  troly-api
 Dự án compose "troly" (/opt/troly)
   troly_edge (bridge): troly-api, troly-worker  -> ra Internet (Claude, Google, R2)
   troly_core (internal): troly-api, troly-worker, troly-db (không cổng)
```

| Luật | Cách làm |
|---|---|
| Thư mục | Chỉ ghi `/opt/troly`; không đụng `/opt/gamebar`, `/opt/gymcanhan` |
| Tên | Dự án compose `troly`; container `troly-api`, `troly-worker`, `troly-db`, `troly-migrate`; volume `troly-pgdata` |
| Cổng | Chỉ `127.0.0.1:8200` ra máy. 8080, 8100 là của app khác; DB không mở cổng |
| Dọn đĩa | Chỉ dọn ảnh nhãn `com.troly.image=1` và bộ đệm build cũ hơn 3 ngày; cấm `docker system prune -a`, `docker volume prune` |

Máy cá nhân: api 8200, Vite 5190, DB dev `127.0.0.1:55432`.

### 3.3 Docker Compose

| Tệp | Dùng ở | Nội dung |
|---|---|---|
| `docker-compose.yml` | VPS; nền ở máy cá nhân | db, api, worker, migrate |
| `docker-compose.dev.yml` | Máy cá nhân, ghép đè | Mã gắn volume, tự nạp lại, DB mở cổng, `web`, S3 giả (mục 3.10) |
| `infra/docker-compose.test.yml` | Máy cá nhân và CI, đứng riêng | `db-test` trên tmpfs, `test`, `web-test`, `android-test` (`70` mục 3.2) |

`backend/Dockerfile` ba đích: `base` (`python:3.12-slim`, phụ thuộc chạy thật, `postgresql-client-16`), `dev` (thêm pytest, ruff, watchfiles; mã gắn volume), `prod` (chép mã, user không phải root). Ảnh nền chốt cho mọi nơi: `postgres:16-alpine`, `python:3.12-slim`, `node:24-alpine`.

```yaml
name: troly

x-backend: &backend
  image: troly-backend:${TROLY_IMAGE_TAG:-latest}
  env_file: .env
  restart: unless-stopped
  stop_grace_period: 30s
  labels: { com.troly.image: "1" }
  logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }

services:
  db:
    image: postgres:16-alpine
    container_name: troly-db
    environment: { POSTGRES_DB: "${POSTGRES_DB}", POSTGRES_USER: "${POSTGRES_USER}", POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}", TZ: UTC }
    command: postgres -c shared_buffers=128MB -c max_connections=30 -c log_min_duration_statement=1000
    volumes: [troly-pgdata:/var/lib/postgresql/data]
    networks: [troly_core]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"], interval: 10s, retries: 5 }
    deploy: { resources: { limits: { cpus: "0.75", memory: 512M } } }
    restart: unless-stopped

  migrate:
    <<: *backend
    container_name: troly-migrate
    command: ["alembic", "upgrade", "head"]
    restart: "no"
    networks: [troly_core]
    depends_on: { db: { condition: service_healthy } }
    profiles: ["migrate"]

  api:
    <<: *backend
    container_name: troly-api
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1",
              "--proxy-headers", "--forwarded-allow-ips", "*"]
    ports: ["${API_BIND:-127.0.0.1}:${API_PORT:-8200}:8000"]
    networks: [troly_core, troly_edge]
    depends_on: { db: { condition: service_healthy } }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"], interval: 30s, retries: 3 }
    deploy: { resources: { limits: { cpus: "0.75", memory: 448M } } }

  worker:
    <<: *backend
    container_name: troly-worker
    command: ["python", "-m", "worker.main"]
    networks: [troly_core, troly_edge]
    depends_on: { db: { condition: service_healthy } }
    deploy: { resources: { limits: { cpus: "0.5", memory: 384M } } }

volumes: { troly-pgdata: {} }
networks: { troly_core: { internal: true }, troly_edge: {} }
```

- `--forwarded-allow-ips "*"` an toàn vì cổng chỉ nghe `127.0.0.1`; IP thật lấy từ `CF-Connecting-IP`.
- Một tiến trình uvicorn để bộ đếm giới hạn trong bộ nhớ đúng (`12` mục 3.7).
- Migration chạy bằng dịch vụ `migrate` lúc deploy, không tự chạy khi api khởi động.

### 3.4 Tài nguyên

Gamebar đã tạm dừng từ Phase 0, `cloudflared` vẫn chạy. Số ước, đo lại ở Phase 0 bước 1.

| Thành phần | RAM ước | Trần |
|---|---|---|
| Hệ điều hành, Docker, `cloudflared` | 550 tới 600 MB | |
| gymcanhan | khoảng 150 MB | của gym |
| troly-db | 150 tới 300 MB | 512 MB |
| troly-api | 150 tới 250 MB | 448 MB |
| troly-worker | 120 tới 200 MB | 384 MB |
| **Tổng lúc chạy** | **1,1 tới 1,5 GB** | trần troly 1,34 GB |
| Dự trữ cho build ảnh, bộ đệm | khoảng 2,5 GB | |

Build ảnh với `nice -n 10`; `pg_dump` với `nice`, `ionice -c3`; nhật ký 3 x 10 MB mỗi container. Job `disk_check` cảnh báo khi ổ trống dưới 15 phần trăm, dưới 8 phần trăm thì dừng việc ghi nhiều. Khi chuyển sang VPS mạnh hơn: dựng `/opt/troly` mới, khôi phục bản sao lưu mới nhất (mục 3.9), đổi Public Hostname; nới trần tài nguyên sau khi đo.

### 3.5 Cloudflare Tunnel

1. Public Hostname `troly.baohuynh.io.vn` trỏ `http://localhost:8200` trong tunnel đang có; không tạo tunnel mới, không sửa compose Gamebar.
2. SSL/TLS chế độ Full, bật *Always Use HTTPS*.
3. Luật WAF: `/api/v1/auth/*` tối đa 20 yêu cầu mỗi 10 giây mỗi IP (`12` mục 3.7).
4. Chat dùng SSE (`12` mục 5.3): Cache Rules để *Bypass* cho `/api/*`; api gửi `X-Accel-Buffering: no` và ping 15 giây.
5. Đường công khai: `/api/health`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/google/oauth/callback`, `/api/v1/webhooks/google/*`, `/chinh-sach-rieng-tu`, `/tai-app`.
6. Không chặn webhook Google và trang OAuth bằng kiểm trình duyệt: tắt *Bot Fight Mode* cho tên miền con này hoặc thêm luật Skip cho hai đường đó.
7. Không cần `/.well-known/assetlinks.json`: app quay về bằng `troly://`.

Gamebar deploy lại có thể khởi động lại tunnel vài giây; app có hàng đợi gửi lại.

### 3.6 Biến môi trường

**Danh sách duy nhất ở `10-kien-truc-backend.md` mục 3.6**; tệp này không chép lại. `.env.example` ở gốc kho theo đúng bảng đó. Trên VPS: `/opt/troly/.env`, quyền 600, chủ root; đổi `.env` thì chạy `docker compose up -d` (`docker restart` không nạp lại). Máy cá nhân thêm `COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml` (Windows ngăn bằng dấu chấm phẩy).

Theo QĐ-27, các biến sau không còn: `BACKUP_AGE_RECIPIENT`, `RELEASE_PUBLISH_TOKEN_HASH`, `LOGIN_MAX_FAILS`, `LOGIN_LOCK_MINUTES`, `AUDIT_LOG_RETENTION_DAYS`, `DEV_RUNNER_TOKEN_HASH` (tới V3). `JWT_REFRESH_DAYS` = 365.

Quota Google Maps Platform (Phase 4, đặt trong Cloud Console > Quotas theo `41` mục 7.3): Compute Routes 30 mỗi ngày, Places 300 mỗi ngày, Route Matrix 300 phần tử mỗi ngày. Ngân sách chỉ cảnh báo, quota mới chặn.

### 3.7 GitHub Actions

| Workflow | Khi chạy | Việc |
|---|---|---|
| `backend-test.yml` | Đổi `backend/**`, `testdata/**`, tệp compose | Đúng lệnh như ở máy: `docker compose -f infra/docker-compose.test.yml run --rm test` chạy `ruff check`, `alembic upgrade head`, `pytest -m "not ai_eval"`; `docker build --target prod` |
| `app-build.yml` job `check` | Đổi `app/**` | Trong `node:24-alpine`: `tsc -b`, lint, `vitest run`; JUnit JVM nếu đổi `app/android/**` |
| `app-build.yml` job `apk` | Đẩy thẻ `v*` | Mục dưới |
| `health-check.yml` | Lịch mỗi 2 giờ | `curl https://troly.baohuynh.io.vn/api/health`; hỏng thì GitHub gửi thư |
| `ai-eval.yml` | Chạy tay | Bộ câu mẫu của `20` với Claude thật (`70` mục 3.7) |

**Đăng bản APK (gọn, không cần mã CI gọi API):**

1. Dựng giao diện, `npx cap sync android`, giải mã keystore từ secret ra tệp tạm, `gradle assembleRelease`.
2. `apksigner verify --print-certs`; dấu vân tay phải bằng biến GitHub `ANDROID_SIGNING_CERT_SHA256`, lệch thì dừng.
3. Đẩy `releases/troly-<versionName>.apk` lên `troly-release`, rồi ghi đè `releases/latest.json`: `{version_code, version_name, apk_key, sha256, size_bytes, min_supported_version_code, notes, published_at}`. Giữ 10 APK mới nhất.
4. Xóa tệp keystore tạm (cả khi lỗi).

api đọc `latest.json` từ R2 (đệm 5 phút) để trả `GET /api/v1/device/release` kèm URL ký sẵn 300 giây. App luôn hỏi trước khi cài (QĐ-18). Bản lỗi thì đăng bản mới có `versionCode` lớn hơn; ép cập nhật bằng `min_supported_version_code`. `versionCode` = `X*10000 + Y*100 + Z` từ thẻ `vX.Y.Z`.

Secrets: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `R2_RELEASE_ACCESS_KEY_ID`, `R2_RELEASE_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `ANTHROPIC_API_KEY_EVAL` (tùy chọn). Đặt trong Environment `release`, chỉ nhánh `main` và thẻ `v*` dùng được.

### 3.8 Deploy và quay lui

GitHub Actions không SSH vào VPS. Người dùng chạy `bash scripts/deploy.sh` ở máy cá nhân (giống gym):

| Bước | Việc | Hỏng thì |
|---|---|---|
| 1 | Kiểm nhánh `main`, cây sạch, `backend-test` của commit đã xanh | Dừng |
| 2 | `git archive` (`docker-compose.yml`, `backend`, `infra`, `scripts`) qua SSH vào `/opt/troly` | Dừng |
| 3 | `nice -n 10 docker build --target prod -t troly-backend:<sha>` | Dừng, bản cũ vẫn chạy |
| 4 | Có migration mới thì sao lưu trước migration (mục 3.9) | Dừng |
| 5 | `TROLY_IMAGE_TAG=<sha> docker compose --profile migrate run --rm migrate` | Dừng, bản cũ vẫn chạy |
| 6 | Ghi `TROLY_IMAGE_TAG` vào `.env`, `docker compose up -d api worker`, chờ `/api/health` tối đa 60 giây | Quay lui |
| 7 | Ghi `releases.log`; giữ 3 thẻ ảnh; `docker builder prune -f --filter until=72h` | Chỉ cảnh báo |

Lần đầu: script báo thiếu `.env` rồi dừng; người dùng tạo `/opt/troly/.env`, chạy lại; tạo tài khoản bằng `docker compose run --rm api python -m app.cli create-owner` (`10` mục 3.17); kiểm `/api/health` trả `status: ok`.

Migration phải tương thích ngược với bản trước (thêm cột cho phép null, thêm bảng; đổi tên hay xóa cột làm hai lần deploy), nên **quay lui** chỉ cần `bash scripts/deploy.sh --rollback`: đặt lại thẻ ảnh trước và `up -d`. Hỏng dữ liệu thì khôi phục bản trước migration.

### 3.9 Sao lưu và khôi phục (QĐ-16, QĐ-27)

- Job `backup_database` (`10` mục 3.9), chủ nhật 02:00 giờ Việt Nam, chạy bù nếu lỡ giờ: `pg_dump --format=custom` (đã nén) đẩy thẳng lên `troly-backup/weekly/YYYY-MM-DD.dump`. **Không mã hóa bằng `age`**; bucket riêng tư, chỉ mã R2 của VPS đọc được. Token Google trong bản sao lưu vẫn là bản mã Fernet, khóa không nằm trong DB.
- Bản trước migration ở `troly-backup/premigrate/<thời điểm>-<sha>.dump`.
- Giữ tối đa 5 bản cả hai loại; xóa bản `premigrate` cũ trước để luôn còn ít nhất 1 bản tuần.
- Ghi khóa R2, kích thước, `sha256`, số dòng các bảng chính vào `tab_job_run.detail`. Quá 8 ngày không có bản thành công thì báo đỏ ở màn Máy chủ.
- Nút *Sao lưu ngay* gọi `POST /api/v1/admin/worker/jobs/backup_database/run` (`12` mục 5.13), dùng trước việc lớn vì sao lưu tuần có thể mất tới 7 ngày dữ liệu.

**Khôi phục:** `scripts/restore-db.sh <khóa R2> [--target drill|production]`. `drill` khôi phục vào container tạm rồi xóa; `production` hỏi gõ lại tên bản, dừng api và worker, sao lưu DB hiện tại thành bản `premigrate`, khôi phục, bật lại.

**Diễn tập** trên máy cá nhân bằng bộ compose dev: lần đầu ngay sau bản sao lưu đầu tiên của Phase 1, sau đó mỗi tháng. Đạt khi khôi phục được, `alembic current` đúng, số dòng khớp `detail`, đăng nhập xem được chi tiêu. Ghi vào `90-quan-ly/nhat-ky-viec.md`.

### 3.10 Môi trường phát triển (QĐ-14)

Máy cá nhân: Windows 11, Docker, Node 24; không cài Python, Postgres, Android SDK.

| Dịch vụ trong `docker-compose.dev.yml` | Khác bản chạy thật |
|---|---|
| `db` | Volume `troly-dev-pgdata`, cổng `127.0.0.1:55432` |
| `api` | Đích `dev`, gắn `./backend`, `uvicorn --reload`, `WATCHFILES_FORCE_POLLING=true` (mã trên ổ Windows) |
| `worker` | Đích `dev`, chạy dưới `watchfiles` để tự khởi động lại |
| `web` | `node:24-alpine`, gắn `./app`, `node_modules` trong volume riêng, Vite cổng 5190, `usePolling` |
| `s3` | S3 giả (ví dụ `motoserver/moto`), mặc định ở máy cá nhân |

| Việc | Lệnh |
|---|---|
| Chạy cả bộ | `docker compose up -d --build` |
| Migration | `docker compose run --rm migrate` |
| Tạo migration | `docker compose run --rm api alembic revision --autogenerate -m "<mô tả>"` |
| Tạo tài khoản | `docker compose run --rm api python -m app.cli create-owner` |
| Bài kiểm một module | `docker compose -f infra/docker-compose.test.yml run --rm test pytest backend/app/modules/<x>` |
| Dừng | `docker compose down` (thêm `-v` để xóa DB dev) |

Thử app trên điện thoại với máy chủ ở máy cá nhân: tạm đặt `API_BIND=0.0.0.0` và mở cổng 8200 trên tường lửa Windows; đơn giản hơn là cho APK thử trỏ vào api trên VPS.

### 3.11 Build APK trên máy bằng Docker (từ Phase 2)

Bản phát hành chỉ build trên GitHub Actions. Khi làm plugin Kotlin (Phase 2) và ổ máy cá nhân còn 10 GB: ảnh tự viết `infra/android-build.Dockerfile` (`eclipse-temurin:21-jdk`, Android command-line tools, Node 24, phiên bản ghim) dùng cho dịch vụ `android-test` (`./gradlew testDebugUnitTest`, `./gradlew assembleDebug`). Bản thử ký khóa debug, `applicationIdSuffix ".debug"`, cài song song bản chính. `adb` để ngoài container.

| | GitHub Actions | Docker trên máy |
|---|---|---|
| Mỗi vòng sửa Kotlin | 8 tới 12 phút | 1 tới 3 phút sau lần đầu |
| Ký phát hành | Có | Không, chỉ debug |
| Tốn | Phút CI | 4 tới 8 GB ổ máy |

### 3.12 Tạm dừng Gamebar (QĐ-24)

Làm ở Phase 0, sau khi người dùng xác nhận. **Chỉ dừng `core-game`, giữ `cloudflared`** vì gym dùng chung tunnel.

1. Mở sảnh Gamebar, kiểm không có phòng đang chơi.
2. Sao lưu Gamebar ngay bằng công cụ của Gamebar (`tools/khoi-phuc-r2.js`).
3. `docker stop core-game`. Không chạy `docker compose down` hay `stop` trong `/opt/gamebar` (sẽ dừng cả `cloudflared`), không xóa container, không xóa volume `gamebar-db`.
4. Kiểm: `docker ps` còn `cloudflared` và `gymcanhan`; `curl -s http://127.0.0.1:8100/api/health` trả lời; tên miền gym vào được.

Mở lại khi RAM đo thật còn dư hơn 600 MB: `docker start core-game`, kiểm `curl -s http://127.0.0.1:8080`. Lưu ý: chạy script deploy của Gamebar cũng làm `core-game` chạy lại.

### 3.13 Trang tĩnh

api phục vụ hai trang HTML ngắn, công khai, ngoài `/api`:

| Đường | Nội dung |
|---|---|
| `/chinh-sach-rieng-tu` | Dữ liệu app thu, gửi tới đâu (Anthropic, Google, Cloudflare), giữ bao lâu (`60` mục 3.6); Google cần trang này cho màn đồng ý OAuth |
| `/tai-app` | Bản APK mới nhất (đọc `latest.json`), `sha256`, dấu vân tay chứng chỉ, nút tải (URL ký sẵn 300 giây), các bước cài trên Galaxy S25+: cho phép cài từ nguồn ngoài, *Cho phép cài đặt bị hạn chế*, *Ứng dụng không bao giờ ngủ*. Nguồn ngoài bị chặn thì cài bằng `adb` (QĐ-27) |

### 3.14 V3: Claude CLI

Để tới V3. Hướng đã chọn: container `troly-dev` trên VPS, không có quyền Docker, không vào mạng `troly_core`, đăng nhập bằng `CLAUDE_CODE_OAUTH_TOKEN` để ở tệp riêng ngoài `/opt/troly/.env`; chỉ chạy ban đêm; deploy sau khi người dùng bấm duyệt. Danh tính máy chạy và các đường `/dev/*` thiết kế lại lúc đó.

## 4. Dữ liệu cần

| Bảng | Việc |
|---|---|
| `tab_job_run` | Cột `detail` (jsonb) cho kết quả sao lưu |
| `tab_job_schedule` | `backup_database` chủ nhật 02:00; job `disk_check` mỗi 15 phút |
| `tab_app_release` | Không cần ở V1: nguồn bản phát hành là `releases/latest.json` trên R2 |

## 5. API hoặc giao tiếp

| Đường | Ghi chú |
|---|---|
| `GET /api/health` | `status`, `db`, `worker_lag_seconds`, `version`, `git_sha` |
| `GET /api/v1/admin/worker` | Thêm: sao lưu gần nhất, số bản đang giữ, ổ trống, chi phí AI tháng so với `AI_MONTHLY_USD`, số OTP bị chặn ở máy chủ |
| `POST /api/v1/admin/worker/jobs/backup_database/run` | Nút *Sao lưu ngay* |
| `GET /api/v1/device/release` | Đọc `latest.json` trên R2 |
| `GET /chinh-sach-rieng-tu`, `GET /tai-app` | Trang tĩnh, ngoài `/api` |

## 6. Kiểm thử

- CI: `docker compose config`, dựng ảnh `prod`, bài kiểm backend trong container (mục 3.7).
- Bài kiểm luật giữ 5 bản sao lưu: một tuần nhiều migration vẫn còn 1 bản tuần.
- `scripts/deploy.sh --dry-run` in các bước.
- Diễn tập khôi phục (mục 3.9); bảng kiểm sau khi dừng Gamebar (mục 3.12).

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Hết RAM khi build ảnh trên VPS 4 GB | Gamebar tạm dừng; trần từng container; build `nice`; nếu vẫn thiếu thì mua VPS mạnh hơn |
| Ổ 22 GB đầy | Giữ 3 thẻ ảnh, dọn bộ đệm 3 ngày, `disk_check`; sao lưu nằm trên R2 |
| Dừng nhầm `cloudflared` | Chỉ `docker stop core-game`; kiểm gym sau khi dừng |
| Mất tới 7 ngày dữ liệu | Sao lưu trước migration; nút *Sao lưu ngay* |
| Lộ mã R2 của VPS thì lộ bản sao lưu không mã hóa | Bucket riêng tư; mã R2 chỉ ở `.env`; token Google vẫn là bản mã |
| Lệnh dọn Docker xóa nhầm volume app khác | Chỉ dọn theo nhãn và theo tuổi |

## 8. Cần agent khác

| Agent | Việc |
|---|---|
| agent kiến trúc | `10` mục 3.6: bỏ các biến nêu ở mục 3.6 của tệp này, `JWT_REFRESH_DAYS` = 365; `10` mục 3.9: job `disk_check`, sao lưu không mã hóa. `11`: bỏ `tab_app_release` ở V1. `12`: bỏ `POST /admin/releases`, `/admin/releases*`, `/device/web-bundle`, kiểu xác thực mã CI; thêm trường cho `/admin/worker` và hai trang tĩnh |
| agent app Android | `30`: bỏ gói giao diện tải riêng và khóa ký ECDSA (QĐ-27); đọc `ReleaseInfo` từ `/device/release`; nội dung trang `/tai-app`; tên biến `ANDROID_SIGNING_CERT_SHA256` |
| điều phối | `02`: `docker-compose.dev.yml`, `infra/docker-compose.test.yml`, `infra/android-build.Dockerfile`, `scripts/deploy.sh`, `scripts/restore-db.sh`, `.github/workflows/health-check.yml`; ghi nhật ký việc khi báo agent Gamebar rằng troly dùng chung tunnel và `core-game` tạm dừng |

## 9. Đề xuất quyết định

| Đề xuất | Lý do |
|---|---|
| Đăng bản APK bằng `releases/latest.json` trên R2, api chỉ đọc; bỏ `tab_app_release` và mã CI ở V1 | Gọn nhất; CI không cần gọi api |
| Thêm `health-check.yml` chạy 2 giờ một lần | Biết api chết mà không cần dịch vụ ngoài (C1 câu 32) |
| Biến môi trường chỉ liệt kê ở `10`; tệp này không chép | Hết lệch giữa hai bảng |
| Khi chuyển VPS mạnh hơn: khôi phục từ bản sao lưu, đổi Public Hostname | Cùng đường với diễn tập, không cần công cụ mới |
