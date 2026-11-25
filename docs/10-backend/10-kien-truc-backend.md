# Kiến trúc backend

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 3, gọn theo QĐ-27, sửa theo `81-ra-cheo-lan-2.md` (QĐ-26) và các hợp đồng đã chốt ở `bang-viec.md` mục 4.

Tệp này là **nguồn chuẩn cho biến môi trường và danh sách job** (QĐ-25). Mạng, cổng, compose, phát hành APK theo `50-ha-tang-trien-khai.md`.

## 1. Mục tiêu

Chốt khuôn mã máy chủ, luật dùng chung, một danh sách biến môi trường và một danh sách job, đủ để dựng V1.0.

## 2. Phạm vi

Tiến trình `api` và `worker` trong `backend/`. Bảng ở [11-co-so-du-lieu.md](11-co-so-du-lieu.md); đường dẫn và giới hạn ở [12-api.md](12-api.md); lời nhắc, công cụ, giá ở `20-bo-nao-ai.md`; thuật toán đồng bộ Google ở `40-tich-hop-google.md`.

## 3. Thiết kế

### 3.1 Chạy trên Docker

Mọi thứ chạy trong Docker, cả máy cá nhân lẫn VPS (QĐ-14).

| Dịch vụ | Lệnh | Việc |
|---|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips "*"` (máy cá nhân thêm `--reload`) | HTTP |
| `worker` | `python -m worker.main` (máy cá nhân chạy dưới `watchfiles`) | Hàng đợi, đồng bộ, sao lưu, dọn |
| `migrate` | `alembic upgrade head` (profile `migrate`, chạy một lần) | Migration |
| `db` | `postgres:16-alpine` | DB |

- Một ảnh `troly-backend` cho `api`, `worker`, `migrate`, `test`; `backend/Dockerfile` ba đích `base` (`python:3.12-slim`, phụ thuộc theo tệp khóa, `postgresql-client-16`), `dev` (thêm pytest, ruff, watchfiles; mã gắn bằng volume), `prod` (chép mã, user không phải root).
- Dịch vụ gọi nhau theo tên Docker: `DATABASE_URL=postgresql+psycopg://troly:<mật khẩu>@db:5432/troly`.
- `api` ra máy ở `127.0.0.1:8200`; Vite ở máy cá nhân cổng 5190. Một tiến trình uvicorn (bộ đếm giới hạn nằm trong bộ nhớ). Container `TZ=UTC`, log ra stdout, dừng êm 30 giây.
- Viết **đồng bộ**: SQLAlchemy 2 với `psycopg` 3, router `def`, SDK `anthropic` và `httpx` đồng bộ.

| Việc | Lệnh |
|---|---|
| Chạy | `docker compose up -d --build` (máy cá nhân đặt `COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml`) |
| Migration | `docker compose --profile migrate run --rm migrate` |
| Bài kiểm một module | `docker compose -f infra/docker-compose.test.yml run --rm test pytest backend/app/modules/<x>` |
| Lệnh quản trị | `docker compose run --rm api python -m app.cli <lệnh>` (mục 3.15) |

### 3.2 Tầng lớp và khuôn công cụ

| Tệp trong module | Làm | Không làm |
|---|---|---|
| `models.py` | Bảng | Luật nghiệp vụ |
| `schemas.py` | Pydantic vào ra, câu lỗi tiếng Việt | Gọi DB |
| `repo.py` | Truy vấn; mọi hàm nhận `(session, user_id, ...)` và lọc theo `user_id` | Gọi ra ngoài, `commit` |
| `service.py` | Luật nghiệp vụ; gọi repo, integrations, service công khai của module khác | Đọc `Request`, `commit` |
| `router.py` | Kiểm đầu vào, gọi service, bọc phong bì | SQL |
| `tools.py` | `TOOLS: list[ToolSpec]` cho AI | Nhận `user_id` từ đầu vào model |
| `jobs.py` | Job chỉ chạm module này | Tự lặp, tự ngủ |

