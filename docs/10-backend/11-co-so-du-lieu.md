# Cơ sở dữ liệu

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 3, gọn theo QĐ-27, sửa theo `81-ra-cheo-lan-2.md` (QĐ-26) và các hợp đồng đã chốt ở `bang-viec.md` mục 4.

Tệp này là **nguồn chuẩn cho tên bảng và tên cột** (QĐ-25). Tài liệu khác lệch thì sửa theo tệp này.

## 1. Mục tiêu

Một chỗ mô tả toàn bộ bảng, chính sách xóa, thời hạn giữ và quy ước migration.

## 2. Phạm vi

Bảng PostgreSQL 16 cho V1.0 tới V1.8. Không gồm bảng Room trên máy (`30-app-android.md`) và tệp trên R2.

## 3. Thiết kế

### 3.1 Quy ước chung

| Mục | Quy ước |
|---|---|
| Tên bảng | `tab_`, số ít, snake_case |
| Khóa chính | `id bigint generated always as identity`; id máy khách sinh là `uuid` ở cột riêng |
| Cột chung | **(cột chung)** = `id`, `user_id bigint NN FK tab_user ON DELETE CASCADE`, `created_at`, `updated_at` (`timestamptz NN default now()`). Hiện một người dùng (QĐ-27) nhưng mọi bảng nghiệp vụ, kể cả bảng con, vẫn có `user_id` |
| Thời gian | `timestamptz` lưu UTC; `date` cho ngày; `time` cho giờ trong ngày |
| Tiền | `bigint` hậu tố `_vnd`; chi phí AI `numeric(12,6)` hậu tố `_usd` |
| Liệt kê | `text` + `CHECK`, không dùng `enum` |
| JSON | `jsonb`, qua schema Pydantic ở service trước khi ghi |
| Xóa mềm | `deleted_at` ở `tab_expense`, `tab_task`, `tab_event`, `tab_note`, `tab_file`, `tab_contact`: xóa một dòng làm ngay, *Hoàn tác* được trong 30 ngày (QĐ-27). Bảng khác xóa cứng |
| Tìm toàn văn | Cột sinh `search_vector tsvector GENERATED ALWAYS AS (to_tsvector('troly_vn', ...)) STORED` + GIN. `troly_vn` = `simple` + `unaccent`: gõ không dấu vẫn ra (QĐ-27 mục 11) |
| Ký hiệu | `NN` not null; `FK` khóa ngoại; `UQ` duy nhất; `CK` check |

Phần mở rộng tạo ở migration đầu: `unaccent`, `pg_trgm`, `citext`. `pgvector` chỉ thêm khi cần tìm theo nghĩa.

**Bảng hệ thống** (không có `user_id` hoặc cho phép rỗng): `tab_user`, `tab_place_cache`, `tab_route_cache`, `tab_job_schedule`, `tab_job_run`, `tab_ai_run` (rỗng với việc hệ thống).

### 3.2 Nơi đặt model và bản

