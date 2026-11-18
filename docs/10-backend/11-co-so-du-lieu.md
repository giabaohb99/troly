# Cơ sở dữ liệu

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 2, đã gộp mục *Dữ liệu cần* của mọi tài liệu theo `80-ra-cheo-lan-1.md` (mục A1, D2) và áp QĐ-15 tới QĐ-25.

Theo QĐ-25, tệp này là **nguồn chuẩn cho tên bảng và tên cột**. Tài liệu khác lệch với tệp này thì sửa theo tệp này.

Tài liệu liên quan: [10-kien-truc-backend.md](10-kien-truc-backend.md), [12-api.md](12-api.md), [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md), [30-app-android.md](../30-app/30-app-android.md), [40-tich-hop-google.md](../40-google/40-tich-hop-google.md), [41-ban-do-lich-trinh.md](../40-google/41-ban-do-lich-trinh.md), [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md).

## 1. Mục tiêu

- Một chỗ duy nhất mô tả **toàn bộ bảng** của mọi module: cột, kiểu, ràng buộc, chỉ mục, quan hệ.
- Chốt chính sách xóa và thời hạn giữ dữ liệu cho từng bảng.
- Chốt quy ước migration Alembic để nhiều agent thêm bảng không giẫm chân nhau.

## 2. Phạm vi

Toàn bộ bảng PostgreSQL 16 cho V1.0 tới V1.8, kèm phác thảo bảng V2, V3. Không gồm dữ liệu trên điện thoại (bảng Room ở `30-app-android.md` mục 4.2) và tệp trên R2 (`50-ha-tang-trien-khai.md`).

## 3. Thiết kế

### 3.1 Quy ước chung

| Mục | Quy ước |
|---|---|
| Tên bảng | Tiền tố `tab_`, số ít, snake_case |
| Khóa chính | `id bigint generated always as identity`. Id do máy khách sinh (chống gửi trùng) là `uuid`, đặt ở cột riêng như `client_event_id` |
| Cột chung | Mọi bảng nghiệp vụ có `user_id bigint NN FK tab_user ON DELETE CASCADE`, `created_at timestamptz NN default now()`, `updated_at timestamptz NN default now()`. Trong bảng dưới, dòng **(cột chung)** nghĩa là có đủ `id`, `user_id`, `created_at`, `updated_at` |
| Bảng con | Cũng có `user_id` (ĐX-KT-03, đã duyệt theo QĐ-25). Không có ngoại lệ *nối qua bảng cha* |
| `updated_at` | SQLAlchemy đặt `onupdate`; không dùng trigger |
| Thời gian | `timestamptz`, lưu UTC. Ngày không giờ dùng `date`. Giờ trong ngày không gắn ngày dùng `time` |
| Tiền | `bigint`, hậu tố `_vnd`, số nguyên VND. Chi phí AI `numeric(12,6)`, hậu tố `_usd` |
| Giá trị liệt kê | `text` + `CHECK (cột IN (...))`, không dùng `enum` của PostgreSQL |
| Dữ liệu bán cấu trúc | `jsonb`; mọi `jsonb` đi qua schema Pydantic ở service trước khi ghi |
| Xóa mềm | Chỉ bảng có đồng bộ ra ngoài hoặc có khóa chống trùng: `tab_expense`, `tab_task`, `tab_event`, `tab_file`, `tab_contact`. Bảng khác xóa cứng |
| Tìm toàn văn | Cột sinh `search_vector tsvector GENERATED ALWAYS AS (to_tsvector('troly_vn', ...)) STORED`, chỉ mục GIN. Cấu hình `troly_vn` là `simple` + `unaccent`: gõ không dấu vẫn tìm ra |
| Chữ ký hiệu | `NN` = `NOT NULL`; `FK` = khóa ngoại; `UQ` = duy nhất; `CK` = `CHECK` |

**Phần mở rộng PostgreSQL** tạo ở migration đầu tiên: `unaccent`, `pg_trgm`, `citext`. `pgvector` để dành.

**Bảng hệ thống** (không có `user_id` hoặc `user_id` cho phép rỗng, có lý do): `tab_user`, `tab_app_release`, `tab_place_cache`, `tab_route_cache`, `tab_job_schedule`, `tab_job_run`, `tab_audit_log` (`user_id` rỗng được), `tab_ai_run` (`user_id` rỗng được với việc hệ thống). Danh sách này là danh sách miễn của bài kiểm `test_user_scoping.py` (`70-kiem-thu.md`).

### 3.2 Sơ đồ quan hệ

```
tab_user ─┬─< tab_auth_session
          ├─< tab_setting, tab_consent
          ├─< tab_device ──< tab_device_event
          ├─< tab_listened_app
          ├─1 tab_profile_memory, ─< tab_profile_memory_revision
          ├─< tab_note
          ├─< tab_conversation ──< tab_message >── tab_ai_run
          ├─< tab_pending_action
          ├─< tab_expense_category ──< tab_expense
          ├─< tab_inbox_message, tab_inbox_rule
          ├─< tab_event <── tab_task.event_id
          ├─1 tab_google_account ─┬─< tab_google_sync_state
          │                       ├─< tab_google_outbox
          │                       ├─< tab_contact
          │                       └─< tab_gmail_draft
          ├─< tab_google_oauth_state
          ├─< tab_trip ─┬─< tab_trip_stop
          │             ├─< tab_trip_option
          │             └─< tab_trip_fact
          ├─< tab_file, tab_export, tab_job_queue
          └─< tab_audit_log (user_id rỗng được)

Bảng hệ thống: tab_app_release, tab_place_cache, tab_route_cache, tab_job_schedule, tab_job_run
```

### 3.3 Tổng hợp bảng theo nơi đặt model