**Khuôn công cụ theo `20-bo-nao-ai.md` mục 3.2** (K16): `ToolSpec` có `name`, `label`, `description`, `input_model` (Pydantic, `strict: true`, không có `user_id`), `run(ctx: ToolContext, data) -> ToolOutput` (đồng bộ), `approval`, `prepare` và `execute` cho công cụ cần duyệt, `since`. `ToolContext` mang `session`, `user` (`UserContext(user_id, timezone)`), `conversation_id`, `now`. `chat.service` gọi `ai.loop.run_turn(ctx, system_parts, history, store, effort)`; `store` là `TurnStore` do `chat` cài để `ai` không đọc ghi bảng của `chat`.

Job một module nằm ở `modules/<x>/jobs.py`; job điều phối nhiều module hoặc việc hệ thống nằm ở `worker/jobs/`.

### 3.3 Giao dịch

- Một yêu cầu, một session, một giao dịch: `get_session` `commit` khi xong, `rollback` khi lỗi.
- Endpoint stream (chat) tự mở session ngắn cho từng bước: lưu tin người dùng, mỗi công cụ, lưu tin trả lời. Mất kết nối vẫn chạy nốt.
- Worker: mỗi đơn vị việc một giao dịch.
- Gọi Claude, Google ngoài giao dịch; hoặc ghi hàng chờ trong giao dịch rồi để worker gọi.

### 3.4 Luật module

1. Module chỉ import `app.modules.<x>.service` và `.schemas` của module khác.
2. Hàm service công khai không trả đối tượng ORM.
3. Khóa ngoại sang module khác khai bằng chuỗi.
4. Không có vòng phụ thuộc.
5. `core/`, `integrations/`, `ai/` không import `modules/`. Chỉ `app/main.py`, `worker/main.py` import mọi module (gắn router, gọi `ai.registry.register_tools`, gắn job theo `ENABLED_MODULES`).

| Module | Gọi service của |
|---|---|
| `setting`, `memory`, `expense`, `device`, `inbox`, `file`, `health` | `setting` |
| `calendar` | `setting`; `chat.create_pending_action` cho thẻ duyệt khi có khách mời |
| `task` | `calendar`, `setting` |
| `trip` | `calendar`, `file`, `setting` |
| `chat` | `memory`, `file`, `setting`; gọi `ai.loop` |
| `search` | `memory`, `chat`, `inbox`, `trip`, `file` (chỉ đọc) |
| `report` | `expense`, `task`, `calendar`, `inbox`, `file`, `setting`; gọi `ai.cost` |
| `notice` | `setting`; đọc `tab_expense`, `tab_inbox_message`, `tab_message`, `tab_file` bằng SQL cho `/device/notices` |
| `gym` | không module nào; gọi `integrations/gym/client.py` (cửa chỉ đọc của app gym, QĐ-54), thẻ `GET /reports/gym` |
| `zalo` | `inbox` (lưu tin qua `inbox/zalo.py`), `file`, `chat` (thẻ duyệt `send_zalo_message`); gọi `integrations/zalo_bridge/client.py` (QĐ-52, sau cờ `FEATURE_ZALO_BRIDGE`) |

Việc đã duyệt: module có `approvals.py` khai `EXECUTORS = {tool_name: hàm(session, user, input)}`; `chat.decide_action` tìm qua `app.registry.approval_executor` trước, không có mới dùng `execute` của công cụ AI, nên thẻ tạo từ API và từ chat chạy cùng một hàm. Đồng bộ Google ở `integrations/google/` không import modules: `calendar`, `task` cài `CalendarStore`, `TaskStore` (khai ở `integrations/google/stores.py`) trong `google_store.py` của mình, `app.registry.register_integrations()` đăng ký lúc api và worker khởi động; module ghi sang Google qua `google.outbox.enqueue` cùng giao dịch. Sự kiện thiết bị điều phối ở `worker/jobs/device_events.py`: theo `kind` và `app_package` gọi `expense`, `inbox`, `task`, `calendar`; `device` không phụ thuộc module nào.

### 3.5 Sự kiện nội bộ

Hàng chờ ghi cùng giao dịch (`tab_google_outbox`) khi cần gọi ra ngoài; `NOTIFY troly_wake` để đánh thức worker sớm hơn chu kỳ 30 giây (sự kiện thiết bị, webhook, việc nền mới). Mất tín hiệu vẫn có vòng quét.

