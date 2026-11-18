# API

Ngày lập: 18/11/2026. Người giữ: agent kiến trúc. Trạng thái: bản 2, thống nhất theo `80-ra-cheo-lan-1.md` (mục A2, A6, D2) và QĐ-15 tới QĐ-25.

Theo QĐ-25, tệp này là **nguồn chuẩn cho đường dẫn API và giới hạn tần suất**. Mọi đường dẫn dưới `/api/v1`, danh từ số nhiều. Tài liệu khác nhắc API thì dẫn sang bảng ở mục 5.1, không chép lại.

Tài liệu liên quan: [10-kien-truc-backend.md](10-kien-truc-backend.md) (đăng nhập, lỗi), [11-co-so-du-lieu.md](11-co-so-du-lieu.md) (bảng), [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md) (kiểu hành động, công cụ), [30-app-android.md](../30-app/30-app-android.md), [31-giao-dien.md](../30-app/31-giao-dien.md), [40-tich-hop-google.md](../40-google/40-tich-hop-google.md), [41-ban-do-lich-trinh.md](../40-google/41-ban-do-lich-trinh.md), [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md).

## 1. Mục tiêu

- Một bảng duy nhất liệt kê **toàn bộ API REST**: đường dẫn, phương thức, quyền, đầu vào, đầu ra, mã lỗi, bản.
- Chốt quy ước chung: phong bì, phân trang, thời gian, tiền, chống gửi trùng, phiên bản, giới hạn tần suất.
- Chốt hợp đồng cho chỗ đặc biệt: chat dạng stream, hành động trả cho app, API cho thiết bị, đăng bản bằng mã CI, OAuth và webhook Google.

## 2. Phạm vi

API do tiến trình `api` phục vụ cho giao diện React, plugin Kotlin, GitHub Actions (đăng bản), Google (webhook, chuyển hướng OAuth) và máy chạy Claude CLI ở V3. Không gồm API Claude, Google mà máy chủ gọi ra (ở 20, 40, 41) và cầu nối giao diện với plugin (ở 30).

## 3. Thiết kế

### 3.1 Quy ước chung

| Mục | Quy ước |
|---|---|
| Gốc | `https://<api-domain>/api/v1`. Riêng `/api/health` không phiên bản |
| Định dạng | JSON UTF-8, tên trường snake_case tiếng Anh |
| Đường dẫn | Danh từ số nhiều, gạch ngang: `/expenses`, `/inbox/conversations`. Hành động không phải CRUD là động từ ở cuối: `/tasks/{id}/complete` |
| Id | Số nguyên. Id máy khách sinh là UUID. Riêng cuộc trò chuyện hộp tin dùng `conversation_key` (chuỗi) |
| Thời điểm | ISO 8601 có độ lệch (`2026-11-18T15:00:00+07:00`); thiếu độ lệch thì 400. Máy chủ trả theo múi giờ người dùng. Ngoại lệ: `fire_at` của `/calendar/reminders` trả UTC (`Z`) vì máy chỉ nhận mốc UTC (30 mục 3.8) |
| Ngày | `YYYY-MM-DD` |
| Tiền | Số nguyên VND, hậu tố `_vnd`. Chi phí AI hậu tố `_usd`, số thực |
| Rỗng | Trả `null`, không bỏ trường |
| Sửa một phần | `PATCH` chỉ gửi trường cần đổi; `null` là xóa giá trị |
| Xóa | `DELETE` trả `data: null`, mã 200 |

Trong bảng ở mục 5, đường dẫn viết bỏ phần `/api/v1`.

### 3.2 Xác thực

| Cách | Tiêu đề | Ký hiệu | Dùng cho |
|---|---|---|---|
| JWT người dùng | `Authorization: Bearer <access_token>` | **U** | Mọi API của giao diện |
| JWT chủ | như trên, `role = owner` | **O** | Quản lý tài khoản, bản phát hành, trạng thái hệ thống, kiểm toán |
| Mã thiết bị | `Authorization: Device <device_token>` | **D** | Nhóm `/device/*` |
| Một trong hai | JWT hoặc mã thiết bị | **U/D** | `/device/release`, `/device/web-bundle`, `/calendar/reminders` |
| Mã CI | `Authorization: CI <release_token>` | **CI** | Chỉ `POST /admin/releases` |
| Mã máy chạy (V3) | `Authorization: Runner <runner_token>` | **R** | Chỉ `/dev/jobs/*`, khi `DEV_JOBS_ENABLED=true` |
| Kênh Google | `X-Goog-Channel-ID`, `X-Goog-Channel-Token` | **G** | Chỉ `/webhooks/google/calendar` |
| Không cần | | **-** | `/api/health`, `/auth/login`, `/auth/refresh`, `/google/oauth/callback` |

- Mỗi loại mã chỉ gọi được đúng nhóm của nó; gọi sai nhóm trả 401 `AUTH_REQUIRED`. Mã thiết bị không đổi được lấy mã truy cập (rà chéo A2 dòng 31).
- Người dùng còn `must_change_password` chỉ gọi được `/auth/me`, `/auth/change-password`, `/auth/logout`; còn lại 403 `AUTH_PASSWORD_CHANGE_REQUIRED`.
- Chi tiết JWT, mã làm mới xoay vòng, mã thiết bị, mã CI ở [10-kien-truc-backend.md](10-kien-truc-backend.md) mục 3.7.

### 3.3 Phong bì

```json
{ "success": true, "message": "", "data": { "id": 15, "amount_vnd": 45000 } }
```

```json
{ "success": false, "message": "Dữ liệu chưa hợp lệ.",
  "data": { "code": "VALIDATION_ERROR", "fields": { "amount_vnd": "Số tiền phải lớn hơn 0." } } }
```

- Thành công: 200; 201 khi tạo mới; 202 khi nhận việc chạy nền hoặc tạo hành động chờ duyệt.
- Lỗi: mã HTTP theo mục 3.5; `data.code` để app rẽ nhánh; `message` hiện thẳng cho người dùng.
- Không dùng phong bì: luồng SSE của chat (mục 5.3), `GET /google/oauth/callback` (trang HTML), `POST /webhooks/google/calendar` (200 rỗng), phản hồi 304.
- Mọi phản hồi có `X-Request-ID`; lỗi 500 đưa `request_id` vào `data`.

### 3.4 Phân trang và lọc

**Con trỏ** cho mọi danh sách dài theo thời gian: tham số `limit` (mặc định 50, tối đa 200) và `cursor` (chuỗi mờ lấy từ `next_cursor`).

```json
{ "success": true, "message": "", "data": { "items": [ ], "next_cursor": "eyJ0Ijo...In0" } }
```

- `next_cursor = null` là hết. Con trỏ hỏng thì 400 `INVALID_CURSOR`.
- Thứ tự sắp cố định theo endpoint. Không trả tổng số dòng.
- Danh sách ngắn có giới hạn tự nhiên (danh mục, luật, thiết bị, sự kiện trong khoảng ngày) trả `data.items`, không có `next_cursor`.

**Lọc** bằng tham số thống nhất: `from`, `to` (`from` tính vào, `to` không tính), `q` (tìm chữ, bỏ dấu), `status`, `app`, `kind`. Nhiều giá trị nối bằng dấu phẩy.

### 3.5 Mã lỗi

| HTTP | `data.code` | Câu mẫu | Khi nào |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Dữ liệu chưa hợp lệ. | Có `fields` |
| 400 | `INVALID_CURSOR` | Trang dữ liệu không hợp lệ, tải lại từ đầu. | |
| 400 | `RELEASE_FILE_MISMATCH` | Tệp phát hành không khớp. | `POST /admin/releases`: tệp không có trên R2 hoặc `sha256` lệch |
| 401 | `AUTH_REQUIRED` | Cần đăng nhập. | Thiếu, sai tiêu đề xác thực, hoặc mã sai nhóm |
| 401 | `AUTH_INVALID_CREDENTIALS` | Email hoặc mật khẩu không đúng. | |
| 401 | `AUTH_TOKEN_EXPIRED` | Phiên đã hết hạn. | App gọi `/auth/refresh` rồi thử lại một lần |
| 401 | `AUTH_REFRESH_INVALID` | Phiên đăng nhập không còn hiệu lực, đăng nhập lại. | |
| 401 | `DEVICE_REVOKED` | Thiết bị đã bị thu hồi. | Plugin dừng gửi |
| 403 | `FORBIDDEN` | Không có quyền làm việc này. | Thành viên gọi API của chủ |
| 403 | `AUTH_PASSWORD_CHANGE_REQUIRED` | Cần đổi mật khẩu trước. | |
| 403 | `ACCOUNT_DISABLED` | Tài khoản đã bị khóa. | |
| 403 | `CONSENT_REQUIRED` | Cần đồng ý thông báo xử lý dữ liệu trước. | Thành viên chưa đồng ý mà bật nghe thông báo (60 mục 3.10) |
| 404 | `NOT_FOUND` | Không tìm thấy. | Không có, **hoặc là dữ liệu của người khác**; cũng dùng cho `/dev/*` khi tắt |
| 409 | `CONFLICT` | Dữ liệu đã thay đổi, tải lại rồi thử lại. | Sai `version` |
| 409 | `DUPLICATE` | Đã có mục này. | |
| 409 | `USER_LIMIT_REACHED` | Đã đủ số tài khoản. | `MAX_USERS` |
| 409 | `OWNER_HAS_MEMBERS` | Còn thành viên, chưa xóa được tài khoản chủ. | `DELETE /me` |
| 409 | `CHAT_BUSY` | Trợ lý đang trả lời câu trước. | |
| 409 | `ACTION_NOT_PENDING` | Yêu cầu này đã được xử lý hoặc đã hết hạn. | |
| 409 | `ACTION_PAYLOAD_CHANGED` | Nội dung đã thay đổi sau khi tạo, nhờ trợ lý làm lại. | `payload_hash` lệch |
| 409 | `RECURRING_SERIES_EDIT` | Sửa cả chuỗi lặp trong Google Calendar. | Sửa bản gốc sự kiện lặp; `data` có `google_html_link` |
| 409 | `GOOGLE_NOT_CONNECTED` | Chưa kết nối Google. | |
| 409 | `GOOGLE_REAUTH_REQUIRED` | Cần kết nối lại Google. | `status = reauth_required` |
| 409 | `GOOGLE_SCOPE_MISSING` | Cần cấp thêm quyền Google cho mục này. | Gói chưa bật hoặc người dùng bỏ tích quyền |
| 413 | `PAYLOAD_TOO_LARGE` | Dữ liệu gửi lên quá lớn. | |
| 415 | `UNSUPPORTED_FILE_TYPE` | Loại tệp này chưa hỗ trợ. | |
| 426 | `APP_VERSION_UNSUPPORTED` | Bản app đã cũ, cập nhật để dùng tiếp. | Mục 3.6 |
| 429 | `RATE_LIMITED` | Thao tác quá nhanh, thử lại sau ít phút. | Có `Retry-After` |
| 429 | `AUTH_LOCKED` | Sai mật khẩu nhiều lần, thử lại sau 15 phút. | |
| 502 | `AI_UNAVAILABLE` | Trợ lý đang bận, thử lại sau. | |
| 502 | `EXTERNAL_SERVICE_ERROR` | Dịch vụ ngoài đang lỗi, thử lại sau. | Google, R2 |
| 500 | `INTERNAL_ERROR` | Máy chủ gặp lỗi, đã ghi lại. | |

