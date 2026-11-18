# Kiến trúc backend

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 2, thống nhất theo `80-ra-cheo-lan-1.md` (mục A4, A6, D2) và QĐ-14 tới QĐ-25.

Theo QĐ-25, tệp này là **nguồn chuẩn cho biến môi trường và danh sách job**. Mạng, cổng, tệp compose theo `50-ha-tang-trien-khai.md`.

Tài liệu liên quan: [11-co-so-du-lieu.md](11-co-so-du-lieu.md), [12-api.md](12-api.md), [02-cau-truc-ma-nguon.md](../00-tong-quan/02-cau-truc-ma-nguon.md), [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md), [40-tich-hop-google.md](../40-google/40-tich-hop-google.md), [50-ha-tang-trien-khai.md](../50-ha-tang/50-ha-tang-trien-khai.md), [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md), [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md).

## 1. Mục tiêu

- Chốt cách tổ chức mã máy chủ để mọi module viết theo một khuôn.
- Chốt luật dùng chung: đăng nhập, phong bì, lỗi, ghi log, múi giờ, tiền, phân quyền nhiều người dùng.
- Chốt **một danh sách biến môi trường** và **một danh sách job** cho cả bộ tài liệu.
- Đủ chi tiết để dựng V1.0 mà không phải hỏi lại.

## 2. Phạm vi

**Trong phạm vi:** tiến trình `api` và `worker` trong `backend/`; tầng lớp; luật module; cấu hình; đăng nhập (người dùng, thiết bị, CI, máy chạy V3); lỗi; ghi log; worker; múi giờ; tiền; phân quyền; chi phí AI ở mức hạ tầng; lệnh quản trị.

**Ngoài phạm vi:**

| Nội dung | Tệp |
|---|---|
| Bảng, cột, thời hạn giữ | [11-co-so-du-lieu.md](11-co-so-du-lieu.md) |
| Đường dẫn API, giới hạn tần suất | [12-api.md](12-api.md) |
| Lời nhắc, vòng công cụ, cache, giá | `20-bo-nao-ai.md` |
| Plugin Kotlin | `30-app-android.md` |
| OAuth, thuật toán đồng bộ Google | `40-tich-hop-google.md`, `41-ban-do-lich-trinh.md` |
| Compose, mạng, cổng, deploy, sao lưu chi tiết | `50-ha-tang-trien-khai.md` |
| Mã hóa, OTP, dữ liệu người khác | `60-bao-mat-rieng-tu.md` |
| Chiến lược kiểm thử | `70-kiem-thu.md` |

## 3. Thiết kế

### 3.1 Chạy trên Docker

Mọi thứ chạy trong Docker, cả máy cá nhân lẫn VPS (QĐ-14). Chi tiết tệp compose ở `50-ha-tang-trien-khai.md` mục 3.4, 3.13; mục này chốt điều mã backend phải tuân theo.

| Dịch vụ | Container | Ảnh | Lệnh | Việc |
|---|---|---|---|---|
| `api` | `troly-api` | `troly-backend` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips "*"` (máy cá nhân thêm `--reload`) | Mọi yêu cầu HTTP |
| `worker` | `troly-worker` | `troly-backend` | `python -m worker.main` (máy cá nhân chạy dưới `watchfiles`) | Hàng đợi, đồng bộ Google, sao lưu, dọn dữ liệu |
| `migrate` | `troly-migrate` | `troly-backend` | `alembic upgrade head` (profile `migrate`, chạy một lần) | Migration |
| `db` | `troly-db` | `postgres:16-alpine` | mặc định | DB, volume `troly-pgdata` |

- **Một ảnh cho `api`, `worker`, `migrate`, `test`**, dựng từ `backend/Dockerfile` ba đích: `base` (`python:3.12-slim`, phụ thuộc chạy thật theo tệp khóa, `postgresql-client-16`, `age`), `dev` (thêm pytest, ruff, pip-audit, watchfiles; mã gắn bằng volume), `prod` (chép mã, user không phải root). Hai tiến trình luôn cùng bản mã.
- **Dịch vụ gọi nhau theo tên dịch vụ Docker**: `DATABASE_URL=postgresql+psycopg://troly:<mật khẩu>@db:5432/troly`. Trong container không dùng `localhost` để trỏ sang dịch vụ khác.
- **Cổng:** `api` nghe 8000 trong container, ra máy ở `127.0.0.1:8200` (cả VPS và máy cá nhân). Giao diện Vite ở máy cá nhân cổng 5190. DB không mở cổng trên VPS; máy cá nhân mở `127.0.0.1:55432`.
- **Một tiến trình uvicorn**: bộ đếm giới hạn tần suất trong bộ nhớ chỉ đúng khi một tiến trình (`12-api.md` mục 3.7). Cần nhiều tiến trình thì chuyển bộ đếm vào PostgreSQL trước.
- Container `TZ=UTC`, log ra stdout, dừng êm trong 30 giây (`stop_grace_period`).
- **Đồng bộ, không async**: SQLAlchemy 2 đồng bộ với `psycopg` 3, router `def`, SDK `anthropic` và `httpx` đồng bộ (ĐX-KT-01).

**Lệnh thường dùng** (máy cá nhân đặt `COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml` trong `.env`):

| Việc | Lệnh |
|---|---|
| Dựng và chạy | `docker compose up -d --build` |
| Chạy migration | `docker compose --profile migrate run --rm migrate` |
| Tạo migration | `docker compose run --rm api alembic revision --autogenerate -m "<mô tả>"` |
| Chạy bài kiểm một module | `docker compose -f infra/docker-compose.test.yml run --rm test pytest backend/app/modules/<x>` |
| Lệnh quản trị | `docker compose run --rm api python -m app.cli <lệnh>` (mục 3.17) |
| Xem log | `docker compose logs -f api worker` |

### 3.2 Tầng lớp trong một module

```
 HTTP ──> router.py ──┐
                      ├──> service.py ──> repo.py ──> models.py ──> PostgreSQL
 AI   ──> tools.py ───┘         │
 worker ─> jobs.py ─────────────┤
                                ├──> service.py công khai của module khác
                                └──> integrations/ (Google, R2), core/, ai/
```

| Tệp | Được làm | Không được làm |
|---|---|---|
| `models.py` | Bảng SQLAlchemy của module | Luật nghiệp vụ |
| `schemas.py` | Pydantic vào ra, giới hạn, câu lỗi tiếng Việt | Gọi DB |
| `repo.py` | Truy vấn. **Mọi hàm nhận `(session, user_id, ...)` và lọc theo `user_id`** | Gọi Google, Claude, `commit` |
| `service.py` | Luật nghiệp vụ; gọi repo, integrations, service công khai của module khác | Đọc `Request`, trả phong bì, `commit` |
| `router.py` | Kiểm đầu vào, lấy người dùng, gọi service, bọc phong bì | SQL, gọi repo |
| `tools.py` | `TOOLS: list[ToolSpec]` cho AI; với công cụ cần duyệt, khai thêm `execute_approved(session, user_id, input)` cạnh công cụ | Nhận `user_id` từ đầu vào model |
| `jobs.py` | Hàm job riêng của module cho worker gọi | Tự lặp, tự ngủ |
| `tests/` | Bài kiểm của module | |