### 3.6 Biến môi trường (danh sách duy nhất)

Cấu hình chỉ đọc từ biến môi trường của container (compose `env_file`), một lần qua `core/config.py` `get_settings()`; thiếu biến bắt buộc thì container dừng với câu rõ tên biến. `.env.example` ở gốc kho có **đúng và đủ** bảng này (`50-ha-tang-trien-khai.md` giữ nội dung tệp).

| Nhóm | Biến | Mặc định | Ghi chú |
|---|---|---|---|
| Chung | `ENV` | bắt buộc | `dev`, `test`, `prod` |
| | `TZ` | `UTC` | |
| | `APP_TIMEZONE` | `Asia/Ho_Chi_Minh` | |
| | `CORS_ORIGINS` | `https://localhost,http://localhost:5190` | |
| | `LOG_LEVEL` | `INFO` | |
| | `PUBLIC_BASE_URL` | bắt buộc | `https://assistant.baohuynh.io.vn`; máy cá nhân `http://localhost:8200` |
| | `API_BIND`, `API_PORT`, `TROLY_IMAGE_TAG` | `127.0.0.1`, `8200`, `latest` | Chỉ compose dùng |
| DB | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `troly`, `troly`, bắt buộc | |
| | `DATABASE_URL` | bắt buộc | Host `db` |
| | `TEST_DATABASE_URL` | khi test | Tên DB phải kết thúc `_test` |
| Đăng nhập | `JWT_SECRET` | bắt buộc | |
| | `JWT_ACCESS_MINUTES` | `30` | |
| | `JWT_REFRESH_DAYS` | `365` | QĐ-27 |
| Mã hóa | `TOKEN_ENCRYPTION_KEYS` | bắt buộc | Vòng khóa Fernet `v1:<khóa>,v2:<khóa>` |
| AI | `ANTHROPIC_API_KEY` | bắt buộc | |
| | `AI_MODEL_CHAT` | `claude-haiku-5-5` | Chat thường, ghi chép (QĐ-27 mục 9) |
| | `AI_MODEL_EXTRACT` | `claude-haiku-5-5` | Bóc tách, chép chữ từ ảnh |
| | `AI_MODEL_SMART` | `claude-sonnet-5-5` | Research có tìm web, đánh giá lịch trình, tóm tắt dài, *nghĩ kỹ* |
| | `AI_MODEL_MAX` | `claude-opus-5-5` | Khi người dùng nói rõ *dùng Opus* |
| | `AI_EFFORT_CHAT` | `low` | |
| | `AI_COMPACT_TOKENS` | `30000` | |
| | `AI_MAX_TOOL_ROUNDS` | `8` | |
| | `AI_USER_HOURLY_TURNS` | `60` | Chặn bấm liên tục, không phải trần tiền |
| | `AI_MONTHLY_USD` | `200` | Chỉ cảnh báo (QĐ-15) |
| | `AI_INBOX_MAX_ITEMS` | `200` | |
| R2 | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | bắt buộc | |
| | `R2_ENDPOINT` | dựng từ `R2_ACCOUNT_ID` | Máy cá nhân trỏ S3 giả |
| | `R2_BUCKET` | `assistant` | Một bucket, tiền tố `files/`, `backups/weekly/`, `backups/premigrate/`, `releases/` (QĐ-31) |
| | `R2_PRESIGN_SECONDS` | `300` | |
| | `R2_RELEASE_PRESIGN_SECONDS` | `1800` | Link tải APK của `/device/release`, `/tai-app/apk` (lỗi thật 25/11: 300 giây hết hạn trước khi người dùng bấm cập nhật) |
| Sao lưu | `BACKUP_WEEKDAY` | `6` (chủ nhật; 0 là thứ Hai) | QĐ-16 |
| | `BACKUP_HOUR`, `BACKUP_MINUTE` | `2`, `0` | Giờ Việt Nam |
| | `BACKUP_KEEP` | `5` | Gồm bản trước migration; không mã hóa `age` (QĐ-27) |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | từ V1.4 | |
| | `GOOGLE_REDIRECT_URI` | từ V1.4 | `https://assistant.baohuynh.io.vn/api/v1/google/oauth/callback` |
| | `GOOGLE_MAPS_API_KEY` | từ V1.6 | |
| | `GOOGLE_SYNC_MIN_SECONDS` | `300` | |
| App gym (QĐ-54) | `GYM_BASE_URL`, `GYM_API_KEY`, `GYM_USERNAME` | khi nối app gym | Khóa gửi ở header `X-Integration-Key`; thiếu một biến thì thẻ Tập luyện `disabled` (*Chưa nối app gym*). Đệm 5 phút, timeout 10 giây |
| Cờ tính năng (luật điều phối 25/11) | `FEATURE_GYM`, `FEATURE_CONNECTORS`, `FEATURE_ZALO_BRIDGE` | `false` | Tắt thì `router`, `tools`, `approvals`, job của module hoặc tích hợp đó không đăng ký (`registry.FEATURE_FLAGS`); `models` và migration luôn nạp. App đọc `features` ở `GET /system/status`. Bài kiểm bật cả ba (`conftest.py`) |
| Zalo (QĐ-52) | `ZALO_BRIDGE_URL` (mặc định `http://zalo-bridge:3000`), `ZALO_BRIDGE_TOKEN` | khi bật Zalo | Khóa nội bộ hai chiều với `zalo-bridge` (50 mục 3.15); trống thì api từ chối sự kiện và báo dịch vụ Zalo tắt |
| Worker | `WORKER_POLL_SECONDS` | `30` | |
| | `WORKER_BATCH_SIZE` | `200` | |
| Thời hạn | `INBOX_RETENTION_DAYS`, `DEVICE_EVENT_RETENTION_DAYS`, `THIRD_PARTY_CHAT_RETENTION_DAYS` | `180` | QĐ-17 |
| | `CHAT_RETENTION_DAYS` | `365` | QĐ-26 |
| Ổ đĩa | `DISK_WARN_PERCENT`, `DISK_STOP_PERCENT` | `15`, `8` | |
| Giới hạn | `RATE_LOGIN_PER_15MIN`, `RATE_DEVICE_EVENTS_PER_MIN`, `RATE_CHAT_PER_MIN`, `RATE_USER_PER_MIN` | `10`, `120`, `20`, `300` | `12-api.md` mục 3.7 |