Không còn mã `AI_BUDGET_EXCEEDED`: theo QĐ-15 không có trần chi phí AI theo ngày; vượt `AI_MONTHLY_USD` chỉ cảnh báo. Khi thêm người dùng có trần riêng thì thêm lại mã này.

**Mã theo từng mục trong lô** (nằm trong `rejected` của `/device/events`, không phải mã HTTP): `APP_NOT_LISTENED`, `OTP_DETECTED`, `INVALID_EVENT`, `EVENT_TOO_OLD` (`posted_at` cũ hơn 7 ngày hoặc sớm hơn giờ máy chủ quá 10 phút).

Mã mới phải ghi vào bảng này; danh sách là hằng số trong `core/errors.py`.

### 3.6 Phiên bản API

- Phiên bản nằm ở đường dẫn: `/api/v1`, kể cả nhóm thiết bị (ĐX-API-01).
- Thay đổi không phá vỡ (thêm endpoint, thêm trường, thêm tham số tùy chọn, thêm giá trị liệt kê) làm thẳng trên `v1`. App bỏ qua trường lạ, `type` hành động lạ, giá trị liệt kê lạ.
- Thay đổi phá vỡ thì mở `/api/v2` cho endpoint đó, chạy song song tối thiểu 30 ngày.
- App gửi mọi yêu cầu `X-App-Version: <versionCode>` và `X-Web-Version: <bản giao diện>`; plugin gửi `X-App-Version`.
- `X-App-Version` nhỏ hơn `min_supported_version_code` của APK mới nhất đã phát hành thì 426, trừ `/device/release`, `/device/web-bundle`, `/auth/*`.
- Nhóm `/device/*` giữ ổn định nhất; đổi nhóm này phải qua đề xuất quyết định.

### 3.7 Giới hạn tần suất và kích thước (bảng chung)

Bảng này thay các con số rời ở `60-bao-mat-rieng-tu.md` mục 3.7 và `50-ha-tang-trien-khai.md` mục 3.7 (A6 dòng 75). Đếm trong bộ nhớ của tiến trình `api` (một tiến trình uvicorn, `50` mục 3.4); khóa đăng nhập nằm trong DB. IP lấy từ `CF-Connecting-IP`.

| Đường dẫn | Khóa đếm | Mức | Biến môi trường |
|---|---|---|---|
| `/api/v1/auth/*` (lớp ngoài, Cloudflare WAF) | IP | 20 yêu cầu mỗi 10 giây | (cấu hình Cloudflare) |
| `POST /auth/login` | IP và email | 10 lần mỗi 15 phút; ngoài ra sai 5 lần liền khóa tài khoản 15 phút | `RATE_LOGIN_PER_15MIN`, `LOGIN_MAX_FAILS`, `LOGIN_LOCK_MINUTES` |
| `POST /auth/refresh` | Phiên | 30 lần mỗi giờ | `RATE_REFRESH_PER_HOUR` |
| `POST /chat/messages` | Người dùng | 20 câu mỗi phút và 60 câu mỗi giờ | `RATE_CHAT_PER_MIN`, `AI_USER_HOURLY_TURNS` |
| `POST /device/events` | Thiết bị; người dùng | Lô 1 tới 50 sự kiện, thân tối đa 256 KB; 120 sự kiện mỗi phút mỗi thiết bị; 5.000 sự kiện mỗi ngày mỗi người | `RATE_DEVICE_EVENTS_PER_MIN`, `RATE_DEVICE_EVENTS_PER_DAY` |
| `/device/*` khác | Thiết bị | 60 yêu cầu mỗi phút | `RATE_DEVICE_PER_MIN` |
| `POST /me/export` | Người dùng | 3 lần mỗi ngày | |
| `POST /admin/releases` | Mã CI | 30 lần mỗi giờ | |
| `POST /webhooks/google/calendar` | | Không đếm; worker gộp thông báo trong 10 giây | |
| Mọi đường khác | Người dùng | 300 yêu cầu mỗi phút | `RATE_USER_PER_MIN` |

| Kích thước | Giới hạn |
|---|---|
| Thân yêu cầu JSON | 1 MB (riêng `/device/events` 256 KB) |
| Tệp tải lên R2 | 25 MB; ghi âm tối đa 5 phút |
| Tin chat | 4.000 ký tự (A6 dòng 80: máy chủ nhận 4.000 để dán đoạn văn dài; giao diện tự đặt giới hạn hiển thị); tối đa 4 tệp đính kèm |
| Chữ trong sự kiện thiết bị | Máy cắt 2.000 ký tự; máy chủ cắt lại nếu dài hơn, không từ chối cả lô |
| URL ký sẵn R2 | Sống 300 giây (`R2_PRESIGN_SECONDS`) cho cả tải lên và tải về (A6 dòng 74). R2 chỉ kiểm chữ ký lúc bắt đầu yêu cầu, nên tải APK lớn vẫn xong dù quá 5 phút |

Vượt mức trả 429 `RATE_LIMITED` kèm `Retry-After`.

### 3.8 Chống gửi trùng

| Chỗ | Cách |
|---|---|
| Gửi tin chat | `client_message_id` (UUID). Gửi lại cùng mã: lượt cũ xong thì trả tin trả lời cũ dạng JSON; đang chạy thì 409 `CHAT_BUSY` |
| Sự kiện thiết bị | `client_event_id` (UUID) mỗi sự kiện; trùng thì vào `duplicates` |
| Duyệt hành động | Duyệt lần hai 409 `ACTION_NOT_PENDING` |
| Việc chạy nền | `dedupe_key` ở máy chủ: bấm *Đánh giá* hai lần trả cùng `job_id` |
| Tạo mới khác | App chặn bấm đúp ở nút lưu; máy chủ không chống trùng |

### 3.9 Hành động trả cho app

Bộ kiểu theo `20-bo-nao-ai.md` mục 3.8 và `31-giao-dien.md` mục 3.3 (A2 dòng 24). Trường phẳng, không bọc trong `payload`. Kiểu `open_map`, `open_url` của bản 1 bỏ hẳn.

| `type` | Trường |
|---|---|
| `open_map_navigation` | `label`, `lat`, `lng`, `mode` (`l` xe hai bánh, `d`, `w`), `avoid` (`h` hoặc `null`), `query` (khi chưa có tọa độ) |
| `open_map_directions` | `label`, `urls[]`, `segment_labels[]` (nhãn mỗi đoạn, cùng độ dài với `urls`) |
| `open_map_place` | `label`, `query`, `place_id` |
| `open_link` | `label`, `url` (chỉ `https`), `kind` (`file`, `gmail`, `sheet`, `web`) |
| `open_screen` | `label`, `screen`, `params` |
| `confirm` | `pending_action_id`, `title`, `summary`, `details[]` (`label`, `value`), `confirm_label`, `cancel_label`, `danger`, `require_unlock`, `expires_at` |
| `memory_changed` | `version`, `text`, `undo_version` |
| `choices` | `options[]` (`label`, `value`) |

Giá trị `screen`: `chat`, `inbox`, `inbox_conversation`, `calendar_day`, `event_detail`, `task_list`, `task_detail`, `expense_list`, `expense_detail`, `trip_list`, `trip_detail`, `report`, `settings_google`, `settings_listened_apps`, `settings_device_check`, `settings_profile`, `settings_ai_budget` (31 mục 3.3). URL bản đồ luôn do máy chủ dựng (`trip/service.py` dùng chung cho API và `ai/actions.py`), không lấy từ chữ AI viết.

## 4. Dữ liệu cần