`ToolSpec` (định nghĩa ở `ai/registry.py`, chi tiết ở `20-bo-nao-ai.md`): `name`, `description`, `input_schema` (`strict: true`), `handler` là hàm **đồng bộ** `def handler(session, user_id, input) -> dict` (A4 dòng 45), `needs_approval`, `execute_approved`.

**Chỗ đặt job** (ĐX-KT-02 làm rõ theo rà chéo mục C): job chỉ chạm một module nằm trong `modules/<x>/jobs.py`; job điều phối nhiều module hoặc việc hệ thống (xử lý sự kiện thiết bị, đẩy hàng chờ Google, sao lưu, dọn dữ liệu, kiểm ổ đĩa) nằm trong `worker/jobs/`.

### 3.3 Giao dịch DB

- **Một yêu cầu, một session, một giao dịch.** `get_session` mở session, `commit` khi router xong không lỗi, `rollback` khi lỗi. Service, repo chỉ `flush`.
- **Endpoint stream (chat)**: FastAPI đóng dependency trước khi phát xong stream, nên hàm sinh stream tự mở session ngắn cho từng bước: lưu tin người dùng rồi `commit`; mỗi công cụ một giao dịch; lưu tin trả lời ở cuối. Mất kết nối thì vẫn chạy nốt và lưu.
- **Worker**: mỗi đơn vị việc một giao dịch.
- **Gọi ra ngoài không nằm trong giao dịch dài**: gọi Claude, Google xong mới mở giao dịch ghi kết quả; hoặc ghi vào hàng chờ trong giao dịch rồi để worker gọi ra.
- **Khi bật RLS** (`11-co-so-du-lieu.md` mục 3.17): `get_session` và mỗi đơn vị việc của worker chạy `SET LOCAL app.user_id = <id>` ngay sau khi mở giao dịch. Viết sẵn điểm gắn này từ V1.0 dù chưa bật RLS.

### 3.4 Luật module và cách module gọi nhau

**Luật cứng:**

1. Module chỉ import từ module khác `app.modules.<x>.service` và `app.modules.<x>.schemas`.
2. Hàm công khai của service không có tiền tố `_`, nhận và trả schema hoặc kiểu cơ bản, không trả đối tượng ORM.
3. Khóa ngoại sang bảng module khác khai bằng chuỗi (`"tab_user.id"`), không import lớp model.
4. Đồ thị phụ thuộc không có vòng.
5. `core/`, `integrations/`, `ai/` không import `modules/`. Chỉ `app/main.py` và `worker/main.py` (gốc ghép) import mọi module để gắn router, công cụ, job. `ai/registry.py` chỉ có `register_tools(tools)`; `main.py` gọi nó cho từng module (A4 dòng 46). Hàm vòng chat là `ai.loop.run_turn`.
6. Dùng chung từ hai module trở lên thì đưa lên `core/` hoặc `integrations/`.

**Chiều phụ thuộc cho phép:**

| Module | Được gọi service của | Ghi chú |
|---|---|---|
| `setting` | (không) | Tầng thấp nhất |
| `file` | `setting` | Gọi `integrations.r2`, `integrations.google.drive` |
| `memory` | `setting` | |
| `calendar` | `setting` | Gọi `integrations.google.calendar` |
| `task` | `calendar`, `setting` | Việc có giờ tạo sự kiện (QĐ-09) |
| `expense` | `setting` | |
| `inbox` | `setting` | Gọi `integrations.google.gmail`, `people`; giữ danh bạ, nháp Gmail |
| `trip` | `calendar`, `file`, `setting` | `to-calendar` đi qua `calendar.service`; gọi `integrations.google.maps` |
| `device` | `setting` | Chỉ nhận và lưu sự kiện |
| `chat` | `memory`, `file`, `setting` | Gọi `ai.loop.run_turn` |
| `report` | `expense`, `task`, `calendar`, `inbox`, `file`, `setting` | Chỉ đọc; gọi `ai.cost` để lấy chi phí. Không module nào gọi `report` |
| `health` (V2) | `setting` | |

**Điều phối sự kiện thiết bị nằm ở `worker/jobs/device_events.py`**: đọc sự kiện qua `device.service`, theo `kind` và `app_package` gọi `expense.service.ingest_bank_notification`, `inbox.service.ingest_notification`, hoặc `task.service.apply_reminder_action` / `calendar.service.apply_reminder_action`, rồi `device.service.mark_event_done`. `device` không phụ thuộc module nào khác.

**Danh sách module bật** đặt cứng trong `app/modules/__init__.py` (`ENABLED_MODULES`); gốc ghép đọc danh sách này để gắn `router`, `TOOLS`, `JOBS`.

### 3.5 Sự kiện nội bộ

| Cách | Khi nào | Ví dụ |
|---|---|---|
| Hàng chờ ghi cùng giao dịch | Cần gọi dịch vụ ngoài sau khi ghi | Sửa sự kiện lịch thì ghi `tab_google_outbox` |
| `NOTIFY troly_wake, '<loại>'` | Đánh thức worker sớm hơn chu kỳ 30 giây | Nhận sự kiện thiết bị, webhook Google, đặt việc vào `tab_job_queue` |

Worker `LISTEN troly_wake` với thời gian chờ bằng `WORKER_POLL_SECONDS`; mất tín hiệu vẫn có vòng quét định kỳ (ĐX-KT-05).

### 3.6 Cấu hình và biến môi trường (danh sách hợp nhất)

- **Cấu hình đọc từ biến môi trường của container**; compose nạp `.env` bằng `env_file`. Mã không tự mở `.env`.
- `core/config.py` khai `Settings` (pydantic-settings, chỉ đọc biến môi trường), đọc **một lần**; thiếu biến bắt buộc thì container dừng với câu báo rõ biến nào. Mã chỉ đọc qua `get_settings()`.
- Bí mật chỉ ở `.env` từng máy, không lên git, không chép vào ảnh. `.env.example` ở gốc kho liệt kê **đúng và đủ** bảng dưới, giá trị giả (`50-ha-tang-trien-khai.md` mục 3.7 giữ nội dung tệp, tên và mặc định theo bảng này).

Cột *Bắt buộc*: **có** là bắt buộc từ V1.0; **V1.x** là bắt buộc từ bản đó; **không** là có mặc định.

