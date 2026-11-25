# API

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 3, gọn theo QĐ-27, sửa theo `81-ra-cheo-lan-2.md` (QĐ-26) và các hợp đồng đã chốt ở `bang-viec.md` mục 4.

Tệp này là **nguồn chuẩn cho đường dẫn API và giới hạn tần suất** (QĐ-25). Tài liệu khác dẫn sang bảng mục 5.1, không chép lại.

## 1. Mục tiêu

Một bảng API duy nhất cùng các quy ước chung: phong bì, phân trang, lỗi, phiên bản, giới hạn, hành động trả cho app.

## 2. Phạm vi

API của tiến trình `api` cho giao diện React, plugin Kotlin và Google (webhook, chuyển hướng OAuth), cộng hai trang tĩnh. Không gồm API Claude, Google mà máy chủ gọi ra.

## 3. Thiết kế

### 3.1 Quy ước chung

| Mục | Quy ước |
|---|---|
| Gốc | `https://assistant.baohuynh.io.vn/api/v1` (QĐ-26). `/api/health` không phiên bản; hai trang tĩnh ở mục 5.10 nằm ngoài `/api` |
| Đường dẫn | Danh từ số nhiều; hành động không phải CRUD là động từ ở cuối (`/tasks/{id}/complete`) |
| JSON | UTF-8, snake_case. Trường không có giá trị trả `null` |
| Id | Số nguyên; id máy khách sinh là UUID; cuộc trò chuyện hộp tin dùng `conversation_key` |
| Thời điểm | ISO 8601 có độ lệch, thiếu thì 400; trả theo múi giờ người dùng. Ngoại lệ: `fire_at` của nhắc trả UTC |
| Tiền | Số nguyên VND, hậu tố `_vnd` |
| `PATCH` | Chỉ gửi trường cần đổi; `null` là xóa giá trị |
| `DELETE` | Trả `data: null`. Với bảng xóa mềm, *Hoàn tác* bằng `POST .../{id}/restore` trong 30 ngày |

Trong bảng mục 5.1, đường dẫn viết bỏ `/api/v1`.

### 3.2 Xác thực

| Cách | Tiêu đề | Ký hiệu | Gọi được |
|---|---|---|---|
| JWT | `Authorization: Bearer <access_token>` | **U** | Mọi API của giao diện |
| Mã thiết bị | `Authorization: Device <device_token>` | **D** | `/device/*` |
| Một trong hai | | **U/D** | `/device/release`, `/calendar/reminders` |
| Kênh Google | `X-Goog-Channel-ID`, `X-Goog-Channel-Token` | **G** | `/webhooks/google/calendar` |
| Không cần | | **-** | `/api/health`, `/auth/login`, `/auth/refresh`, `/google/oauth/callback`, trang tĩnh |

Mã sai nhóm trả 401 `AUTH_REQUIRED`. Một tài khoản, không có vai trò (QĐ-27). Chi tiết ở `10-kien-truc-backend.md` mục 3.7.

### 3.3 Phong bì

```json
{ "success": true, "message": "", "data": { "id": 15 } }
{ "success": false, "message": "Dữ liệu chưa hợp lệ.",
  "data": { "code": "VALIDATION_ERROR", "fields": { "amount_vnd": "Số tiền phải lớn hơn 0." } } }
```

200 khi đọc, sửa; 201 khi tạo; 202 khi nhận việc chạy nền hoặc tạo hành động chờ duyệt. Không dùng phong bì: luồng SSE, trang OAuth, webhook, 304, trang tĩnh. Mọi phản hồi có `X-Request-ID`.

### 3.4 Phân trang và lọc

Danh sách dài dùng con trỏ: `limit` (mặc định 50, tối đa 200), `cursor`; trả `{items, next_cursor}`, `next_cursor = null` là hết; con trỏ hỏng thì 400 `INVALID_CURSOR`. Danh sách ngắn (danh mục, luật, thiết bị, sự kiện trong khoảng) trả `{items}`. Lọc bằng `from`, `to` (`to` không tính), `q`, `status`, `app`, `kind`; nhiều giá trị nối dấu phẩy.

### 3.5 Mã lỗi

| HTTP | `data.code` | Khi nào |
|---|---|---|
| 400 | `VALIDATION_ERROR` (có `fields`), `INVALID_CURSOR` | |
| 401 | `AUTH_REQUIRED`, `AUTH_INVALID_CREDENTIALS`, `AUTH_TOKEN_EXPIRED`, `AUTH_REFRESH_INVALID`, `DEVICE_REVOKED` | App gặp `AUTH_TOKEN_EXPIRED` thì làm mới rồi thử lại một lần |
| 404 | `NOT_FOUND` | Không có, hoặc không thuộc người gọi |
| 409 | `CONFLICT` | Sai `version`, trạng thái không cho phép |
| 409 | `DUPLICATE` | Trùng khóa duy nhất |
| 409 | `CHAT_BUSY` | Lượt trước chưa xong |
| 409 | `ACTION_NOT_PENDING`, `ACTION_PAYLOAD_CHANGED` | Duyệt lần hai, hết hạn; `payload_hash` lệch |
| 409 | `RECURRING_SERIES_EDIT` | Sửa bản gốc sự kiện lặp; `data` có `google_html_link` |
| 409 | `EVENT_NOT_ORGANIZER` | Sửa nội dung sự kiện người khác mời |
| 409 | `GOOGLE_NOT_CONNECTED`, `GOOGLE_REAUTH_REQUIRED`, `GOOGLE_SCOPE_MISSING` | |
| 413, 415 | `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE` | |
| 426 | `APP_VERSION_UNSUPPORTED` | Mục 3.6 |
| 429 | `RATE_LIMITED` | Kèm `Retry-After` |
| 502 | `AI_UNAVAILABLE`, `EXTERNAL_SERVICE_ERROR` | Claude; Google, R2 |
| 500 | `INTERNAL_ERROR` | Kèm `request_id` |