Không có bảng riêng. API đọc ghi các bảng ở [11-co-so-du-lieu.md](11-co-so-du-lieu.md) qua service của từng module.

## 5. API hoặc giao tiếp

### 5.1 Bảng API duy nhất

Cột *Mục* chỉ tới phần mô tả thêm bên dưới. Lỗi chung (`AUTH_*`, `VALIDATION_ERROR`, `NOT_FOUND` với mọi đường có `{id}`, `RATE_LIMITED`, `INTERNAL_ERROR`) không ghi lại từng dòng.

**Hệ thống, đăng nhập, tài khoản**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/api/health` | - | | `{status, db, worker_lag_seconds, version, git_sha}` | | V1.0 | 5.2 |
| POST | `/auth/login` | - | `email`, `password`, `label` | `Tokens` + `user` | `AUTH_INVALID_CREDENTIALS`, `AUTH_LOCKED`, `ACCOUNT_DISABLED` | V1.0 | 5.2 |
| POST | `/auth/refresh` | - | `refresh_token` | `Tokens` | `AUTH_REFRESH_INVALID` | V1.0 | 5.2 |
| POST | `/auth/logout` | U | | `null` | | V1.0 | |
| POST | `/auth/change-password` | U | `current_password`, `new_password` | `null` | `AUTH_INVALID_CREDENTIALS` | V1.0 | |
| GET | `/auth/me` | U | | `User` | | V1.0 | |
| GET | `/auth/sessions` | U | | `items: Session[]` | | V1.0 | |
| DELETE | `/auth/sessions/{id}` | U | | `null` | | V1.0 | |
| POST | `/me/export` | U | `password` | `{job_id}` (202) | | V1.0 | 5.2 |
| DELETE | `/me` | U | `password` | `null` | `AUTH_INVALID_CREDENTIALS`, `OWNER_HAS_MEMBERS` | V1.0 | 5.2 |
| GET | `/consents` | U | | `items: [{kind, notice_version, accepted_at, withdrawn_at}]`, `current_notice_version` | | V1.0 | 5.2 |
| POST | `/consents` | U | `kind`, `notice_version` | `Consent` (201) | | V1.0 | |
| DELETE | `/consents/{kind}` | U | | `null` | | V1.0 | 5.2 |
| GET | `/users` | O | | `items: User[]` | | V1.0 | |
| POST | `/users` | O | `name`, `email` | `user`, `temporary_password` (một lần) | `USER_LIMIT_REACHED`, `DUPLICATE` | V1.0 | |
| PATCH | `/users/{id}` | O | `name`, `is_active` | `User` | Chủ không tự khóa mình | V1.0 | |
| POST | `/users/{id}/reset-password` | O | | `temporary_password` | | V1.0 | |
| GET | `/settings` | U | | `{values, defaults}` | | V1.0 | 5.2 |
| PATCH | `/settings` | U | `{khóa: giá trị}` | `{values}` | | V1.0 | |
| GET | `/jobs/{id}` | U | | `{id, kind, status, result, error, created_at, finished_at}` | | V1.0 | |
| POST | `/jobs/{id}/cancel` | U | | `{id, status}` | `CONFLICT` khi đã xong | V1.0 | |

**Trí nhớ và chat**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/memory/profile` | U | | `{content, version, updated_by, updated_at}` | | V1.0 | |
| PUT | `/memory/profile` | U | `content`, `version` | như trên | `CONFLICT` | V1.0 | |
| GET | `/memory/profile/revisions` | U | `cursor`, `limit` | `items: [{version, changed_by, reason, created_at, preview}]` | | V1.0 | |
| GET | `/memory/profile/revisions/{version}` | U | | `{version, content, changed_by, reason, created_at}` | | V1.0 | |
| POST | `/memory/profile/revisions/{version}/restore` | U | `version` (bản hiện tại) | hồ sơ sau khôi phục | `CONFLICT` | V1.0 | Hoàn tác của `memory_changed` |
| GET | `/memory/notes` | U | `q`, `tag`, `cursor`, `limit` | `items: Note[]`, `next_cursor` | | V1.0 | |
| POST | `/memory/notes` | U | `title`, `body`, `tags` | `Note` (201) | | V1.0 | |
| GET, PATCH, DELETE | `/memory/notes/{id}` | U | `title`, `body`, `tags` | `Note` / `null` | | V1.0 | |
| GET | `/chat/today` | U | | `{conversation, messages: Message[] (50 tin), next_cursor, pending_actions}` | | V1.0 | 5.3 |
| GET | `/chat/conversations` | U | `cursor`, `limit` | `items: [{id, local_date, summary, message_count}]` | | V1.0 | |
| GET | `/chat/conversations/{id}/messages` | U | `cursor`, `limit` | `items: Message[]`, `next_cursor` | | V1.0 | |
| DELETE | `/chat/conversations/{id}` | U | | `null` | | V1.0 | 5.3 |
| POST | `/chat/messages` | U | `client_message_id`, `text`, `attachment_file_ids`, `think_harder` | **SSE** hoặc JSON | `CHAT_BUSY`, `AI_UNAVAILABLE` | V1.0 | 5.3 |
| GET | `/chat/status` | U | | `{model, today_usd, month_usd, monthly_warn_usd, over_monthly_warning, cache_read_ratio_7d}` | | V1.0 | 5.3 |
| GET | `/chat/actions` | U | `status` (mặc định `pending`) | `items: PendingAction[]` | | V1.0 | 5.3 |
| POST | `/chat/actions/{id}/approve` | U | | `{action: PendingAction, result_text}` | `ACTION_NOT_PENDING`, `ACTION_PAYLOAD_CHANGED` | V1.0 | 5.3 |
| POST | `/chat/actions/{id}/reject` | U | | `{action}` | `ACTION_NOT_PENDING` | V1.0 | |

**Chi tiêu, hộp tin, danh bạ, Gmail**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/expenses` | U | `from`, `to`, `kind`, `account`, `category_id`, `source`, `needs_review`, `q`, `cursor`, `limit` | `items: Expense[]`, `next_cursor` | | V1.1 | 5.4 |
| POST | `/expenses` | U | `amount_vnd`, `kind`, `account`, `account_last4`, `to_account`, `category_id`, `merchant`, `place`, `note`, `spent_at` | `Expense` (201) | | V1.1 | |
| GET, PATCH, DELETE | `/expenses/{id}` | U | như POST, thêm `needs_review` | `Expense` / `null` | | V1.1 | |
| GET | `/expenses/{id}/source` | U | | `{app_package, title, text, posted_at}` | `NOT_FOUND` khi sự kiện gốc đã quá hạn | V1.2 | 5.4 |
| GET | `/expenses/summary` | U | `period` (`day`, `week`, `month`, `custom`), `date`, `from`, `to`, `group_by` (`category`, `day`, `account`) | `Summary` | | V1.1 | 5.4 |
| GET | `/expenses/categories` | U | `include_archived` | `items: Category[]` | | V1.1 | |
| POST | `/expenses/categories` | U | `name`, `kind`, `keywords` | `Category` (201) | `DUPLICATE` | V1.1 | |
| PATCH, DELETE | `/expenses/categories/{id}` | U | `name`, `keywords`, `sort_order`, `is_archived` | `Category` / `null` | `DUPLICATE`; xóa khi đã có khoản chi thì `CONFLICT` | V1.1 | |
| GET | `/inbox/conversations` | U | `app`, `status`, `importance`, `from`, `to`, `cursor`, `limit` | `items: Conversation[]`, `next_cursor` | | V1.3 | 5.5 |
| GET | `/inbox/conversations/{conversation_key}/messages` | U | `cursor`, `limit` | `items: InboxMessage[]`, `next_cursor` | | V1.3 | |
| POST | `/inbox/conversations/{conversation_key}/mark` | U | `status` | `{updated}` | | V1.3 | |
| GET | `/inbox/messages` | U | `app`, `status`, `importance`, `from`, `to`, `q`, `cursor`, `limit` | `items: InboxMessage[]`, `next_cursor` | | V1.3 | |
| PATCH | `/inbox/messages/{id}` | U | `status` | `InboxMessage` | | V1.3 | |
| POST | `/inbox/messages/mark` | U | `ids` (tối đa 500), `status` | `{updated}` | | V1.3 | |
| GET | `/inbox/rules` | U | `kind` | `items: Rule[]` | | V1.3 | |
| POST | `/inbox/rules` | U | `kind`, `value`, `app`, `contact_id` | `Rule` (201) | `DUPLICATE` | V1.3 | 5.5 |
| DELETE | `/inbox/rules/{id}` | U | | `null` | | V1.3 | |
| GET | `/contacts` | U | `q`, `cursor`, `limit` | `items: Contact[]` | `GOOGLE_NOT_CONNECTED` | V1.8 | |
| PATCH | `/contacts/{id}` | U | `remind_birthday`, `is_important` | `Contact` | | V1.8 | |
| GET | `/gmail/drafts` | U | `status`, `cursor` | `items: GmailDraft[]` | `GOOGLE_NOT_CONNECTED` | V1.8 | 5.5 |
| POST | `/gmail/drafts` | U | `to`, `cc`, `subject`, `body`, `thread_ref` | `GmailDraft` (201) | `GOOGLE_SCOPE_MISSING` | V1.8 | |
| GET, PATCH, DELETE | `/gmail/drafts/{id}` | U | `to`, `cc`, `subject`, `body` | `GmailDraft` / `null` (xóa là bỏ nháp) | | V1.8 | |
| POST | `/gmail/drafts/{id}/send` | U | | `{pending_action: PendingAction}` (202) | `CONFLICT` khi nháp không ở `draft` | V1.8 | 5.5 |

**Việc, lịch, Google**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/tasks` | U | `status` (mặc định `todo`), `due` (`overdue`, `today`, `week`, `none`), `from`, `to`, `cursor`, `limit` | `items: Task[]`, `next_cursor` | | V1.4 | 5.6 |
| POST | `/tasks` | U | `title`, `note`, `priority`, `due_date` hoặc `due_at`, `remind_minutes` | `Task` (201) | có cả `due_date` và `due_at` thì `VALIDATION_ERROR` | V1.4 | |
| GET, PATCH, DELETE | `/tasks/{id}` | U | như POST | `Task` / `null` | | V1.4 | |
| POST | `/tasks/{id}/complete`, `/tasks/{id}/reopen` | U | | `Task` | | V1.4 | |
| POST | `/tasks/{id}/resolve-remote-delete` | U | `keep` (bool) | `Task` hoặc `null` | `CONFLICT` khi không ở `remote_deleted` | V1.4 | 5.6 |
| GET | `/calendar/events` | U | `from`, `to` (bắt buộc, tối đa 92 ngày) | `items: Event[]` (đã trải lần lặp) | | V1.4 | 5.6 |
| POST | `/calendar/events` | U | `title`, `description`, `location`, `all_day`, `start_at`, `end_at` hoặc `start_date`, `end_date`, `remind_minutes`, `is_alarm`, `attendees` | `Event` (201); có `attendees` thì `{pending_action}` (202) | | V1.4 | 5.6 |
| GET | `/calendar/events/{id}` | U | `occurrence_start` | `Event` | | V1.4 | |
| PATCH | `/calendar/events/{id}` | U | như POST, thêm `remind_source`; `occurrence_start` khi sửa một lần lặp | `Event`; có khách mời thì `{pending_action}` (202) | `RECURRING_SERIES_EDIT` | V1.4 | 5.6 |
| DELETE | `/calendar/events/{id}` | U | `occurrence_start` | `null`; có khách mời thì `{pending_action}` (202) | `RECURRING_SERIES_EDIT` | V1.4 | |
| GET | `/calendar/reminders` | U/D | `from` (mặc định bây giờ), `days` (mặc định 14, tối đa 31); `If-None-Match` | `{revision, items: Reminder[]}` hoặc 304 | | V1.4 | 5.6 |
| GET | `/google/status` | U | | `GoogleStatus` | | V1.4 | 5.7 |
| POST | `/google/connect` | U | `packs` | `{auth_url}` | | V1.4 | 5.7 |
| GET | `/google/oauth/callback` | - | `code`, `state`, `error` (Google gửi) | Trang HTML chuyển về app | | V1.4 | 5.7 |
| POST | `/google/disconnect` | U | `keep_data` | `null` | `GOOGLE_NOT_CONNECTED` | V1.4 | 5.7 |
| POST | `/google/sync/{service}` | U | | `{queued: true}` (202) | `GOOGLE_NOT_CONNECTED`, `GOOGLE_SCOPE_MISSING` | V1.4 | |
| GET | `/google/outbox` | U | `status` (mặc định `failed,conflict`) | `items: OutboxItem[]` | | V1.4 | 5.7 |
| POST | `/google/outbox/{id}/retry` | U | `reapply` (bool, với `conflict`) | `OutboxItem` | | V1.4 | |
| POST | `/webhooks/google/calendar` | G | tiêu đề `X-Goog-*` | 200 rỗng | | V1.4 | 5.7 |