| Nhóm | Biến | Bắt buộc | Mặc định | Ghi chú |
|---|---|---|---|---|
| Chung | `ENV` | có | | `dev`, `test`, `prod` |
| | `TZ` | không | `UTC` | |
| | `APP_TIMEZONE` | không | `Asia/Ho_Chi_Minh` | Múi giờ mặc định cho người dùng mới |
| | `MAX_USERS` | không | `4` | |
| | `CORS_ORIGINS` | không | `https://localhost,http://localhost:5190` | WebView Capacitor và Vite máy cá nhân |
| | `LOG_LEVEL` | không | `INFO` | |
| | `PUBLIC_BASE_URL` | có | | `https://<api-domain>`; máy cá nhân `http://localhost:8200` |
| | `API_BIND`, `API_PORT` | không | `127.0.0.1`, `8200` | Chỉ compose dùng |
| | `TROLY_IMAGE_TAG` | không | `latest` | Script deploy ghi |
| DB | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | có | `troly`, `troly`, | Cho dịch vụ `db` |
| | `DATABASE_URL` | có | | Host `db` |
| | `DB_POOL_SIZE` | không | `5` | |
| | `TEST_DATABASE_URL` | chỉ khi test | | Tên DB phải kết thúc `_test` (mục 6) |
| Đăng nhập | `JWT_SECRET` | có | | 64 byte ngẫu nhiên |
| | `JWT_ACCESS_MINUTES` | không | `30` | |
| | `JWT_REFRESH_DAYS` | không | `60` | |
| | `BCRYPT_ROUNDS` | không | `12` | |
| | `LOGIN_MAX_FAILS`, `LOGIN_LOCK_MINUTES` | không | `5`, `15` | |
| Mã hóa | `TOKEN_ENCRYPTION_KEYS` | có | | Vòng khóa Fernet `v1:<khóa>,v2:<khóa>`; khóa đầu mã hóa bản ghi mới. Thay `GOOGLE_TOKEN_KEY` của 40 (A4 dòng 49) |
| AI | `ANTHROPIC_API_KEY` | có | | |
| | `AI_MODEL_CHAT`, `AI_MODEL_EXTRACT` | không | `claude-haiku-5-5` | QĐ-05 |
| | `AI_EFFORT_CHAT` | không | `low` | Tên theo 20 (thay `AI_EFFORT_DEFAULT` của 50) |
| | `AI_COMPACT_TOKENS` | không | `30000` | |
| | `AI_MAX_TOOL_ROUNDS` | không | `8` | |
| | `AI_USER_HOURLY_TURNS` | không | `60` | Chặn bấm liên tục, không phải trần chi phí |
| | `AI_MONTHLY_USD` | không | `200` | **Chỉ cảnh báo**, không chặn (QĐ-15) |
| | `AI_INBOX_MAX_ITEMS` | không | `200` | Số tin hộp tin tối đa gửi Claude một lần |
| R2 | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | có | | Quyền trên `troly-files`, `troly-backup` |
| | `R2_BUCKET_FILES` | không | `troly-files` | |
| | `R2_BUCKET_BACKUP` | không | `troly-backup` | |
| | `R2_BUCKET_RELEASE` | không | `troly-release` | api chỉ đọc (ký URL tải) |
| | `R2_ENDPOINT` | không | dựng từ `R2_ACCOUNT_ID` | Máy cá nhân trỏ S3 giả |
| | `R2_PRESIGN_SECONDS` | không | `300` | Một số cho tải lên và tải về |
| Sao lưu | `BACKUP_AGE_RECIPIENT` | có | | Khóa công khai `age` |
| | `BACKUP_WEEKDAY` | không | `6` (chủ nhật; 0 là thứ Hai) | QĐ-16 |
| | `BACKUP_HOUR`, `BACKUP_MINUTE` | không | `2`, `0` | Giờ Việt Nam |
| | `BACKUP_KEEP` | không | `5` | Gồm bản trước migration (QĐ-16); thay `BACKUP_KEEP_DAILY`, `_MONTHLY`, `_PREDEPLOY` |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | V1.4 | | |
| | `GOOGLE_REDIRECT_URI` | V1.4 | | `https://<api-domain>/api/v1/google/oauth/callback`. Một tên duy nhất (A4 dòng 50) |
| | `GOOGLE_MAPS_API_KEY` | V1.6 | | Giới hạn theo IP VPS |
| | `GOOGLE_SYNC_MIN_SECONDS` | không | `300` | Mỗi người mỗi dịch vụ tối đa một lần đồng bộ mỗi 5 phút, trừ đồng bộ do webhook |
| Đăng bản | `RELEASE_PUBLISH_TOKEN_HASH` | V1.5 | | SHA-256 của mã CI |
| Worker | `WORKER_POLL_SECONDS` | không | `30` | |
| | `WORKER_BATCH_SIZE` | không | `200` | Lô sự kiện thiết bị mỗi vòng (A6 dòng 78) |
| Thời hạn giữ | `INBOX_RETENTION_DAYS` | không | `180` | QĐ-17 |
| | `DEVICE_EVENT_RETENTION_DAYS` | không | `180` | QĐ-17 |
| | `THIRD_PARTY_CHAT_RETENTION_DAYS` | không | `180` | Khối `contains_third_party` trong `tab_message` |
| | `CHAT_RETENTION_DAYS` | không | `365` | Chờ người dùng (`11` câu hỏi mở 1) |
| | `AUDIT_LOG_RETENTION_DAYS` | không | `365` | |
| Ổ đĩa | `DISK_WARN_PERCENT`, `DISK_STOP_PERCENT` | không | `15`, `8` | |
| Giới hạn | `RATE_LOGIN_PER_15MIN` | không | `10` | Bảng ở `12-api.md` mục 3.7 |
| | `RATE_REFRESH_PER_HOUR` | không | `30` | |
| | `RATE_CHAT_PER_MIN` | không | `20` | |
| | `RATE_DEVICE_EVENTS_PER_MIN` | không | `120` | |
| | `RATE_DEVICE_EVENTS_PER_DAY` | không | `5000` | |
| | `RATE_DEVICE_PER_MIN` | không | `60` | |
| | `RATE_USER_PER_MIN` | không | `300` | |
| V3 | `DEV_JOBS_ENABLED` | không | `false` | |
| | `DEV_RUNNER_TOKEN_HASH` | V3 | | |
| | `DEV_JOB_DAILY_USD` | không | `5` | Trần cho việc tự phát triển (không thuộc QĐ-15) |
| Chỉ máy cá nhân | `COMPOSE_FILE`, `WATCHFILES_FORCE_POLLING` | không | | Không có trên VPS |