Mã theo từng sự kiện trong `rejected` của `/device/events`: `APP_NOT_LISTENED`, `OTP_DETECTED`, `INVALID_EVENT`, `EVENT_TOO_OLD`.

### 3.6 Phiên bản

Phiên bản ở đường dẫn. Thêm trường, endpoint, giá trị liệt kê làm thẳng trên `v1`; app bỏ qua trường và `type` lạ. Đổi phá vỡ thì mở `/api/v2` cho endpoint đó, chạy song song 30 ngày. App và plugin gửi `X-App-Version: <versionCode>`; nhỏ hơn `min_supported_version_code` của `releases/latest.json` thì 426, trừ `/device/release` và `/auth/*`.

### 3.7 Giới hạn (bảng chung)

Chỉ vài trần cơ bản (QĐ-27 mục 7). Đếm trong bộ nhớ của một tiến trình `api`; IP lấy từ `CF-Connecting-IP`.

| Chỗ | Mức | Biến |
|---|---|---|
| `/api/v1/auth/*` ở Cloudflare WAF | 20 yêu cầu mỗi 10 giây mỗi IP | (Cloudflare) |
| `POST /auth/login` | 10 lần mỗi 15 phút mỗi IP | `RATE_LOGIN_PER_15MIN` |
| `POST /device/events` | Lô 1 tới 50 sự kiện, thân 256 KB; 120 sự kiện mỗi phút mỗi thiết bị | `RATE_DEVICE_EVENTS_PER_MIN` |
| `POST /chat/messages` | 20 câu mỗi phút | `RATE_CHAT_PER_MIN` |
| Mọi đường khác | 300 yêu cầu mỗi phút | `RATE_USER_PER_MIN` |

Thân JSON tối đa 1 MB; tệp 25 MB (đi thẳng R2); tin chat 4.000 ký tự, tối đa 4 tệp; URL ký sẵn R2 sống 300 giây (`R2_PRESIGN_SECONDS`) cho cả tải lên và tải về; riêng link APK bản phát hành sống 1.800 giây (`R2_RELEASE_PRESIGN_SECONDS`).

### 3.8 Chống gửi trùng

Tin chat có `client_message_id`: gửi lại khi lượt đã xong thì trả tin trả lời cũ, đang chạy thì `CHAT_BUSY`. Sự kiện thiết bị có `client_event_id`: trùng thì vào `duplicates`. Việc nền dùng `dedupe_key`. Tạo mới khác do app chặn bấm đúp.

### 3.9 Hành động trả cho app

Danh sách `type` và trường theo `20-bo-nao-ai.md` mục 3.8; **vỏ phẳng** (QĐ-26, K6): trường nằm ngay trong đối tượng, không bọc `payload`; có `id` duy nhất trong một tin (`a1`, `a2`).

| `type` | Trường (ngoài `id`, `type`, `label`) |
|---|---|
| `open_map_navigation` | `lat`, `lng` (rỗng khi chưa có tọa độ), `query`, `mode` (`l`, `d`, `w`), `avoid` (`h` hoặc `null`), `fallback_url` |
| `open_map_directions` | `urls[]`, `segment_labels[]` |
| `open_map_place` | `query`, `place_id` |
| `open_link` | `url` (chỉ `https`), `kind` (`file`, `gmail`, `sheet`, `web`) |
| `open_screen` | `screen`, `params` |
| `confirm` | `pending_action_id`, `title`, `summary`, `details[]` (`label`, `value`), `confirm_label`, `cancel_label`, `danger`, `expires_at` |
| `undo` | `text`, `resource` (`expense`, `task`, `event`), `ids`, `expires_at` (10 phút); app gọi `POST /<resource>/{id}/restore` |
| `memory_changed` | `version`, `text`, `undo_version` |
| `choices` | `options[]` (`label`, `value`), tối đa 5 |

`confirm` không có `kind`, `require_unlock` (K6, QĐ-27). Giá trị `screen`: `chat`, `inbox`, `inbox_conversation`, `calendar_day`, `event_detail`, `task_list`, `task_detail`, `expense_list`, `expense_detail`, `trip_list`, `trip_detail`, `report`, `search`, `note_detail`, `file_detail`, `settings_google`, `settings_listened_apps`, `settings_device_check`, `settings_profile`, `settings_ai_cost`. URL bản đồ luôn do `trip/service.py` dựng.

## 4. Dữ liệu cần

Bảng ở [11-co-so-du-lieu.md](11-co-so-du-lieu.md).

## 5. API hoặc giao tiếp

### 5.1 Bảng API duy nhất

Lỗi chung (`AUTH_*`, `VALIDATION_ERROR`, `NOT_FOUND`, `RATE_LIMITED`, `INTERNAL_ERROR`) không ghi từng dòng. *R* ở cột đầu ra là có `POST .../{id}/restore` để *Hoàn tác* xóa.

**Hệ thống, đăng nhập, cài đặt**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Bản |
|---|---|---|---|---|---|
| GET | `/api/health` | - | | `{status, db, worker_lag_seconds, version, git_sha}` | V1.0 |
| POST | `/auth/login` | - | `email`, `password`, `label` | `{access_token, access_expires_at, refresh_token, refresh_expires_at, user}` | V1.0 |
| POST | `/auth/refresh` | - | `refresh_token` | như trên (mã làm mới xoay vòng, 365 ngày); mã vừa xoay gửi lại trong 60 giây thì nhận lại đúng mã làm mới kế tiếp, không 401 | V1.0 |
| POST | `/auth/logout` | U | | `null` | V1.0 |
| POST | `/auth/change-password` | U | `current_password`, `new_password` | `null`; thu hồi phiên khác | V1.0 |
| GET | `/auth/me` | U | | `{id, name, email, timezone}` | V1.0 |
| GET, DELETE | `/auth/sessions`, `/auth/sessions/{id}` | U | | Danh sách phiên; thu hồi | V1.0 |
| GET, PATCH | `/settings` | U | `{khóa: giá trị}` | `{values, defaults}` | V1.0 |
| GET | `/jobs/{id}` | U | | `{id, kind, status, result, error, finished_at}` | V1.0 |
| GET | `/system/status` | U | | `SystemStatus` (mục 5.9) | V1.0 |
| POST | `/system/jobs/{name}/run` | U | | `{queued: true}` (202); dùng cho *Sao lưu ngay* | V1.0 |
| POST | `/client-logs` | U hoặc - | `items[]` (1 tới 50): `level` (`error`, `warn`, `info`), `kind`, `screen`, `message`, `detail`, `app_version`, `occurred_at` | `{accepted}`; nhận cả khi chưa đăng nhập, 60 mục mỗi phút mỗi IP (QĐ-30) | V1.0 |