Bỏ so với bản 2: `MAX_USERS`, `BCRYPT_ROUNDS`, `LOGIN_MAX_FAILS`, `LOGIN_LOCK_MINUTES`, `BACKUP_AGE_RECIPIENT`, `RELEASE_PUBLISH_TOKEN_HASH`, `RATE_REFRESH_PER_HOUR`, `RATE_DEVICE_PER_MIN`, `RATE_DEVICE_EVENTS_PER_DAY`, `DEV_*`, `AUDIT_LOG_RETENTION_DAYS`.

### 3.7 Đăng nhập

| Ai gọi | Tiêu đề | Gọi được |
|---|---|---|
| Giao diện | `Authorization: Bearer <JWT>` | API của app |
| Plugin | `Authorization: Device <mã>` | `/device/*`, `/calendar/reminders` |
| Google | `X-Goog-Channel-Token` | `/webhooks/google/calendar` |

- **Một tài khoản** (QĐ-27): tạo bằng `app.cli create-owner`, mật khẩu băm bcrypt. Không vai trò, không khóa khi sai mật khẩu; chỉ giới hạn 10 lần đăng nhập mỗi 15 phút mỗi IP.
- **Đăng nhập một lần**: mã truy cập JWT HS256 30 phút (`sub`, `sid`, `iat`, `exp`); mã làm mới 32 byte, **365 ngày**, băm SHA-256 trong `tab_auth_session`, xoay vòng mỗi lần làm mới. Đổi mật khẩu thu hồi phiên khác; cắt mọi phiên ngay bằng đổi `JWT_SECRET`.
- **Mã thiết bị**: `POST /devices` sinh `dev_<base64url 32 byte>`, trả một lần, lưu SHA-256; thu hồi bằng `revoked_at` thì 401 `DEVICE_REVOKED`.
- Dependency: `get_current_user` (`UserContext`), `get_current_device` (`DeviceContext`), `get_device_or_user`, `verify_google_channel`. `user_id` chỉ lấy từ JWT hoặc mã thiết bị.