**Đã bỏ** (QĐ-15, A4): `AI_USER_DAILY_USD`, `AI_DAILY_USD`, `R2_BUCKET`, `GOOGLE_TOKEN_KEY`, `GOOGLE_OAUTH_REDIRECT_URI`, `AI_EFFORT_DEFAULT`, `BACKUP_KEEP_DAILY`, `BACKUP_KEEP_MONTHLY`, `BACKUP_KEEP_PREDEPLOY`.

Biến **không** nằm trong `.env` của app: `CLAUDE_CODE_OAUTH_TOKEN` (chỉ container `troly-dev`), khóa bí mật `age`, khóa ký APK và gói giao diện, `RELEASE_PUBLISH_TOKEN` gốc (GitHub Secrets), `TUNNEL_TOKEN` (của Gamebar).

### 3.7 Đăng nhập và xác thực

Năm loại danh tính, mỗi loại chỉ gọi được đúng nhóm đường của nó (bảng đầy đủ ở `12-api.md` mục 3.2):

| Ai gọi | Tiêu đề | Được gọi |
|---|---|---|
| Giao diện (người dùng) | `Authorization: Bearer <JWT>` | Mọi API của app; `/admin/*` (trừ `releases` POST) cần `role = owner` |
| Plugin (thiết bị) | `Authorization: Device <mã>` | `/device/*` và `/calendar/reminders` |
| GitHub Actions | `Authorization: CI <mã>` | Chỉ `POST /admin/releases` |
| Máy chạy Claude CLI (V3) | `Authorization: Runner <mã>` | Chỉ `/dev/jobs/*` khi `DEV_JOBS_ENABLED=true` |
| Google | `X-Goog-Channel-Token` | Chỉ `/webhooks/google/calendar` |

**Mật khẩu** (`60-bao-mat-rieng-tu.md` mục 3.3 xác nhận): bcrypt hệ số `BCRYPT_ROUNDS`; 8 ký tự tới 72 byte; sai `LOGIN_MAX_FAILS` lần liền khóa `LOGIN_LOCK_MINUTES` phút; câu lỗi chung. Chủ tạo bằng `app.cli create-owner`; thành viên do chủ tạo, mật khẩu tạm, `must_change_password` chặn mọi API trừ đổi mật khẩu, `/auth/me`, đăng xuất.

**JWT cho app:** mã truy cập HS256 30 phút (`sub`, `sid`, `role`, `iat`, `exp`, `typ`); mã làm mới 32 byte, 60 ngày, băm SHA-256 trong `tab_auth_session`, **xoay vòng** mỗi lần; dùng lại mã cũ thì thu hồi cả phiên và ghi kiểm toán. Thu hồi phiên trễ tối đa 30 phút; cắt ngay bằng đổi `JWT_SECRET`. Mở app bằng vân tay là việc trên máy (`30-app-android.md` mục 3.9).

**Mã thiết bị:** `POST /devices` sinh `dev_<base64url 32 byte>`, trả một lần, lưu SHA-256. Thu hồi bằng `revoked_at`, sau đó 401 `DEVICE_REVOKED`. `last_seen_at` cập nhật tối đa một lần mỗi phút. Không đổi được mã thiết bị lấy mã truy cập.

**Mã CI và mã máy chạy:** so SHA-256 của mã gửi lên với `RELEASE_PUBLISH_TOKEN_HASH` (hoặc `DEV_RUNNER_TOKEN_HASH`) bằng phép so thời gian hằng (`hmac.compare_digest`). Mã gốc chỉ nằm ở GitHub Secrets (hoặc máy chạy), VPS chỉ giữ băm.

**Dependency trong router:**

| Dependency | Trả về | Dùng ở |
|---|---|---|
| `get_current_user` | `UserContext(user_id, role, timezone)` | API của app |
| `require_owner` | như trên, chặn nếu không phải chủ | `/users`, `/admin/*` (trừ POST `releases`), `/reports/ai-cost/system` |
| `get_current_device` | `DeviceContext(device_id, user_id)` | `/device/*` |
| `get_device_or_user` | một trong hai, cùng có `user_id` | `/device/release`, `/device/web-bundle`, `/calendar/reminders` |
| `require_ci` | `None` | `POST /admin/releases` |
| `require_runner` | `None` | `/dev/jobs/*` |
| `verify_google_channel` | `sync_state_id` hoặc `None` | Webhook |

`user_id` chỉ lấy từ JWT hoặc mã thiết bị, không bao giờ từ thân yêu cầu hay đường dẫn.

### 3.8 Phong bì và lỗi

Mọi API JSON trả `{success, message, data}`; khi lỗi `data = {code, fields}`. Không dùng phong bì cho SSE, trang OAuth, webhook, 304. Danh sách mã lỗi ở `12-api.md` mục 3.5.

| Lớp (`core/errors.py`) | HTTP | Mã mặc định |
|---|---|---|
| `ValidationError` | 400 | `VALIDATION_ERROR`; lỗi Pydantic cũng đổi thành 400 |
| `UnauthorizedError` | 401 | `AUTH_REQUIRED` |
| `ForbiddenError` | 403 | `FORBIDDEN` |
| `NotFoundError` | 404 | `NOT_FOUND`, kể cả dữ liệu người khác |
| `ConflictError` | 409 | `CONFLICT` |
| `RateLimitError` | 429 | `RATE_LIMITED`, kèm `Retry-After` |
| `ExternalServiceError` | 502 | `EXTERNAL_SERVICE_ERROR`; Claude dùng `AI_UNAVAILABLE` |
| (chưa bắt) | 500 | `INTERNAL_ERROR`, kèm `request_id`, không lộ vết lỗi |

Service ném lỗi; bộ xử lý toàn cục ở `main.py` đổi thành phong bì. Dữ liệu người khác luôn 404.

### 3.9 Worker và danh sách job (danh sách duy nhất)

**Vòng chạy** (`worker/main.py`): chờ `troly_wake` hoặc hết `WORKER_POLL_SECONDS`; chạy mọi job hàng đợi (mỗi job một lô rồi nhường); chạy job theo lịch đã tới giờ (`tab_job_schedule.next_run_at <= now()`); bắt lỗi ở mức từng job. Khởi động lại thì job theo lịch đã lỡ giờ (ví dụ sao lưu) chạy bù ngay. `SIGTERM` thì làm nốt đơn vị việc rồi thoát.

**Bảng job** (40 và 50 dẫn sang đây; tên theo dạng động từ, thay tên ở 40 mục 14 và 50 mục 3.10):