**Lịch trình, báo cáo, tệp**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/trips` | U | `status`, `cursor`, `limit` | `items: TripBrief[]`, `next_cursor` | | V1.6 | |
| POST | `/trips/import` | U | `file_id` hoặc `text` hoặc `url`; `title`, `start_date`, `travel_mode` | `{trip_id, job_id}` (202) | | V1.6 | 5.8 |
| GET | `/trips/{id}` | U | | `Trip` | | V1.6 | 5.8 |
| PATCH | `/trips/{id}` | U | `title`, `start_date`, `travel_mode`, `origin_text`, `status` | `Trip` | | V1.6 | |
| DELETE | `/trips/{id}` | U | | `null` | | V1.6 | |
| POST | `/trips/{id}/stops` | U | `day_no`, `seq`, `title`, `category`, `planned_start`, `fixed`, `place_query`, `note` | `Stop` (201) | | V1.6 | |
| PATCH, DELETE | `/trips/{id}/stops/{stop_id}` | U | như POST, thêm `place_id`, `lat`, `lng` (chọn gợi ý) | `Stop` / `null` | | V1.6 | |
| POST | `/trips/{id}/stops/reorder` | U | `day_no`, `stop_ids` | `items: Stop[]` | `VALIDATION_ERROR` khi danh sách lệch | V1.6 | |
| POST | `/trips/{id}/stops/{stop_id}/resolve` | U | `place_query` | `{candidates: [{name, address, lat, lng, place_id}]}` | `EXTERNAL_SERVICE_ERROR` | V1.6 | |
| POST | `/trips/{id}/evaluate` | U | | `{job_id}` (202) | | V1.6 | 5.8 |
| POST | `/trips/{id}/options/{option_id}/choose` | U | | `Trip` | | V1.6 | |
| GET | `/trips/{id}/map-links` | U | `day_no` (rỗng là mọi ngày), `max_waypoints` (`9` hoặc `3`) | `{days: [...]}` | | V1.6 | 5.8 |
| POST | `/trips/{id}/export-docx` | U | | `{file_id, download_url}` | | V1.6 | |
| POST | `/trips/{id}/to-calendar` | U | | `{event_ids}` | | V1.6 | 5.8 |
| GET | `/reports/dashboard` | U | `date` | `Dashboard` | | V1.7 | 5.9 |
| GET | `/reports/ai-cost` | U | `month` (`YYYY-MM`) | `AiCost` | | V1.7 | 5.9 |
| GET | `/reports/ai-cost/system` | O | `month` | `AiCost` + `by_user` | | V1.7 | |
| POST | `/reports/exports` | U | `kind` (`expense_sheet`, `expense_docx`, `report_docx`), `from`, `to` hoặc `month` | `{export_id}` (202) | `GOOGLE_NOT_CONNECTED` với `expense_sheet` | V1.8 | 5.9 |
| GET | `/reports/exports` | U | `cursor`, `limit` | `items: Export[]` | | V1.8 | |
| GET | `/reports/exports/{id}` | U | | `Export` | | V1.8 | |
| POST | `/files/upload-url` | U | `original_name`, `mime`, `size_bytes`, `purpose`, `sha256` | `{file_id, upload_url, upload_headers, expires_at}` | `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE` | V1.0 | 5.10 |
| POST | `/files/{id}/complete` | U | | `File` | `VALIDATION_ERROR` khi tệp trên R2 lệch | V1.0 | |
| GET | `/files` | U | `purpose`, `cursor`, `limit` | `items: File[]` | | V1.0 | |
| GET, DELETE | `/files/{id}` | U | | `File` + `download_url` / `null` | | V1.0 | |
| POST | `/files/{id}/drive` | U | | `{queued: true}` (202) | `GOOGLE_SCOPE_MISSING` | V1.8 | 5.10 |

**Thiết bị, phát hành, quản trị, V2, V3**

| PT | Đường dẫn | Quyền | Đầu vào | Đầu ra `data` | Lỗi riêng | Bản | Mục |
|---|---|---|---|---|---|---|---|
| GET | `/devices` | U | | `items: Device[]` | | V1.0 | 5.11 |
| POST | `/devices` | U | `name`, `model`, `os_version`, `app_version_code`, `app_version_name` | `{device, device_token}` (201, mã trả một lần) | | V1.0 | |
| PATCH, DELETE | `/devices/{id}` | U | `name` | `Device` / `null` (thu hồi) | | V1.0 | |
| GET | `/devices/listened-apps` | U | | `items: ListenedApp[]` | | V1.2 | |
| POST | `/devices/listened-apps` | U | `package_name`, `label`, `purpose`, `parser` | `ListenedApp` (201) | `DUPLICATE`, `CONSENT_REQUIRED` | V1.2 | |
| PATCH, DELETE | `/devices/listened-apps/{id}` | U | `label`, `enabled` | `ListenedApp` / `null` | | V1.2 | |
| POST | `/device/events` | D | `events` (1 tới 50) | `{accepted, duplicates, rejected: [{client_event_id, code}]}` | `DEVICE_REVOKED`, `PAYLOAD_TOO_LARGE` | V1.2 | 5.12 |
| GET | `/device/config` | D | `If-None-Match` | `{revision, listened_apps: [{package_name, purpose, enabled}], upload: {batch_max, min_interval_seconds}}` hoặc 304 | | V1.2 | 5.12 |
| POST | `/device/heartbeat` | D | `app_version_code`, `app_version_name`, `web_version`, `notification_access`, `listener_connected`, `notifications_enabled`, `exact_alarm_allowed`, `battery_optimization_ignored`, `queue_size` | `{server_time, config_revision}` | | V1.2 | 5.12 |
| GET | `/device/release` | U/D | `current_version_code` | `ReleaseInfo` | | V1.5 | 5.12 |
| GET | `/device/web-bundle` | U/D | `current_version`, `app_version_code` | `WebBundleInfo` | | V1.5 | 5.12 |
| POST | `/device/health` | D | `days[]` (`date`, `steps`, `sleep_minutes`, `resting_heart_rate`) | `{accepted}` | | V2 | |
| GET | `/admin/worker` | O | | `WorkerStatus` | | V1.2 | 5.13 |
| POST | `/admin/worker/jobs/{name}/run` | O | | `{queued: true}` (202) | | V1.2 | |
| GET | `/admin/audit-log` | O | `event`, `from`, `to`, `cursor` | `items: AuditEntry[]` | | V1.0 | 5.13 |
| POST | `/admin/releases` | CI | `kind`, `version_code`, `version_name`, `r2_key`, `sha256`, `size_bytes`, `signature`, `min_supported_version_code`, `notes` | `Release` (201) | `RELEASE_FILE_MISMATCH`, `DUPLICATE` | V1.5 | 5.13 |
| GET | `/admin/releases` | O | `kind` | `items: Release[]` | | V1.5 | |
| PATCH | `/admin/releases/{id}` | O | `is_published`, `notes`, `min_supported_version_code` | `Release` | | V1.5 | |
| GET | `/dev/jobs/next` | R | | `DevJob` hoặc `null` | | V3 | 5.14 |
| POST | `/dev/jobs/{id}/result` | R | `status`, `branch`, `commit_sha`, `summary`, `cost_usd`, `error` | `DevJob` | | V3 | |
| GET | `/dev/jobs/approved` | R | | `items: DevJob[]` | | V3 | |

Đổi so với bản 1: `/inbox/threads` thành `/inbox/conversations` (gom theo `conversation_key`, khớp màn `/hop-tin/:conversationId` của 31); bỏ `/inbox/summarize` (mục 5.5); `/google/account` thành `/google/status`; bỏ `/calendar/sync`, `/calendar/sync-status` (thay bằng `/google/sync/{service}`, `/google/status`); `/releases` thành `/admin/releases`; bỏ ý *bản phát hành thêm bằng `scripts/`*.

### 5.2 Hệ thống và tài khoản

```json
// Tokens
{ "access_token": "eyJ...", "access_expires_at": "2026-11-18T15:30:00+07:00",
  "refresh_token": "rt_...", "refresh_expires_at": "2027-01-17T15:00:00+07:00" }