### 3.8 Phong bì và lỗi

Mọi API JSON trả `{success, message, data}`; lỗi có `data = {code, fields}`. Lớp lỗi ở `core/errors.py`: `ValidationError` 400 (lỗi Pydantic cũng 400), `UnauthorizedError` 401, `NotFoundError` 404 (cả dữ liệu không thuộc người gọi), `ConflictError` 409, `RateLimitError` 429, `ExternalServiceError` 502; lỗi chưa bắt 500 kèm `request_id`, không lộ vết. Mã lỗi ở `12-api.md` mục 3.5.

### 3.9 Worker và danh sách job (danh sách duy nhất)

Vòng chạy: chờ `troly_wake` hoặc `WORKER_POLL_SECONDS`; chạy job hàng đợi (mỗi job một lô rồi nhường); chạy job theo lịch tới giờ (`tab_job_schedule`); job lỡ giờ chạy bù khi khởi động; `SIGTERM` làm nốt đơn vị việc rồi thoát.

| Job | Lịch (giờ Việt Nam) | Việc | Chỗ đặt | Bản |
|---|---|---|---|---|
| `process_device_events` | mỗi vòng, lô 200 | `notification` sang expense (kể cả ghép cặp chuyển nội bộ) hoặc inbox; `reminder_action` `done` đánh dấu việc xong | `worker/jobs/device_events.py` | V1.2 |
| `run_queued_jobs` | mỗi vòng, lô 5 | `tab_job_queue`: `trip_import`, `trip_evaluate`, `trip_geocode` (tọa độ OpenStreetMap, khóa trùng `trip_geocode:<id>`), `google_initial_sync` | `worker/jobs/queue.py` | V1.4 |
| `extract_file_text` | mỗi vòng, lô 5 | Tệp `extract_status = pending`: trích chữ vào `tab_file_text` (`11-co-so-du-lieu.md` mục 3.8) | `modules/file/jobs.py` | V1.1 |
| `push_google_outbox` | mỗi vòng, lô 20 | Ghi lên Calendar, Tasks, Gmail, Drive, Sheets | `integrations/google/jobs.py` | V1.4 |
| `sync_google_calendar` | mỗi vòng xét `needs_sync` (webhook, gộp 10 giây) hoặc `next_sync_at` (15 phút ±25%) | Kéo thay đổi bằng `syncToken` | `integrations/google/jobs.py` | V1.4 |
| `renew_google_watch` | 03:00 hằng ngày | Gia hạn kênh còn dưới 48 giờ | `integrations/google/jobs.py` | V1.4 |
| `pull_google_tasks_status` | mỗi vòng xét `next_sync_at` (15 phút ±25%) | Đọc ngược xong, đã xóa (QĐ-21) | `integrations/google/jobs.py` | V1.4 |
| `sync_gmail` | 5 phút | `history.list` vào hộp tin | `integrations/google/jobs.py` (khóa 7006) | V1.8 |
| `fetch_zalo_media` | mỗi vòng, lô 10 (khóa 7009, chỉ khi `FEATURE_ZALO_BRIDGE`) | Ảnh, video, tệp của tin Zalo về R2 qua `POST /media/fetch` của bridge (link CDN Zalo hết hạn sau vài giờ); lỗi thử 3 lần rồi `failed` | `modules/zalo/jobs.py` | QĐ-52 |
| `sync_google_contacts` | 04:00 hằng ngày | Danh bạ | `modules/inbox/jobs.py` | V1.8 |
| `summarize_idle_conversations` | mỗi giờ (khóa 7101) | Phiên ngủ quá 6 giờ hoặc có quá 80 tin chưa tóm thì tóm phần đầu, giữ nguyên đuôi (`compaction.choose_cut`) (QĐ-51, thay `summarize_previous_day`) | `modules/chat/jobs.py` | V1.0 |
| `expire_pending_actions` | 5 phút | `pending` quá hạn thành `expired` | `modules/chat/jobs.py` | V1.0 |
| `check_silent_devices` | mỗi giờ | Thiết bị `listener_connected` mà 24 giờ không có sự kiện: cảnh báo ở `/system/status` | `modules/device/jobs.py` | V1.2 |
| `backup_database` | chủ nhật 02:00 | `pg_dump` lên `backups/weekly/`; giữ 5 bản cả bản `premigrate`, xóa bản không phải weekly trước, luôn còn 1 bản weekly; ghi `tab_job_run.detail` | `worker/jobs/backup.py` | V1.0 |
| `cleanup_old_data` | 03:30 hằng ngày | Theo `11-co-so-du-lieu.md` mục 3.15, gồm cả đặt rỗng tọa độ Google quá 30 ngày ở `tab_place_cache` và `tab_trip_stop` (K19); phiên chat không có tin nào quá 1 ngày (phản hồi 1.1.1) | `worker/jobs/cleanup.py` | V1.0 |
| `disk_check` | 15 phút | Dưới 15% cảnh báo; dưới 8% tạm dừng `sync_gmail`, `extract_file_text` | `worker/jobs/disk.py` | V1.0 |
| `recover_stuck_items` | 5 phút | Dòng kẹt ở `processing` quá 10 phút trả về `pending` | `worker/jobs/queue.py` | V1.0 |