| Job | Loại | Lịch (giờ Việt Nam) | Việc | Chỗ đặt | Bản |
|---|---|---|---|---|---|
| `process_device_events` | hàng đợi | mỗi vòng, lô `WORKER_BATCH_SIZE` | `notification`: ngân hàng, MoMo sang expense (kể cả ghép cặp chuyển nội bộ), tin nhắn sang inbox; `reminder_action`: `done` đánh dấu việc xong, `ack`, `snooze` chỉ ghi nhận | `worker/jobs/device_events.py` | V1.2, `reminder_action` V1.4 |
| `run_queued_jobs` | hàng đợi | mỗi vòng, lô 5 | `tab_job_queue`: `trip_import`, `trip_evaluate`, `google_initial_sync`, `user_export`, `user_delete_files` | `worker/jobs/queue.py` | V1.0 |
| `push_google_outbox` | hàng đợi | mỗi vòng, lô 20 | `tab_google_outbox`: Calendar, Tasks, nháp và gửi Gmail, tải Drive, ghi Sheets | `worker/jobs/google_outbox.py` | V1.4 |
| `sync_google_calendar` | theo trạng thái | mỗi vòng xét: `needs_sync` (webhook, gộp 10 giây) hoặc `next_sync_at` tới hạn (15 phút, lệch ngẫu nhiên ±25%) | Kéo thay đổi bằng `syncToken` | `modules/calendar/jobs.py` | V1.4 |
| `renew_google_watch` | lịch | mỗi ngày 03:00 | Gia hạn kênh còn dưới 48 giờ, dừng kênh cũ | `modules/calendar/jobs.py` | V1.4 |
| `pull_google_tasks_status` | lịch | 15 phút | Đọc ngược `completed`, `deleted` từ danh sách *Trợ lý* (QĐ-21) | `modules/task/jobs.py` | V1.4 |
| `sync_gmail` | lịch | 5 phút | `history.list`, đưa thư vào hộp tin | `modules/inbox/jobs.py` | V1.8 |
| `sync_google_contacts` | lịch | mỗi ngày 04:00 | Kéo danh bạ, cập nhật tên người gửi, sinh nhật | `modules/inbox/jobs.py` | V1.8 |
| `cleanup_google_oauth_state` | lịch | mỗi giờ | Xóa `tab_google_oauth_state` quá hạn | `worker/jobs/cleanup.py` | V1.4 |
| `summarize_previous_day` | lịch | mỗi ngày 04:05 | Tóm tắt phiên chat hôm trước chưa có `day_summary_done` (20 mục 3.5) | `modules/chat/jobs.py` | V1.0 |
| `expire_pending_actions` | lịch | 5 phút | `tab_pending_action` quá `expires_at` thành `expired` | `modules/chat/jobs.py` | V1.0 |
| `check_silent_devices` | lịch | mỗi giờ | Thiết bị có `listener_connected` mà quá 24 giờ không có sự kiện: ghi cảnh báo vào trạng thái hệ thống, đặt `silent_warned_at` (30) | `modules/device/jobs.py` | V1.2 |
| `backup_database` | lịch | **chủ nhật 02:00** | `pg_dump` qua `age` lên `troly-backup`, giữ `BACKUP_KEEP = 5` bản (gồm bản trước migration), ghi `tab_job_run.detail` (QĐ-16) | `worker/jobs/backup.py` | V1.0 |
| `cleanup_old_data` | lịch | mỗi ngày 03:30 | Theo bảng `11-co-so-du-lieu.md` mục 3.15: xóa hộp tin, sự kiện thiết bị quá 180 ngày; thay nội dung khối `contains_third_party` quá 180 ngày; xóa tọa độ `tab_place_cache` quá 30 ngày; dọn tệp, phiên, hàng đợi | `worker/jobs/cleanup.py` | V1.0 |
| `disk_check` | lịch | 15 phút | Đo ổ trống; dưới `DISK_WARN_PERCENT` cảnh báo, dưới `DISK_STOP_PERCENT` tạm dừng `sync_gmail` và nhập tệp | `worker/jobs/disk.py` | V1.0 |
| `recover_stuck_items` | lịch | 5 phút | Trả về `pending` các dòng hàng đợi kẹt ở `processing` quá 10 phút | `worker/jobs/queue.py` | V1.0 |

Sao lưu trước migration do `scripts/deploy.sh` chạy (cùng hàm của `backup_database`, tính vào 5 bản). Chi tiết thuật toán đồng bộ thuộc `40-tich-hop-google.md`; worker chỉ cung cấp khung.

**Tránh chạy trùng:**

| Lớp | Cách | Chặn |
|---|---|---|
| Khóa dòng hàng đợi | `SELECT ... FOR UPDATE SKIP LOCKED`, đặt `processing`, `locked_at`, `attempts + 1`, `commit` rồi mới xử lý | Hai worker lấy cùng dòng |
| Khóa job theo lịch | `pg_try_advisory_lock(<số cố định>)`; không lấy được thì bỏ lượt | Chạy chồng một job |
| Khóa theo tài khoản Google | `pg_try_advisory_xact_lock` theo `google_account_id` khi đồng bộ | Đồng bộ định kỳ và do webhook chạy cùng lúc |
| Khóa làm mới token Google | `pg_advisory_xact_lock` theo `google_account_id` khi làm mới access token (40 mục 3.4) | `api` và `worker` cùng làm mới |

Số khóa cố định khai trong `core/scheduler.py`.

**Thử lại, hai mức** (thống nhất A6 dòng 77):

| Mức | Áp cho | Luật |
|---|---|---|
| Trong một lời gọi | Google 429, 5xx, `rateLimitExceeded`, hết giờ | Chờ `2^n` giây cộng ngẫu nhiên tối đa 1 giây, trần 64 giây, tối đa 5 lần (theo 40 mục 10) |
| Dòng hàng đợi | `tab_device_event`, `tab_job_queue`, `tab_google_outbox` khi lời gọi vẫn hỏng | `next_attempt_at = now() + 30 giây × 2^(attempts-1)`; `tab_google_outbox` tối đa 5 lần, hai bảng kia tối đa 6; quá thì `failed` |

Lỗi vĩnh viễn (dữ liệu hỏng, `invalid_grant`, 403 thiếu quyền) thì `failed` ngay. Mọi job **idempotent** nhờ khóa duy nhất (`source_ref`, `google_event_id`, `client_event_id`).

### 3.10 Ghi log