// User
{ "id": 1, "name": "Gia Bảo", "email": "...", "role": "owner",
  "timezone": "Asia/Ho_Chi_Minh", "must_change_password": false }
```

- `/api/health` trả `degraded` khi DB không trả lời hoặc worker trễ quá 5 phút; không trả thông tin người dùng.
- Đổi mật khẩu thu hồi mọi phiên khác. `/auth/logout` thu hồi phiên theo `sid` trong JWT. Mật khẩu tạm chỉ trả trong phản hồi.
- `POST /me/export`: đặt việc `user_export`; kết quả trong `/jobs/{id}` là `{file_id, download_url}` của tệp zip JSON chứa toàn bộ dữ liệu của người đó (trừ token, mã băm); tệp giữ 7 ngày. Ghi kiểm toán.
- `DELETE /me`: nhập lại mật khẩu; chủ không xóa được khi còn thành viên đang hoạt động. Ghi kiểm toán rồi xóa (`11-co-so-du-lieu.md` mục 3.15).
- `DELETE /consents/data_processing`: tắt nghe thông báo (mọi `tab_listened_app.enabled = false`) và xóa hộp tin của người đó. `DELETE /consents/inbox_ai`: đặt `inbox.ai_enabled = false`.
- `/settings`: khóa lạ hoặc sai kiểu thì 400 với `fields` theo khóa; danh sách khóa ở `11-co-so-du-lieu.md` mục 3.5.

### 5.3 Chat

**Gửi tin, nhận trả lời dạng stream (SSE):**

```json
POST /api/v1/chat/messages
Accept: text/event-stream
{ "client_message_id": "7d4f0c1e-2b8a-4f43-9a8e-0f6a1d2c3b4e",
  "text": "cơm trưa 45k", "attachment_file_ids": [], "think_harder": false }
```

- `think_harder = true` dùng effort `medium` (`20-bo-nao-ai.md` mục 3.10).
- Lỗi xảy ra **trước khi** bắt đầu stream trả JSON phong bì với mã HTTP lỗi.
- `Accept: application/json` thì chạy hết lượt rồi trả một lần `data = {user_message, assistant_message, actions}`; dùng cho bài kiểm và khi WebView gặp sự cố với SSE.

Phản hồi `200`, `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`:

| Sự kiện | `data` |
|---|---|
| `message.created` | `{user_message: Message, conversation_id}` |
| `text.delta` | `{text}` |
| `tool.started` | `{name, label}`; `label` tiếng Việt, ví dụ *Đang ghi khoản chi* |
| `tool.finished` | `{name, ok}` |
| `action` | Một `Action` (mục 3.9) |
| `message.completed` | `{assistant_message: Message, usage: {input_tokens, output_tokens, cost_usd}}` |
| `error` | `{code, message}` (`AI_UNAVAILABLE`, `INTERNAL_ERROR`); sau sự kiện này luồng đóng |

```
event: message.created
data: {"user_message":{"id":881,"role":"user","text":"cơm trưa 45k"},"conversation_id":52}

event: tool.started
data: {"name":"add_expense","label":"Đang ghi khoản chi"}

event: tool.finished
data: {"name":"add_expense","ok":true}

event: text.delta
data: {"text":"Ghi 45.000 đ ăn uống, "}

event: text.delta
data: {"text":"hôm nay chi 120.000 đ."}

event: action
data: {"type":"open_screen","label":"Sửa khoản này","screen":"expense_detail","params":{"expense_id":551}}

event: message.completed
data: {"assistant_message":{"id":884},"usage":{"input_tokens":3120,"output_tokens":24,"cost_usd":0.0003}}
```

- Gửi `: ping` mỗi 15 giây khi chưa có gì mới (Cloudflare cắt kết nối rỗi sau 100 giây).
- App mất kết nối: máy chủ chạy hết lượt và lưu; app gọi lại `GET /chat/today`, không gửi lại câu hỏi.
- `Message`: `{id, role, text, attachments: [{file_id, mime, name}], actions: Action[], status, created_at}`. Chỉ trả tin `hidden = false`; khối nội dung gốc của Claude không ra app.

**Duyệt hành động** (luật ở `60-bao-mat-rieng-tu.md` mục 3.12):

- `PendingAction`: `{id, tool_name, title, summary, details, danger, require_unlock, status, expires_at, decided_at, created_at}`.
- `approve`: máy chủ kiểm chủ sở hữu, `status = pending`, chưa hết hạn, `payload_hash` khớp; chạy `execute_approved` của công cụ (không qua Claude); đổi `done` hoặc `failed`; nối tin `system` ẩn báo kết quả vào phiên (nếu có `conversation_id`). App gọi `Secure.unlock()` trước khi gửi khi `require_unlock = true`.
- Câu chat như *ok*, *đồng ý* không duyệt được hành động.

**Xóa phiên:** `DELETE /chat/conversations/{id}` xóa phiên và tin của nó (dùng cho nút *Xóa phiên hôm nay* của 31). Phiên kế tiếp không mang tóm tắt của phiên đã xóa.

**Trạng thái AI** (`/chat/status`): chỉ số liệu, không có trần ngày (QĐ-15). `over_monthly_warning = true` khi tổng tháng toàn hệ thống vượt `AI_MONTHLY_USD`; app hiện cảnh báo, không khóa ô nhập.

### 5.4 Chi tiêu

```json
// Expense
{ "id": 15, "amount_vnd": 45000, "kind": "expense", "account": "vcb", "account_last4": "1234",
  "to_account": null, "to_account_last4": null,
  "category": { "id": 2, "name": "Ăn uống" }, "merchant": null, "place": null, "note": "cơm trưa",
  "spent_at": "2026-11-18T12:05:00+07:00", "source": "bank_notification",
  "parser": "regex:vcb_v1", "parse_confidence": null, "needs_review": false,
  "created_at": "...", "updated_at": "..." }
// Summary
{ "from": "2026-11-01", "to": "2026-12-01",
  "total_expense_vnd": 5230000, "total_income_vnd": 0, "total_transfer_vnd": 2000000,
  "groups": [ { "key": "2", "label": "Ăn uống", "total_vnd": 1890000, "count": 41 } ] }
```

- Danh sách sắp `spent_at` mới nhất trước; không gửi `from`, `to` thì 30 ngày gần nhất. `needs_review=true` là mục *Cần xem lại* của 31.
- `total_expense_vnd` không tính `transfer`. Không có trường số dư (QĐ-22).
- `/expenses/{id}/source` trả chữ thông báo gốc khi `tab_device_event` còn trong hạn 180 ngày.
- Xóa là xóa mềm; thông báo gửi trùng không ghi lại dòng đã xóa.

### 5.5 Hộp tin, danh bạ, nháp Gmail

```json
// Conversation: gom theo conversation_key, tin quan trọng chưa xử lý đứng đầu
{ "conversation_key": "c_9f2a...", "app": "zalo", "title": "Mẹ", "is_group": false,
  "last_sender": "Mẹ", "last_text": "Tối nay về ăn cơm không con", "last_posted_at": "...",
  "unread_count": 2, "importance": "important", "is_private": false }
// InboxMessage
{ "id": 301, "source": "notification", "app": "zalo", "sender": "Mẹ", "conversation_key": "c_9f2a...",
  "conversation_title": null, "subject": null, "text": "...", "hidden_content": false,
  "posted_at": "...", "status": "new", "importance": "important", "importance_reason": "vip_sender",
  "labels": [] }