Sao lưu trước migration do `scripts/deploy.sh` gọi cùng hàm, tính vào 5 bản.

**Tránh chạy trùng:** hàng đợi `SELECT ... FOR UPDATE SKIP LOCKED`; job theo lịch `pg_try_advisory_lock` với số cố định ở `core/scheduler.py`; đồng bộ và làm mới token Google giữ `pg_advisory_xact_lock` theo `google_account_id`.

**Thử lại hai mức:** trong một lời gọi Google gặp 429, 5xx, hết giờ thì chờ `2^n` giây cộng ngẫu nhiên tối đa 1 giây, trần 64 giây, tối đa 5 lần; dòng hàng đợi còn hỏng thì `next_attempt_at = now() + 30 giây × 2^(attempts-1)`, `tab_google_outbox` tối đa 5 lần, hàng đợi khác 6 lần, quá thì `failed`. Lỗi vĩnh viễn (`invalid_grant`, thiếu quyền, dữ liệu hỏng) thì `failed` ngay. Mọi job idempotent nhờ khóa duy nhất.

### 3.10 Ghi log

JSON một dòng ra stdout (`ts`, `level`, `msg`, `request_id`, `user_id`, `device_id`, `path`, `status`, `duration_ms`, `job`). Không ghi mật khẩu, mã, token, URL ký sẵn, tiêu đề `Authorization`, nội dung tin nhắn, thông báo, chat, thư, hồ sơ lõi; bộ lọc ở `core/logging.py` che khóa nhạy cảm, chuỗi giống token và dãy từ 9 chữ số.

### 3.11 Thời gian và tiền

- `timestamptz` UTC; mỗi người có `timezone`. Ngày của chi tiêu, lịch, báo cáo tính từ 00:00 giờ người dùng; phiên chat không còn tách theo ngày (QĐ-51, `11-co-so-du-lieu.md` mục 3.7); `core.clock.chat_day` chỉ còn để ghi ngày mở phiên. Giờ hiện tại qua `core.clock.now()`.
- Tiền là số nguyên VND `bigint`; không `float`. Không lưu số dư, chỉ 4 số cuối tài khoản (QĐ-22).

### 3.12 Một người dùng

Hiện chỉ một tài khoản (QĐ-27). Vẫn giữ `user_id` ở mọi bảng và mọi hàm repo để thêm người sau không phải sửa cấu trúc. Không có vai trò, màn đồng ý, nhật ký kiểm toán, xuất và xóa tài khoản, RLS.

### 3.13 Khởi động và lớp giữa

`app/main.py`: đọc cấu hình, dựng logging; lớp giữa `request_id`, IP từ `CF-Connecting-IP`, CORS, giới hạn thân (1 MB, `/device/events` 256 KB), giới hạn tần suất theo `12-api.md` mục 3.7, kiểm `X-App-Version` (426); bộ xử lý lỗi; gắn router dưới `/api/v1`, `/api/health`, hai trang tĩnh `/chinh-sach-rieng-tu`, `/tai-app` (`12-api.md` mục 5.10); đăng ký công cụ AI. Migration không chạy lúc khởi động.