- JSON một dòng ra stdout; Docker `json-file` 3 tệp x 10 MB.
- Trường: `ts`, `level`, `logger`, `msg`, `request_id`, `user_id`, `device_id`, `method`, `path`, `status`, `duration_ms`, `job`, `run_id`.
- Middleware gắn `request_id` (nhận `X-Request-ID` nếu có), trả lại ở phản hồi. Mỗi yêu cầu một dòng truy cập.
- **Không ghi**: mật khẩu, JWT, mã làm mới, mã thiết bị, mã CI, token Google, khóa API, URL ký sẵn, tiêu đề `Authorization`, nội dung tin nhắn, thông báo, chat, thư, hồ sơ lõi.
- Bộ lọc cuối trong `core/logging.py`: che giá trị của khóa có tên `password`, `token`, `secret`, `authorization`, `text`, `content`, `payload`, `body`; che mọi chuỗi giống token (base64 dài trên 24 ký tự) và mọi dãy từ 9 chữ số trở lên (`60-bao-mat-rieng-tu.md` mục 3.13). Lỗi chưa bắt in vết ngăn xếp, không in biến cục bộ.
- Sự kiện bảo mật ghi thêm `tab_audit_log` (danh sách ở `11-co-so-du-lieu.md` mục 3.4).

### 3.11 Múi giờ

- DB lưu `timestamptz` UTC; session DB `timezone = 'UTC'`; container `TZ=UTC`.
- Mỗi người có `tab_user.timezone`. *Hôm nay*, *tuần này* (từ thứ Hai), *tháng này* của chi tiêu, lịch, báo cáo tính từ **00:00** giờ người dùng bằng `zoneinfo`.
- **Riêng phiên chat tách lúc 04:00** (QĐ-20): `local_date = date(giờ địa phương - 4 giờ)`; hàm `core.clock.chat_day(user_tz, at)` dùng chung cho `chat` và `ai`.
- API nhận ISO 8601 có độ lệch, thiếu thì 400; trả theo múi giờ người dùng. Ngoại lệ: `fire_at` của nhắc trả UTC.
- Ngày không giờ dùng `date`.
- Giờ hiện tại đi qua `core.clock.now()` để bài kiểm đóng băng được.
- Lời nhắc hệ thống AI không chứa giờ hiện tại; giờ đi trong tin `role: system` riêng (ĐX-AI-01).

### 3.12 Tiền

- Số nguyên VND, `bigint`, hậu tố `_vnd`. Cấm `float`, `Decimal` cho VND.
- Khoản chi lưu số dương; chiều nằm ở `kind`. Tổng tính bằng SQL `sum`.
- Đọc số tiền (*45k*, *1tr2*, *1.200.000đ*, *200 cành*) làm ở `expense/service.py`, kiểm `0 < amount_vnd < 1.000.000.000`.
- Không lưu số dư; số tài khoản chỉ giữ 4 số cuối (QĐ-22). Che số tài khoản trước khi gửi Claude.
- Chi phí AI `numeric(12,6)`, hậu tố `_usd`.

### 3.13 Phân quyền nhiều người dùng

- **Hiện chỉ một người dùng** (QĐ-15); khung nhiều người dùng vẫn giữ đủ trong mã: tối đa `MAX_USERS = 4`, lọc `user_id`, bài kiểm chéo.
- Vai trò `owner` và `member`. Chủ không có API đọc dữ liệu nghiệp vụ của thành viên; quyền thêm chỉ là quản lý tài khoản, bản phát hành, trạng thái hệ thống, kiểm toán, chi phí AI toàn hệ thống (chỉ số tiền theo người).
- Mọi bảng nghiệp vụ có `user_id`, kể cả bảng con (ĐX-KT-03). Bảng hệ thống liệt kê ở `11-co-so-du-lieu.md` mục 3.1.
- Mọi hàm repo nhận `user_id` làm tham số thứ hai; không có hàm tra theo id mà không có `user_id`.
- **RLS** bật trước khi có người dùng thứ hai dùng hộp tin (`11-co-so-du-lieu.md` mục 3.17); điểm gắn `SET LOCAL app.user_id` có từ V1.0 (mục 3.3).
- Thành viên phải đồng ý bản thông báo xử lý dữ liệu (`tab_consent`) trước khi bật nghe thông báo.

### 3.14 Khởi động và các lớp giữa

`app/main.py` theo thứ tự:

1. Đọc cấu hình, dựng logging.
2. Tạo FastAPI; `docs_url` chỉ bật khi `ENV != prod`.
3. Lớp giữa, theo thứ tự ngoài vào trong: `request_id` và log truy cập; lấy IP từ `CF-Connecting-IP`; CORS theo `CORS_ORIGINS`; giới hạn thân (1 MB, `/device/events` 256 KB); giới hạn tần suất theo bảng `12-api.md` mục 3.7 (thùng token trong bộ nhớ); kiểm `X-App-Version` (426 khi quá cũ, trừ `/device/release`, `/device/web-bundle`, `/auth/*`).
4. Bộ xử lý lỗi toàn cục.
5. Gắn router mọi module dưới `/api/v1`; `/api/health` không phiên bản; `/dev/jobs/*` chỉ gắn khi `DEV_JOBS_ENABLED=true`.
6. `register_tools` cho từng module, kiểm mỗi công cụ có `handler` và công cụ `needs_approval` có `execute_approved`.

Migration không chạy lúc `api` khởi động; script deploy chạy sao lưu rồi `docker compose --profile migrate run --rm migrate` trước khi đổi ảnh `api`, `worker` (ĐX-KT-08, khớp dịch vụ `migrate` của 50). Migration phải tương thích ngược với bản trước (`11-co-so-du-lieu.md` mục 3.18).

### 3.15 Gọi dịch vụ ngoài và bí mật lưu trong DB

- Mọi lời gọi ra ngoài đi qua `integrations/` hoặc `ai/client.py`, có thời hạn: Google và R2 10 giây; Claude 60 giây cho lượt không stream (SDK tự thử lại 2 lần).
- Lỗi mạng, 5xx, 429 đổi thành `ExternalServiceError` (hoặc `AI_UNAVAILABLE`).
- Token Google mã hóa Fernet trong `core/security.py` với vòng khóa `TOKEN_ENCRYPTION_KEYS` và cột `key_version`. **Bản rõ là JSON `{user_id, provider, token}`**; giải mã xong kiểm `user_id`, `provider` khớp dòng đang đọc, lệch thì coi như lỗi và ghi kiểm toán (`60-bao-mat-rieng-tu.md` mục 3.5). Chỉ `integrations/google/oauth.py` gọi hàm giải mã.
- Làm mới access token khi còn dưới 5 phút, giữ khóa tư vấn theo tài khoản (mục 3.9).
- URL ký sẵn R2 sống `R2_PRESIGN_SECONDS`; ký chỉ sau khi kiểm `tab_file` thuộc người gọi; khóa đối tượng có tiền tố `u/<user_id>/`.

### 3.16 Chi phí AI