```

- `/inbox/conversations` sắp: còn tin `important` chưa xử lý trước, rồi `last_posted_at` mới nhất.
- **Tóm tắt hộp tin không có endpoint riêng** (ĐX-AI-08, rà chéo A2 dòng 33): nút *Tóm tắt* của 31 gửi một câu chat dựng sẵn qua `POST /chat/messages` (ví dụ *Tóm tắt tin quan trọng hôm nay trong Zalo*); model chat gọi công cụ `summarize_inbox`, trả lời ngắn và có thể kèm hành động. Một lần gọi Claude, ghi `purpose = chat`.
- Đánh dấu cuộc trò chuyện riêng tư: `POST /inbox/rules` với `kind = private_conversation`, `value = <conversation_key>`. Người quan trọng: `kind = vip_sender`, có thể kèm `contact_id`.
- Thư Gmail (V1.8) dùng chung API, `source = gmail`, `app = gmail`, có `subject`, `labels`; `conversation_key` theo luồng thư.
- **Gửi thư chỉ qua một cơ chế** (A3 dòng 36): `POST /gmail/drafts/{id}/send` không gửi ngay mà tạo `tab_pending_action` (`tool_name = send_gmail_draft`) và trả thẻ `confirm`; thư chỉ đi khi `POST /chat/actions/{id}/approve`. Trước khi gửi, máy chủ so nội dung nháp trên Gmail với `body_hash`; khác thì `ACTION_PAYLOAD_CHANGED`. Công cụ AI `send_gmail_draft` dùng cùng đường.

### 5.6 Việc và lịch

```json
// Task
{ "id": 40, "title": "Gọi điện cho anh Tư", "note": null, "status": "todo", "priority": "high",
  "due_date": null, "due_at": "2026-11-18T15:00:00+07:00", "completed_at": null,
  "completed_source": null, "event_id": 77, "sync_status": "synced", "created_at": "...", "updated_at": "..." }
// Event (một lần xảy ra)
{ "id": 77, "occurrence_start": null, "is_recurring": false, "title": "Họp nhóm", "description": null,
  "location": "Văn phòng", "all_day": false,
  "start_at": "2026-11-19T09:00:00+07:00", "end_at": "2026-11-19T10:00:00+07:00",
  "start_date": null, "end_date": null, "status": "confirmed",
  "remind_minutes": [15], "remind_source": "app", "is_alarm": false,
  "attendees": [], "source": "google", "task_id": null, "sync_status": "synced",
  "google_html_link": "https://www.google.com/calendar/event?eid=..." }
// Reminder
{ "reminder_key": "event:77:15", "source": "event", "source_id": 77,
  "fire_at": "2026-11-19T01:45:00Z", "title": "Họp nhóm", "body": "09:00 tại Văn phòng",
  "kind": "normal", "deep_link": "troly://lich/su-kien/77" }
```

**Việc:**

- Việc có `due_at` tạo hoặc cập nhật một sự kiện lịch (QĐ-09); `remind_minutes` ghi vào sự kiện đó. Bỏ `due_at` thì sự kiện bị xóa. Việc không giờ đẩy lên danh sách *Trợ lý* của Google Tasks.
- Google Tasks báo việc đã xong thì app đánh dấu `done`, `completed_source = google`; báo đã xóa thì `sync_status = remote_deleted` (QĐ-21). App hiện dòng hỏi; `resolve-remote-delete` với `keep = false` xóa việc, `keep = true` giữ trong app và bỏ liên kết.
- Danh sách sắp: quá hạn trước, rồi hạn gần nhất, việc không hạn cuối cùng.

**Lịch:**

- Sự kiện lặp trả từng lần xảy ra trong khoảng: `id` là id bản gốc, `occurrence_start` là giờ gốc của lần đó, `is_recurring = true`. Sửa, xóa một lần thì gửi kèm `occurrence_start` (máy chủ tạo ngoại lệ trên Google). Sửa, xóa bản gốc (không có `occurrence_start` với sự kiện lặp) trả `RECURRING_SERIES_EDIT` kèm `google_html_link` để app mở Google Calendar (rà chéo B, kỹ thuật tự chốt).
- **Khách mời** (QĐ-23): `POST`, `PATCH`, `DELETE` với sự kiện có `attendees` không chạy ngay mà trả 202 `{pending_action}` và thẻ `confirm` (người nhận, giờ, nội dung thư mời); duyệt xong mới ghi và đẩy lên Google với `sendUpdates=all`.
- `remind_source`: sự kiện tạo ở app mặc định `app`, tạo trên Google mặc định `google`; người dùng đổi được từng sự kiện (ĐX-G6).

**Nhắc trên máy** (`/calendar/reminders`):

- Nguồn duy nhất cho `AlarmManager`. Chỉ gồm sự kiện có `remind_source = app` (kể cả sự kiện sinh từ việc có giờ), trải cả lần lặp trong cửa sổ.
- Gọi được bằng JWT (giao diện) và mã thiết bị (worker nền của app) (A2 dòng 28).
- `reminder_key` ổn định để hủy và đặt lại báo thức; `kind = alarm` khi `is_alarm = true`. `revision` là băm của danh sách; `If-None-Match` trùng thì 304.
- Nút *Xong*, *Đã biết*, *Hoãn* trên thông báo nhắc gửi sự kiện `reminder_action` qua `/device/events` (mục 5.12).

### 5.7 Kết nối Google và webhook

```json
// GoogleStatus
{ "connected": true, "email": "...", "status": "active",
  "packs": [ { "name": "calendar", "enabled": true, "granted": true, "last_sync_at": "...",
               "status": "ok", "last_error": null } ],
  "failed_outbox_count": 0 }
```

**Luồng kết nối** (theo ĐX-G1 phần Custom Tab và luồng máy chủ web; quay về app theo ĐX-31-06):

1. App gọi `POST /google/connect` với `packs` (`calendar`, `tasks`, `gmail`, `contacts`, `drive`; `base` luôn kèm). Máy chủ tạo `state` ngẫu nhiên và cặp PKCE, lưu `tab_google_oauth_state` (10 phút, dùng một lần), trả `auth_url` (`access_type=offline`, `prompt=consent`, `include_granted_scopes=true`, `code_challenge_method=S256`).
2. App mở `auth_url` bằng Custom Tab, không mở trong WebView.
3. Google chuyển về `https://<api-domain>/api/v1/google/oauth/callback` (biến `GOOGLE_REDIRECT_URI`). Máy chủ kiểm `state`, đổi `code`, đọc `id_token` và `scope`, mã hóa token, lưu, đặt việc `google_initial_sync`, thu hồi token cũ nếu nối lại.
4. Máy chủ trả trang HTML ngắn có nút và chuyển hướng tới `troly://cai-dat/google?ket-qua=<ok|huy|thieu-quyen|loi>`. App bắt liên kết; dù không bắt được, app vẫn gọi lại `GET /google/status` khi quay về tiền cảnh.
5. `sub` khác tài khoản đã nối thì trang hỏi *Thay tài khoản Google?* chứ không tự ghi đè.

**Ngắt kết nối:** `POST /google/disconnect` với `keep_data` (40 mục 3.6): thu hồi token ở Google, dừng kênh Calendar, xóa dữ liệu theo `11-co-so-du-lieu.md` mục 3.15.

**Hàng chờ lỗi:** `GET /google/outbox` liệt kê lệnh `failed`, `conflict` cho màn *Cài đặt > Google > Lỗi đồng bộ*. `retry` đặt lại `pending`; với `conflict`, `reapply = true` áp lại thay đổi của app lên bản Google mới nhất.

**Webhook Google Calendar** (`POST /webhooks/google/calendar`):

- Google gửi `X-Goog-Channel-ID`, `X-Goog-Channel-Token`, `X-Goog-Resource-ID`, `X-Goog-Resource-State` (`sync`, `exists`, `not_exists`), `X-Goog-Message-Number`; thân rỗng.
- Máy chủ tìm `tab_google_sync_state` theo `channel_id`, so băm token; khớp thì đặt `needs_sync = true` và `NOTIFY troly_wake`; worker gộp thông báo trong 10 giây rồi đồng bộ. `sync` chỉ ghi nhận.
- Luôn trả `200` rỗng trong 1 giây, kể cả token sai hoặc kênh không còn (khi đó ghi log, đặt việc dừng kênh).
- Google Tasks không có webhook: đọc ngược trạng thái bằng quét 15 phút (QĐ-21). Gmail quét `history.list` 5 phút, không dùng Pub/Sub (ĐX-API-05 sửa theo ĐX-G7).
- Đường công khai, Cloudflare không chặn bằng bước kiểm trình duyệt (`50-ha-tang-trien-khai.md` mục 3.6).

### 5.8 Lịch trình

```json
// Trip (rút gọn)
{ "id": 9, "title": "Phước Hải - Trà Vinh", "start_date": "2026-12-20", "end_date": "2026-12-22",
  "travel_mode": "motorbike", "status": "draft", "evaluated_at": null,
  "days": [ { "day_no": 1, "date": "2026-12-20", "stops": [ "Stop" ] } ],
  "needs_confirmation": [ { "stop_id": 31, "title": "Bún nước lèo", "resolve_status": "uncertain" } ],
  "facts": [ { "kind": "ferry_last", "value_time": "17:00", "text": "Chuyến cuối từ Vũng Tàu lúc 17h" } ],
  "options": [ { "id": 3, "name": "Đúng giờ, ít rủi ro", "summary": "...", "total_km": 212.5,
                 "total_ride_minutes": 330, "night_ride_minutes": 0, "red_count": 0, "yellow_count": 2,
                 "risks": [ ], "chosen": false } ] }
// Stop
{ "id": 31, "day_no": 1, "seq": 4, "title": "...", "category": "an_uong", "role": "main",
  "time_text": "~11h30", "planned_start": "...", "planned_end": "...", "approx": true, "fixed": false,
  "optional": false, "place_id": "...", "lat": 9.93, "lng": 106.34, "coord_source": "google",
  "resolve_status": "ok", "alternatives": [ ] }
```