| Nơi đặt | Bảng | Bản |
|---|---|---|
| `core/models.py` | `tab_user`, `tab_auth_session`, `tab_job_queue`, `tab_job_schedule`, `tab_job_run` | V1.0 |
| `ai/models.py` | `tab_ai_run` | V1.0 |
| `modules/setting` | `tab_setting` | V1.0 |
| `modules/memory` | `tab_profile_memory`, `tab_profile_memory_revision`, `tab_note` | V1.0 |
| `modules/chat` | `tab_conversation`, `tab_message`, `tab_pending_action` | V1.0 |
| `modules/file` | `tab_file` (V1.0); `tab_file_text` (V1.1) | |
| `modules/device` | `tab_device` (V1.0); `tab_listened_app`, `tab_device_event` (V1.2) | |
| `modules/expense` | `tab_expense_category`, `tab_expense` | V1.1 |
| `modules/inbox` | `tab_inbox_message`, `tab_inbox_rule` (V1.3); `tab_contact`, `tab_gmail_draft` (V1.8) | |
| `modules/calendar`, `modules/task` | `tab_event`, `tab_task` | V1.4 |
| `integrations/google/models.py` | `tab_google_account`, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox` | V1.4 |
| `modules/trip` | `tab_trip`, `tab_trip_stop`, `tab_trip_option`, `tab_trip_fact`, `tab_place_cache`, `tab_route_cache` | V1.6 |
| `modules/report` | `tab_export` | V1.7 |
| `modules/health` | `tab_health_daily`: (cột chung), `local_date`, `steps`, `sleep_minutes`, `resting_heart_rate`; UQ `(user_id, local_date)` | V2 |

Bỏ theo QĐ-27: `tab_audit_log`, `tab_consent`, `tab_app_release` (bản APK đọc từ tệp kê trên R2, `50-ha-tang-trien-khai.md` chốt), `tab_dev_job` (thiết kế khi tới V3).

### 3.3 Core

**`tab_user`**: `id`; `name text NN`; `email citext NN UQ`; `password_hash text NN` (bcrypt); `timezone text NN default 'Asia/Ho_Chi_Minh'`; `last_login_at`, `password_changed_at`; `created_at`, `updated_at`. Một dòng, tạo bằng `app.cli create-owner`. Không có vai trò, không khóa khi sai mật khẩu (QĐ-27).

**`tab_auth_session`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| refresh_token_hash | text NN UQ | SHA-256 |
| label | text | *Galaxy S25+, app 1.2.0* |
| last_used_at | timestamptz | |
| expires_at | timestamptz NN | 365 ngày (QĐ-27) |
| revoked_at | timestamptz | |
| previous_token_hash | text | Mã làm mới liền trước; chỉ mục một phần khi khác rỗng |
| rotated_at | timestamptz | Lúc xoay mã gần nhất |
| current_token_enc, current_token_key_version | bytea, smallint | Mã làm mới hiện tại mã hóa Fernet (`TOKEN_ENCRYPTION_KEYS`) để trả lại khi ân hạn |

Ân hạn xoay mã (lỗi cài đè APK 19/11): mã vừa bị xoay mà dùng lại trong 60 giây, cùng phiên chưa thu hồi, thì trả lại đúng cặp kế tiếp (mã truy cập mới, cùng mã làm mới); ngoài 60 giây hoặc mã cũ hơn một lần xoay thì 401 như cũ.

**`tab_job_queue`**: việc dài chạy nền.

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| kind | text NN | `trip_import`, `trip_evaluate`, `google_initial_sync` |
| payload | jsonb NN default `{}` | |
| status | text NN CK `pending`, `processing`, `done`, `failed`, `cancelled` | |
| attempts, max_attempts | smallint NN default 0, 3 | |
| next_attempt_at | timestamptz NN default now() | |
| locked_at, started_at, finished_at | timestamptz | |
| result | jsonb | |
| error | text | Câu tiếng Việt |
| dedupe_key | text | UQ một phần `(user_id, dedupe_key) WHERE status IN ('pending','processing')` |

Chỉ mục `(status, next_attempt_at) WHERE status = 'pending'`. Sự kiện máy chủ chặn vì OTP lưu `payload = {}`, `status = ignored`, `error = OTP_DETECTED` để đếm `otp_blocked_server`, không giữ nội dung.

**`tab_job_schedule`**: `name text PK`; `next_run_at NN`; `last_started_at`, `last_finished_at`; `last_status` CK `ok`, `error`, `skipped`; `last_error`; `last_duration_ms`; `updated_at`.

**`tab_job_run`**: `id`; `job_name NN`; `started_at NN`; `finished_at`; `status` CK `running`, `ok`, `error`; `items_processed int NN default 0`; `detail jsonb` (sao lưu: khóa R2, kích thước, `sha256`, số dòng bảng chính); `error`. Chỉ mục `(job_name, started_at DESC)`.

**`tab_client_log`** (QĐ-30): lỗi giao diện và lỗi gọi API do app gửi về. `id`; `user_id FK CASCADE` (rỗng được: lỗi trước khi đăng nhập); `device_id bigint`; `level` CK `error`, `warn`, `info`; `kind text NN` (`ui_error`, `api_error`, `native_error`...); `screen`; `message text NN`; `detail jsonb`; `app_version`; `occurred_at NN`; `created_at`. Chỉ mục `(created_at)`. Giữ 30 ngày.

### 3.4 Setting

**`tab_setting`**: PK `(user_id, key)`; `value jsonb NN`; `updated_at`. Khóa hợp lệ khai trong `setting/service.py`, khóa lạ bị 400.

| Khóa | Mặc định |
|---|---|
| `ui.voice_reply` | `false` |
| `calendar.default_remind_minutes` | `[15]`; tạo sự kiện không ghi phút nhắc mà mốc mặc định đã qua (*3 phút nữa*) thì nhắc đúng giờ (`[0]`) |
| `calendar.week_start` | `1` (thứ Hai) |
| `expense.default_account` | `cash` |
| `inbox.ai_enabled` | `true` (tắt thì hộp tin không gửi Claude) |
| `notify.new_transaction` | `false`: máy báo khi ghi giao dịch mới (QĐ-38) |
| `notify.important_message` | `true`: máy báo khi có tin quan trọng (QĐ-38) |
| `notify.chat_done` | `true`: lượt chat xong khi app không ở màn hình thì máy báo (QĐ-41) |
| `notify.booking_added` | `true`: đặt chỗ tự thêm vào Lịch từ thư xác nhận thì máy báo, có nút Hoàn tác (QĐ-49) |
| `calendar.app_reminds_google` | `false`: bật thì app nhắc cả sự kiện tạo trên Google, theo `remind_minutes` của sự kiện hoặc mặc định (QĐ-38) |
| `inbox.quiet_hours` | `null` |
| `gmail.categories` | `"primary_updates"`: mục Gmail vào hộp tin, `primary` (chỉ Chính), `primary_updates` (Chính và Cập nhật), `all` (trừ Quảng cáo, Mạng xã hội); thư `IMPORTANT` luôn vào, `SPAM`, `TRASH` luôn bỏ; đổi thì quét lại 7 ngày (`gmail.rescan_inbox`), thư đã có không ghi trùng |
| `trip.default_travel_mode` | `motorbike` |
| `trip.night_start`, `trip.night_end` | `18:00`, `05:30` |
| `trip.ride_break_minutes` | `90` |
| `trip.speed_factor` | `1.2` |
| `trip.ferries` | `[]`; tối đa 10 bến `{name, place_query, first_time (HH:MM), last_time (HH:MM), hotline, note, updated_at (YYYY-MM-DD)}`, giờ phà quen cho luật R3 (41 mục 5.4) |

Bỏ `app.lock_enabled`, `app.lock_after_minutes` (QĐ-27 bỏ khóa vân tay).

### 3.5 Device

**`tab_device`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| name | text NN | |
| manufacturer, model, os_version | text | `manufacturer` để hiện bước *Không bao giờ ngủ* của Samsung |
| token_hash | text NN UQ | SHA-256 mã thiết bị |
| token_prefix | text NN | 8 ký tự đầu |
| app_version_code | int | |
| app_version_name | text | |
| default_sms_package | text | Gói SMS mặc định thật, để máy chủ biết `sms_default` là gói nào (K14) |
| notification_access, listener_connected, notifications_enabled, exact_alarm_allowed, battery_optimization_ignored | boolean | Màn *Kiểm tra máy* |
| queue_size | int | |
| otp_blocked_today | int | Bộ đếm của lớp lọc trên máy |
| last_seen_at, last_event_at, silent_warned_at | timestamptz | |
| revoked_at | timestamptz | Thu hồi, không xóa dòng |

**`tab_listened_app`**: (cột chung); `package_name text NN`; `label text NN`; `purpose` CK `expense`, `inbox`; `parser` CK `vcb`, `tcb`, `momo`, `zalo`, `telegram`, `messenger`, `sms`, `generic`; `enabled boolean NN default true`; `is_default boolean NN default false`. UQ `(user_id, package_name)`.

Dòng tạo sẵn: `com.VCB` (expense, vcb), `vn.com.techcombank.bb.app` (expense, tcb), `com.mservice.momotransfer` (expense, momo), `com.zing.zalo`, `org.telegram.messenger`, `com.facebook.orca` (inbox), `sms_default` (inbox, sms). QĐ-42: hộp tin bỏ Telegram, Messenger: hai dòng đó vẫn tạo nhưng mặc định `enabled = false` (migration `0010_inbox_apps` tắt cho người dùng hiện có); tin cũ không xóa, hộp tin, tìm, tóm tắt, đếm tin, thông báo chỉ lấy tin của app đang bật. `sms_default` là **một dòng**: plugin thay bằng gói SMS mặc định của máy (Samsung Messages hoặc Google Messages trên Galaxy S25+, QĐ-19) và tự theo khi người dùng đổi app SMS mặc định (K14). Khi gói `gmail` của Google đã nối, `/device/config` bỏ `com.google.android.gm`. Danh sách chỉ đổi trên màn Cài đặt.

**`tab_device_event`**: hàng đợi sự kiện từ điện thoại.

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| device_id | bigint NN FK `tab_device` CASCADE | |
| client_event_id | uuid NN | UQ `(device_id, client_event_id)` |
| kind | text NN CK `notification`, `reminder_action` | |
| app_package | text | NN khi `notification` |
| posted_at | timestamptz NN | |
| payload | jsonb NN | Bảng dưới |
| received_at | timestamptz NN default now() | |
| status | text NN CK `pending`, `processing`, `done`, `ignored`, `failed` | |
| attempts | smallint NN default 0 | |
| next_attempt_at | timestamptz NN default now() | |
| locked_at, processed_at | timestamptz | |
| result_kind | text CK `expense`, `inbox_message`, `transfer_merged`, `task_updated`, `none` | |
| result_id | bigint | Không khóa ngoại |
| error | text | |

Chỉ mục `(status, next_attempt_at) WHERE status = 'pending'`.

| `kind` | `payload` (theo `30-app-android.md` mục 5.1; không trường nào khác rời máy) |
|---|---|
| `notification` | `title`, `text`, `conversation_title`, `messages[]` (`sender`, `text`, `at`), `is_group_conversation`, `category`, `notification_key_hash`, `hidden_content` |
| `reminder_action` | `reminder_key`, `source` (`event`, `task`), `source_id`, `action` (`done`, `ack`, `snooze`), `at` |

### 3.6 Memory

**`tab_profile_memory`**: (cột chung, `user_id` UQ); `content text NN default ''` CK `char_length(content) <= 8000`; `version int NN default 1`; `updated_by` CK `user`, `ai`.

**`tab_profile_memory_revision`**: `id`; `user_id NN FK`; `version int NN` (bản trước lần sửa); `content text NN`; `changed_by` CK `user`, `ai`; `reason text` (`remember`, `forget`, `manual_edit`, `restore`); `created_at`. UQ `(user_id, version)`. Giữ 50 bản mới nhất.

**`tab_note`**: (cột chung); `title text NN` tối đa 200; `body text NN default ''` tối đa 20.000; `tags text[] NN default '{}'`; `source` CK `user`, `ai`; `deleted_at`; `search_vector` từ `title`, `body`, `tags`. GIN `search_vector`, GIN `tags`.

### 3.7 Chat và AI

**`tab_conversation`**: mỗi người mỗi ngày một phiên.

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | UQ `(user_id, local_date)` |
| local_date | date NN | Tách lúc 04:00 giờ người dùng (QĐ-20): `date(giờ địa phương - 4 giờ)` |
| started_at, last_message_at | timestamptz | |
| summary | text | Không chép nguyên văn tin của người khác |
| summary_upto_id | bigint | |
| last_prompt_tokens | int | |
| compacted_count | int NN default 0 | |
| day_summary_done | boolean NN default false | |
| message_count | int NN default 0 | |

**Nối phiên** (QĐ-27 mục 12): tin mới cách tin cuối của phiên trước dưới 3 giờ thì lịch sử gửi Claude của phiên mới (vẫn là dòng mới theo `local_date`) mang thêm 10 tin hiện cuối của phiên trước, dù đã qua 04:00. Luật nằm ở `chat/service.py`, không thêm cột.

**`tab_message`**: lưu nguyên khối nội dung Claude, chỉ nối thêm.

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| conversation_id | bigint NN FK CASCADE | |
| turn_id | uuid NN | Gom tin của một lượt |
| role | text NN CK `user`, `assistant`, `system` | |
| content | jsonb NN | Khối Claude, không chuẩn hóa |
| text | text | Chữ hiển thị |
| hidden | boolean NN default false | Tin `system`, tin chỉ có công cụ |
| model | text | Tin `assistant`: model đã dùng (QĐ-27 mục 9) |
| citations | jsonb | Tin `assistant` có tìm web: `[{title, url}]`, tối đa 5 |
| status | text NN CK `complete`, `failed` | |
| client_message_id | uuid | UQ một phần `(user_id, client_message_id)` |
| attachment_file_ids | bigint[] NN default `{}` | |
| actions | jsonb | Hành động trả cho app |
| contains_third_party | boolean NN default false | Khối có tin, thư của người khác |
| redacted_at | timestamptz | |
| notify_done | boolean NN default false | Lượt xong khi app đã ngắt (SSE chưa đọc `message.completed` sau 5 giây); chỉ tin có cờ này mới ra notice `chat_done` |
| ai_run_id | bigint FK `tab_ai_run` SET NULL | |
| input_tokens, output_tokens | int | |
| search_vector | tsvector | Sinh từ `text` |

Chỉ mục `(conversation_id, id)`; GIN `search_vector` một phần `WHERE hidden = false`; `(created_at) WHERE contains_third_party AND redacted_at IS NULL`.

**`tab_pending_action`**: chỉ cho việc **gửi ra ngoài** (gửi thư, mời khách, chia sẻ tệp, V2 trả lời tin) và **xóa hàng loạt hoặc xóa cả chuyến** (QĐ-27 mục 2).

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| conversation_id, message_id | bigint FK SET NULL | |
| tool_name | text NN | `delete_expense`, `delete_task`, `delete_event` (từ 2 mục), `delete_trip`, `add_event`, `update_event` (có khách mời), `send_gmail_draft`, `share_drive_file` (QĐ-38); kiểm trong mã theo registry, không có CHECK trong DB |
| input | jsonb NN | Đầu vào đã kiểm |
| payload_hash | text NN | SHA-256 của `tool_name` + `input` chuẩn hóa (K7) |
| title, summary | text NN | |
| details | jsonb NN default `[]` | `[{label, value}]` |
| danger | boolean NN default false | |
| status | text NN CK `pending`, `done`, `failed`, `rejected`, `expired` | |
| expires_at | timestamptz NN | 24 giờ |
| decided_at | timestamptz | |
| result | jsonb | |
| error | text | |

Không có `kind`, `payload` (K7), `require_unlock` (QĐ-27 bỏ vân tay).

**`tab_ai_run`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| id | bigint PK | |
| user_id | bigint FK CASCADE | Rỗng với việc hệ thống |
| purpose | text NN CK `chat`, `compaction`, `bank_extract`, `file_extract`, `trip_extract`, `trip_evaluate`, `eval` | |
| mode | text CK `chat`, `think`, `research`, `summary` | Lượt chat; chọn model theo `20-bo-nao-ai.md` mục 3.1 |
| model | text NN | |
| effort | text | |
| conversation_id | bigint FK SET NULL | |
| input_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cache_read_tokens, output_tokens | int NN default 0 | |
| web_search_requests | int NN default 0 | Công cụ tìm web của Claude, tính tiền riêng |
| fallback_used | boolean NN default false | Sonnet, Opus dùng dự phòng phía máy chủ |
| cost_usd | numeric(12,6) NN | |
| rate_card | text CK `le_100k`, `gt_100k` | |
| stop_reason, refusal_category, request_id, error_code | text | |
| latency_ms | int | |
| created_at | timestamptz NN | |

Chỉ mục `(user_id, created_at)`; `(created_at)` cho cảnh báo `AI_MONTHLY_USD`.

### 3.8 File

**`tab_file`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| r2_key | text NN UQ | Bucket `assistant`, khóa `files/u/<user_id>/<năm>/<tháng>/<uuid>` |
| original_name | text | |
| mime | text NN | |
| size_bytes | bigint NN CK `> 0` | |
| sha256 | text | |
| purpose | text NN CK `chat_attachment`, `voice`, `document`, `trip_source`, `trip_export`, `report_export`, `other` | |
| status | text NN CK `pending_upload`, `ready`, `deleted` | |
| extract_status | text NN CK `none`, `pending`, `done`, `failed`, `skipped` default `none` | Hàng đợi của job `extract_file_text` |
| drive_file_id | text | |
| drive_web_view_link | text | Link mở tệp trên Drive (thư mục *Trợ lý*) |

Tệp bot xuất (QĐ-41): `file/render.py` dựng PDF (fpdf2, font DejaVu Sans trong image), Word (python-docx), Excel (openpyxl, mỗi bảng một trang tính, cột số là số); `file.service.save_generated_file(session, user, fmt, title, blocks)` lưu `files/` với `purpose = document`, tên tệp là tiêu đề bỏ dấu.
| deleted_at | timestamptz | |

Chỉ mục `(user_id, purpose, created_at DESC) WHERE status = 'ready'`; `(extract_status) WHERE extract_status = 'pending'`.

**`tab_file_text`**: chữ trích để tìm. `file_id bigint PK FK tab_file CASCADE`; `user_id NN`; `content text NN` (cắt 200.000 ký tự); `method` CK `docx`, `pdf_text`, `ai_ocr`, `plain` (tệp chữ); `page_count int`; `extracted_at timestamptz NN`; `search_vector` sinh từ `content` (GIN). Do job `extract_file_text` ghi (`10-kien-truc-backend.md` mục 3.9): Word bằng python-docx, PDF có lớp chữ bằng pypdf, ảnh và PDF quét (tối đa 20 trang) nhờ Haiku chép chữ (`purpose = file_extract`).

### 3.9 Expense

**`tab_expense_category`**: (cột chung); `name NN`; `keywords text[] NN default '{}'`; `kind` CK `expense`, `income`; `sort_order smallint`; `is_archived boolean`. UQ `(user_id, lower(name))`. Bộ mặc định có `Khác`.

**`tab_expense`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| amount_vnd | bigint NN CK `> 0` | |
| kind | text NN CK `expense`, `income`, `transfer` | `transfer` không tính vào chi |
| account | text NN CK `vcb`, `tcb`, `momo`, `cash`, `card`, `other` | |
| account_last4 | text CK `^[0-9]{4}$` | Không lưu số đầy đủ, không lưu số dư (QĐ-22) |
| to_account, to_account_last4 | text | Chỉ với `transfer`; CK `kind <> 'transfer' OR to_account IS NOT NULL` |
| category_id | bigint FK SET NULL | |
| merchant, place, note | text | |
| spent_at | timestamptz NN | |
| source | text NN CK `chat`, `bank_notification`, `manual` | |
| source_ref | text | UQ một phần `(user_id, source_ref)` |
| transfer_peer_ref | text | UQ một phần `(user_id, transfer_peer_ref)` |
| device_event_id | bigint FK SET NULL | |
| parser | text | `regex:<tên>`, `ai`, `chat`, `manual` |
| parse_confidence | numeric(3,2) | |
| needs_review | boolean NN default false | `parse_confidence < 0.7` hoặc chưa có danh mục |
| deleted_at | timestamptz | |

Chỉ mục `(user_id, spent_at DESC) WHERE deleted_at IS NULL`; `(user_id) WHERE needs_review AND deleted_at IS NULL`.

**Ghép cặp chuyển nội bộ**: tiền ra ngân hàng và tiền vào MoMo (hoặc ngược lại) cùng số tiền, cách nhau tối đa 10 phút, chưa ghép: dòng có sẵn đổi thành `transfer`, điền `to_account`, `transfer_peer_ref`; sự kiện thứ hai ghi `result_kind = transfer_merged`. Nạp ví MoMo từ ngân hàng, rút ví về ngân hàng luôn là `transfer` kể cả khi chưa thấy thông báo bên kia; hai giao dịch MoMo không ghép với nhau. Chống trùng: `source_ref = <gói>:<băm tiêu đề, nội dung, giờ giao dịch trong nội dung (hoặc phút hiện thông báo)>`; thông báo thứ hai của cặp lưu ở `transfer_peer_ref`. Mẫu cố định ở `modules/expense/bank.py`, `parser = regex:<vcb|tcb|momo>`; mẫu lạ gửi Haiku sau khi che (`parser = ai`, `parse_confidence < 0.7` vào *Cần xem lại*).

### 3.10 Inbox, danh bạ, nháp Gmail

**`tab_inbox_message`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| source | text NN CK `notification`, `gmail` | |
| app | text NN CK `zalo`, `telegram`, `messenger`, `sms`, `gmail`, `other` | |
| app_package | text | |
| device_id, device_event_id | bigint FK SET NULL | |
| sender | text | |
| sender_key | text NN | `<app>:<tên đã chuẩn hóa>` |
| conversation_key | text NN | Băm `(app, conversation_title hoặc sender_key)`; Gmail theo `thread_ref` |
| conversation_title | text | |
| is_group | boolean NN default false | |
| account_email | citext | Thư Gmail của tài khoản nào (QĐ-50, nhiều tài khoản); tin thông báo máy để trống. Gỡ tài khoản kèm `delete_messages` thì xóa tin của email đó (migration `0015_inbox_account`) |
| contact_id | bigint FK `tab_contact` SET NULL | |
| subject | text | Thư Gmail |
| text | text NN, tối đa 4.000 | Gmail: đoạn trích |
| hidden_content | boolean NN default false | |
| posted_at | timestamptz NN | |
| status | text NN CK `new`, `seen`, `done` | |
| importance | text NN CK `normal`, `important` | |
| importance_reason | text | |
| external_id, thread_ref | text | Gmail |
| labels | text[] NN default `{}` | |
| dedupe_hash | text NN | UQ `(user_id, dedupe_hash)` |
| search_vector | tsvector | Từ `sender`, `conversation_title`, `subject`, `text` |

Nhóm Zalo không đặt `conversation_title`, `is_group_conversation`: tiêu đề `Nhóm: <tên>` hoặc `Group: <tên>` là nhóm, `conversation_title` lấy phần sau tiền tố, người gửi lấy từ `messages[].sender`, thiếu thì tách `Tên: nội dung` trong chữ. Tiêu đề trùng tên app (`Zalo`, `Telegram`, `Messenger`) là thông báo của chính app, không vào hộp tin. Mẫu ở `testdata/inbox-notifications/`; `python -m app.cli export-inbox-samples` xuất dạng thông báo thật đã thay tên và nội dung, `reparse-inbox [--since <ngày ISO>]` bóc tách lại hộp tin từ `tab_device_event` gốc sau khi sửa luật (chạy lại không nhân đôi, giữ trạng thái đã xem; tên cũ `reprocess-inbox` vẫn dùng được). UQ một phần `(user_id, external_id) WHERE source = 'gmail'`. Chỉ mục `(user_id, conversation_key, posted_at DESC)`; `(user_id, status, importance, posted_at DESC)`; GIN `search_vector`.

**`tab_inbox_rule`**: (cột chung); `kind` CK `vip_sender`, `urgent_keyword`, `muted_sender`, `muted_keyword`, `muted_app`, `private_conversation`; `value text NN`; `app text`; `contact_id FK SET NULL`. UQ `(user_id, kind, lower(value), coalesce(app,''))`. `private_conversation`: tin vào hộp tin nhưng không gửi Claude.

**`tab_contact`** (V1.8): (cột chung); `google_account_id NN FK CASCADE`; `resource_name NN`; `etag`; `display_name NN`; `phones text[]` (dạng `+84`); `emails citext[]`; `birthday_day`, `birthday_month`, `birthday_year smallint` (năm rỗng khi không rõ); `remind_birthday`, `is_important boolean NN default false`; `synced_at NN`; `deleted_at`. UQ `(user_id, resource_name)`; GIN `phones`, `emails`.

**`tab_gmail_draft`** (V1.8): (cột chung); `google_account_id NN FK CASCADE` (tài khoản gửi, QĐ-50: trả lời theo tài khoản nhận luồng, thư mới theo `account_id` chọn hoặc tài khoản chính); `account_email citext`; `google_draft_id` (rỗng tới khi `drafts.create` xong); `thread_ref`; `to_addrs`, `cc_addrs citext[] NN`; `subject NN`; `body NN`; `body_hash NN`; `status` CK `draft`, `sending`, `sent`, `discarded`; `pending_action_id FK SET NULL`; `approved_at`, `sent_at`; `sent_message_id`. Gửi chỉ qua `tab_pending_action` (`tool_name = send_gmail_draft`, input `{draft_id}`, chạy ở `modules/inbox/approvals.py`); nháp trên Gmail lệch `body_hash` thì 409 `ACTION_PAYLOAD_CHANGED`, nháp giữ `draft`. `thread_ref` chỉ là luồng đang trả lời. Thư Gmail hộp Chính vào `tab_inbox_message` với `conversation_key = gmail:<thread_id>`, `conversation_title` là tiêu đề, `text` là đoạn trích; thư có OTP bỏ cả thư (QĐ-43). Cột `citext[]` đọc ra list nhờ `core/db` đăng ký kiểu `citext` với psycopg lúc mở kết nối.

### 3.11 Calendar và task

**`tab_event`**: Google Calendar làm gốc. **Sự kiện lặp lưu bản gốc có `recurrence` cộng ngoại lệ, đồng bộ `singleEvents=false`, máy chủ tự trải lần lặp** (K1, QĐ-26).

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| title | text NN | |
| description, location | text | |
| all_day | boolean NN default false | |
| start_at, end_at | timestamptz | Khi không cả ngày |
| start_date, end_date | date | Khi cả ngày; `end_date` không tính |
| timezone | text | Để trải lần lặp đúng giờ |
| status | text NN CK `confirmed`, `tentative`, `cancelled` | |
| recurrence | text[] | `RRULE`, `EXDATE` của bản gốc |
| recurring_event_id | text | Ngoại lệ: id Google của bản gốc |
| original_start_at | timestamptz | Ngoại lệ: giờ gốc của lần lặp |
| attendees | jsonb NN default `[]` | `[{email, name, response_status, is_self}]` |
| remind_minutes | int[] NN default `{}` | |
| remind_source | text NN CK `app`, `google` | Tạo ở app: `app`; tạo trên Google: `google` (Google nhắc) |
| is_alarm | boolean NN default false | Máy dùng `setAlarmClock` |
| is_organizer | boolean NN default true | Google `organizer.self`; sự kiện người khác mời chỉ đổi được nhắc |
| source | text NN CK `app`, `google` | |
| task_id | bigint | Bản sao để trả API nhanh |
| google_account_id | bigint FK SET NULL | |
| google_calendar_id, google_event_id, google_etag | text | UQ một phần `(user_id, google_calendar_id, google_event_id)` |
| google_updated_at | timestamptz | |
| google_html_link | text | Link mở trên Google Calendar (lỗi `RECURRING_SERIES_EDIT`) |
| meet_url | text | Link Google Meet (`hangoutLink`); Google có khi tạo chậm, lần đồng bộ sau mới có (5-01) |
| sync_status | text NN CK `local_only`, `pending`, `synced`, `conflict`, `error` | |
| sync_error | text | |
| deleted_at | timestamptz | |

CK `(all_day AND start_date IS NOT NULL AND end_date > start_date) OR (NOT all_day AND start_at IS NOT NULL AND end_at >= start_at)`. Chỉ mục `(user_id, start_at) WHERE deleted_at IS NULL`; `(user_id) WHERE recurrence IS NOT NULL AND deleted_at IS NULL`; `(user_id, recurring_event_id)`.

Sự kiện có khách mời chỉ ghi sau khi duyệt (QĐ-23); dữ liệu chờ nằm trong `tab_pending_action.input` (`add_event`: `{data}`; `update_event`: `{event_id, occurrence_start, changes}`; `delete_event`: `{event_id, occurrence_start}`), chạy bằng `modules/calendar/approvals.py`. Sự kiện lặp chỉ đến từ Google; sửa, xóa một lần tạo dòng ngoại lệ (xóa một lần là ngoại lệ `status = cancelled`, không đặt `deleted_at`). Khóa lần lặp là `original_start_at` theo UTC; lần lặp cả ngày dùng 00:00 UTC của ngày. App tạo sự kiện thì đặt sẵn `google_event_id`, `google_calendar_id = primary`. Đổi `remind_source`, `remind_minutes`, `is_alarm` của bản gốc áp luôn cho các ngoại lệ. Phút nhắc đồng bộ hai chiều (QĐ-39): sự kiện Google nhắc lấy phút popup Google gửi, sửa phút trong app thì đẩy `reminders`; sự kiện app nhắc thì Google im, chỉ lấy phút khi người dùng đặt nhắc trên Google. `is_alarm` lưu trên Google ở `extendedProperties.private.troly_alarm` để đồng bộ lại không mất.

**`tab_task`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| title | text NN tối đa 1.024 | |
| note | text tối đa 8.000 | |
| status | text NN CK `todo`, `done`, `cancelled` | |
| priority | text NN CK `low`, `normal`, `high` | |
| due_date | date | Không giờ: đi Google Tasks |
| due_at | timestamptz | Có giờ: đi Calendar qua `event_id`. CK `due_date IS NULL OR due_at IS NULL` |
| completed_at | timestamptz | |
| completed_source | text CK `app`, `google` | |
| event_id | bigint FK `tab_event` SET NULL | |
| source | text NN CK `app`, `chat` | |
| google_account_id | bigint FK SET NULL | |
| google_tasklist_id, google_task_id, google_etag | text | UQ một phần `(user_id, google_task_id)` |
| google_updated_at | timestamptz | |
| sync_status | text NN CK `local_only`, `pending`, `synced`, `remote_deleted`, `error` | `remote_deleted`: Google báo đã xóa, người dùng chọn xóa hay giữ (QĐ-21, K11) |
| sync_error | text | |
| deleted_at | timestamptz | |

Nhắc trên máy không có bảng riêng: tính từ `tab_event` có `remind_source = 'app'`, trải cả lần lặp. Việc có giờ sinh sự kiện có `task_id`; dời sự kiện thì `due_at`, tên việc đổi theo; bỏ giờ của việc thì xóa mềm sự kiện.

### 3.12 Google

**`tab_google_account`** (một dòng): (cột chung, `user_id` UQ); `google_sub NN UQ`; `email citext NN`; `granted_scopes text[] NN`; `enabled_packs text[] NN default '{base}'` (`base`, `calendar`, `tasks`, `gmail`, `contacts`, `drive`); `refresh_token_enc bytea NN`; `access_token_enc bytea`; `access_expires_at`; `key_version smallint NN`; `status` CK `active`, `reauth_required`, `revoked`; `last_error`; `invalid_grant_count int NN default 0`; `connected_at NN`. Token mã hóa Fernet, bản rõ `{user_id, provider, token}`.

**`tab_google_oauth_state`** (K2, giữ bảng): (cột chung); `state_hash text NN UQ`; `packs text[] NN`; `code_verifier_enc bytea NN`; `key_version smallint NN` (giải mã được sau khi xoay khóa); `expires_at NN` (10 phút); `used_at` (dùng một lần, chống phát lại).

**`tab_google_sync_state`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| google_account_id | bigint NN FK CASCADE | |
| service | text NN CK `calendar`, `tasks`, `gmail`, `contacts`, `drive`, `sheets` | |
| resource_id | text NN | `primary`, id danh sách *Trợ lý*, `me`, id thư mục *Trợ lý*, id bảng tính |
| sync_token, history_id | text | |
| updated_min | timestamptz | Tasks |
| needs_sync | boolean NN default true | |
| last_sync_at, last_full_sync_at, next_sync_at | timestamptz | |
| initial_sync_state | text CK `pending`, `running`, `done`, `failed` | Cho câu trạng thái ở màn Google (31) |
| status | text NN CK `ok`, `error`, `disabled` | |
| last_error | text | |
| channel_id | uuid UQ | Kênh webhook Calendar |
| channel_resource_id, channel_token_hash | text | |
| channel_expires_at | timestamptz | |

UQ `(google_account_id, service, resource_id)`.

**`tab_google_outbox`**: (cột chung); `google_account_id NN FK CASCADE`; `service` CK `calendar`, `tasks`, `gmail`, `drive`, `sheets`; `op` CK `insert`, `patch`, `delete`, `draft_create`, `draft_send`, `file_upload`, `sheet_write`; `local_type` CK `event`, `task`, `gmail_draft`, `file`, `export`; `local_id bigint NN`; `payload jsonb NN default '{}'`; `status` CK `pending`, `processing`, `done`, `failed`, `conflict`; `attempts smallint` (tối đa 5); `next_attempt_at NN`; `locked_at`; `last_error` (với `conflict`: JSON thay đổi bị bỏ). UQ một phần `(local_type, local_id, op) WHERE status IN ('pending','processing')`. Chỉ mục `(status, next_attempt_at) WHERE status = 'pending'`.

### 3.13 Trip

Tên cột theo bảng dưới; `41-ban-do-lich-trinh.md` sửa theo (K5). Cấu trúc một rủi ro theo 41 mục 6.3: `{code, level (red, yellow), day_no, stop_id, message, suggestion, checked_at}`.

**`tab_trip`**: (cột chung); `title NN`; `start_date`, `end_date` (CK `end_date >= start_date`); `nights smallint`; `travel_mode` CK `motorbike`, `car`, `walk`; `origin_text`, `end_text`; `status` CK `importing`, `draft`, `evaluating`, `planned`, `done`, `failed`; `source_kind` CK `docx`, `pdf`, `image`, `text`, `link`; `source_file_id FK tab_file SET NULL`; `source_text`; `extract_json jsonb`; `notes jsonb NN default '[]'`; `hotels jsonb NN default '[]'`; `evaluation jsonb` (`{evaluated_at, risks[]}` cho danh sách điểm hiện tại); `chosen_option_id FK SET NULL` (`use_alter`); `export_file_id FK SET NULL`; `error`; `archived_at timestamptz` (lưu trữ chuyến, QĐ-42, migration `0009_trip_archive`); `search_vector` từ `title`, `origin_text`, `end_text`.

**`tab_trip_stop`**

| Cột | Kiểu, ràng buộc | Ghi chú |
|---|---|---|
| (cột chung) | | |
| trip_id | bigint NN FK CASCADE | |
| day_no | smallint NN CK `>= 1` | |
| seq | smallint NN | UQ `(trip_id, day_no, seq)` `DEFERRABLE INITIALLY DEFERRED` |
| title | text NN | |
| category | text NN CK `an_uong`, `nghi`, `tham_quan`, `pha`, `di_chuyen`, `khach_san`, `mua_sam`, `khac` | |
| role | text NN CK `main`, `alternative`, `backup`, `generic`, `via` | |
| parent_stop_id | bigint FK CASCADE | |
| time_text | text | Nguyên văn |
| planned_start, planned_end | timestamptz | |
| approx, fixed, optional | boolean NN default false | |
| stay_minutes | smallint | |
| place_query, source_url, place_id | text | |
| lat, lng | numeric(9,6) | |
| coord_source | text CK `user`, `google` | |
| coord_fetched_at | timestamptz | Nguồn `google` quá 30 ngày chưa làm mới thì đặt rỗng (K19) |
| resolve_status | text NN CK `ok`, `uncertain`, `not_found`, `manual` | |
| phone, cost_note, note | text | |
| alternatives | jsonb NN default `[]` | `place_id` và nhãn, không lưu tọa độ |
| search_vector | tsvector | Sinh từ `title`, `place_query`, `note`; dùng cho `/search` |

Không có cột `address`: địa chỉ Google chỉ lưu tạm ở `tab_place_cache`.

**`tab_trip_option`**: (cột chung); `trip_id NN FK CASCADE`; `name NN`; `summary`; `plan jsonb NN` (theo ngày: `stop_id`, `planned_start`, `leg_minutes`, `leg_km`); `total_km numeric(7,1)`; `total_ride_minutes`, `night_ride_minutes int`; `red_count`, `yellow_count smallint`; `risks jsonb NN default '[]'`; `changes jsonb NN default '[]'`; `chosen boolean`; `evaluated_at NN`.

**`tab_trip_fact`** (K4, giữ bảng): (cột chung); `trip_id NN FK CASCADE`; `kind` CK `ferry_last`, `ferry_first`, `checkin`, `checkout`, `hotline`, `opening_hours`, `other`; `stop_id FK SET NULL`; `day_no`; `value_time time`; `value_text`; `text NN`.

**`tab_place_cache`** (hệ thống, dùng chung): PK `(query_norm, bias_key)`; `place_id` (giữ mãi); `lat`, `lng`, `formatted_address` (đặt rỗng khi `fetched_at` quá 30 ngày); `fetched_at`; `created_at`. Không lưu giờ mở cửa.

**`tab_route_cache`** (hệ thống): `id`; `origin_key`, `destination_key NN`; `travel_mode` CK `two_wheeler`, `drive`, `walk`; `avoid_highways boolean NN`; `distance_m`, `duration_s int NN`; `fetched_at`, `expires_at NN` (30 ngày). UQ `(origin_key, destination_key, travel_mode, avoid_highways)`.

### 3.14 Report

**`tab_export`**: (cột chung); `kind` CK `expense_sheet`, `expense_docx`, `report_docx`; `params jsonb NN`; `status` CK `pending`, `running`, `done`, `failed`; `file_id FK SET NULL`; `google_file_id`; `url`; `error`. Sheets đi qua `tab_google_outbox` (`sheet_write`). Module `report` không có bảng số liệu riêng.

### 3.15 Thời hạn giữ dữ liệu

Job `cleanup_old_data` chạy 03:30 hằng ngày, lô 1.000 dòng.

| Dữ liệu | Giữ |
|---|---|
| `tab_inbox_message`, `tab_device_event` | 180 ngày (QĐ-17) |
| Khối `contains_third_party` trong `tab_message` | 180 ngày, thay nội dung bằng *[đã xóa sau 180 ngày]*, giữ cấu trúc, đặt `redacted_at` |
| `tab_message` | 365 ngày (QĐ-26); `tab_conversation.summary` giữ lại |
| Dòng xóa mềm | 30 ngày (hết hạn *Hoàn tác*) rồi xóa cứng |
| `tab_pending_action` | Quá hạn thành `expired`; xóa sau 30 ngày |
| `tab_ai_run` | 13 tháng |
| `tab_auth_session` | 30 ngày sau hết hạn hoặc thu hồi |
| `tab_google_oauth_state` | 1 giờ sau hết hạn (job `cleanup_old_data` hằng ngày) |
| `tab_job_queue` | 30 ngày (`failed` 90 ngày); `tab_job_run` 30 ngày |
| `tab_client_log` | 30 ngày |
| `tab_google_outbox` | `done` 7 ngày; `failed`, `conflict` 30 ngày |
| Tọa độ Google ở `tab_place_cache`, `tab_trip_stop` | 30 ngày từ lần lấy (điều khoản Places) |
| `tab_route_cache` | Tới `expires_at` |
| `tab_file` | `pending_upload` 24 giờ; `deleted` 30 ngày rồi xóa cả đối tượng R2 |
| `tab_gmail_draft` | `sent`, `discarded` 30 ngày |
| `tab_profile_memory_revision` | 50 bản mới nhất |
| Bản sao lưu | 5 bản trên bucket R2 riêng tư, không mã hóa `age` (QĐ-16, QĐ-27) |

**Ngắt kết nối Google** (`keep_data`): xóa token, trạng thái OAuth, đồng bộ, hàng chờ; danh bạ và thư Gmail trong hộp tin luôn bị xóa. `keep_data = true`: sự kiện, việc giữ lại, cột `google_*` rỗng, `sync_status = local_only`. `keep_data = false`: xóa thêm sự kiện `source = google`.

### 3.16 Migration Alembic

- Chạy trong container: `docker compose --profile migrate run --rm migrate`; tạo mới bằng `docker compose run --rm api alembic revision --autogenerate -m "<mô tả>"`.
- Một lịch sử thẳng. `env.py` nạp model của `core`, `ai`, `integrations/google` và `ENABLED_MODULES`. Tên tệp `YYYYMMDD_HHMM_<module>_<mô tả>.py`. Quy ước tên ràng buộc `ix_`, `uq_`, `ck_`, `fk_`, `pk_` trong `MetaData`.
- Migration đầu: phần mở rộng, cấu hình `troly_vn`, bảng của `core`, `ai`, `setting`, `memory`, `chat`, `file`, `tab_device`.
- Luật: autogenerate rồi đọc lại tay (cột sinh, chỉ mục một phần, `CHECK`, phần mở rộng viết bằng `op.execute`); có `downgrade`; không sửa migration đã chạy trên VPS; **tương thích ngược với bản mã trước** (thêm cột cho rỗng hoặc có mặc định; đổi tên, xóa cột qua hai lần deploy); hai migration cùng cha thì điều phối `alembic merge`; deploy sao lưu trước khi migrate.

## 4. API hoặc giao tiếp

Bảng chỉ đọc ghi qua `repo.py` của nơi sở hữu (mục 3.2). Chỉ `api`, `worker`, `migrate` và `app.cli` kết nối DB.

## 5. Kiểm thử

Chỉ phần dễ sai (QĐ-27 mục 8): ràng buộc tiền và `account_last4`; ghép cặp chuyển tiền (3 phút thì ghép, 30 phút thì không); tìm *phuoc hai* ra ghi chú *Phước Hải*; trải sự kiện lặp có ngoại lệ; mốc phiên 04:00 và luật nối phiên dưới 3 giờ; dọn dữ liệu đúng hạn ở mục 3.15; chuỗi migration lên, xuống, lên.

## 6. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Tin người khác giữ 180 ngày | Đánh dấu `contains_third_party`, dọn đúng hạn, R2 riêng tư |
| Trải sự kiện lặp sai múi giờ, sai `EXDATE` | Lưu `timezone`; kiểm với RRULE thật; sửa cả chuỗi thì mở Google Calendar |
| Chữ trích tệp lớn làm bảng nặng | Cắt 200.000 ký tự; trích một lần khi tải lên, ở bảng riêng `tab_file_text` |

## 7. Cần agent khác

| Agent | Việc |
|---|---|
| điều phối | `01` mục 6, `02`: dẫn sang mục 3.2 tệp này |
| agent AI | `tab_pending_action` chỉ `tool_name`, `input`, không còn `kind`, `payload` |
| agent app Android | Một dòng `sms_default` (bỏ ĐX-30-12); `heartbeat` gửi `manufacturer`, `default_sms_package`, `otp_blocked_today`; bỏ khóa cài đặt `app.lock_*` |
| agent Google | 40: theo mục 3.11, 3.12 (sự kiện lặp `singleEvents=false`, giữ `tab_google_oauth_state`, `keep_data`, `remote_deleted`, `birthday_year` rỗng, tên cột `granted_scopes`, `enabled_packs`, `service`, `local_type`; xuất Drive, Sheets qua `tab_google_outbox`). 41: tên cột mục 3.13, giữ `tab_trip_fact`, `tab_place_cache` khóa `(query_norm, bias_key)` |
| agent hạ tầng | 50: không còn bảng phát hành, thay bằng tệp kê trên R2; sao lưu không `age` |