**Trí nhớ, chat, tìm kiếm**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Bản |
|---|---|---|---|---|---|
| GET, PUT | `/memory/profile` | U | `content`, `version` | `{content, version, updated_by, updated_at}`; lệch `version` thì `CONFLICT` | V1.0 |
| GET | `/memory/profile/revisions` | U | `cursor` | `items: [{version, changed_by, reason, created_at, preview}]` | V1.0 |
| POST | `/memory/profile/revisions/{version}/restore` | U | `version` hiện tại | Hồ sơ sau khôi phục (Hoàn tác của `memory_changed`) | V1.0 |
| GET, POST | `/memory/notes` | U | `q`, `tag`, `cursor` / `title`, `body`, `tags` | `items: Note[]` / `Note` | V1.0 |
| GET, PATCH, DELETE | `/memory/notes/{id}` | U | | `Note` / `null` (R) | V1.0 |
| GET | `/chat/today` | U | | `{conversation, messages (50 tin), next_cursor, pending_actions}`; từ QĐ-51 là phiên hoạt động gần nhất, giữ cho bản app cũ; chưa có phiên nào thì `conversation: null`, không tạo phiên rỗng (phản hồi 1.1.1) | V1.0 |
| GET | `/chat/conversations` | U | `q`, `cursor`, `limit` | `{items: Conversation[], next_cursor}`; ghim trước, rồi `last_message_at` giảm dần; không trả phiên chưa có tin nào, trừ phiên tạo bằng `POST` trong 10 phút gần nhất; `q` tìm theo tiêu đề (không dấu) và nội dung tin hiện (tìm toàn văn); con trỏ `<0|1>|<giờ>|<id>` | QĐ-51 |
| GET | `/chat/conversations/{id}` | U | | cùng dạng `/chat/today` cho một phiên: `{conversation, messages (50 tin), next_cursor, pending_actions}`; không có thì 404 | QĐ-51 |
| POST | `/chat/conversations` | U | `title` (tùy chọn) | `Conversation` (201); phiên gần nhất còn trống, chưa tên và vừa tạo trong 10 phút thì dùng lại | QĐ-51 |
| PATCH | `/chat/conversations/{id}` | U | `title`, `pinned` | `Conversation`; đổi tên thì `title_source = user` | QĐ-51 |
| GET | `/chat/conversations/{id}/messages` | U | `cursor` | `items: Message[]` | V1.0 |
| DELETE | `/chat/conversations/{id}` | U | | `null` (xóa phiên, không hoàn tác) | V1.0 |
| POST | `/chat/messages` | U | `client_message_id`, `text`, `attachment_file_ids`, `mode` (`chat`, `think`, `research`, `summary`; mặc định `chat`), `conversation_id` (QĐ-51; bỏ trống thì phiên hoạt động gần nhất, chưa có thì tạo; phiên không có thì 404) | **SSE** hoặc JSON (mục 5.2) | V1.0 |
| GET | `/chat/status` | U | | `{models, today_usd, month_usd, monthly_warn_usd, over_monthly_warning, cache_read_ratio_7d}` | V1.0 |
| GET | `/chat/actions` | U | `status` | `items: PendingAction[]` | V1.0 |
| POST | `/chat/actions/{id}/approve`, `/chat/actions/{id}/reject` | U | | `{action, result_text}` | V1.0 |
| GET | `/search` | U | `q` (bắt buộc), `types` (`note`, `chat`, `inbox`, `trip`, `file`; mặc định tất cả), `from`, `to`, `limit` (mặc định 20) | `items: SearchHit[]` (mục 5.3) | V1.1 |