- `import` tạo chuyến `status = importing` rồi chạy nền (`trip_import`); `evaluate` đặt `status = evaluating` và chạy `trip_evaluate`. App hỏi `GET /jobs/{job_id}` hoặc `GET /trips/{id}` mỗi 3 giây (ĐX-API-04).
- `map-links` (ĐX-API-06): máy chủ dựng link, chia đoạn theo `max_waypoints` (app gửi `3` khi máy không có Google Maps), giới hạn 2.048 ký tự (41 mục 9.2):

```json
{ "days": [ { "day_no": 1,
  "segments": [ { "type": "open_map_directions", "label": "Phước Hải → Mỹ Tho (8 điểm)", "urls": ["https://www.google.com/maps/dir/?api=1&..."], "segment_labels": ["Đoạn 1/2"] } ],
  "stops": [ { "stop_id": 31,
               "navigation": { "type": "open_map_navigation", "label": "Dẫn đường tới ...", "lat": 9.93, "lng": 106.34, "mode": "l", "avoid": "h", "query": null },
               "place": { "type": "open_map_place", "label": "Xem điểm", "query": "...", "place_id": "..." } } ] } ] }
```

- `to-calendar` (41 mục 8): mỗi ngày một sự kiện cả ngày cộng sự kiện có giờ cho mốc cứng; `remind_source = app`, mốc phà và trả phòng đặt `is_alarm = true`.
- Xóa chuyến từ app chạy thẳng; xóa qua trợ lý đi qua thẻ duyệt (`tool_name = delete_trip`).

### 5.9 Báo cáo

```json
// Dashboard: mỗi thẻ lỗi riêng được (31 mục 4)
{ "date": "2026-11-18",
  "cards": {
    "expense":  { "status": "ok", "data": { "today_vnd": 145000, "week_vnd": 820000, "month_vnd": 5230000,
                  "last_month_same_day_vnd": 4800000, "top_categories": [ ], "needs_review_count": 1 } },
    "calendar": { "status": "ok", "data": { "today": [ "Event" ], "week_count": 9 } },
    "tasks":    { "status": "ok", "data": { "open": 12, "overdue": 2, "due_today": 3, "remote_deleted": 0 } },
    "inbox":    { "status": "ok", "data": { "unread": 18, "important_unread": 2 } },
    "ai":       { "status": "ok", "data": { "today_usd": 0.04, "month_usd": 1.92, "monthly_warn_usd": 200 } },
    "devices":  { "status": "error", "message": "Không lấy được trạng thái thiết bị.", "data": null },
    "health":   { "status": "disabled", "data": null } } }
// AiCost
{ "month": "2026-11", "total_usd": 1.92, "today_usd": 0.04, "monthly_warn_usd": 200,
  "by_day": [ { "date": "2026-11-18", "usd": 0.04 } ],
  "by_purpose": [ { "purpose": "chat", "usd": 1.7, "runs": 512 } ], "cache_read_ratio": 0.81 }
```

- Mức `monthly_warn_usd` là mức cảnh báo toàn hệ thống (QĐ-15), không phải trần của một người; giao diện ghi rõ (A6 dòng 82).
- `/reports/exports` với `expense_sheet` ghi `tab_export` và một lệnh `sheet_write` vào `tab_google_outbox`; `expense_docx`, `report_docx` dựng Word, lưu R2, đẩy Drive nếu gói `drive` đã bật.

### 5.10 Tệp

- Luồng tải lên: `upload-url` (URL ký sẵn PUT, 300 giây, bucket `troly-files`) → app `PUT` thẳng lên R2 → `/complete` kiểm kích thước. Tệp không xác nhận trong 24 giờ bị dọn.
- Loại cho phép: ảnh (`image/jpeg`, `image/png`, `image/webp`, `image/heic`), ghi âm (`audio/mp4`, `audio/ogg`, `audio/webm`), tài liệu (`application/pdf`, `.docx`).
- `POST /files/{id}/drive` đặt lệnh `file_upload` lên thư mục *Trợ lý* (`drive.file`); không chia sẻ cho người khác. Chia sẻ (nếu có) qua thẻ duyệt.

### 5.11 Thiết bị, phía giao diện

`Device`: `{id, name, model, token_prefix, app_version_code, app_version_name, web_version, notification_access, listener_connected, notifications_enabled, exact_alarm_allowed, battery_optimization_ignored, queue_size, last_seen_at, last_event_at, revoked_at}`. Cài lại app tạo thiết bị mới; thiết bị cũ người dùng tự thu hồi. Danh sách app được nghe chỉ đổi trên màn Cài đặt (không có công cụ AI). Thành viên chưa đồng ý `data_processing` thì không bật được app nào (`CONSENT_REQUIRED`).

### 5.12 API cho thiết bị (plugin Kotlin)

Mọi yêu cầu kèm `Authorization: Device <mã>` và `X-App-Version`.

**Gửi sự kiện:**

```json
POST /api/v1/device/events
{ "events": [
  { "client_event_id": "0b6c2f0e-5d1a-4d2e-8a7b-9f3c1e2d4a5b", "kind": "notification",
    "app_package": "com.VCB", "posted_at": "2026-11-18T12:04:51+07:00",
    "payload": { "title": "Thông báo biến động số dư", "text": "TK ...1234 -45,000VND lúc 18-11-2026 12:04:50 ...",
                 "conversation_title": null, "messages": [], "is_group_conversation": false,
                 "category": null, "notification_key_hash": "5f1c...", "hidden_content": false } },
  { "client_event_id": "a1e2...", "kind": "reminder_action", "app_package": null,
    "posted_at": "2026-11-18T15:00:12+07:00",
    "payload": { "reminder_key": "event:77:15", "source": "task", "source_id": 40, "action": "done", "at": "2026-11-18T15:00:10+07:00" } } ] }
```

- Trường `payload` chốt theo `30-app-android.md` mục 5.1 (`11-co-so-du-lieu.md` mục 3.6); không gửi `notification_key` gốc, `sub_text`, `is_group_summary`.
- Máy chủ chỉ lưu vào `tab_device_event`, trả ngay, `NOTIFY troly_wake`; bóc tách, ghép cặp, đưa vào hộp tin, xử lý `reminder_action` đều trong worker.
- Từ chối từng sự kiện, không hỏng cả lô: app không nằm trong danh sách được nghe (`APP_NOT_LISTENED`), khớp luật OTP lần hai (`OTP_DETECTED`, không lưu, tăng `otp_blocked_server`), thiếu trường (`INVALID_EVENT`), quá cũ (`EVENT_TOO_OLD`).
- `accepted + duplicates + số rejected = số sự kiện gửi lên`; plugin xóa cả lô khỏi hàng đợi, chỉ giữ lại khi lỗi mạng hoặc 5xx; 429 chờ theo `Retry-After`.

**Cấu hình và nhịp tim:** `/device/config` trả danh sách app được nghe, giữ nguyên giá trị `sms_default` (plugin tự thay bằng gói SMS mặc định của máy); `heartbeat` gửi khi mở app, khi quyền đổi, và 6 giờ một lần; `config_revision` mới thì plugin tải lại `/device/config`.

**Kiểm bản cập nhật:**

```json
GET /api/v1/device/release?current_version_code=12
{ "success": true, "message": "",
  "data": { "update_available": true, "required": false,
            "latest": { "version_code": 14, "version_name": "1.5.0",
                        "download_url": "https://<URL ký sẵn bucket troly-release>",
                        "sha256": "9f2c...", "size_bytes": 8123456, "notes": "Thêm tự cập nhật.",
                        "min_supported_version_code": 10 } } }
```

- `required = true` khi bản đang chạy thấp hơn `min_supported_version_code`. App luôn hỏi trước khi cài (QĐ-18).
- `WebBundleInfo`: `{update_available, latest: {version, download_url, sha256, signature, min_app_version_code}}`; tên trường khớp `manifest.json` của gói (30 mục 3.11). Gói cần APK mới hơn máy đang có thì không trả.
- Bản bị thu hồi (`is_published = false`) không được trả; app lấy bản liền trước.

### 5.13 Quản trị (chủ) và đăng bản (CI)

```json
// WorkerStatus
{ "jobs": [ { "name": "backup_database", "last_status": "ok", "last_started_at": "...",
              "last_finished_at": "...", "next_run_at": "...", "last_error": null } ],
  "queues": { "device_event_pending": 0, "job_queue_pending": 0, "google_outbox_pending": 0,
              "google_outbox_failed": 0 },
  "backup": { "last_ok_at": "...", "last_size_bytes": 12345678, "kept": 5 },
  "disk": { "free_percent": 41.2, "state": "ok" },
  "ai": { "today_usd": 0.04, "month_usd": 1.92, "monthly_warn_usd": 200 },
  "otp_blocked_server": 0,
  "silent_devices": [ ] }
```