### 3.14 Dịch vụ ngoài và bí mật

- Gọi ra ngoài qua `integrations/` hoặc `ai/client.py`; thời hạn 10 giây cho Google, R2; 60 giây cho Claude không stream.
- Token Google mã hóa Fernet (`TOKEN_ENCRYPTION_KEYS`, cột `key_version`), bản rõ `{user_id, provider, token}`, kiểm khớp khi giải mã; chỉ `integrations/google/oauth.py` giải mã.
- URL ký sẵn R2 sống `R2_PRESIGN_SECONDS`; khóa đối tượng có tiền tố `u/<user_id>/`.
- AI: mã chọn model theo loại việc (`AI_MODEL_CHAT`, `AI_MODEL_SMART`, `AI_MODEL_MAX`), ghi `model` vào tin trả lời; research dùng công cụ tìm web có sẵn của Claude API, số lần tìm ghi `tab_ai_run.web_search_requests`. Không trần ngày; tổng tháng vượt `AI_MONTHLY_USD` chỉ cảnh báo. Chặn sự cố bằng `AI_MAX_TOOL_ROUNDS` và giới hạn tần suất; nên đặt hạn mức chi trên trang Anthropic làm chặn cứng cuối.
- Tìm tài liệu: toàn văn PostgreSQL, không RAG ở V1 (QĐ-27 mục 11), qua module `search` dùng chung cho `GET /search` và công cụ `search_everything`; chữ tệp ở `tab_file_text` do job `extract_file_text` ghi.

### 3.15 Lệnh quản trị

`python -m app.cli <lệnh>`: `create-owner --email <e> --name <n>` (hỏi mật khẩu), `revoke-device <device_id>`, `reencrypt-tokens` (sau khi thêm khóa Fernet mới).

## 4. Dữ liệu cần

Bảng hạ tầng ở `11-co-so-du-lieu.md`: `tab_user`, `tab_auth_session`, `tab_device`, `tab_device_event`, `tab_job_queue`, `tab_job_schedule`, `tab_job_run`, `tab_google_outbox`, `tab_ai_run`.

## 5. API hoặc giao tiếp

HTTP theo [12-api.md](12-api.md). Giữa module qua `service.py`. `api` và `worker` qua bảng hàng đợi và `NOTIFY troly_wake`. Với AI qua `run_turn` (mục 3.2).

## 6. Kiểm thử

Chỉ phần dễ sai (QĐ-27 mục 8), chạy trên `db-test` (PostgreSQL 16, tmpfs) của `infra/docker-compose.test.yml`; session gắn được vào giao dịch ngoài để `ROLLBACK` sau mỗi bài. Phần của tệp này: hàng đợi `SKIP LOCKED` không trùng dòng và thử lại đúng hai mức; mốc 00:00, 04:00 và nối phiên dưới 3 giờ; bộ lọc log che nội dung nhạy cảm; `.env.example` khớp bảng mục 3.6.

## 7. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Không có trần AI theo ngày | Giới hạn vòng công cụ, giới hạn tần suất, cảnh báo tháng, hạn mức chi trên trang Anthropic |
| Mã làm mới 365 ngày, máy mất thì người khác dùng được lâu | Thu hồi phiên và thiết bị từ máy khác; cắt hết bằng đổi `JWT_SECRET` |
| Worker chết | `/api/health` báo trễ quá 5 phút; `/system/status` |
| Gắn mã từ ổ Windows, `--reload` không thấy tệp đổi | `WATCHFILES_FORCE_POLLING=true` |

## 8. Cần agent khác

| Agent | Việc |
|---|---|
| điều phối | `02`: thêm `modules/search/`, `worker/jobs/{device_events,queue,backup,cleanup,disk}.py`, `app/cli.py`, `core/clock.py`, `ai/models.py` |
| agent AI | 20: `UserContext` không còn `role`; tên job `summarize_previous_day` |
| agent Google | 40: tên job theo mục 3.9; thử lại hai mức mục 3.9; `GOOGLE_REDIRECT_URI` |
| agent hạ tầng | 50: `.env.example` đúng bảng mục 3.6; bỏ `age`, mã CI. 60: bỏ phần đã gọn theo QĐ-27 |