**Chi tiêu, hộp tin, Gmail, danh bạ**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Bản |
|---|---|---|---|---|---|
| GET, POST | `/expenses` | U | lọc `from`, `to`, `kind`, `account`, `category_id`, `source`, `needs_review`, `q`, `cursor` / `amount_vnd`, `kind`, `account`, `account_last4`, `to_account`, `category_id`, `merchant`, `place`, `note`, `spent_at` | `items: Expense[]` / `Expense` | V1.1 |
| GET, PATCH, DELETE | `/expenses/{id}` | U | | `Expense` / `null` (R) | V1.1 |
| GET | `/expenses/{id}/source` | U | | `{app_package, title, text, posted_at}`; quá hạn 180 ngày thì 404 | V1.2 |
| GET | `/expenses/summary` | U | `period` (`day`, `week`, `month`, `custom`), `date`, `from`, `to`, `group_by` (`category`, `day`, `account`) | `{from, to, total_expense_vnd, total_income_vnd, total_transfer_vnd, groups[]}` | V1.1 |
| GET, POST, PATCH, DELETE | `/expenses/categories`, `/expenses/categories/{id}` | U | `name`, `kind`, `keywords`, `sort_order`, `is_archived` | `Category`; xóa khi đã có khoản chi thì `CONFLICT` | V1.1 |
| GET | `/inbox/conversations` | U | `app`, `status`, `importance`, `from`, `to`, `account_email` hoặc `account` (QĐ-50, cùng nghĩa), `cursor` | `{items: Conversation[], next_cursor, accounts}`; xếp theo tin mới nhất giảm dần (quan trọng chỉ là cờ, tab Quan trọng lọc `importance = important`); `accounts` là email các tài khoản Gmail có thư, cho chip lọc | V1.3 |
| GET | `/inbox/conversations/{conversation_key}/messages` | U | `cursor` | `items: InboxMessage[]` | V1.3 |
| POST | `/inbox/conversations/{conversation_key}/mark` | U | `status` | `{updated}` | V1.3 |
| PATCH | `/inbox/messages/{id}` | U | `status` | `InboxMessage` | V1.3 |
| POST | `/inbox/messages/mark` | U | `ids` (tối đa 500), `status` | `{updated}` | V1.3 |
| GET, POST, DELETE | `/inbox/rules`, `/inbox/rules/{id}` | U | `kind`, `value`, `app`, `contact_id` | `Rule` | V1.3 |
| GET | `/contacts` | U | `q`, `cursor` | `items: Contact[]` | V1.8 |
| PATCH | `/contacts/{id}` | U | `remind_birthday`, `is_important` | `Contact` | V1.8 |
| GET, POST | `/gmail/drafts` | U | `status` / `to`, `cc`, `subject`, `body`, `thread_ref`, `account_id` (tài khoản gửi, QĐ-50; bỏ trống thì trả lời theo tài khoản nhận luồng, thư mới theo tài khoản chính) | `GmailDraft` có `account_id`, `account_email`; thẻ duyệt `send_gmail_draft` có dòng *Gửi từ* | V1.8 |
| GET, PATCH, DELETE | `/gmail/drafts/{id}` | U | | `GmailDraft` / `null` (bỏ nháp) | V1.8 |
| POST | `/gmail/drafts/{id}/send` | U | | `{pending_action}` (202); thư đi khi duyệt | V1.8 |
| GET | `/gmail/threads/{thread_id}` | U | | `{thread_id, account_id, account_email, subject, messages: [{id, from_name, from_email, to, cc, date, text}], reply: {to, cc, subject, in_reply_to}}`; chưa bật gói `gmail` thì 409 | V1.8 |

**Việc, lịch, Google**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Bản |
|---|---|---|---|---|---|
| GET, POST | `/tasks` | U | `status`, `due` (`overdue`, `today`, `week`, `none`), `cursor` / `title`, `note`, `priority`, `due_date` hoặc `due_at`, `remind_minutes` | `items: Task[]` / `Task` | V1.4 |
| GET, PATCH, DELETE | `/tasks/{id}` | U | | `Task` / `null` (R) | V1.4 |
| POST | `/tasks/{id}/complete`, `/tasks/{id}/reopen` | U | | `Task` | V1.4 |
| POST | `/tasks/{id}/resolve-remote-delete` | U | `keep` | `Task` hoặc `null` | V1.4 |
| GET, POST | `/calendar/events` | U | `from`, `to` (tối đa 92 ngày) / `title`, `description`, `location`, `all_day`, `start_at`, `end_at` hoặc `start_date`, `end_date`, `remind_minutes`, `is_alarm`, `attendees` | `items: Event[]` (đã trải lần lặp) / `Event` (201) hoặc `{pending_action}` (202) khi có khách | V1.4 |
| GET, PATCH, DELETE | `/calendar/events/{id}` | U | `occurrence_start` khi là một lần lặp; PATCH thêm `remind_source` | `Event` / `null` (R); có khách thì 202 kèm `pending_action`; bản gốc sự kiện lặp thì `RECURRING_SERIES_EDIT` | V1.4 |
| GET | `/calendar/reminders` | U/D | `from`, `days` (mặc định 14, tối đa 31); `If-None-Match` | `{revision, items: Reminder[]}` hoặc 304 | V1.4 |
| GET | `/device/notices` | D | `after` (con trỏ; lần đầu bỏ trống thì chỉ trả `cursor`) | `{items: [{id, kind (transaction, important_message, chat_done, booking_added), title, body, deep_link}], cursor}`; `booking_added` (QĐ-49) thêm `created_at`, `booking_id`, `event_id`, `body` là tên chỗ và giờ nhận phòng hoặc khởi hành, `deep_link troly://lich/su-kien/<event_id>`; `chat_done` thêm `conversation_id`, `message_id`, `file_ids` (tệp `export_document` tạo trong lượt) và `file_id` (tệp đầu hoặc null), `body` là câu đầu của trả lời (tối đa 120 ký tự), `deep_link troly://?phien=<conversation_id>&tin=<message_id>`; đường này không giới hạn tốc độ riêng, máy hỏi 20 giây một lần được; con trỏ `<chi>.<tin>.<chat>.<đặt chỗ>` (bản hai, ba phần cũ vẫn nhận, phần thiếu tính từ hiện tại); chỉ loại đang bật ở `notify.*` (QĐ-38, QĐ-41, QĐ-49) | V1.4 |
| POST | `/device/bookings/{booking_id}/undo` | D | | `{undone: true}`; gọi `booking.service.undo_booking` (agent Google): xóa sự kiện Lịch đã tạo, gỡ khỏi chuyến, `calendar_state = undone` để lần quét sau không thêm lại, gọi lại trả kết quả cũ; không phải của người dùng thì 404; sự kiện đã bị sửa thì 409 `BOOKING_EDITED` | QĐ-49 |
| GET | `/google/status` | U | | `GoogleStatus` (mục 5.6) | V1.4 |
| POST | `/google/connect` | U | `packs` | `{auth_url}` | V1.4 |
| GET | `/google/oauth/callback` | - | `code`, `state`, `error` | Trang HTML chuyển về app | V1.4 |
| POST | `/google/disconnect` | U | `keep_data` | `null` | V1.4 |
| POST | `/google/sync/{service}` | U | | `{queued: true}` (202) | V1.4 |
| GET | `/google/outbox` | U | `status` (mặc định `failed,conflict`) | `items: OutboxItem[]` | V1.4 |
| POST | `/google/outbox/{id}/retry` | U | `reapply` (với `conflict`) | `OutboxItem` | V1.4 |
| POST | `/webhooks/google/calendar` | G | tiêu đề `X-Goog-*` | 200 rỗng | V1.4 |