| Nơi đặt `models.py` | Bảng | Từ bản |
|---|---|---|
| `core/models.py` | `tab_user`, `tab_auth_session`, `tab_job_queue`, `tab_job_schedule`, `tab_job_run`, `tab_audit_log`, `tab_consent` | V1.0 |
| `ai/models.py` | `tab_ai_run` | V1.0 |
| `modules/setting` | `tab_setting` | V1.0 |
| `modules/memory` | `tab_profile_memory`, `tab_profile_memory_revision`, `tab_note` | V1.0 |
| `modules/chat` | `tab_conversation`, `tab_message`, `tab_pending_action` | V1.0 |
| `modules/file` | `tab_file` | V1.0 |
| `modules/device` | `tab_device` | V1.0 |
| `modules/expense` | `tab_expense_category`, `tab_expense` | V1.1 |
| `modules/device` | `tab_listened_app`, `tab_device_event` | V1.2 |
| `modules/inbox` | `tab_inbox_message`, `tab_inbox_rule` | V1.3 |
| `modules/calendar` | `tab_event` | V1.4 |
| `modules/task` | `tab_task` | V1.4 |
| `integrations/google/models.py` | `tab_google_account`, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox` | V1.4 |
| `modules/device` | `tab_app_release` | V1.5 |
| `modules/trip` | `tab_trip`, `tab_trip_stop`, `tab_trip_option`, `tab_trip_fact`, `tab_place_cache`, `tab_route_cache` | V1.6 |
| `modules/report` | `tab_export` | V1.7 |
| `modules/inbox` | `tab_contact`, `tab_gmail_draft` | V1.8 |
| `modules/health` | `tab_health_daily` | V2 |
| `core/models.py` | `tab_dev_job` | V3 |

Bảng `tab_google_*` đặt ở `integrations/google/models.py` (chốt A4 dòng 47): đây là trạng thái kết nối dùng chung cho calendar, task, inbox, report, file; đặt trong một module sẽ buộc các module kia phụ thuộc module đó.

### 3.4 Core: người dùng, phiên, hàng đợi, kiểm toán, đồng ý

**`tab_user`** (bảng hệ thống)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| name | text | NN, 1 tới 80 ký tự | |
| email | citext | NN, UQ | |
| password_hash | text | NN | bcrypt |
| role | text | NN, CK `owner`, `member` | Một owner: UQ một phần `WHERE role = 'owner'` |
| timezone | text | NN, default `Asia/Ho_Chi_Minh` | IANA |
| is_active | boolean | NN, default true | |
| must_change_password | boolean | NN, default false | |
| failed_login_count | int | NN, default 0 | |
| locked_until | timestamptz | | |
| last_login_at, password_changed_at | timestamptz | | |
| created_at, updated_at | timestamptz | NN | |

**`tab_auth_session`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| refresh_token_hash | text | NN, UQ | SHA-256 hex |
| label | text | | *Galaxy S25+, app 1.2.0* |
| user_agent | text | | |
| ip | inet | | Lấy từ `CF-Connecting-IP` |
| last_used_at | timestamptz | | |
| expires_at | timestamptz | NN | |
| revoked_at | timestamptz | | |
| replaced_by_id | bigint | FK `tab_auth_session` SET NULL | Xoay vòng mã |

Chỉ mục: `(user_id, revoked_at)`.

**`tab_job_queue`**: việc dài chạy nền theo yêu cầu.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| kind | text | NN | `trip_import`, `trip_evaluate`, `google_initial_sync`, `user_export`, `user_delete_files` |
| payload | jsonb | NN, default `{}` | Không chứa bí mật |
| status | text | NN, CK `pending`, `processing`, `done`, `failed`, `cancelled` | |
| attempts | smallint | NN, default 0 | |
| max_attempts | smallint | NN, default 3 | |
| next_attempt_at | timestamptz | NN, default now() | |
| locked_at, started_at, finished_at | timestamptz | | |
| result | jsonb | | Ví dụ `{"trip_id": 12}` |
| error | text | | Câu tiếng Việt |
| dedupe_key | text | | |

Chỉ mục: `(status, next_attempt_at) WHERE status = 'pending'`; UQ một phần `(user_id, dedupe_key) WHERE status IN ('pending', 'processing')`.

**`tab_job_schedule`** (bảng hệ thống): mỗi job theo lịch một dòng; lịch khai trong mã (`core/scheduler.py`), bảng chỉ giữ trạng thái.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| name | text | PK | |
| next_run_at | timestamptz | NN | |
| last_started_at, last_finished_at | timestamptz | | |
| last_status | text | CK `ok`, `error`, `skipped` | |
| last_error | text | | |
| last_duration_ms | int | | |
| updated_at | timestamptz | NN | |

**`tab_job_run`** (bảng hệ thống): lịch sử mỗi lần chạy job theo lịch.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| job_name | text | NN | |
| started_at | timestamptz | NN | |
| finished_at | timestamptz | | |
| status | text | NN, CK `running`, `ok`, `error` | |
| items_processed | int | NN, default 0 | |
| detail | jsonb | | Với `backup_database`: khóa R2, kích thước, `sha256` tệp mã hóa, số dòng các bảng chính (`50-ha-tang-trien-khai.md` mục 4) |
| error | text | | |

Chỉ mục: `(job_name, started_at DESC)`.

**`tab_audit_log`** (`60-bao-mat-rieng-tu.md` mục 3.13)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | FK `tab_user` SET NULL | Rỗng với sự kiện hệ thống hoặc đăng nhập sai email lạ |
| device_id | bigint | FK `tab_device` SET NULL | |
| event | text | NN | `login_ok`, `login_failed`, `account_locked`, `password_changed`, `refresh_reused`, `device_added`, `device_revoked`, `google_connected`, `google_disconnected`, `action_approved`, `action_rejected`, `data_exported`, `account_deleted`, `user_created`, `release_published`, `deploy` |
| ip | inet | | |
| detail | jsonb | | Không chứa nội dung nhạy cảm (chỉ id, mã, số đếm) |
| created_at | timestamptz | NN | |

Chỉ mục: `(user_id, created_at DESC)`; `(event, created_at DESC)`. Chỉ ghi thêm, không sửa.

**`tab_consent`** (`60-bao-mat-rieng-tu.md` mục 3.10)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| kind | text | NN, CK `data_processing`, `inbox_ai` | |
| notice_version | text | NN | Phiên bản bản thông báo đã hiện |
| accepted_at | timestamptz | NN | |
| withdrawn_at | timestamptz | | |

UQ một phần `(user_id, kind) WHERE withdrawn_at IS NULL`.

### 3.5 Setting

**`tab_setting`**: khóa và giá trị; danh sách khóa hợp lệ, kiểu, mặc định khai trong `setting/service.py`, khóa lạ bị từ chối 400.

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| user_id | bigint | PK cùng `key`, FK `tab_user` CASCADE |
| key | text | PK cùng `user_id` |
| value | jsonb | NN |
| updated_at | timestamptz | NN |

Khóa V1 (gom từ 30, 31, 41, 60; quy ước `<mảng>.<tên>`):

| Khóa | Kiểu | Mặc định | Nguồn |
|---|---|---|---|
| `app.lock_enabled` | bool | `true` | 30 |
| `app.lock_after_minutes` | int | `5` | 30 |
| `ui.voice_reply` | bool | `false` | 31 |
| `calendar.default_remind_minutes` | int[] | `[15]` | |
| `calendar.week_start` | int | `1` (thứ Hai) | |
| `expense.default_account` | text | `cash` | |
| `inbox.ai_enabled` | bool | `true` | 60: tắt thì hộp tin không gửi Claude |
| `inbox.quiet_hours` | object hoặc null | `null` | |
| `trip.default_travel_mode` | text | `motorbike` | |
| `trip.night_start` | time | `18:00` | 41 |
| `trip.night_end` | time | `05:30` | 41 |
| `trip.ride_break_minutes` | int | `90` | 41 |
| `trip.speed_factor` | number | `1.2` | 41 |

Bỏ so với bản 1: `ai.daily_usd_limit` (QĐ-15 không còn trần ngày), `google.services` (thay bằng `tab_google_account.enabled_packs`), `app.auto_install_update` (QĐ-18 luôn hỏi trước khi cài).

### 3.6 Device: thiết bị, app được nghe, sự kiện, bản phát hành

**`tab_device`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| name | text | NN | |
| platform | text | NN, CK `android` | |
| model, os_version | text | | |
| token_hash | text | NN, UQ | SHA-256 của mã thiết bị |
| token_prefix | text | NN | 8 ký tự đầu |
| app_version_code | int | | |
| app_version_name | text | | |
| web_version | text | | |
| notification_access | boolean | | Quyền đọc thông báo đã cấp |
| listener_connected | boolean | | Dịch vụ nghe đang kết nối (30) |
| notifications_enabled | boolean | | `POST_NOTIFICATIONS` (30) |
| exact_alarm_allowed | boolean | | (30) |
| battery_optimization_ignored | boolean | | |
| queue_size | int | | Số sự kiện đang chờ trên máy (30) |
| last_seen_at, last_event_at | timestamptz | | |
| silent_warned_at | timestamptz | | Lần cuối cảnh báo thiết bị im lặng (job `check_silent_devices`, `10-kien-truc-backend.md` mục 3.9) |
| revoked_at | timestamptz | | Thu hồi, không xóa dòng |

Chỉ mục: `(user_id)`.

**`tab_listened_app`**: theo người dùng, đồng bộ xuống plugin qua `/device/config`.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| package_name | text | NN | Giá trị đặc biệt `sms_default`: plugin thay bằng gói SMS mặc định của máy |
| label | text | NN | |
| purpose | text | NN, CK `expense`, `inbox` | |
| parser | text | NN, CK `vcb`, `tcb`, `momo`, `zalo`, `telegram`, `messenger`, `sms`, `generic` | |
| enabled | boolean | NN, default true | |
| is_default | boolean | NN, default false | |

UQ `(user_id, package_name)`. Dòng tạo sẵn cho người dùng mới (`30-app-android.md` mục 4.1): `com.VCB` (expense, `vcb`), `vn.com.techcombank.bb.app` (expense, `tcb`), `com.mservice.momotransfer` (expense, `momo`), `com.zing.zalo` (inbox, `zalo`), `org.telegram.messenger` (inbox, `telegram`), `com.facebook.orca` (inbox, `messenger`), `sms_default` (inbox, `sms`). Với máy Samsung Galaxy S25+ (QĐ-19), `sms_default` thành `com.samsung.android.messaging` hoặc `com.google.android.apps.messaging` tùy app SMS mặc định thật. Khi gói `gmail` của Google đã nối, `com.google.android.gm` bị bỏ khỏi danh sách (`40-tich-hop-google.md` mục 6.5). Danh sách chỉ đổi trên màn Cài đặt, không qua công cụ AI.

**`tab_device_event`**: hàng đợi sự kiện từ điện thoại.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| device_id | bigint | NN, FK `tab_device` CASCADE | |
| client_event_id | uuid | NN | |
| kind | text | NN, CK `notification`, `reminder_action`, `health_daily` | `reminder_action` từ V1.4; `health_daily` V2 |
| app_package | text | | NN khi `kind = notification` (CK) |
| posted_at | timestamptz | NN | |
| payload | jsonb | NN | Theo bảng dưới |
| received_at | timestamptz | NN, default now() | |
| status | text | NN, CK `pending`, `processing`, `done`, `ignored`, `failed` | |
| attempts | smallint | NN, default 0 | |
| next_attempt_at | timestamptz | NN, default now() | |
| locked_at, processed_at | timestamptz | | |
| result_kind | text | CK `expense`, `inbox_message`, `transfer_merged`, `task_updated`, `none` | |
| result_id | bigint | | Không khóa ngoại (đích ở nhiều bảng) |
| error | text | | |

UQ `(device_id, client_event_id)`. Chỉ mục: `(status, next_attempt_at) WHERE status = 'pending'`; `(user_id, received_at DESC)`.

Trường `payload` (chốt theo `30-app-android.md` mục 5.1; không trường nào khác rời máy):

| `kind` | Trường |
|---|---|
| `notification` | `title`, `text`, `conversation_title`, `messages[]` (`sender`, `text`, `at`), `is_group_conversation`, `category`, `notification_key_hash`, `hidden_content` |
| `reminder_action` | `reminder_key`, `source` (`event`, `task`), `source_id`, `action` (`done`, `ack`, `snooze`), `at` |
| `health_daily` (V2) | `date`, `steps`, `sleep_minutes`, `resting_heart_rate` |

**`tab_app_release`** (bảng hệ thống)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| kind | text | NN, CK `apk`, `web` | |
| version_code | int | NN | APK: `versionCode`; web: số tăng dần |
| version_name | text | NN | Web: chuỗi `version` của gói, ví dụ `1.5.2+20261118.1` |
| r2_key | text | NN | Trong bucket `troly-release` |
| sha256 | text | NN | |
| size_bytes | bigint | NN | |
| signature | text | | Web: chữ ký ECDSA P-256 base64 trên `version|min_app_version_code|sha256` |
| min_supported_version_code | int | | APK: thấp hơn thì bắt buộc cập nhật. Web: đóng vai `min_app_version_code` |
| notes | text | | |
| is_published | boolean | NN, default true | `false` là thu hồi bản lỗi |
| published_by | text | NN, CK `ci`, `manual` | |
| published_at | timestamptz | NN | |
| created_at | timestamptz | NN | |

UQ `(kind, version_code)`. Dòng được ghi qua `POST /api/v1/admin/releases` bằng mã CI sau khi GitHub Actions đẩy tệp lên R2 (`12-api.md` mục 5.13); máy chủ kiểm tệp có trên R2 và `sha256` khớp rồi mới ghi.

### 3.7 Memory

**`tab_profile_memory`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | user_id UQ | |
| content | text | NN, default `''`, CK `char_length(content) <= 8000` | Markdown, 8 mục cố định (`20-bo-nao-ai.md` mục 3.4) |
| version | int | NN, default 1 | |
| updated_by | text | NN, CK `user`, `ai` | |

**`tab_profile_memory_revision`**: lịch sử để hoàn tác.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | NN, FK CASCADE | |
| version | int | NN | Bản **trước** lần sửa lên `version + 1` |
| content | text | NN | |
| changed_by | text | NN, CK `user`, `ai` | |
| reason | text | | Ví dụ `remember`, `forget`, `manual_edit`, `restore` (20) |
| created_at | timestamptz | NN | |

UQ `(user_id, version)`. Giữ 50 bản mới nhất mỗi người.

**`tab_note`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| title | text | NN, tối đa 200 | |
| body | text | NN, default `''`, tối đa 20.000 | |
| tags | text[] | NN, default `{}` | |
| source | text | NN, CK `user`, `ai` | |
| search_vector | tsvector | cột sinh từ `title`, `body`, `tags` | |

Chỉ mục: GIN `search_vector`; GIN `tags`; `(user_id, updated_at DESC)`.

### 3.8 Chat và AI

**`tab_conversation`**: mỗi người mỗi ngày một phiên.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| local_date | date | NN | Ngày phiên, **tách lúc 04:00** giờ của người dùng (QĐ-20): `local_date = date(giờ địa phương - 4 giờ)` |
| started_at | timestamptz | NN | |
| last_message_at | timestamptz | | |
| summary | text | | Tóm tắt các lượt cũ hoặc cả ngày; không chép nguyên văn tin của người khác |
| summary_upto_id | bigint | | Id `tab_message` cuối đã gộp |
| last_prompt_tokens | int | | Tổng lời nhắc lần gọi gần nhất (20) |
| compacted_count | int | NN, default 0 | |
| day_summary_done | boolean | NN, default false | |
| message_count | int | NN, default 0 | |

UQ `(user_id, local_date)`. Mốc 04:00 chỉ áp cho phiên chat; báo cáo, chi tiêu, lịch vẫn tính ngày từ 00:00.

**`tab_message`**: lưu nguyên khối nội dung Claude, kể cả lượt công cụ, chỉ nối thêm.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| conversation_id | bigint | NN, FK `tab_conversation` CASCADE | |
| turn_id | uuid | NN | Gom các tin của một lượt người dùng (20) |
| role | text | NN, CK `user`, `assistant`, `system` | `system`: tin thời gian, tin kết quả duyệt (ĐX-AI-01) |
| content | jsonb | NN | Mảng khối Claude (`text`, `thinking`, `tool_use`, `tool_result`, `image`, `document`); không chuẩn hóa |
| text | text | | Chữ hiển thị cho app |
| hidden | boolean | NN, default false | Không hiện trên app: tin `system`, tin chỉ có `tool_use` hoặc `tool_result` |
| status | text | NN, CK `complete`, `failed`, default `complete` | |
| client_message_id | uuid | | Tin người dùng gửi; chống gửi trùng |
| attachment_file_ids | bigint[] | NN, default `{}` | Không khóa ngoại |
| actions | jsonb | | Hành động trả cho app, theo kiểu ở `20-bo-nao-ai.md` mục 3.8 |
| contains_third_party | boolean | NN, default false | Khối có tin nhắn, thư của người khác (kết quả `list_inbox`, `summarize_inbox`, `get_gmail_thread`...) (60) |
| redacted_at | timestamptz | | Lúc khối bên thứ ba bị thay nội dung (mục 3.15) |
| ai_run_id | bigint | FK `tab_ai_run` SET NULL | |
| input_tokens, output_tokens | int | | |

UQ một phần `(user_id, client_message_id) WHERE client_message_id IS NOT NULL`. Chỉ mục: `(conversation_id, id)`; `(user_id, created_at DESC)`; `(contains_third_party, created_at) WHERE contains_third_party AND redacted_at IS NULL`.

**`tab_pending_action`**: hành động chờ duyệt, dùng chung cho xóa qua AI, gửi Gmail, mời khách lịch, chia sẻ Drive, V2 trả lời tin (tên chốt theo A1 dòng 1; thay `tab_ai_pending_action`).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| conversation_id | bigint | FK `tab_conversation` SET NULL | Để nối tin hệ thống kết quả; rỗng khi tạo từ màn khác (ví dụ màn nháp Gmail) |
| message_id | bigint | FK `tab_message` SET NULL | Tin có thẻ duyệt |
| tool_name | text | NN | `delete_expense`, `delete_task`, `delete_event`, `delete_note`, `delete_trip`, `delete_file`, `add_event`, `update_event` (có khách mời), `send_gmail_draft`, `share_drive_file`, `update_setting` |
| input | jsonb | NN | Đầu vào đã kiểm, đủ để chạy `execute_approved` |
| payload_hash | text | NN | SHA-256 của `tool_name` + `input` chuẩn hóa; đổi nội dung thì không duyệt được (60) |
| title | text | NN | Dòng đầu thẻ |
| summary | text | NN | Câu hiển thị trên thẻ |
| details | jsonb | NN, default `[]` | `[{label, value}]` |
| danger | boolean | NN, default false | |
| require_unlock | boolean | NN, default false | Máy chủ quyết; `true` với gửi ra ngoài và `danger` (31) |
| status | text | NN, CK `pending`, `done`, `failed`, `rejected`, `expired` | |
| expires_at | timestamptz | NN | 24 giờ (A6 dòng 73) |
| decided_at | timestamptz | | |
| result | jsonb | | |
| error | text | | |

Chỉ mục: `(user_id, status, created_at DESC)`; `(status, expires_at) WHERE status = 'pending'`.

**`tab_ai_run`**: mỗi lần gọi Claude một dòng (bộ cột theo `20-bo-nao-ai.md` mục 4).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | FK `tab_user` CASCADE | Rỗng với việc hệ thống |
| purpose | text | NN, CK `chat`, `compaction`, `bank_extract`, `trip_extract`, `eval` | |
| model | text | NN | |
| effort | text | | |
| conversation_id | bigint | FK SET NULL | |
| input_tokens | int | NN, default 0 | |
| cache_write_5m_tokens, cache_write_1h_tokens | int | NN, default 0 | Giá khác nhau theo TTL |
| cache_read_tokens | int | NN, default 0 | |
| output_tokens | int | NN, default 0 | Gồm token thinking |
| cost_usd | numeric(12,6) | NN | |
| rate_card | text | CK `le_100k`, `gt_100k` | |
| stop_reason | text | | |
| refusal_category | text | | |
| latency_ms | int | | |
| request_id | text | | Mã yêu cầu của Anthropic |
| error_code | text | | |
| created_at | timestamptz | NN | |

Chỉ mục: `(user_id, created_at)`; `(created_at)` cho tổng tháng toàn hệ thống (cảnh báo `AI_MONTHLY_USD`, QĐ-15).

### 3.9 Expense

**`tab_expense_category`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| name | text | NN | |
| keywords | text[] | NN, default `{}` | |
| kind | text | NN, CK `expense`, `income`, default `expense` | |
| sort_order | smallint | NN, default 0 | |
| is_archived | boolean | NN, default false | |

UQ `(user_id, lower(name))`. Người dùng mới có sẵn bộ danh mục mặc định, gồm `Khác`.

**`tab_expense`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| amount_vnd | bigint | NN, CK `> 0` | |
| kind | text | NN, CK `expense`, `income`, `transfer` | `transfer`: chuyển nội bộ giữa tài khoản của chính người dùng, không tính vào chi |
| account | text | NN, CK `vcb`, `tcb`, `momo`, `cash`, `card`, `other` | Mã nơi tiền đi ra (hoặc vào với `income`) |
| account_last4 | text | CK `account_last4 ~ '^[0-9]{4}$'` | 4 số cuối tài khoản hoặc thẻ (QĐ-22). Không bao giờ lưu số đầy đủ |
| to_account | text | CK như `account` | Chỉ với `transfer` |
| to_account_last4 | text | CK như trên | |
| category_id | bigint | FK `tab_expense_category` SET NULL | |
| merchant | text | | |
| place | text | | |
| note | text | | |
| spent_at | timestamptz | NN | |
| source | text | NN, CK `chat`, `bank_notification`, `manual` | |
| source_ref | text | | Thông báo: `<app_package>:<băm nội dung>` |
| transfer_peer_ref | text | | `source_ref` của thông báo thứ hai trong cặp chuyển nội bộ |
| device_event_id | bigint | FK `tab_device_event` SET NULL | Để xem chữ thông báo gốc khi còn trong hạn |
| parser | text | | `regex:<tên mẫu>`, `ai`, `chat`, `manual` (20) |
| parse_confidence | numeric(3,2) | CK `0 <= x <= 1` | Rỗng với `regex`, `manual` |
| needs_review | boolean | NN, default false | Đặt `true` khi `parse_confidence < 0.7` hoặc chưa có danh mục; mục *Cần xem lại* ở 31 lọc theo cột này |
| deleted_at | timestamptz | | |

Không có cột số dư (QĐ-22; bỏ `balance_after_vnd` của bản 1).

Ràng buộc: CK `kind <> 'transfer' OR to_account IS NOT NULL`.
UQ một phần `(user_id, source_ref) WHERE source_ref IS NOT NULL`; UQ một phần `(user_id, transfer_peer_ref) WHERE transfer_peer_ref IS NOT NULL`.
Chỉ mục: `(user_id, spent_at DESC) WHERE deleted_at IS NULL`; `(user_id, category_id)`; `(user_id) WHERE needs_review AND deleted_at IS NULL`.

**Ghép cặp chuyển nội bộ.** Thông báo tiền ra từ ngân hàng và tiền vào MoMo (hoặc ngược lại) cùng số tiền, cách nhau tối đa 10 phút, chưa ghép: dòng đã có đổi thành `kind = 'transfer'`, điền `to_account`, `transfer_peer_ref`; sự kiện thứ hai ghi `result_kind = 'transfer_merged'`. Chỉ ghép trong cùng `user_id`. Khoảng 10 phút chốt lại khi có bộ mẫu thật.

### 3.10 Inbox, danh bạ, nháp Gmail

**`tab_inbox_message`**: tin nghe từ thông báo và thư Gmail.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| source | text | NN, CK `notification`, `gmail` | |
| app | text | NN, CK `zalo`, `telegram`, `messenger`, `sms`, `gmail`, `other` | |
| app_package | text | | Rỗng với Gmail |
| device_id | bigint | FK `tab_device` SET NULL | |
| device_event_id | bigint | FK `tab_device_event` SET NULL | |
| sender | text | | Tên trên thông báo, hoặc tên người gửi thư (tra Contacts) |
| sender_key | text | NN | `<app>:<tên hoặc địa chỉ đã chuẩn hóa>` |
| conversation_key | text | NN | Khóa gom cuộc trò chuyện: băm `(app, conversation_title nếu có, không thì sender_key)`; Gmail dùng `thread_ref` (31) |
| conversation_title | text | | Tên nhóm chat; Gmail để rỗng |
| is_group | boolean | NN, default false | |
| contact_id | bigint | FK `tab_contact` SET NULL | Từ V1.8 |
| subject | text | | Tiêu đề thư |
| text | text | NN, tối đa 4.000 ký tự | Thông báo: nội dung; Gmail: đoạn trích `snippet` |
| hidden_content | boolean | NN, default false | App ẩn nội dung tin |
| posted_at | timestamptz | NN | |
| status | text | NN, CK `new`, `seen`, `done`, default `new` | |
| importance | text | NN, CK `normal`, `important`, default `normal` | 40 dùng `important`, không dùng `high` |
| importance_reason | text | | `vip_sender`, `urgent_keyword`, `gmail_important` |
| external_id | text | | Gmail: id thư |
| thread_ref | text | | Gmail: id luồng |
| labels | text[] | NN, default `{}` | Nhãn Gmail (40) |
| dedupe_hash | text | NN | Chống trùng khi một tin hiện nhiều thông báo, và thư Gmail trùng thông báo Gmail |
| search_vector | tsvector | cột sinh từ `sender`, `conversation_title`, `subject`, `text` | |

UQ `(user_id, dedupe_hash)`; UQ một phần `(user_id, external_id) WHERE source = 'gmail'`.
Chỉ mục: `(user_id, posted_at DESC)`; `(user_id, conversation_key, posted_at DESC)`; `(user_id, status, importance, posted_at DESC)`; GIN `search_vector`.

**`tab_inbox_rule`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| kind | text | NN, CK `vip_sender`, `urgent_keyword`, `muted_sender`, `muted_keyword`, `muted_app`, `private_conversation` | `private_conversation`: tin vẫn vào hộp tin nhưng không bao giờ gửi Claude (60) |
| value | text | NN | Tên người, từ khóa, tên gói, hoặc `conversation_key` |
| app | text | | Giới hạn trong một app; rỗng là mọi app |
| contact_id | bigint | FK `tab_contact` SET NULL | Khi người quan trọng chọn từ danh bạ |

UQ `(user_id, kind, lower(value), coalesce(app, ''))`. Luật `muted_*` làm tin không vào hộp tin (sự kiện ghi `result_kind = 'none'`). Danh sách `vip_sender`, `urgent_keyword` đổi được qua công cụ AI có duyệt (ĐX-AI-09, đã duyệt theo QĐ-25); `muted_app` chỉ đổi trên màn Cài đặt.

**`tab_contact`** (V1.8, People API, chỉ đọc)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| google_account_id | bigint | NN, FK `tab_google_account` CASCADE | |
| resource_name | text | NN | |
| etag | text | | |
| display_name | text | NN | |
| phones | text[] | NN, default `{}` | Chuẩn hóa `+84...` |
| emails | citext[] | NN, default `{}` | |
| birthday_day, birthday_month | smallint | CK ngày 1 tới 31, tháng 1 tới 12 | |
| birthday_year | smallint | | Rỗng khi không rõ năm (thay cách lưu năm 1900 của bản 1) |
| remind_birthday | boolean | NN, default false | (40) |
| is_important | boolean | NN, default false | (40) |
| synced_at | timestamptz | NN | |
| deleted_at | timestamptz | | Google báo `metadata.deleted` |

UQ `(user_id, resource_name)`. Chỉ mục: GIN `phones`, GIN `emails`, `(user_id, lower(display_name))`.

**`tab_gmail_draft`** (V1.8): theo dõi nháp; gửi chỉ qua `tab_pending_action` (`tool_name = send_gmail_draft`).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| google_account_id | bigint | NN, FK CASCADE | |
| google_draft_id | text | | Có sau khi `drafts.create` |
| thread_ref | text | | Trả lời trong luồng nào |
| to_addrs, cc_addrs | citext[] | NN, default `{}` | |
| subject | text | NN | |
| body | text | NN | |
| body_hash | text | NN | So với bản trên Gmail trước khi gửi |
| status | text | NN, CK `draft`, `sending`, `sent`, `discarded` | |
| pending_action_id | bigint | FK `tab_pending_action` SET NULL | |
| approved_at, sent_at | timestamptz | | |
| sent_message_id | text | | |

Nội dung nháp là dữ liệu của chính người dùng; giữ tới khi gửi hoặc bỏ cộng 30 ngày.

### 3.11 Calendar và task

**`tab_event`**: Google Calendar làm gốc (QĐ-09). Sự kiện lặp lưu **bản gốc có `recurrence`** và các lần lặp bị sửa riêng (ngoại lệ); máy chủ tự trải lần lặp khi liệt kê (theo `40-tich-hop-google.md` mục 4.3, xem ĐX-CSDL-10).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| title | text | NN | |
| description | text | | Ánh xạ `description` của Google (không dùng tên `note`) |
| location | text | | |
| all_day | boolean | NN, default false | |
| start_at, end_at | timestamptz | | Khi `all_day = false` |
| start_date, end_date | date | | Khi `all_day = true`; `end_date` không tính (như Google) |
| timezone | text | | Múi giờ của sự kiện lặp, để trải đúng giờ |
| status | text | NN, CK `confirmed`, `tentative`, `cancelled` | |
| recurrence | text[] | | Dòng `RRULE`, `EXDATE`... của bản gốc |
| recurring_event_id | text | | Ngoại lệ: id Google của bản gốc |
| original_start_at | timestamptz | | Ngoại lệ: giờ gốc của lần lặp bị sửa |
| attendees | jsonb | NN, default `[]` | `[{email, name, response_status, is_self}]` (QĐ-23) |
| remind_minutes | int[] | NN, default `{}` | |
| remind_source | text | NN, CK `app`, `google` | Mặc định `app` nếu tạo ở app, `google` nếu tạo trên Google (ĐX-G6). Nhắc trên máy chỉ với `app` |
| is_alarm | boolean | NN, default false | Nhắc loại báo thức (giờ phà, giờ trả phòng): máy dùng `setAlarmClock` (30 mục 3.8) |
| source | text | NN, CK `app`, `google` | Nơi tạo |
| task_id | bigint | | Không khóa ngoại; tra ngược từ `tab_task.event_id` khi cần, cột này chỉ là bản sao để trả API nhanh |
| google_account_id | bigint | FK `tab_google_account` SET NULL | |
| google_calendar_id | text | | `primary` |
| google_event_id | text | | App đặt sẵn khi tạo (hex của UUID, 40 mục 4.2) |
| google_etag | text | | |
| google_updated_at | timestamptz | | |
| sync_status | text | NN, CK `local_only`, `pending`, `synced`, `conflict`, `error` | |
| sync_error | text | | |
| deleted_at | timestamptz | | |

Ràng buộc: CK `(all_day AND start_date IS NOT NULL AND end_date > start_date) OR (NOT all_day AND start_at IS NOT NULL AND end_at >= start_at)`.
UQ một phần `(user_id, google_calendar_id, google_event_id) WHERE google_event_id IS NOT NULL`.
Chỉ mục: `(user_id, start_at) WHERE deleted_at IS NULL`; `(user_id, start_date) WHERE all_day AND deleted_at IS NULL`; `(user_id) WHERE recurrence IS NOT NULL AND deleted_at IS NULL`; `(user_id, recurring_event_id)`.

Sự kiện có khách mời chỉ được tạo hoặc sửa sau khi người dùng duyệt (QĐ-23): dữ liệu nằm trong `tab_pending_action.input`, duyệt xong mới ghi `tab_event` và hàng chờ (Google gửi thư mời với `sendUpdates=all`).

**`tab_task`**: app làm gốc; đẩy lên Google Tasks; **đọc ngược trạng thái xong và đã xóa** (QĐ-21). Việc có giờ sinh sự kiện lịch, không lên Tasks.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| title | text | NN, tối đa 1.024 | Giới hạn của Google Tasks |
| note | text | tối đa 8.000 | |
| status | text | NN, CK `todo`, `done`, `cancelled`, default `todo` | |
| priority | text | NN, CK `low`, `normal`, `high`, default `normal` | |
| due_date | date | | Hạn không giờ (đi Google Tasks) |
| due_at | timestamptz | | Hạn có giờ (đi Google Calendar qua `event_id`) |
| completed_at | timestamptz | | |
| completed_source | text | CK `app`, `google` | Ai đánh dấu xong |
| event_id | bigint | FK `tab_event` SET NULL | |
| source | text | NN, CK `app`, `chat` | |
| google_account_id | bigint | FK `tab_google_account` SET NULL | |
| google_tasklist_id | text | | Danh sách *Trợ lý* (ĐX-G5) |
| google_task_id | text | | |
| google_etag | text | | (40) |
| google_updated_at | timestamptz | | |
| sync_status | text | NN, CK `local_only`, `pending`, `synced`, `remote_deleted`, `error` | `remote_deleted`: Google báo đã xóa, chờ người dùng chọn xóa hay giữ |
| sync_error | text | | |
| deleted_at | timestamptz | | |

Ràng buộc: CK `due_date IS NULL OR due_at IS NULL`. Không cần cột `due_has_time` của 40: có `due_at` là có giờ.
UQ một phần `(user_id, google_task_id) WHERE google_task_id IS NOT NULL`.
Chỉ mục: `(user_id, status, due_at) WHERE deleted_at IS NULL`; `(user_id, status, due_date) WHERE deleted_at IS NULL`.

**Nhắc trên máy** không có bảng riêng: `GET /calendar/reminders` tính từ `tab_event.remind_minutes` của sự kiện có `remind_source = 'app'` (gồm sự kiện sinh từ việc có giờ), trải cả lần lặp trong cửa sổ.

### 3.12 Google: tài khoản, trạng thái OAuth, đồng bộ, hàng chờ

Đặt ở `integrations/google/models.py`. Tên cột chốt ở đây; `40-tich-hop-google.md` sửa theo.

**`tab_google_account`**: V1 mỗi người một tài khoản Google.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | user_id UQ | `bigint` như mọi bảng (không dùng `uuid`) |
| google_sub | text | NN, UQ | |
| email | citext | NN | |
| granted_scopes | text[] | NN | Đọc từ trường `scope` của phản hồi token |
| enabled_packs | text[] | NN, default `{base}` | `base`, `calendar`, `tasks`, `gmail`, `contacts`, `drive`. Nơi duy nhất lưu gói đã bật |
| refresh_token_enc | bytea | NN | Fernet, bản rõ `{user_id, provider, token}` (60 mục 3.5) |
| access_token_enc | bytea | | |
| access_expires_at | timestamptz | | |
| key_version | smallint | NN | |
| status | text | NN, CK `active`, `reauth_required`, `revoked` | Khớp mã lỗi `GOOGLE_REAUTH_REQUIRED` |
| last_error | text | | |
| invalid_grant_count | int | NN, default 0 | Đếm theo tháng để phát hiện dự án bị coi như Testing |
| connected_at | timestamptz | NN | |

**`tab_google_oauth_state`**: trạng thái luồng OAuth, sống 10 phút.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| state_hash | text | NN, UQ | SHA-256 của `state` gửi Google |
| packs | text[] | NN | |
| code_verifier_enc | bytea | NN | PKCE, mã hóa Fernet |
| expires_at | timestamptz | NN | |
| used_at | timestamptz | | Dùng một lần |

**`tab_google_sync_state`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| google_account_id | bigint | NN, FK CASCADE | |
| service | text | NN, CK `calendar`, `tasks`, `gmail`, `contacts`, `drive`, `sheets` | Đổi tên từ `resource` của bản 1 cho khớp 40 |
| resource_id | text | NN | `primary`, id danh sách *Trợ lý*, `me`, id thư mục *Trợ lý*, id bảng tính |
| sync_token | text | | Calendar, People |
| history_id | text | | Gmail |
| updated_min | timestamptz | | Tasks: mốc lần đọc ngược trước |
| needs_sync | boolean | NN, default true | |
| last_sync_at, last_full_sync_at | timestamptz | | |
| next_sync_at | timestamptz | | Lần quét kế tiếp đã tính lệch ngẫu nhiên |
| status | text | NN, CK `ok`, `error`, `disabled` | |
| last_error | text | | |
| channel_id | uuid | UQ | Kênh webhook Calendar |
| channel_resource_id | text | | |
| channel_token_hash | text | | |
| channel_expires_at | timestamptz | | |

UQ `(google_account_id, service, resource_id)`. Chỉ mục: `(needs_sync) WHERE needs_sync`; `(next_sync_at)`; `(channel_expires_at)`.

**`tab_google_outbox`**: ghi lên Google, ghi cùng giao dịch với thay đổi ở app.

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| google_account_id | bigint | NN, FK CASCADE | |
| service | text | NN, CK `calendar`, `tasks`, `gmail`, `drive`, `sheets` | |
| op | text | NN, CK `insert`, `patch`, `delete`, `draft_create`, `draft_send`, `file_upload`, `sheet_write` | |
| local_type | text | NN, CK `event`, `task`, `gmail_draft`, `file`, `export` | |
| local_id | bigint | NN | |
| payload | jsonb | NN, default `{}` | Tham số thêm (ví dụ `send_updates`, tháng của báo cáo); không chép lại dữ liệu đã có ở dòng gốc |
| status | text | NN, CK `pending`, `processing`, `done`, `failed`, `conflict` | Dùng `processing` như mọi hàng đợi khác (thay `running` của 40) |
| attempts | smallint | NN, default 0 | Tối đa 5 (40 mục 10) |
| next_attempt_at | timestamptz | NN, default now() | |
| locked_at | timestamptz | | |
| last_error | text | | Với `conflict`: JSON thay đổi bị bỏ, để áp lại một chạm |

UQ một phần `(local_type, local_id, op) WHERE status IN ('pending', 'processing')`: sửa nhiều lần liền chỉ còn một dòng chờ; worker đọc trạng thái mới nhất của dòng gốc lúc đẩy. Chỉ mục: `(status, next_attempt_at) WHERE status = 'pending'`; `(user_id, status) WHERE status IN ('failed', 'conflict')`.

### 3.13 Trip

Bảng theo `41-ban-do-lich-trinh.md` mục 12 (A1 dòng 16, lấy 41 làm gốc).

**`tab_trip`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| title | text | NN | |
| start_date, end_date | date | | CK `end_date >= start_date` |
| nights | smallint | | |
| travel_mode | text | NN, CK `motorbike`, `car`, `walk`, default `motorbike` | |
| origin_text, end_text | text | | |
| status | text | NN, CK `importing`, `draft`, `evaluating`, `planned`, `done`, `failed` | (ĐX-CSDL-05 đã duyệt, thêm `evaluating`) |
| source_kind | text | CK `docx`, `pdf`, `image`, `text`, `link` | |
| source_file_id | bigint | FK `tab_file` SET NULL | |
| source_text | text | | Lời mô tả hoặc link |
| extract_json | jsonb | | Đầu ra bóc tách gốc, để chạy lại |
| notes | jsonb | NN, default `[]` | Mục *Lưu ý* nguyên văn |
| hotels | jsonb | NN, default `[]` | `[{night_no, label, url, booked, backups[]}]` |
| chosen_option_id | bigint | FK `tab_trip_option` SET NULL (`use_alter`) | |
| evaluated_at | timestamptz | | |
| export_file_id | bigint | FK `tab_file` SET NULL | |
| error | text | | Khi `failed` |

Chỉ mục: `(user_id, start_date DESC)`.

**`tab_trip_stop`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| trip_id | bigint | NN, FK `tab_trip` CASCADE | |
| day_no | smallint | NN, CK `>= 1` | |
| seq | smallint | NN | |
| title | text | NN | |
| category | text | NN, CK `an_uong`, `nghi`, `tham_quan`, `pha`, `di_chuyen`, `khach_san`, `mua_sam`, `khac` | |
| role | text | NN, CK `main`, `alternative`, `backup`, `generic`, `via`, default `main` | |
| parent_stop_id | bigint | FK `tab_trip_stop` CASCADE | Điểm phụ trỏ về điểm chính |
| time_text | text | | Nguyên văn trong tệp |
| planned_start, planned_end | timestamptz | | |
| approx | boolean | NN, default false | |
| fixed | boolean | NN, default false | Mốc cứng, không sắp lại |
| optional | boolean | NN, default false | |
| stay_minutes | smallint | | |
| place_query | text | | |
| source_url | text | | Link gốc trong tệp |
| place_id | text | | Lưu lâu dài |
| lat, lng | numeric(9,6) | | |
| coord_source | text | CK `user`, `google` | |
| coord_fetched_at | timestamptz | | Tọa độ `google` quá 30 ngày thì làm mới khi mở chuyến |
| resolve_status | text | NN, CK `ok`, `uncertain`, `not_found`, `manual`, default `uncertain` | Danh sách *Điểm cần xác nhận* (41) |
| phone, cost_note, note | text | | |
| alternatives | jsonb | NN, default `[]` | Gợi ý cho điểm `generic`: `place_id` và nhãn, không lưu tọa độ |

UQ `(trip_id, day_no, seq)` khai `DEFERRABLE INITIALLY DEFERRED`. Chỉ mục: `(trip_id, day_no, seq)`.

**`tab_trip_option`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| trip_id | bigint | NN, FK `tab_trip` CASCADE | |
| name | text | NN | |
| summary | text | | Số trong chữ phải khớp số đã tính |
| plan | jsonb | NN | Theo ngày: `stop_id`, `planned_start`, `leg_minutes`, `leg_km` |
| total_km | numeric(7,1) | | |
| total_ride_minutes | int | | |
| night_ride_minutes | int | | |
| red_count, yellow_count | smallint | NN, default 0 | |
| risks | jsonb | NN, default `[]` | `[{code, level, day_no, stop_id, text, hint}]` |
| changes | jsonb | NN, default `[]` | |
| chosen | boolean | NN, default false | |
| evaluated_at | timestamptz | NN | |

**`tab_trip_fact`**: mốc cứng của chuyến (bảng riêng thay vì nhét JSON, để luật rủi ro truy vấn được).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| trip_id | bigint | NN, FK `tab_trip` CASCADE | |
| kind | text | NN, CK `ferry_last`, `ferry_first`, `checkin`, `checkout`, `hotline` | |
| stop_id | bigint | FK `tab_trip_stop` SET NULL | |
| day_no | smallint | | |
| value_time | time | | |
| value_text | text | | Số điện thoại, câu nguyên văn |
| text | text | NN | |

**`tab_place_cache`** (bảng hệ thống, dùng chung; theo ĐX-T1)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| query_norm | text | PK cùng `bias_key` | Chữ thường, bỏ dấu, gộp khoảng trắng |
| bias_key | text | PK cùng `query_norm` | Vùng ưu tiên đã làm tròn |
| place_id | text | | Giữ vô thời hạn |
| lat, lng | numeric(9,6) | | Xóa khi `fetched_at` quá 30 ngày |
| formatted_address | text | | Như trên |
| fetched_at | timestamptz | | |
| created_at | timestamptz | NN | |

Không lưu giờ mở cửa, tên, đánh giá. Chỉ mục: `(place_id)`; `(fetched_at) WHERE lat IS NOT NULL`.

**`tab_route_cache`** (bảng hệ thống)

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| id | bigint | PK | |
| origin_key, destination_key | text | NN | `place_id` hoặc `lat,lng` làm tròn 5 chữ số |
| travel_mode | text | NN, CK `two_wheeler`, `drive`, `walk` | |
| avoid_highways | boolean | NN | |
| distance_m | int | NN | |
| duration_s | int | NN | |
| fetched_at | timestamptz | NN | |
| expires_at | timestamptz | NN | 30 ngày, chờ đọc lại điều khoản (41 câu hỏi mở 6) |

UQ `(origin_key, destination_key, travel_mode, avoid_highways)`.

### 3.14 File và report

**`tab_file`**

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| r2_key | text | NN, UQ | Bucket `troly-files`, khóa `u/<user_id>/<năm>/<tháng>/<uuid>` |
| original_name | text | | |
| mime | text | NN | |
| size_bytes | bigint | NN, CK `> 0` | |
| sha256 | text | | |
| purpose | text | NN, CK `chat_attachment`, `voice`, `trip_source`, `trip_export`, `report_export`, `user_export`, `other` | |
| status | text | NN, CK `pending_upload`, `ready`, `deleted` | |
| drive_file_id | text | | Bản đã lên thư mục *Trợ lý* trên Drive |
| deleted_at | timestamptz | | |

Chỉ mục: `(user_id, purpose, created_at DESC) WHERE status = 'ready'`.

**`tab_export`**: lịch sử xuất báo cáo (Sheets, Word).

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| kind | text | NN, CK `expense_sheet`, `expense_docx`, `report_docx` | |
| params | jsonb | NN | Tháng hoặc khoảng ngày |
| status | text | NN, CK `pending`, `running`, `done`, `failed` | |
| file_id | bigint | FK `tab_file` SET NULL | Bản Word |
| google_file_id | text | | Bảng tính trên Drive |
| url | text | | |
| error | text | | |

Chỉ mục: `(user_id, created_at DESC)`. Xuất ra Sheets đi qua `tab_google_outbox` (`op = sheet_write`, `local_type = export`). Module `report` không có bảng số liệu riêng ở V1.

### 3.15 Chính sách xóa và thời hạn giữ dữ liệu

Job `cleanup_old_data` chạy 03:30 mỗi ngày, xóa theo lô 1.000 dòng. Số ngày đặt bằng biến môi trường ở [10-kien-truc-backend.md](10-kien-truc-backend.md) mục 3.6.

| Bảng | Giữ bao lâu | Cách xóa |
|---|---|---|
| `tab_inbox_message` | **180 ngày** từ `posted_at` (QĐ-17, `INBOX_RETENTION_DAYS`) | Xóa cứng |
| `tab_device_event` | **180 ngày** từ `received_at`, mọi trạng thái (QĐ-17, `DEVICE_EVENT_RETENTION_DAYS`) | Xóa cứng |
| Khối có `contains_third_party` trong `tab_message` | **180 ngày** (QĐ-17) | Thay nội dung khối `tool_result` bằng *[đã xóa sau 180 ngày]*, giữ cấu trúc khối, đặt `redacted_at` |
| `tab_message` | 365 ngày (đề xuất, chờ người dùng: câu hỏi mở 1) | Xóa cứng; `tab_conversation.summary` giữ lại |
| `tab_conversation` | Tới khi người dùng xóa | |
| `tab_pending_action` | Quá `expires_at` thì đổi `expired` (job `expire_pending_actions`); xóa sau 30 ngày | |
| `tab_ai_run` | 13 tháng | |
| `tab_auth_session` | 30 ngày sau hết hạn hoặc thu hồi | |
| `tab_google_oauth_state` | 1 giờ sau `expires_at` (job `cleanup_google_oauth_state`) | |
| `tab_job_queue` | `done`, `cancelled`: 30 ngày; `failed`: 90 ngày | |
| `tab_job_run` | 30 ngày | |
| `tab_google_outbox` | `done`: 7 ngày; `failed`, `conflict`: 30 ngày | |
| `tab_audit_log` | 365 ngày (`AUDIT_LOG_RETENTION_DAYS`) | |
| `tab_place_cache` | Hàng vô thời hạn; `lat`, `lng`, `formatted_address` đặt rỗng khi `fetched_at` quá 30 ngày | Theo điều khoản Places API |
| `tab_route_cache` | Tới `expires_at` | |
| `tab_trip_stop.lat`, `lng` có `coord_source = google` | Làm mới khi mở chuyến có `coord_fetched_at` quá 30 ngày | Job dọn đặt rỗng tọa độ quá 60 ngày chưa được làm mới |
| `tab_expense`, `tab_task`, `tab_event`, `tab_contact` | Tới khi người dùng xóa; dòng xóa mềm giữ 30 ngày rồi xóa cứng | |
| `tab_file` | `pending_upload` quá 24 giờ: xóa; `deleted`: xóa đối tượng R2 rồi xóa dòng sau 7 ngày; `user_export`: 7 ngày | |
| `tab_gmail_draft` | `sent`, `discarded`: 30 ngày | |
| `tab_profile_memory_revision` | 50 bản mới nhất mỗi người | |
| `tab_note`, `tab_trip`, `tab_expense_category`, `tab_inbox_rule`, `tab_setting`, `tab_listened_app`, `tab_consent` | Tới khi người dùng xóa | Bảng con theo `CASCADE` |
| `tab_device` | Không xóa; thu hồi bằng `revoked_at` | |
| `tab_app_release` | Giữ mọi dòng; tệp APK trên R2 giữ 10 bản mới nhất | |
| Bản sao lưu DB trên R2 | **5 bản**, gồm bản hằng tuần (chủ nhật 02:00) và bản trước mỗi migration (QĐ-16) | Job `backup_database` và script deploy |

Hệ quả của QĐ-16 và QĐ-17: tin của người khác tồn tối đa 180 ngày trong DB, cộng tối đa khoảng 5 tuần trong bản sao lưu. Ghi rõ trong thông báo cho thành viên (`60-bao-mat-rieng-tu.md`).

**Ngắt kết nối Google** (`keep_data` do người dùng chọn, 40 mục 3.6): xóa token, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox`, đặt `tab_google_account.status = 'revoked'` rồi xóa dòng. Với `keep_data = true`: sự kiện, việc giữ lại, cột `google_*` đặt rỗng, `sync_status = 'local_only'`; danh bạ và thư Gmail trong hộp tin vẫn bị xóa (là bản sao dữ liệu Google, không còn cập nhật). Với `keep_data = false`: xóa thêm sự kiện có `source = 'google'`.