- Mọi lần gọi Claude đi qua `ai.client.create_message` và ghi `tab_ai_run` (bộ cột ở `11-co-so-du-lieu.md` mục 3.8; công thức giá ở `20-bo-nao-ai.md` mục 3.10).
- **Không có trần theo ngày** (QĐ-15). Tổng tháng toàn hệ thống vượt `AI_MONTHLY_USD` thì: `/chat/status` trả `over_monthly_warning = true`, trạng thái hệ thống của chủ hiện dải cảnh báo; **không chặn**.
- Chặn sự cố bằng giới hạn không theo tiền: `AI_MAX_TOOL_ROUNDS`, `AI_USER_HOURLY_TURNS`, `RATE_CHAT_PER_MIN`, giới hạn sự kiện thiết bị (chặn app rác làm `bank_extract` chạy liên tục).
- Khi thêm người dùng thứ hai trở đi, đặt trần riêng cho họ (QĐ-15) bằng khóa cài đặt mới và mã lỗi `AI_BUDGET_EXCEEDED`; chưa làm ở V1.

### 3.17 Lệnh quản trị trong container

Một điểm vào `python -m app.cli <lệnh>`, tên lệnh gạch ngang (A4 dòng 57). Chạy bằng `docker compose run --rm api python -m app.cli <lệnh>`.

| Lệnh | Việc | Nguồn |
|---|---|---|
| `create-owner --email <e> --name <n>` | Tạo tài khoản chủ đầu tiên, in mật khẩu tạm một lần | 50, 60 |
| `revoke-device <device_id>` | Thu hồi thiết bị khi mất máy | 60 |
| `unlock-user <email>` | Bỏ khóa đăng nhập sai | 60 |
| `reencrypt-tokens` | Mã hóa lại token Google bằng khóa đầu vòng, sau khi thêm khóa mới | 60 |
| `export-openapi --out testdata/contracts/` | Xuất lược đồ `/device/events`, `/device/release`, `/device/web-bundle` cho bài kiểm Kotlin | 70 |

Mọi lệnh ghi `tab_audit_log`.

## 4. Dữ liệu cần

Bảng hạ tầng do tệp này dùng (mô tả ở [11-co-so-du-lieu.md](11-co-so-du-lieu.md)): `tab_user`, `tab_auth_session`, `tab_device`, `tab_device_event`, `tab_job_queue`, `tab_job_schedule`, `tab_job_run`, `tab_google_outbox`, `tab_audit_log`, `tab_consent`, `tab_ai_run`.

## 5. API hoặc giao tiếp

- HTTP: [12-api.md](12-api.md).
- Giữa module: hàm công khai trong `service.py` (mục 3.4).
- `api` với `worker`: bảng hàng đợi và `NOTIFY troly_wake`; không gọi HTTP nội bộ.
- Với bộ não AI: `chat.service` gọi `ai.loop.run_turn(session_factory, ctx: UserContext, text, attachments, client_message_id, think_harder)`, trả bộ sinh sự kiện SSE; `ai` gọi công cụ đã đăng ký; công cụ gọi service. Chi tiết vòng ở `20-bo-nao-ai.md` mục 3.6.

## 6. Kiểm thử

**DB kiểm thử** theo `70-kiem-thu.md` mục 3.2 (A4 dòng 54): tệp `infra/docker-compose.test.yml` đứng riêng, dịch vụ `db-test` (`postgres:16-alpine`, DB `troly_test` trên tmpfs, không mở cổng) và `test` (ảnh `troly-backend:dev`). Không dùng DB của bộ dev. Cùng một lệnh ở máy cá nhân và GitHub Actions.

Điều mã backend phải hỗ trợ cho bài kiểm:

- `TEST_DATABASE_URL`; bộ kiểm từ chối chạy nếu tên DB không kết thúc `_test`.
- `core/db.py` cho phép gắn session vào một giao dịch ngoài và `SAVEPOINT`, để mỗi bài kiểm `ROLLBACK` cuối bài; bài cần `commit` thật đánh dấu `@pytest.mark.commits`.
- `core.clock` thay được để đóng băng giờ.
- Bảng ánh xạ trường mã trong thân yêu cầu cho bài kiểm chéo người dùng: `backend/tests/cross_user_fields.py` (70 mục 3.3).
- `app.cli export-openapi` cho hợp đồng thiết bị.

| Bài kiểm | Canh gì |
|---|---|
| `test_cross_user.py` | Mọi endpoint và công cụ AI dưới người A không chạm dữ liệu người B |
| `test_module_imports.py` | Luật import mục 3.4 |
| `test_envelope.py` | Phong bì, 400 thay 422, 500 không lộ vết |
| `test_auth.py` | Khóa sau 5 lần sai; xoay mã làm mới; dùng lại mã cũ thu hồi phiên; `must_change_password`; mỗi loại mã chỉ gọi đúng nhóm; mã CI so thời gian hằng |
| `test_worker.py` | `SKIP LOCKED` không trùng dòng; khóa job; thử lại hai mức; dòng kẹt được trả về; job lỡ giờ chạy bù |
| `test_clock.py` | Ranh giới 00:00 cho chi tiêu; ranh giới 04:00 cho phiên chat |
| `test_config.py` | Thiếu biến bắt buộc thì dừng với câu rõ; `.env.example` có đủ và chỉ có các biến ở mục 3.6 |
| `test_logging_privacy.py` | Bộ lọc che khóa nhạy cảm, chuỗi giống token, dãy 9 chữ số |
| `test_tool_registry.py` | Mọi công cụ có `handler` đồng bộ; công cụ cần duyệt có `execute_approved`; không lược đồ nào có `user_id` |
| `test_rate_limit.py` | Theo bảng `12-api.md` mục 3.7 |

## 7. Rủi ro

| Rủi ro | Ảnh hưởng | Cách giảm |
|---|---|---|
| Quên lọc `user_id` | Lộ dữ liệu chéo | Chữ ký hàm bắt buộc; bài kiểm tự quét; RLS trước người dùng thứ hai |
| Không có trần AI theo ngày (QĐ-15) | Sự cố vòng lặp đốt tiền | Giới hạn vòng, giới hạn lượt mỗi giờ, giới hạn sự kiện; cảnh báo tháng; đề nghị người dùng đặt hạn mức chi trên trang Anthropic làm chặn cứng cuối |
| Thu hồi phiên trễ 30 phút | Máy mất vẫn gọi được API 30 phút | Đổi `JWT_SECRET` khi cần cắt ngay |
| Worker chết | Chi tiêu, hộp tin không cập nhật | `/api/health` báo trễ quá 5 phút; trạng thái hệ thống của chủ |
| Một tiến trình uvicorn | Chat stream giữ luồng threadpool | Một người dùng; threadpool 40 luồng là dư |
| Bộ đếm giới hạn trong bộ nhớ | Mất khi khởi động lại | Chấp nhận; khóa đăng nhập ở DB |
| Mất `TOKEN_ENCRYPTION_KEYS` | Phải kết nối lại Google | Bản cất trong trình quản lý mật khẩu |
| Gắn mã từ ổ Windows, `--reload` không thấy tệp đổi | Phát triển chậm | `WATCHFILES_FORCE_POLLING=true`; phương án để kho trong WSL2 |
| Ảnh `api` và `worker` lệch bản | Hai bản mã chạy cùng lúc | Một ảnh, gắn thẻ theo commit; deploy đổi cả hai cùng lúc |