**Lịch trình, báo cáo, tệp, thiết bị**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Bản |
|---|---|---|---|---|---|
| GET | `/trips` | U | `status`, `cursor` | `items: TripBrief[]` | V1.6 |
| POST | `/trips/import` | U | `file_id` hoặc `text` hoặc `url`; `title`, `start_date`, `travel_mode` | `{trip_id, job_id}` (202) | V1.6 |
| GET, PATCH | `/trips/{id}` | U | `title`, `start_date`, `travel_mode`, `origin_text`, `status` | `Trip` | V1.6 |
| DELETE | `/trips/{id}` | U | | Từ app: `null`. Từ trợ lý: qua thẻ duyệt (`delete_trip`) | V1.6 |
| POST, PATCH, DELETE | `/trips/{id}/stops`, `/trips/{id}/stops/{stop_id}` | U | `day_no`, `seq`, `title`, `category`, `planned_start`, `fixed`, `place_query`, `note`; PATCH thêm `place_id`, `lat`, `lng` | `Stop` / `null` | V1.6 |
| POST | `/trips/{id}/stops/reorder` | U | `day_no`, `stop_ids` | `items: Stop[]` | V1.6 |
| POST | `/trips/{id}/stops/{stop_id}/resolve` | U | `place_query` | `{candidates: [{name, address, lat, lng, place_id}]}` | V1.6 |
| POST | `/trips/{id}/evaluate` | U | | `{job_id}` (202) | V1.6 |
| POST | `/trips/{id}/options/{option_id}/choose` | U | | `Trip` | V1.6 |
| GET | `/trips/{id}/map-links` | U | `day_no`, `max_waypoints` (`9` hoặc `3`) | Mục 5.7 | V1.6 |
| POST | `/trips/{id}/export-docx` | U | `save_to_drive` | `{file_id, download_url}` | V1.6 |
| POST | `/trips/{id}/to-calendar` | U | | `{event_ids}` | V1.6 |
| GET | `/reports/dashboard` | U | `date` | `{date, cards: {expense, calendar, tasks, inbox, ai, devices, health}}`; mỗi thẻ `{status, data, message}` lỗi riêng được | V1.7 |
| GET | `/reports/ai-cost` | U | `month` | `{total_usd, today_usd, monthly_warn_usd, by_day[], by_model[], by_purpose[], cache_read_ratio}` | V1.7 |
| GET | `/reports/gym` | U | `period` (`week` 7 ngày, `month` 30 ngày tới hôm nay; mặc định `week`) hoặc `from`, `to` (tối đa 92 ngày) | thẻ `{status (ok, disabled, error), message, data}`, luôn 200: `data = {period, from, to, sessions_done (ngày có tập), sessions_complete (buổi đủ hiệp), sessions_planned, lift_highlights[{exercise, from_kg, to_kg, delta_kg}] (tối đa 3 bài tăng tạ), weight {first_kg, last_kg, first_date, last_date} hoặc null, protein {avg_g, target_g, days_logged} hoặc null, today {date, title, rest, exercises, done}, tomorrow {date, title, rest, exercises}, app_url}`; chỉ đọc app gym, không ghi | QĐ-54 |
| POST | `/internal/zalo/events` | `Bearer ZALO_BRIDGE_TOKEN` | `{events: [...]}` tối đa 100 (50 mục 3.15) | `{accepted, rejected: [{event_id, reason}]}`; sai khóa 401 | QĐ-52 |
| GET | `/zalo/status` | U | | `{state (logged_out, waiting_scan, scanned, logged_in, expired, kicked, error, unavailable), account {uid, name}, qr_png_base64, qr_expires_at, last_event_at}`; app hỏi mỗi 2 giây khi đang chờ quét | QĐ-52 |
| POST | `/zalo/login`, `/zalo/logout` | U | | `{state, qr_png_base64, qr_expires_at}` / `{state}`; đã đăng nhập thì 409 | QĐ-52 |
| GET | `/zalo/contacts` | U | | `items: [{thread_id, thread_type, name, avatar, conversation_key}]` (bạn bè, nhóm để mở hội thoại mới) | QĐ-52 |
| POST | `/zalo/conversations/{conversation_key}/sync` | U | | nhóm: lấy 50 tin cũ từ Zalo `{mode: group_history, saved}`; một-một: xin Zalo gửi lại tin cũ `{mode: requested}` (tin về qua sự kiện) | QĐ-52 |
| POST | `/zalo/messages` | U | `conversation_key` (hoặc `thread_id`, `thread_type`), `text`, `file_ids` (tối đa 5), `client_ref` | `{msg_ids, client_ref, conversation_key}`; người dùng tự gõ nên gửi thẳng; tin hiện trong hộp tin khi bridge báo lại; lỗi `NOT_LOGGED_IN` 409, `RATE_LIMITED` 429, `THREAD_NOT_FOUND` 404, `ZALO_BRIDGE_UNAVAILABLE` 503 | QĐ-52 |
| GET, POST | `/reports/exports` | U | `kind` (`expense_sheet`, `expense_docx`, `report_docx`), `month` hoặc `from`, `to` | `Export` (202 khi tạo) | V1.8 |
| GET | `/reports/exports/{id}` | U | | `Export` | V1.8 |
| POST | `/files/upload-url` | U | `original_name`, `mime`, `size_bytes`, `purpose`, `sha256` | `{file_id, upload_url, upload_headers, expires_at}` | V1.0 |
| POST | `/files/{id}/complete` | U | | `File`; đặt việc `file_extract` nếu là PDF, Word, ảnh | V1.0 |
| GET | `/files` | U | `purpose`, `cursor` | `items: File[]` | V1.0 |
| GET, DELETE | `/files/{id}` | U | | `File` + `download_url` / `null` (R) | V1.0 |
| POST | `/files/{id}/drive` | U | | `{queued: true}` (202); lên thư mục *Trợ lý*; chưa nối Drive thì 409 `GOOGLE_NOT_CONNECTED`; xong thì `File` có `drive_file_id`, `drive_url` | V1.8 |
| GET, POST | `/devices` | U | `name`, `model`, `manufacturer`, `os_version`, `app_version_code`, `app_version_name` | `items: Device[]` / `{device, device_token}` (mã trả một lần) | V1.0 |
| PATCH, DELETE | `/devices/{id}` | U | `name` | `Device` / `null` (thu hồi) | V1.0 |
| GET, POST, PATCH, DELETE | `/devices/listened-apps`, `/devices/listened-apps/{id}` | U | `package_name`, `label`, `purpose`, `parser`, `enabled` | `ListenedApp` | V1.2 |
| POST | `/device/events` | D | `events` (1 tới 50) | `{accepted, duplicates, rejected: [{client_event_id, code}]}` | V1.2 |
| GET | `/device/config` | D | `If-None-Match` | Mục 5.8 | V1.2 |
| POST | `/device/heartbeat` | D | Mục 5.8 | `{server_time, config_revision}` | V1.2 |
| GET | `/device/release` | U/D | `current_version_code` | `{update_available, required, latest}`; `latest.download_url` ký mới mỗi lần gọi, sống `latest.download_expires_in` giây (1.800); app gọi lại lúc bấm tải | V1.0 |
| POST | `/device/health` | D | `days[]` | `{accepted}` | V2 |