**Xóa tài khoản** (`DELETE /me`): ghi `tab_audit_log` trước, rồi xóa `tab_user`; `CASCADE` dọn mọi bảng; việc `user_delete_files` xóa tệp R2 theo tiền tố `u/<user_id>/`. Bản sao lưu cũ còn dữ liệu tới khi bị thay hết (tối đa 5 bản).

### 3.16 Bảng V2 và V3 (phác thảo)

**`tab_health_daily`** (V2, module `health`): cột chung; `local_date date NN`; `steps int`; `sleep_minutes int`; `resting_heart_rate smallint`; `source text`; UQ `(user_id, local_date)`. Ghi từ `POST /device/health`.

**`tab_dev_job`** (V3, core): cột chung; `prompt text NN`; `branch text`; `worktree_path text`; `status text CK queued, running, awaiting_approval, approved, rejected, deployed, failed, rolled_back`; `summary text`; `cost_usd numeric(12,6)`; `commit_sha text`; `approved_by bigint FK tab_user`; `approved_at`, `deployed_at timestamptz`; `deploy_result text`; `error text`.

### 3.17 Bảo vệ lớp hai: Row-Level Security

Theo `80-ra-cheo-lan-1.md` mục B (*kỹ thuật tự chốt được*) và QĐ-25: **bật RLS cho mọi bảng nghiệp vụ trước khi có người dùng thứ hai dùng hộp tin**. Hiện chỉ một người dùng (QĐ-15) nên V1.0 tới lúc đó chưa bật. Cách bật đã chốt sẵn để không phải thiết kế lại:

- Mỗi giao dịch của ứng dụng chạy `SET LOCAL app.user_id = <id>` ngay sau khi mở (dependency `get_session` và mỗi đơn vị việc của worker).
- Chính sách `USING (user_id = current_setting('app.user_id')::bigint)` trên mọi bảng có `user_id` NN.
- Việc hệ thống cần đọc nhiều người (dọn dữ liệu, quét đồng bộ) chạy bằng vai trò DB riêng có `BYPASSRLS`, chỉ dùng trong `worker`.
- Bài kiểm chéo người dùng thêm ca: truy vấn thô không lọc `user_id` chỉ thấy dòng của người đang chạy.

### 3.18 Quy ước migration Alembic

**Chạy lệnh:** mọi lệnh Alembic chạy trong container, không cài Alembic trên máy (QĐ-14):

| Việc | Lệnh |
|---|---|
| Chạy migration ở máy cá nhân hoặc VPS | `docker compose --profile migrate run --rm migrate` (dịch vụ `migrate` của `50-ha-tang-trien-khai.md` mục 3.4) |
| Tạo migration mới | `docker compose run --rm api alembic revision --autogenerate -m "<mô tả>"` |
| Kiểm trong CI và bài kiểm | `docker compose -f infra/docker-compose.test.yml run --rm test alembic ...` |