## 8. Câu hỏi mở

1. Mã làm mới 60 ngày, mã truy cập 30 phút có hợp với thói quen mở app bằng vân tay không (rà chéo B câu 3)? Đề xuất giữ 60 ngày.
2. Có cần đăng nhập bằng Google thay mật khẩu (rà chéo B câu 4)? Đề xuất không.

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| điều phối | `02-cau-truc-ma-nguon.md`: thêm `core/models.py`, `core/clock.py`, `app/cli.py`, `ai/models.py`, `integrations/google/models.py`, `jobs.py` trong khuôn module, `worker/jobs/{device_events,queue,google_outbox,backup,cleanup,disk}.py`, `backend/tests/cross_user_fields.py` (A4 dòng 56) |
| agent AI | `20-bo-nao-ai.md`: `ToolSpec.handler` là `def` đồng bộ; `ai/registry.py` chỉ có `register_tools`, không import `tools.py` của module; tên hàm `run_turn`; bỏ `check_budget` theo ngày và bảng trần `AI_USER_DAILY_USD`, `AI_DAILY_USD`, ngưỡng 0,20 USD của `bank_extract` (QĐ-15), giữ `AI_MONTHLY_USD` chỉ cảnh báo; tên biến `AI_EFFORT_CHAT`; job tóm tắt cuối ngày tên `summarize_previous_day` |
| agent Google | `40-tich-hop-google.md`: tên job theo bảng mục 3.9 (`push_google_outbox`, `sync_google_calendar`, `renew_google_watch`, `pull_google_tasks_status`, `sync_gmail`, `sync_google_contacts`, `cleanup_google_oauth_state`); mã hóa Fernet với `TOKEN_ENCRYPTION_KEYS` (bỏ `GOOGLE_TOKEN_KEY`, AES-GCM); biến `GOOGLE_REDIRECT_URI` có `/api/v1`; thử lại hai mức mục 3.9 |
| agent hạ tầng | `50-ha-tang-trien-khai.md` mục 3.7: `.env.example` theo đúng bảng mục 3.6 (bỏ `AI_USER_DAILY_USD`, `AI_DAILY_USD`, `AI_EFFORT_DEFAULT`, ba biến `BACKUP_KEEP_*`; thêm `BACKUP_WEEKDAY`, `BACKUP_KEEP`, `AI_EFFORT_CHAT`, `AI_COMPACT_TOKENS`, `AI_MAX_TOOL_ROUNDS`, `AI_USER_HOURLY_TURNS`, `THIRD_PARTY_CHAT_RETENTION_DAYS`, `CHAT_RETENTION_DAYS`, `RATE_REFRESH_PER_HOUR`, `RATE_DEVICE_PER_MIN`, `RATE_USER_PER_MIN`, `R2_ENDPOINT`; đổi `INBOX_RETENTION_DAYS`, `DEVICE_EVENT_RETENTION_DAYS` thành 180); mục 3.10 sao lưu hằng tuần giữ 5 bản (QĐ-16); lệnh tạo chủ là `python -m app.cli create-owner`. `60-bao-mat-rieng-tu.md`: lệnh `app.cli` theo mục 3.17; hạn giữ 180 ngày. `70-kiem-thu.md`: `test_retention.py` 180 ngày; `test_clock.py` mốc 04:00 |
| agent app Android | `30-app-android.md`: worker nền gọi `/calendar/reminders` bằng mã thiết bị (đã được phép); `heartbeat` gửi đủ 9 trường ở `12-api.md` |

## 10. Đề xuất quyết định

| Số | Đề xuất | Trạng thái |
|---|---|---|
| ĐX-KT-01 | Backend viết đồng bộ | Đã duyệt theo QĐ-25 |
| ĐX-KT-02 | `jobs.py` trong khuôn module cho job một module; job điều phối và hệ thống ở `worker/jobs/` | Đã duyệt theo QĐ-25 (bản làm rõ ở mục 3.2) |
| ĐX-KT-03 | Mọi bảng nghiệp vụ có `user_id`, kể cả bảng con | Đã duyệt theo QĐ-25 |
| ĐX-KT-04 | Dữ liệu người khác 404; lỗi đầu vào 400 | Đã duyệt theo QĐ-25 |
| ĐX-KT-05 | Worker thức bằng `LISTEN/NOTIFY`, giữ vòng quét 30 giây | Đã duyệt theo QĐ-25 |
| ĐX-KT-06 | Mã làm mới xoay vòng băm SHA-256; mã thiết bị băm SHA-256 | Đã duyệt theo QĐ-25 |
| ĐX-KT-07 | Hàng đợi việc dài chung `tab_job_queue` | Đã duyệt theo QĐ-25 |
| ĐX-KT-08 | Migration chạy ở bước deploy bằng dịch vụ `migrate`, sau sao lưu | Đã duyệt theo QĐ-25 |
| ĐX-KT-09 | Một ảnh cho `api`, `worker`, `migrate`, `test`; cấu hình chỉ từ biến môi trường; dịch vụ gọi nhau theo tên Docker | Đã duyệt theo QĐ-25 |
| ĐX-KT-10 | **Mới.** Năm loại danh tính tách nhóm đường: JWT, mã thiết bị, mã CI (`Authorization: CI`), mã máy chạy V3 (`Authorization: Runner`), token kênh Google | Mã CI chỉ đăng được bản phát hành; lộ mã nào thì thiệt hại gói trong nhóm đó |
| ĐX-KT-11 | **Mới.** Thử lại hai mức: trong lời gọi theo 40 (2^n giây, trần 64 giây, 5 lần), dòng hàng đợi theo giãn 30 giây × 2^n | Giữ được khuyến nghị của Google cho lời gọi, mà dòng hỏng lâu vẫn không chạy dồn |
| ĐX-KT-12 | **Mới.** Không trần AI theo ngày; chặn sự cố bằng giới hạn vòng, lượt, sự kiện; `AI_MONTHLY_USD` chỉ cảnh báo; đề nghị người dùng đặt hạn mức chi trên trang Anthropic | Cụ thể hóa QĐ-15 mà vẫn có chặn cứng cuối cùng nằm ngoài mã |
| ĐX-KT-13 | **Mới.** Một điểm vào lệnh quản trị `python -m app.cli`, tên lệnh gạch ngang | Một cách gọi cho 50, 60 (A4 dòng 57) |