Bỏ theo QĐ-27: `/users`, `/me/export`, `DELETE /me`, `/consents`, `/admin/audit-log`, `/admin/releases`, `/device/web-bundle`, `/dev/jobs/*`; `/admin/worker` thành `/system/status`.

### 5.2 Chat

**`POST /chat/messages`** với `Accept: text/event-stream` trả SSE; `Accept: application/json` chạy hết lượt rồi trả `{user_message, assistant_message, actions}` một lần. Lỗi trước khi bắt đầu stream trả phong bì JSON.

- `mode` từ nút trên app (*Nghĩ kỹ*, *Tìm web*, *Tóm tắt*); không gửi thì mã tự nhận theo cụm từ trong câu, kể cả *dùng Opus*. Bảng chọn model ở `20-bo-nao-ai.md` mục 3.1 (QĐ-27 mục 9). `research` bật công cụ tìm web của Claude API.

| Sự kiện SSE | `data` |
|---|---|
| `message.created` | `{user_message, conversation_id}` |
| `text.delta` | `{text}` |
| `tool.started` | `{name, label}` |
| `tool.finished` | `{name, ok}` |
| `action` | Một hành động (mục 3.9) |
| `message.completed` | `{assistant_message (có `model`, `citations`), usage: {input_tokens, output_tokens, cache_read_tokens, cost_usd}}` |
| `error` | `{code, message}`; sau đó luồng đóng |

```
event: tool.started
data: {"name":"add_expense","label":"Đang ghi khoản chi"}

event: text.delta
data: {"text":"Ghi 45.000 đ ăn uống."}

event: action
data: {"id":"a1","type":"open_screen","label":"Sửa khoản này","screen":"expense_detail","params":{"expense_id":551}}

event: message.completed
data: {"assistant_message":{"id":884,"model":"claude-haiku-5-5"},"usage":{"input_tokens":3120,"output_tokens":24,"cache_read_tokens":2900,"cost_usd":0.0003}}
```

- `Conversation` (QĐ-51): `{id, title, title_source (auto, user), pinned, started_at, last_message_at, message_count, last_preview (120 ký tự đầu tin hiện cuối), created_at, local_date, summary}`. Phiên chưa tên thì sau lượt trả lời đầu (thử tới lượt thứ 3) máy chủ gọi `app.ai.session_title.suggest_title` ở luồng nền, chỉ ghi khi phiên vẫn chưa tên và người dùng chưa đặt.
- `Message`: `{id, conversation_id, role, text, model, citations, attachments, actions, status, created_at}`; chỉ trả tin `hidden = false`. `citations` là `[{title, url}]`, tối đa 5, chỉ có khi tìm web.
- Ping `: ping` mỗi 15 giây; tiêu đề `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Mất kết nối thì máy chủ vẫn chạy hết lượt và lưu; app gọi lại `/chat/conversations/{id}/messages` (bản cũ gọi `/chat/today`).
- **Phiên** (QĐ-51): không tách 04:00, không nối phiên 3 giờ; mở lại phiên cũ thì lịch sử gửi Claude là tóm tắt cộng tin chưa tóm của chính phiên đó (`11-co-so-du-lieu.md` mục 3.7).
- **Tóm tắt hộp tin** không có endpoint riêng: nút *Tóm tắt* gửi câu chat dựng sẵn với `mode = summary`; model gọi công cụ `summarize_inbox`.

**Duyệt** chỉ cho gửi ra ngoài và xóa hàng loạt hoặc xóa cả chuyến (QĐ-27 mục 2). `PendingAction`: `{id, tool_name, title, summary, details, danger, status, expires_at, created_at}`. `approve` kiểm hạn, trạng thái, `payload_hash`, chạy hàm `execute` của công cụ (không qua Claude), nối tin `system` ẩn báo kết quả. Câu chat *ok* không duyệt được.

### 5.3 Tìm chung

`GET /search?q=` tìm toàn văn (cấu hình `troly_vn`, gõ không dấu vẫn ra) trên ghi chú, tin chat hiện, hộp tin, lịch trình (tên chuyến và điểm dừng), chữ trích của tệp (QĐ-27 mục 11). Kết quả xếp theo `ts_rank` rồi thời gian.

```json
{ "source": "file", "id": 77, "title": "Lich trinh Tra Vinh.docx", "rank": 0.42,
  "snippet": "... ngày 2 ghé <b>chùa Âng</b> ...", "date": "2026-11-10T09:12:00+07:00",
  "open": { "id": "s1", "type": "open_screen", "label": "Mở", "screen": "trip_detail", "params": { "trip_id": 9 } } }