**Cấu trúc:**

- Một lịch sử thẳng, một `head`.
- `alembic/env.py` nạp model của `core`, `ai`, `integrations/google` và mọi module trong `ENABLED_MODULES`.
- Tên tệp: `YYYYMMDD_HHMM_<module>_<mô tả ngắn>.py` (đặt `file_template` trong `alembic.ini`).
- `MetaData` dùng quy ước đặt tên ràng buộc:

| Loại | Mẫu |
|---|---|
| Chỉ mục | `ix_%(table_name)s_%(column_0_N_name)s` |
| Duy nhất | `uq_%(table_name)s_%(column_0_N_name)s` |
| Kiểm | `ck_%(table_name)s_%(constraint_name)s` |
| Khóa ngoại | `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` |
| Khóa chính | `pk_%(table_name)s` |

**Migration đầu tiên** (`..._core_init.py`): phần mở rộng `unaccent`, `pg_trgm`, `citext`; cấu hình tìm kiếm `troly_vn`; bảng của `core`, `ai`, `setting`, `memory`, `chat`, `file`, `tab_device`.

**Luật viết:**

1. `autogenerate` để nháp, **luôn đọc lại bằng tay**. Autogenerate không thấy: cột sinh `tsvector`, chỉ mục một phần phức tạp, đổi `CHECK`, phần mở rộng, cấu hình tìm kiếm, chính sách RLS. Những thứ này viết tay bằng `op.execute`.
2. Mỗi migration có `upgrade` và `downgrade`. `downgrade` làm mất dữ liệu thì ghi chú ở đầu tệp.
3. Đổi cấu trúc và chuyển dữ liệu tách hai migration.
4. **Không sửa migration đã chạy trên VPS.**
5. **Tương thích ngược với bản mã ngay trước** (`50-ha-tang-trien-khai.md` mục 3.9): thêm cột cho phép rỗng hoặc có mặc định; đổi tên, xóa cột làm qua hai lần deploy; chỉ mục trên bảng lớn tạo `CONCURRENTLY`.
6. Thêm cột `NOT NULL` vào bảng có dữ liệu phải có `server_default` hoặc chép dữ liệu trước.
7. Mỗi agent chỉ thêm migration cho bảng của module mình. Hai migration cùng cha thì điều phối nối bằng `alembic merge` trước khi gộp.
8. Script deploy sao lưu (tính vào 5 bản, QĐ-16) rồi mới chạy `migrate`.