- `/admin/audit-log`: chỉ sự kiện của chính chủ và sự kiện hệ thống; với thành viên chỉ thấy đăng nhập thất bại và khóa tài khoản (60 mục 5).
- `POST /admin/releases` (mã CI): job `ui` và `apk` gọi sau khi đẩy tệp lên `troly-release`. Máy chủ kiểm băm mã CI với `RELEASE_PUBLISH_TOKEN_HASH`, kiểm tệp có trên R2 và `sha256` khớp, rồi ghi `tab_app_release` với `published_by = ci`, ghi kiểm toán. Mã CI không gọi được đường nào khác.

### 5.14 V3: máy chạy Claude CLI

Chỉ mở khi `DEV_JOBS_ENABLED=true`; tắt thì 404. Xác thực bằng mã máy chạy (`DEV_RUNNER_TOKEN_HASH`). Container `troly-dev` lấy việc và nộp kết quả; deployer hỏi việc đã duyệt (`50-ha-tang-trien-khai.md` mục 3.11). Duyệt gộp và deploy là hành động chờ duyệt trong app.

## 6. Kiểm thử

| Bài kiểm | Canh gì |
|---|---|
| Danh mục endpoint | Quét `app.routes`: mỗi route có trong bảng mục 5.1 với đúng quyền; route không có trong bảng thì đỏ |
| Phong bì | Mọi route JSON trả đủ ba khóa; `data.code` nằm trong bảng mục 3.5 |
| Chéo người dùng | Mọi route có `{id}` hoặc `{conversation_key}`: người B gọi mã của A nhận 404; trường mã trong thân khai trong bảng ánh xạ (70 mục 3.3) |
| Quyền | Thành viên gọi route O nhận 403; JWT gọi `/device/events` nhận 401; mã thiết bị gọi `/expenses` nhận 401 nhưng gọi `/calendar/reminders` được; mã CI chỉ gọi được `/admin/releases` |
| Giới hạn | Mỗi dòng bảng mục 3.7 có ca vượt mức ra 429 kèm `Retry-After`; lô 51 sự kiện ra 400 |
| Phân trang | Duyệt hết bằng `next_cursor` không trùng, không sót khi có dòng cùng thời điểm |
| Chat SSE | Thứ tự sự kiện; `message.completed` cuối cùng; mất kết nối vẫn lưu; gửi lại cùng `client_message_id` không gọi Claude lần hai |
| Duyệt | Hết hạn, đổi `input` sau khi tạo, người khác duyệt, duyệt hai lần đều bị từ chối; khách mời lịch không lên Google trước khi duyệt |
| Sự kiện thiết bị | Lô gửi hai lần: lần hai toàn `duplicates`; app ngoài danh sách, OTP, quá cũ bị `rejected`; `reminder_action` với `done` đánh dấu việc xong |
| Nhắc | Sự kiện `remind_source = google` không có trong `/calendar/reminders`; lần lặp trong cửa sổ có đủ |
| Webhook | Token sai không đặt `needs_sync`; luôn 200 trong 1 giây |
| Phiên bản | `X-App-Version` cũ ra 426, trừ `/device/release`, `/auth/*` |
| Hợp đồng | Lược đồ OpenAPI của `/device/events`, `/device/release`, `/device/web-bundle` xuất ra `testdata/contracts/`; CI đỏ khi lệch (70 mục 5) |

## 7. Rủi ro

| Rủi ro | Ảnh hưởng | Cách giảm |
|---|---|---|
| WebView hoặc Cloudflare đệm SSE | Chữ hiện một lần ở cuối | `X-Accel-Buffering: no`, ping 15 giây, Cache Rules *Bypass*; đường lui JSON |
| Plugin cũ gọi API đã đổi | Mất sự kiện ngân hàng | Nhóm `/device/*` ổn định; đổi phá vỡ mở `v2` song song |
| Bộ đếm giới hạn trong bộ nhớ mất khi khởi động lại | Vượt mức ngắn hạn | Chấp nhận; khóa đăng nhập nằm trong DB |
| URL ký sẵn bị lộ | Tải được tệp trong 5 phút | Hạn ngắn; không ghi URL vào log |
| Webhook bị gọi giả | Đồng bộ thừa | Kiểm token kênh; webhook chỉ đặt cờ |
| Bỏ endpoint tóm tắt hộp tin | Nút *Tóm tắt* phụ thuộc chất lượng lượt chat | Câu dựng sẵn cố định; bộ câu mẫu AI có ca này |

## 8. Câu hỏi mở

1. Tên miền API cụ thể (`<api-domain>`) là gì? Cần để đăng ký `GOOGLE_REDIRECT_URI` và địa chỉ webhook (rà chéo B câu 1).

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| điều phối | `01-thiet-ke-tong-the.md` mục 8.5: `GET /api/v1/device/release` |
| agent AI | `20-bo-nao-ai.md` mục 5: bỏ bảng đường dẫn riêng, dẫn sang bảng mục 5.1 tệp này; gửi chat là SSE (`attachment_file_ids`, không `file_ids`); duyệt qua `/chat/actions/{id}/approve`; hoàn tác hồ sơ qua `/memory/profile/revisions/{version}/restore`; chi phí qua `/reports/ai-cost`; thêm `require_unlock`, `choices`, `segment_labels`, `query` vào bảng kiểu hành động; `summarize_inbox` là đường duy nhất để tóm tắt hộp tin; thêm `delete_trip` vào danh mục công cụ (41 nói xóa chuyến qua duyệt) |
| agent app Android | `30-app-android.md` mục 5.3: bỏ `open_map`, `open_url`, dùng bộ kiểu mục 3.9; lô sự kiện tối đa 50 (bảng mục 3.7); quay về sau OAuth bằng `troly://cai-dat/google?ket-qua=`. `31-giao-dien.md`: nút *Tóm tắt* gửi câu chat dựng sẵn; dashboard đọc `cards.<tên>.status`; hộp tin gọi `/inbox/conversations`; thẻ chi phí ghi *mức cảnh báo tháng toàn hệ thống*; bỏ ý *đổi mã thiết bị lấy mã truy cập*; thẻ duyệt dựa vào `require_unlock` của máy chủ |
| agent Google | `40-tich-hop-google.md` mục 14: dùng đường dẫn ở bảng mục 5.1 (`/api/v1/google/status`, `packs`, `/api/v1/webhooks/google/calendar`, `/gmail/drafts/{id}/send` qua thẻ duyệt, `/files/{id}/drive`, `/reports/exports`); quay về app bằng `troly://cai-dat/google?ket-qua=` (bỏ App Link). `41-ban-do-lich-trinh.md` mục 13: `/trips` số nhiều, `/stops/`, `/options/`, nhập và đánh giá chạy nền 202, `day_no`, hành động `open_map_navigation`, `open_map_directions`, `open_map_place` thay `open_map`; bỏ câu *App tự dựng link* |
| agent hạ tầng | `50-ha-tang-trien-khai.md`: thống nhất `/api/v1` ở mọi chỗ (mục 3.6 có chỗ thiếu); giới hạn tần suất dẫn sang bảng mục 3.7; `GOOGLE_REDIRECT_URI` có `/api/v1`. `60-bao-mat-rieng-tu.md` mục 3.7: dẫn sang bảng mục 3.7, bỏ bảng số riêng; URL ký sẵn 300 giây |

## 10. Đề xuất quyết định

| Số | Đề xuất | Trạng thái |
|---|---|---|
| ĐX-API-01 | Mọi API dưới `/api/v1`, kể cả nhóm thiết bị | Đã duyệt theo QĐ-25 |
| ĐX-API-02 | Phân trang bằng con trỏ | Đã duyệt theo QĐ-25 |
| ĐX-API-03 | Chat dùng SSE, có đường lui JSON | Đã duyệt theo QĐ-25 |
| ĐX-API-04 | Việc dài trả 202 kèm `job_id` | Đã duyệt theo QĐ-25 |
| ĐX-API-05 | Gmail quét định kỳ, không Pub/Sub; chu kỳ 5 phút | Đã duyệt theo QĐ-25 (sửa theo ĐX-G7) |
| ĐX-API-06 | Link Google Maps dựng ở máy chủ, nhận `max_waypoints` | Đã duyệt theo QĐ-25 |
| ĐX-API-07 | Nhắc trên máy lấy từ `/calendar/reminders` có `revision` và 304, nhận cả mã thiết bị | Đã duyệt theo QĐ-25 |
| ĐX-API-08 | Máy chủ kiểm OTP và danh sách app được nghe thêm một lần ở `/device/events` | Đã duyệt theo QĐ-25 |
| ĐX-API-09 | **Mới.** Bỏ `/inbox/summarize`; tóm tắt hộp tin là lượt chat gọi `summarize_inbox` | Theo ĐX-AI-08 đã duyệt; một cơ chế, một lần gọi Claude |
| ĐX-API-10 | **Mới.** Gửi Gmail, mời khách lịch, chia sẻ Drive đều trả 202 kèm thẻ `confirm`, chạy khi `/chat/actions/{id}/approve` | Một cơ chế duyệt cho mọi hành động ra ngoài (A3 dòng 36, QĐ-23) |
| ĐX-API-11 | **Mới.** Một con số cho URL ký sẵn: 300 giây cả tải lên và tải về | R2 chỉ kiểm chữ ký lúc bắt đầu; khớp `R2_PRESIGN_SECONDS` của 50 và 60 |
| ĐX-API-12 | **Mới.** Lô sự kiện thiết bị tối đa 50, thân 256 KB (theo 60), thay mức 100 của bản 1 | Khớp mức plugin đang gửi; giảm thiệt hại khi bị dội |