```

`snippet` dựng bằng `ts_headline`, chỉ thẻ `<b>`; không ra kết quả thì thử `pg_trgm` trên tiêu đề. Module `search` giữ hàm này, công cụ AI `search_everything` dùng chung. Chữ của tệp lấy từ `tab_file_text`.

### 5.4 Chi tiêu và hộp tin

- `Expense`: `{id, amount_vnd, kind, account, account_last4, to_account, to_account_last4, category, merchant, place, note, spent_at, source, parser, parse_confidence, needs_review}`. Không có số dư (QĐ-22). `total_expense_vnd` không tính `transfer`.
- `Conversation`: `{conversation_key, app, title, is_group, last_sender, last_text, last_posted_at, unread_count, importance, is_private, account_email}`; `InboxMessage` cũng có `account_email` (Gmail, QĐ-50).
- `InboxMessage` có thêm (QĐ-52) `is_self`, `media: [{type, name, size, mime, status, file_id}]` (mở bằng `GET /files/{file_id}`), `recalled_at`, `quote`. Bot gửi Zalo thay chỉ qua thẻ `send_zalo_message` (`zalo.service.request_send`). Route `/zalo/*` và `/internal/zalo/events` chỉ có khi `FEATURE_ZALO_BRIDGE`; `GET /system/status` có `features: {gym, connectors, zalo_bridge}`.
- Riêng tư: `POST /inbox/rules` với `kind = private_conversation`, `value = <conversation_key>`. Tin riêng tư hiện trong app và `GET /search`, không bao giờ ra công cụ AI (`search_everything`, công cụ hộp tin).
- Danh sách hộp tin, tin trong cuộc trò chuyện phân trang bằng `cursor`, trả `next_cursor`.
- Gửi Gmail chỉ qua thẻ duyệt (`tool_name = send_gmail_draft`); trước khi gửi so nội dung với `body_hash`, khác thì `ACTION_PAYLOAD_CHANGED`.

### 5.5 Việc và lịch

- `Task`: `{id, title, note, status, priority, due_date, due_at, completed_at, completed_source, event_id, sync_status}`. `GET /tasks` không truyền `status` thì trả mọi trạng thái; xếp theo hạn (việc theo ngày tính 23:59 giờ người dùng, không hạn cuối cùng), trả `next_cursor`; `due = week` là 7 ngày từ hôm nay. Việc có `due_at` sinh sự kiện lịch; bỏ `due_at` thì xóa sự kiện. Google Tasks báo xong thì `done`; báo xóa thì `remote_deleted`, người dùng chọn qua `resolve-remote-delete`.
- `Event`: `{id, occurrence_start, is_recurring, title, description, location, all_day, start_at, end_at, start_date, end_date, status, remind_minutes, remind_source, is_alarm, attendees, is_organizer, source, task_id, sync_status, google_html_link, meet_url}`. Tạo, sửa sự kiện nhận `meet: true` để Google tạo link Meet; có khách thì vẫn qua thẻ duyệt. `is_organizer = false` (người khác mời) thì sửa nội dung trả 409 `EVENT_NOT_ORGANIZER`, chỉ đổi được `remind_source`, `remind_minutes`, `is_alarm`. Lần lặp có `id` của bản gốc và `occurrence_start`; sửa, xóa một lần thì gửi kèm `occurrence_start`.
- **Khách mời** (QĐ-23): tạo, sửa, xóa sự kiện có `attendees` trả 202 với `data = {pending_action: {id, tool_name, title, summary, details, danger, status, expires_at, action}}`, `action` là hành động `confirm`; duyệt bằng `POST /chat/actions/{id}/approve` mới ghi và đẩy Google với `sendUpdates=all`. Chỉ đổi `remind_minutes`, `is_alarm`, `remind_source` thì không cần duyệt, kể cả trên bản gốc sự kiện lặp.
- `Reminder`: `{reminder_key, source, source_id, fire_at (UTC), title, body, kind (normal, alarm), deep_link}`. Nhắc của việc có giờ có `source = task`, `source_id` là id việc, `deep_link` `troly://lich/viec/<id>`; còn lại `troly://lich/su-kien/<id>`, lần lặp thêm `?lan=<occurrence_start UTC>`. `reminder_key` ổn định: `event:<id>:<giờ gốc UTC dạng 20261123T020000Z>:<phút>` hoặc `task:<id>:...`; `If-None-Match` nhận cả `revision` trần lẫn có ngoặc kép. Nút *Xong* gửi `reminder_action` `done` thì việc thành `done`. Chỉ sự kiện `remind_source = app`, trải cả lần lặp. Sự kiện tạo trên Google do Google nhắc (QĐ-26). `revision` là băm danh sách, trùng `If-None-Match` thì 304.

### 5.6 Google

- `GoogleStatus`: `{connected, email, status, packs: [{name, enabled, granted, last_sync_at, status, last_error}], initial_sync: {state, message}, failed_outbox_count}`. `initial_sync.message` là câu cho giao diện, ví dụ *Đang lấy lịch lần đầu*.
- **Kết nối**: `POST /google/connect` tạo `state` và PKCE (lưu `tab_google_oauth_state`, 10 phút, dùng một lần), trả `auth_url` (`access_type=offline`, `prompt=consent`, `include_granted_scopes=true`). App mở bằng Custom Tab. Google về `GOOGLE_REDIRECT_URI` (`https://assistant.baohuynh.io.vn/api/v1/google/oauth/callback`); máy chủ đổi mã, lưu token mã hóa, đặt việc `google_initial_sync`, trả trang HTML chuyển về `troly://cai-dat/google?ket-qua=<ok|huy|thieu-quyen|loi>`.
- **Ngắt**: `keep_data` theo `11-co-so-du-lieu.md` mục 3.15.
- **Webhook**: kiểm `channel_id` và băm token; khớp thì `needs_sync = true` và `NOTIFY troly_wake`; luôn trả 200 rỗng trong 1 giây. Tasks đọc ngược bằng quét 15 phút; Gmail quét 5 phút.

### 5.7 Lịch trình

- `import`, `evaluate` chạy nền (`status` `importing`, `evaluating`); app hỏi `/jobs/{id}` hoặc `/trips/{id}` mỗi 3 giây.
- `Trip` gồm `days[].stops[]`, `needs_confirmation[]`, `facts[]` (`tab_trip_fact`), `options[]`, `evaluation` (`{evaluated_at, risks[]}`). Một rủi ro: `{code, level, day_no, stop_id, message, suggestion, checked_at}` (41 mục 6.3).
- `map-links` trả mỗi ngày `segments[]` là hành động `open_map_directions`, mỗi điểm `{stop_id, lat, lng, navigation, place}` với `navigation` là `open_map_navigation` (có `fallback_url`), `place` là `open_map_place`. Chia đoạn theo `max_waypoints`, link tối đa 2.048 ký tự (41 mục 9.2).
- `to-calendar`: mỗi ngày một sự kiện cả ngày cộng sự kiện có giờ cho mốc cứng; `remind_source = app`, mốc phà và trả phòng `is_alarm = true`.
- `export-docx` với `save_to_drive = true` thì thêm lệnh `file_upload` lên Drive.

### 5.8 Thiết bị

- `/device/events`: máy chủ chỉ lưu `tab_device_event` rồi trả ngay, `NOTIFY troly_wake`. `payload` theo `11-co-so-du-lieu.md` mục 3.5. Từ chối từng sự kiện (app không được nghe, khớp luật OTP lần hai, thiếu trường, `posted_at` cũ hơn 7 ngày hoặc sớm hơn giờ máy chủ quá 10 phút), không hỏng cả lô. `accepted + duplicates + số rejected` bằng số đã gửi; plugin xóa cả lô, chỉ giữ khi lỗi mạng hoặc 5xx. `messages[].at` là ISO 8601 có múi giờ hoặc mili giây epoch; trường lạ trong `payload` bị bỏ.
- `/device/config`: `{revision, listened_apps: [{package_name, purpose, parser, enabled}], otp_rules_version, sms_brand_senders[], upload: {batch_max, min_interval_seconds}}`; trả `ETag` là `revision`, `If-None-Match` khớp thì 304. Giữ nguyên `sms_default`; bỏ `com.google.android.gm` khi gói `gmail` của Google đã nối.
- `/device/heartbeat` nhận: `app_version_code`, `app_version_name`, `manufacturer`, `default_sms_package`, `notification_access`, `listener_connected`, `notifications_enabled`, `exact_alarm_allowed`, `battery_optimization_ignored`, `queue_size`, `otp_blocked_today`.
- `/device/release`: đọc `releases/latest.json` trên bucket `assistant` (tiền tố `releases/`) (đệm 5 phút, `50-ha-tang-trien-khai.md` chốt); trả `latest = {version_code, version_name, download_url (300 giây), sha256, size_bytes, notes, min_supported_version_code}`; `required = true` khi bản đang chạy thấp hơn `min_supported_version_code`. App luôn hỏi trước khi cài (QĐ-18).

### 5.9 Trạng thái hệ thống

`SystemStatus`: `{jobs: [{name, last_status, last_finished_at, next_run_at, last_error}], queues: {device_event_pending, job_queue_pending, google_outbox_failed}, backup: {last_ok_at, size_bytes, kept}, disk: {free_percent, state}, ai: {today_usd, month_usd, monthly_warn_usd}, otp_blocked_server, silent_devices[]}`. `/system/jobs/{name}/run` chỉ nhận job trong bảng của `10-kien-truc-backend.md` mục 3.9.

### 5.10 Trang tĩnh (ngoài `/api`)

| Đường | Nội dung |
|---|---|
| `GET /chinh-sach-rieng-tu` | Dữ liệu thu, gửi tới đâu, giữ bao lâu; Google cần trang này cho màn đồng ý OAuth |
| `GET /tai-app` | Bản APK mới nhất từ `latest.json`, `sha256`, nút tải, các bước cài trên Galaxy S25+ (`50-ha-tang-trien-khai.md`); `Cache-Control: no-store`; nút tải trỏ tới `/tai-app/apk` nên trang mở lâu vẫn tải được |
| `GET /tai-app/apk` | 302 sang link R2 ký mới (1.800 giây) của APK mới nhất; chưa có bản phát hành thì 404 |

## 6. Kiểm thử

Chỉ phần dễ sai (QĐ-27 mục 8): mọi route có trong bảng mục 5.1; luồng SSE đúng thứ tự, mất kết nối vẫn lưu, gửi lại cùng `client_message_id` không gọi Claude lần hai; `/device/events` gửi trùng thành `duplicates`, OTP bị `rejected`; `/calendar/reminders` bỏ sự kiện `remind_source = google`, có đủ lần lặp; duyệt hết hạn hoặc đổi `input` bị từ chối; `/search` tìm không dấu ra kết quả có dấu ở cả năm loại.

## 7. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| WebView hoặc Cloudflare đệm SSE | Tiêu đề chống đệm, ping 15 giây, đường lui JSON |
| Plugin cũ gọi API đã đổi | Nhóm `/device/*` giữ ổn định; đổi phá vỡ mở `v2` |
| Tìm chung chậm khi dữ liệu lớn | Mỗi loại một truy vấn có `limit`, chỉ mục GIN; xem lại khi quá 1 giây |

## 8. Cần agent khác

| Agent | Việc |
|---|---|
| agent AI | 20 mục 3.8: vỏ phẳng có `id` (bỏ `payload`), `confirm` bỏ `kind` (QĐ-26) |
| agent app Android | 31: bỏ thẻ duyệt cho xóa một dòng, thêm *Hoàn tác*; màn `search` gọi `/search`; màn *Máy chủ* gọi `/system/status` và nút *Sao lưu ngay*; `settings_ai_cost`. 30: `heartbeat` đủ trường mục 5.8 |
| agent Google | 40, 41: đường dẫn theo bảng mục 5.1; `initial_sync` trong `GoogleStatus`; `save_to_drive` |
| agent hạ tầng | 50: `releases/latest.json` là nguồn duy nhất của `/device/release` và `/tai-app`. 60: dẫn sang bảng mục 3.7 |