**Kiểm trong CI:** `upgrade head` trên `db-test` trống; với migration mới nhất `downgrade -1` rồi `upgrade head`; `alembic check` không lệch model (`70-kiem-thu.md` `test_migrations.py`).

## 4. Dữ liệu cần

Tệp này là nơi gom dữ liệu cần của mọi module. Lần gộp hai đã gom đủ:

| Nguồn | Đã gom |
|---|---|
| `20-bo-nao-ai.md` mục 4 | `tab_ai_run` (bộ cột mới), `tab_message` (`system`, `hidden`, `turn_id`, `ai_run_id`), `tab_conversation` (3 cột), `tab_profile_memory_revision.reason`, `tab_pending_action` (gộp cột của `tab_ai_pending_action`), `tab_expense.parser`, `parse_confidence` |
| `30-app-android.md` mục 4.1 | `tab_device` (4 cột), `tab_device_event.kind`, `payload`, `tab_app_release.signature`, `tab_listened_app` mặc định, khóa `app.*` |
| `31-giao-dien.md` mục 4 | `require_unlock`, `conversation_key`, `ui.voice_reply`, mục *Cần xem lại* dùng `needs_review` |
| `40-tich-hop-google.md` mục 13 | `tab_google_account`, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox`, `tab_event`, `tab_task`, `tab_contact`, `tab_gmail_draft`, `tab_inbox_message.labels`, `tab_file.drive_file_id` |
| `41-ban-do-lich-trinh.md` mục 12 | `tab_trip`, `tab_trip_stop`, `tab_trip_option`, `tab_trip_fact`, `tab_place_cache`, khóa `trip.*` |
| `50-ha-tang-trien-khai.md` mục 4 | `tab_job_run.detail`, `tab_app_release.published_by`, `tab_dev_job` (5 cột) |
| `60-bao-mat-rieng-tu.md` mục 4 | `tab_audit_log`, `tab_consent`, `payload_hash`, `contains_third_party`, `redacted_at`, `private_conversation`, `inbox.ai_enabled`, `account_last4`, bỏ số dư |
| `70-kiem-thu.md` mục 4 | Danh sách bảng hệ thống (mục 3.1); không có ngoại lệ bảng con |

## 5. API hoặc giao tiếp

Bảng chỉ được đọc ghi qua `repo.py` của nơi sở hữu (mục 3.3). Module khác đọc qua service công khai ([10-kien-truc-backend.md](10-kien-truc-backend.md) mục 3.4). Chỉ `api`, `worker`, dịch vụ `migrate` và lệnh `app.cli` kết nối DB; container `troly-dev` của V3 không vào được DB.

## 6. Kiểm thử

- Chuỗi migration lên, xuống, lên và `alembic check` (mục 3.18).
- Ràng buộc: khoản chi 0 đồng bị chặn; `account_last4` khác 4 chữ số bị chặn; trùng `source_ref` bị chặn; sự kiện cả ngày thiếu `start_date` bị chặn; việc có cả `due_date` và `due_at` bị chặn; hồ sơ lõi quá 8.000 ký tự bị chặn; `tab_pending_action` thiếu `payload_hash` bị chặn.
- Tìm kiếm: ghi chú *Phước Hải* tìm bằng *phuoc hai* ra đúng.
- Dọn dữ liệu: mỗi dòng của bảng mục 3.15 có ca quá hạn và ca còn hạn; khối `contains_third_party` 181 ngày tuổi bị thay nội dung, cấu trúc khối còn nguyên; tọa độ trong `tab_place_cache` quá 30 ngày bị xóa, `place_id` còn.
- `test_user_scoping.py`: mọi bảng có `user_id` trừ danh sách bảng hệ thống ở mục 3.1.
- Ghép cặp chuyển tiền: cách 3 phút thành một dòng `transfer`; cách 30 phút thành hai dòng; giao dịch của hai người khác nhau không ghép.
- Phiên chat 04:00: tin lúc 01:00 ngày 19 thuộc phiên `local_date = 18`; tin lúc 04:01 thuộc phiên ngày 19.
- Sự kiện lặp: bản gốc RRULE hằng tuần cộng một ngoại lệ trải đúng trong khoảng 30 ngày, ngoại lệ thay đúng lần lặp.

## 7. Rủi ro

| Rủi ro | Ảnh hưởng | Cách giảm |
|---|---|---|
| Tin người khác giữ 180 ngày (QĐ-17) | Nhiều dữ liệu nhạy cảm hơn bản 1 | Đã đánh dấu `contains_third_party`; dọn đúng hạn; sao lưu mã hóa; RLS trước người dùng thứ hai |
| Trải sự kiện lặp ở máy chủ sai múi giờ hoặc sai `EXDATE` | Lịch, nhắc sai giờ | Lưu `timezone` của sự kiện; bài kiểm với RRULE thật lấy từ Google; sửa cả chuỗi thì mở Google Calendar |
| Hai agent tạo migration cùng cha | Nhiều `head` | Luật 7 mục 3.18; CI báo lỗi |
| `jsonb` không ràng buộc cấu trúc | Lệch kiểu theo thời gian | Schema Pydantic ở service |
| Bảng `tab_pending_action` dùng cho nhiều nguồn | Nhầm luật duyệt | `tool_name` là danh sách đóng; `execute_approved` khai cạnh từng công cụ; kiểm `payload_hash` |
| Quên `SET LOCAL app.user_id` khi bật RLS | Truy vấn trả rỗng | Bật RLS trên DB thử trước; bài kiểm canh |

## 8. Câu hỏi mở

1. Lịch sử chat (`tab_message`) giữ 365 ngày rồi xóa, chỉ giữ tóm tắt theo ngày (ĐX-CSDL-06, rà chéo mục B câu 7): có đồng ý không?
2. Có cần chi tiết nhiều thẻ, nhiều tài khoản cùng ngân hàng (rà chéo B câu 9)? Bản này giữ mã cố định `account` cộng `account_last4`, đủ phân biệt hai thẻ cùng ngân hàng ở mức hiển thị.
3. Tọa độ điểm dừng lấy từ Google chưa được làm mới quá 60 ngày thì đặt rỗng: đúng tinh thần điều khoản 30 ngày chưa, hay phải làm mới chủ động mỗi 30 ngày (tốn lượt gọi Places)? Chờ đọc lại *Maps Service Specific Terms* (41 câu hỏi mở 6).

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| điều phối | `01-thiet-ke-tong-the.md` mục 6: thay bảng tóm tắt bằng tham chiếu tới tệp này. `02-cau-truc-ma-nguon.md`: ghi chỗ đặt model ở mục 3.3 (`core/models.py`, `ai/models.py`, `integrations/google/models.py`) |
| agent AI | `20-bo-nao-ai.md`: đổi tên `tab_ai_pending_action` thành `tab_pending_action` (cột `tool_name`, `input`, `summary`, `payload_hash`, `require_unlock`), `tab_profile_memory_version` thành `tab_profile_memory_revision`; `tab_message.hidden`; công cụ chi tiêu dùng `kind` (`expense`, `income`, `transfer`), `account`, `account_last4` thay `direction`; bỏ `balance_after_vnd` khỏi `BankNotificationExtract`; `update_task.status` dùng `todo`/`done`/`cancelled`; luật inbox dùng `vip_sender`; đặt `contains_third_party` cho khối kết quả công cụ đọc tin người khác; lược đồ bóc tách lịch trình dẫn sang 41 mục 4.2 |
| agent app Android | `31-giao-dien.md`: mục *Cần xem lại* lọc `needs_review` (không tự so `parse_confidence`); hộp tin gom theo `conversation_key`. `30-app-android.md`: không cần thêm gì về bảng |
| agent Google | `40-tich-hop-google.md` mục 13: theo tên cột ở mục 3.12 (`bigint`, `granted_scopes`, `enabled_packs`, `access_expires_at`, `status = reauth_required`, `service`, outbox `processing`); `tab_event.description` (không `note`), `source`, `recurring_event_id`, `original_start_at`, `attendees`; bỏ `due_has_time`; `tab_inbox_message.external_id`, `thread_ref`, `importance = important`, tiêu đề thư ở `subject`; sinh nhật lưu `birthday_day`, `birthday_month`, `birthday_year`; bảng `tab_google_*` ở `integrations/google/models.py`. `41-ban-do-lich-trinh.md`: khóa cài đặt `trip.night_start`... (dấu chấm) |
| agent hạ tầng | `60-bao-mat-rieng-tu.md`: hạn giữ 180 ngày theo QĐ-17 (thay 30 ngày ở mục 3.9), sao lưu 5 bản (QĐ-16), bỏ ngoại lệ bảng con không có `user_id` (mục 3.11), hạn duyệt 24 giờ kèm `payload_hash`. `70-kiem-thu.md`: `test_retention.py` theo bảng mục 3.15; bỏ ngoại lệ bảng con; mẫu kiểm dùng `kind: transfer`. `50-ha-tang-trien-khai.md`: `backup_database` hằng tuần, `BACKUP_KEEP=5` |

## 10. Đề xuất quyết định

| Số | Đề xuất | Trạng thái |
|---|---|---|
| ĐX-CSDL-01 | Khóa chính `bigint identity`; id máy khách sinh là `uuid` ở cột riêng | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-02 | Liệt kê dùng `text` + `CHECK` | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-03 | `tab_expense` dùng `kind` + `account`; thêm `account_last4`, bỏ số dư | Đã duyệt theo QĐ-25, QĐ-22 |
| ĐX-CSDL-04 | Không có bảng nhắc riêng; nhắc tính từ `tab_event.remind_minutes` với `remind_source = app` | Đã duyệt theo QĐ-25 (sửa theo ĐX-G6) |
| ĐX-CSDL-05 | `tab_trip.status`: `importing`, `draft`, `evaluating`, `planned`, `done`, `failed` | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-06 | `tab_message` giữ 365 ngày; khối tin người khác thay nội dung sau 180 ngày | Phần 180 ngày theo QĐ-17; phần 365 ngày chờ người dùng |
| ĐX-CSDL-07 | Tìm toàn văn bằng cấu hình `troly_vn` | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-08 | Một lịch sử migration thẳng, tên tệp có ngày giờ và module | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-09 | Thêm bảng ngoài thiết kế tổng thể, gồm cả `tab_google_oauth_state`, `tab_gmail_draft`, `tab_trip_fact`, `tab_audit_log`, `tab_consent` | Đã duyệt theo QĐ-25 |
| ĐX-CSDL-10 | **Mới.** Sự kiện lặp lưu bản gốc có `recurrence` cộng ngoại lệ (`singleEvents=false`), máy chủ tự trải lần lặp; không dùng `singleEvents=true` như bản 1 và đề xuất ở rà chéo A1 dòng 11 | Lý do: đồng bộ tăng dần bằng `syncToken` không cho kèm `timeMin`, `timeMax`, nên `singleEvents=true` sẽ trải cả chuỗi lặp vô hạn trong lần đồng bộ đủ; cách của 40 có nguồn tài liệu Google. Chờ điều phối xác nhận |
| ĐX-CSDL-11 | **Mới.** `tab_task.sync_status = remote_deleted` khi Google Tasks báo đã xóa; người dùng chọn xóa hay giữ | Cụ thể hóa QĐ-21 |
| ĐX-CSDL-12 | **Mới.** Sự kiện có khách mời chỉ ghi vào `tab_event` sau khi duyệt; dữ liệu chờ nằm trong `tab_pending_action.input` | Cụ thể hóa QĐ-23; không có sự kiện nửa vời trên Google |
| ĐX-CSDL-13 | **Mới.** RLS bật trước khi có người dùng thứ hai dùng hộp tin, theo cách ở mục 3.17 | Theo rà chéo mục B (kỹ thuật tự chốt) |
