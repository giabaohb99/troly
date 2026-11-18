# Rà chéo tài liệu lần 1

Ngày 18/11/2026. Trạng thái: chờ người dùng chốt mục B, sau đó giao các agent sửa.

Em đã đọc hết 17 tệp. Có ba điểm cần biết trước khi xem bảng:

- **`11-co-so-du-lieu.md` chưa gom mục *Dữ liệu cần* của bất kỳ tệp nào.** Dòng 3 và dòng 795 tự ghi là đang *chờ gộp lần hai*. Vì vậy mọi bảng, cột mà 20, 30, 31, 40, 41, 50, 60, 70 xin thêm đều chưa có trong 11 (liệt kê ở mục A1).
- **`12-api.md` lệch với gần như mọi tệp có nhắc API.** 20, 40, 41 dùng đường dẫn không có `/v1`, tên số ít, và có endpoint 12 không có.
- **`01-thiet-ke-tong-the.md` và `02-cau-truc-ma-nguon.md` đã cũ** so với các đề xuất của agent.
- Một yêu cầu đã tự khớp: `60` đã dùng ECDSA P-256, nên yêu cầu sửa Ed25519 ở `30` dòng 527 không còn cần.

Dưới đây "11:L334" nghĩa là tệp `11-co-so-du-lieu.md`, dòng 334.

---

## A. Bảng chỗ vênh

### A1. Bảng và cột

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 1 | nặng | 11:L347-362; 20:L311, L443, L608-620; 31:L641; 60:L308 | Bảng hành động chờ duyệt có hai tên: `tab_pending_action` (cột `kind`, `title`, `payload`; trạng thái `approved`) và `tab_ai_pending_action` (cột `tool_name`, `input`, `summary`; trạng thái `done`). 31 cần thêm `require_unlock`, 60 cần thêm `payload_hash` | Giữ tên `tab_pending_action` (dùng chung cho xóa, gửi Gmail, trả lời tin ở V2). Gộp đủ cột: `tool_name`, `input`, `summary`, `require_unlock`, `payload_hash`. Trạng thái: `pending`, `done`, `failed`, `rejected`, `expired` | 11, 20 |
| 2 | nặng | 11:L334, L337; 20:L131, L594-600 | `tab_message.role` chỉ cho `user`, `assistant`, cột là `is_visible`. 20 cần `role = system`, cột `hidden`, thêm `turn_id`. 60:L309 cần thêm `contains_third_party`, `redacted_at` | Thêm `system` vào ràng buộc `role`; thống nhất một tên cột ẩn hiện; thêm `turn_id`, `contains_third_party`, `redacted_at` | 11 (hoặc 20) |
| 3 | nặng | 11:L286-297; 20:L245, L606 | Bảng lịch sử hồ sơ lõi có hai tên: `tab_profile_memory_revision` và `tab_profile_memory_version`. 20 có thêm cột `reason` | Giữ `_revision`, thêm cột `reason` | 11, 20 |
| 4 | vừa | 11:L364-380; 20:L578-592 | `tab_ai_run`: 11 có `cache_creation_tokens`, `duration_ms`, `error`. 20 cần `cache_write_5m_tokens`, `cache_write_1h_tokens`, `effort`, `refusal_category`, `rate_card`, `latency_ms`, `request_id`, `error_code`. Giá trị `purpose` cũng lệch: 11 có `extract_bank`, `trip_import`, `summarize_inbox`; 20 có `bank_extract`, `trip_extract`, `eval` | Lấy bộ cột của 20 (giá ghi cache 5 phút và 1 giờ khác nhau). Chốt danh sách `purpose` theo 20 | 11 |
| 5 | vừa | 11:L314-326; 20:L604 | `tab_conversation` thiếu `last_prompt_tokens`, `compacted_count`, `day_summary_done` | Thêm vào 11 | 11 |
| 6 | nặng | 11:L403-416; 20:L335, L338, L622; 60:L198, L312; 31:L642 | `tab_expense`: 11 dùng `kind` + `account` (mã cố định `vcb`, `tcb`...), `parse_method`, `balance_after_vnd`. Công cụ của 20 vẫn dùng `direction chi/thu`, thiếu `account`, xin thêm `parser`, `parse_confidence`. 60 đòi không lưu số dư và cột `account` chỉ chứa 4 số cuối. 31 dùng `parse_confidence` cho mục *Cần xem lại*, trong khi 11 đã có `needs_review` | Giữ `kind` (ĐX-CSDL-03), sửa đầu vào công cụ ở 20 theo. Thêm `account_last4` riêng, giữ `account` là mã. Bỏ `balance_after_vnd` ở V1 nếu duyệt câu hỏi mở 60-Q4. Đổi `parse_method` thành `parser` (cho phép dạng `regex:<tên>`), thêm `parse_confidence` | 11, 20, 31 |
| 7 | nặng | 11:L243; 12:L574-580; 30:L445-447 | Trường trong `payload` sự kiện thiết bị lệch. 30 bỏ `notification_key` (thay bằng `notification_key_hash`), bỏ `sub_text`, `is_group_summary`; thêm `conversation_title`, `messages[]`, `is_group_conversation`, `hidden_content`. `kind` thêm `reminder_action` (11:L240 chỉ cho `notification`) | Theo 30 | 11, 12 |
| 8 | vừa | 11:L199-217; 30:L408; 12:L558 | `tab_device` thiếu `listener_connected`, `notifications_enabled`, `exact_alarm_allowed`, `queue_size`. `heartbeat` cũng chưa nhận các trường này | Thêm vào 11 và 12 | 11, 12 |
| 9 | nặng | 11:L544-558; 40:L443-458; 60:L85 | `tab_google_account`: 40 dùng `uuid` cho `id` và `user_id` (11 là `bigint`), tên cột `granted_scopes` khác `scopes`, `access_expires_at` khác `access_token_expires_at`; 40 thêm `enabled_packs` (11 để ở cài đặt `google.services`, 11:L195). Trạng thái `needs_reconnect` khác `reauth_required` | Theo quy ước 11 (`bigint`, `key_version`). Chốt một tên trạng thái (`reauth_required`, khớp mã lỗi `GOOGLE_REAUTH_REQUIRED` ở 12:L115). Chốt `enabled_packs` nằm một chỗ | 40, 11 |
| 10 | nặng | 11:L560-596; 40:L462-484 | `tab_google_sync_state`: khóa trong 40 là `user_id` + `service`, trong 11 là `google_account_id` + `resource`; 40 có thêm `drive`, `sheets`, `updated_min`. `tab_google_outbox`: 40 có `op` gồm `insert`, `patch`, `delete`, `draft_create`, `draft_send`, `file_upload`, `sheet_write`, có `payload`, trạng thái `running` và `conflict`; 11 chỉ có `upsert`, `delete`, không có `payload` | Gộp: giữ khóa theo `google_account_id`, mở rộng giá trị liệt kê theo 40, thêm `payload`. Chọn một trong hai tên `processing` hoặc `running` | 11, 40 |
| 11 | nặng | 11:L485-511; 40:L157-166, L176-184, L224-231, L486-496; 12:L418 | `tab_event`: 11 đồng bộ từng lần lặp (`singleEvents=true`, có `is_recurring_instance`); 40 đồng bộ bản gốc có RRULE (`singleEvents=false`) và tự trải ở máy chủ. Lệch tên `origin` và `source`, `google_recurring_event_id` và `recurring_event_id`. 11 có `description`, nhưng bảng ánh xạ ở 40:L162 lại dùng `note`. 11 thiếu `remind_source` và `recurrence` | Chọn một cách xử lý sự kiện lặp: em đề xuất `singleEvents=true` như 11 (đơn giản, khớp 12). Thêm `remind_source` (xem dòng 27). Sửa ánh xạ của 40 dùng `description` | 40 hoặc 11, 12 |
| 12 | vừa | 11:L513-536; 40:L251, L498 | `tab_task`: 40 viết *`due_at` chỉ có ngày* và xin `due_has_time`, `google_etag`; 11 đã tách sẵn `due_date` và `due_at` | 40 dùng `due_date`/`due_at`, bỏ `due_has_time`; thêm `google_etag` vào 11 | 40, 11 |
| 13 | vừa | 11:L433-453; 40:L290-292, L504; 31:L643 | `tab_inbox_message`: 40 dùng `source_ref` (11 là `external_id`), `importance = high` (11 là `important`), đặt `conversation_title` bằng tiêu đề thư (11 có cột `subject` riêng), thêm `labels`. 31 xin `conversation_key` | 40 theo tên của 11; thêm `labels` và `conversation_key` vào 11 | 40, 11 |
| 14 | vừa | 11:L467-481; 40:L500 | `tab_contact`: 40 thêm `remind_birthday`, `is_important`, `deleted_at`, cho năm sinh để trống; 11 lưu năm 1900 khi không rõ năm | Gộp cột; chốt cách lưu sinh nhật không có năm | 11 |
| 15 | vừa | 40:L460, L502; 41:L550; 60:L306-307 | Bảng mới chưa có trong 11: `tab_google_oauth_state`, `tab_gmail_draft`, `tab_trip_fact`, `tab_audit_log`, `tab_consent`. Riêng `tab_audit_log`, 50:L540 đã viết là sẽ có | Thêm vào 11; với `tab_trip_fact`, quyết định gộp vào JSON hay để bảng riêng | 11 |
| 16 | nặng | 11:L600-657; 41:L526-548; 20:L508-517 | Bảng lịch trình lệch nhiều. `tab_trip.status`: 11 thêm `importing`, `failed`; 41 thêm `evaluating`. `tab_trip_stop`: 11 dùng `planned_time time`, `is_fixed_time`, `duration_minutes`, `resolve_status`; 41 dùng `planned_start`/`planned_end timestamptz`, `fixed`, `stay_minutes`, có thêm `approx`, `optional`, `role`, `parent_stop_id`, `time_text`, `source_url`, `coord_source`, `coord_fetched_at`. `category`: 41 thêm `khach_san`, `mua_sam`; 11 thêm `khac`. `tab_trip_option`: 11 có `stops`, `total_minutes`; 41 có `plan`, `total_ride_minutes`, `night_ride_minutes`, `red_count`, `yellow_count`, `changes`. Lược đồ bóc tách của 20 (`hard_constraints`) khác 41 (`hard_facts`, `places[]`, `hotels[]`) | Lấy 41 làm gốc cho module trip. 20 bỏ lược đồ `TripExtract` riêng, dẫn sang 41 mục 4.2 | 11, 20 |
| 17 | nặng | 11:L659-673, L740; 41:L217-239, L552 | `tab_place_cache`: 11 còn `opening_hours`, `name`, `address` và cho cả dòng hết hạn sau 30 ngày. 41 bỏ giờ mở cửa, giữ `place_id` vô thời hạn, chỉ xóa tọa độ sau 30 ngày, khóa ghép `query_norm` + `bias_key` | Theo 41 (ĐX-T1, dựa trên điều khoản của Google) | 11, 01 |
| 18 | vừa | 11:L184-195; 30:L412; 31:L644; 60:L311; 41:L554-558 | Khóa cài đặt chưa gom: `app.lock_enabled`, `app.lock_after_minutes`, `app.auto_install_update`, `ui.voice_reply`, `inbox.ai_enabled`, và nhóm `trip_night_start`... Nhóm của 41 không dùng dấu chấm như quy ước của 11 (`trip.*`) | Gom vào 11, đổi tên của 41 thành `trip.night_start`... | 11, 41 |
| 19 | vừa | 11:L456-465; 01:L115; 60:L310 | `tab_inbox_rule` không có cột `effect` (01 có), nhưng 60 xin giá trị `effect = private` | Thêm `kind = private_conversation` (hoặc cột `effect`) | 11 |
| 20 | nhẹ | 11:L159-171, L255-273; 50:L616-619 | `tab_job_run` thiếu `detail`; `tab_app_release` thiếu `published_by`; `tab_dev_job` thiếu `commit_sha`, `approved_by`, `deployed_at`, `deploy_result`. 11:L273 vẫn ghi bản phát hành được thêm bằng `scripts/`, trong khi 50 chuyển sang API | Gom vào 11 và sửa câu L273 | 11 |

### A2. API

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 21 | nặng | 20:L417-425, L630, L724; 12:L247, L254-307; 31:L245 | Gửi chat: 20 trả JSON một lần `{reply_text, message_id, actions}`, gửi `file_ids`, và câu hỏi mở 5 đề xuất bỏ stream ở V1.0. 12 dùng SSE với `attachment_file_ids`; 31 cần sự kiện `tool.started` và `text.delta` | Giữ SSE của 12 (ĐX-API-03). 20 sửa mục 3.8 và mục 5 | 20 |
| 22 | nặng | 20:L444-446, L632-633; 12:L248-250; 31:L142, L708 | Duyệt hành động: 20 dùng `/api/ai/actions/{id}/confirm`, 12 dùng `/chat/actions/{id}/approve`. 31 đi theo 12 | Theo 12 | 20 |
| 23 | vừa | 20:L635-636; 12:L228-231, L493 | 20 dùng `/api/memory/profile/undo` và `/api/report/ai-cost`; 12 dùng `/memory/profile/revisions/{v}/restore` và `/reports/ai-cost` | Theo 12 | 20 |
| 24 | nặng | 12:L307; 20:L429-437; 30:L455; 31:L91-100; 41:L410, L592-595 | Kiểu hành động trả cho app có ba bộ. 12: `open_map`, `open_url`, `open_screen`, `confirm` với `{id, type, label, payload}`. 20 và 31: `open_map_navigation`, `open_map_directions`, `open_map_place`, `open_link`, `open_screen`, `confirm`, `memory_changed` (31 thêm `choices`), trường phẳng. 30 và 41: `open_map` có `kind`, `uri`, `fallback_url` | Lấy bộ của 20 và 31 (có thêm `choices`, `require_unlock`). 12, 30, 41 sửa theo | 12, 30, 41, 20 |
| 25 | nặng | 40:L82-100, L508-526; 12:L429-453; 31:L552, L711; 30:L521; 50:L241, L333 | Google: 40 dùng `/api/google/status`, `packs`, `/api/google/calendar/webhook`, `/api/google/oauth/callback` (không `/v1`). 12 dùng `/google/account`, `services`, `/webhooks/google/calendar`. 12, 40 cũng không có các endpoint của nhau: 40 có `disconnect` với `keep_data`, `/sync/{service}`, `/outbox`, `/gmail/drafts*`, `/drive/upload`, `/sheets/expense-report`. Quay về app: 40 dùng App Link, 12 dùng `troly://google/connected?status=`, 30 và 31 dùng `troly://cai-dat/google?ket-qua=`. Riêng 50 lệch ngay trong tệp: L241 có `/v1`, L333 không | Một bảng duy nhất ở 12, dưới `/api/v1`. Quay về app bằng `troly://cai-dat/google?ket-qua=` (ĐX-31-06). Chú ý: câu *Google bỏ custom scheme* ở 40:L85 chỉ áp cho redirect OAuth, còn ở đây redirect vẫn là https về máy chủ. Thêm các endpoint còn thiếu vào 12 | 12, 40, 50 |
| 26 | nặng | 41:L564-576; 12:L457-486 | Lịch trình: 41 dùng `/api/trip` (số ít), `/stop/`, `/option/`; nhập và đánh giá chạy đồng bộ, trả kết quả ngay. 12 dùng `/trips`, `/stops/`, trả 202 kèm `job_id`. Bản đồ: 41 dùng `?day=N` và nhận `max_waypoints`, 12 dùng `day_no`. 41 có `/to-calendar`, 12 không | Theo quy ước 12 (ĐX-API-04, chạy nền). Thêm `/to-calendar` và tham số `max_waypoints` vào 12 | 41, 12 |
| 27 | nặng | 40:L224-231; 11:L497, L538; 12:L409, L418; 30:L188 | Nguồn nhắc: 40 để Google tự nhắc sự kiện tạo trên Google (`remind_source = google`). Nhưng 11, 12, 30 coi `remind_minutes` là nguồn duy nhất và đặt nhắc trên máy cho mọi sự kiện | Nếu duyệt ĐX-G6 thì `/calendar/reminders` chỉ trả sự kiện có `remind_source = app` | 11, 12, 30 |
| 28 | vừa | 30:L190, L440, L521; 12:L409 | Worker nền của app cần gọi `/calendar/reminders` bằng mã thiết bị (U/D), nhưng 12 chỉ cho JWT (U) | Đổi thành U/D, và thêm đường này vào danh sách được phép ở 10:L184 | 12, 10 |
| 29 | vừa | 30:L374; 50:L397, L404, L629; 12:L548 | `POST /api/v1/admin/releases` (CI đăng bản bằng mã riêng) chưa có trong 12; 12 vẫn ghi bản phát hành được thêm bằng `scripts/` | Thêm vào 12; thêm kiểu xác thực *mã CI* vào 10:L180-184 | 12, 10, 11 |
| 30 | vừa | 60:L327-330; 12:L666 | Endpoint mới chưa có trong 12: `POST /me/export`, `DELETE /me`, `/consents`, `/admin/audit-log` | Thêm vào 12 (trả lời luôn câu hỏi mở 12-Q4) | 12 |
| 31 | vừa | 31:L243, L655-656 | 31 cần *Xóa phiên hôm nay* và *đổi mã thiết bị lấy mã truy cập*. Cả hai không có trong 12; cái thứ hai còn trái 10:L182-184 (mã thiết bị chỉ được gọi nhóm `/device/*`) | Thêm `DELETE /chat/conversations/{id}` vào 12. Bỏ ý đổi mã thiết bị ở 31 (dùng mã làm mới cất sau vân tay) | 12, 31 |
| 32 | vừa | 31:L66, L278-279; 12:L352, L364 | Hộp tin trong 31 gom theo cuộc trò chuyện (`/hop-tin/:conversationId`, cả nhóm chat); 12 gom theo `sender_key` (người gửi) | Thêm `conversation_key` (dòng 13), `/inbox/threads` gom theo khóa này | 12, 11 |
| 33 | vừa | 12:L356, L374; 20:L346, L756 | `/inbox/summarize` ở 12 tự gọi AI và trả `ai_cost_usd`; ĐX-AI-08 lại nói *không gọi AI lồng*, để model chat tự tóm | Chốt: nút *Tóm tắt* ở 31 gọi một lượt chat ẩn, hoặc giữ endpoint riêng có ghi `purpose = summarize_inbox` | 12 hoặc 20 |
| 34 | nhẹ | 30:L342, L441; 01:L225 | `POST /api/device/health` (V2) và `GET /api/device/release` thiếu `/v1`; `/device/health` chưa có trong 12 | Sửa đường dẫn; thêm dòng V2 vào 12 | 30, 01, 12 |
| 35 | nhẹ | 41:L599-601; 30:L112 | Tên hàm plugin Maps: 41 dùng `openNavigation`, `hasGoogleMaps`; 30 dùng `navigate`, `isMapsInstalled` | Theo 30 | 41 |

### A3. Tên công cụ AI (lấy `20` làm danh mục chuẩn)

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 36 | nặng | 40:L299, L546-554, L643; 20:L350-352, L391 | 40 đặt tên `draft_email`, `search_contacts`, `export_expense_sheet`; 20 đặt `create_gmail_draft`, `lookup_contact`, `export_expenses_to_sheets`. 40 nói *không có công cụ gửi thư*, gửi qua màn nháp riêng (`/gmail/drafts/{id}/send`); 20 có `send_gmail_draft` đi qua thẻ duyệt (câu mẫu 18 cũng dùng nó) | Giữ tên của 20. Gửi thư chỉ qua một cơ chế: `tab_pending_action` có `kind = send_gmail`; vẫn giữ `tab_gmail_draft` để theo dõi nháp | 40 |
| 37 | vừa | 41:L139, L588; 20:L382 | 41 đặt tên `search_places`, 20 đặt `find_place`; phạm vi gần như trùng nhau | Một tên (`find_place`), đặt theo đặc tả SKU của 41 mục 5.2 | 41 hoặc 20 |
| 38 | vừa | 20:L398; 60:L257; 20:L723 | `update_setting` của 20 cho AI đổi `listened_app` (có duyệt); 60 cấm đổi danh sách app được nghe qua AI | Bỏ `listened_app` khỏi công cụ (chờ người dùng quyết câu hỏi mở 20-Q4) | 20 |
| 39 | vừa | 31:L117; 20:L379, L391; 60:L256 | 31 hiện thẻ duyệt cho *xuất Drive hoặc Sheets lần đầu* và *lưu phương án đè bản cũ*; 20 và 60 nói hai việc này không cần duyệt | Thống nhất theo bảng 60 mục 3.12 | 31 |
| 40 | vừa | 20:L408-409; 40:L344-350 (ĐX-G8) | `list_drive_files`, `import_drive_file` cần thấy tệp của người dùng, nhưng quyền `drive.file` chỉ thấy tệp do app tạo; 40 nhập tệp bằng hộp chọn tệp của Android | Bỏ hai công cụ này, hoặc chỉ cho tìm trong thư mục *Trợ lý* | 20 |
| 41 | vừa | 20:L367; 40:L23 | `add_event` có `attendee_emails` (mời khách), nhưng 40 để *mời khách* ngoài phạm vi | Chốt có mời khách hay không ở V1.4 (câu hỏi mở 20-Q7) | 20 hoặc 40 |
| 42 | nhẹ | 01:L161-171 | Danh mục công cụ ở 01 thiếu khoảng 16 công cụ mới của 20 (`search_conversations`, `delete_task`, `delete_event`, `get_report`...). 41:L576 nói xóa chuyến qua bản nháp của AI, nhưng 20 không có `delete_trip` | Điều phối cập nhật 01 mục 7.5; thêm `delete_trip` vào 20 hoặc bỏ câu ở 41 | 01, 20 hoặc 41 |
| 43 | nhẹ | 20:L359, L398; 11:L520, L461 | `update_task.status` là `open`/`done` (11 dùng `todo`); `important_sender` (11 dùng `vip_sender`) | Theo tên của 11 | 20 |
| 44 | nhẹ | 20:L312 | Ghi khoảng 55 công cụ, nhưng bảng thực tế có 43 | Sửa số | 20 |

### A4. Module, thư mục, gói Android, biến môi trường

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 45 | nặng | 20:L103; 10:L63 (ĐX-KT-01) | `ToolSpec.handler` khai `async def`, trong khi backend chốt viết đồng bộ | Đổi thành `def` | 20 |
| 46 | vừa | 20:L73, L94; 10:L106, L128 | 20 cho `ai/registry.py` import `tools.py` của từng module; luật 5 của 10 cấm, `main.py` phải gọi `register_tools`. Tên hàm cũng lệch: `run_turn` (10:L363) và `run_chat_turn` (20:L88) | Theo 10 | 20 |
| 47 | vừa | 11:L84, L542; 40:L542-543 | Chỗ đặt bảng `tab_google_*`: 11 để ở `integrations/google/models.py`; 40 nói thuộc module `setting` và *integrations không đụng bảng* | Chốt một chỗ (em đề xuất theo 11) | 40 |
| 48 | vừa | 11:L75, L362; 20:L311 | Bảng duyệt hành động ở module `chat` (11) hay `ai` (20) | Để ở `chat` (API đã ở `/chat/actions`) | 20 |
| 49 | vừa | 40:L108, L632, L650; 10:L162; 11:L552; 50:L295; 60:L85-91 | Mã hóa token Google: 40 dùng AES-GCM với `GOOGLE_TOKEN_KEY`; các tệp còn lại dùng Fernet với `TOKEN_ENCRYPTION_KEYS` (60 thêm bản rõ gắn `user_id`) | Theo 60 | 40 |
| 50 | vừa | 40:L632; 50:L334; 10:L169-170 | Biến redirect OAuth có hai tên: `GOOGLE_OAUTH_REDIRECT_URI` và `GOOGLE_REDIRECT_URI`; 10 không có biến nào | Chốt một tên, thêm vào 10 | 40 hoặc 50, 10 |
| 51 | vừa | 20:L645; 50:L298-308; 10:L163-172 | Biến AI lệch: `AI_EFFORT_CHAT` (20) và `AI_EFFORT_DEFAULT` (50). 10 và 50 thiếu `AI_COMPACT_TOKENS`, `AI_MAX_TOOL_ROUNDS`, `AI_USER_HOURLY_TURNS`; 10 thiếu `AI_MONTHLY_USD`, `AI_INBOX_MAX_ITEMS` | Chốt danh sách hợp nhất ở bảng của 10 | 10, 50, 20 |
| 52 | vừa | 10:L168; 50:L314-318; 30:L299, L378 | 10 có một biến `R2_BUCKET`; 50 có ba bucket (`R2_BUCKET_FILES`, `_BACKUP`, `_RELEASE`) và `R2_PRESIGN_SECONDS` | Theo 50 | 10 |
| 53 | vừa | 10:L45, L156; 50:L84, L265 | Máy phát triển: 10 mở api ở cổng 8000, `CORS_ORIGINS` có `:5173`; 50 dùng 8200 và 5190 | Theo 50 | 10 |
| 54 | nặng | 10:L379; 50:L108, L578; 70:L45-64 | DB kiểm thử: 10 dùng dịch vụ `db` của Compose chính, DB `troly_test`; 50 và 70 dùng `infra/docker-compose.test.yml` với `db-test` trên tmpfs | Theo 50 và 70 | 10 |
| 55 | vừa | 10:L88 (ĐX-KT-02); 02:L83; 40:L528; 50:L678 | Job đặt ở `modules/<x>/jobs.py` (10) hay `worker/jobs/` (02, 40, 50). Tên job lệch: 10 dùng `push_google_outbox`, `sync_google_calendar`, `renew_google_watch`, `sync_gmail`; 40 dùng `google_outbox`, `calendar_sync`, `calendar_watch_renew`, `gmail_sync`, thêm `tasks_pull_status`, `google_oauth_state_cleanup`. 50 thêm `disk_check` | Bảng job duy nhất ở 10 mục 3.9; 40 và 50 dẫn sang | 10, 40 |
| 56 | vừa | 02:L42-48, L60-84, L113-121; 30:L82-92; 20:L66-79; 10:L406 | 02 thiếu: `core/models.py`, `core/clock.py`, `app/cli.py`, `ai/pricing.py`, `ai/extract.py`, `ai/schemas.py`, `integrations/google/models.py`, `jobs.py`; gói Android `queue/`, `secure/`, `system/`, `voice/`; `src/core/native`, `src/core/offline`, `src/app/` (31:L176); `testdata/`, `infra/docker-compose.test.yml`, `docker-compose.dev.yml`, `ai-eval.yml`. Tên gói `vn.io.baohuynh.troly` khớp giữa 02 và 30 | Điều phối cập nhật 02 | 02 |
| 57 | nhẹ | 10:L58, L190; 50:L431, L571; 60:L331 | Lệnh tạo owner có hai dạng: `python -m app.cli create-owner` và `create_owner` qua `exec` | Một tên | 50, 60 |
| 58 | nhẹ | 10:L40; 50:L137 | `postgres:16` và `postgres:16-alpine`. Node 22 (30:L37, L368) và Node 24 (50:L556, L590) | Chốt bản | 10 hoặc 50 |

### A5. Mâu thuẫn quyết định (với 90 hoặc 00)

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 59 | nặng | 40:L257-259 (ĐX-G4); 90 QĐ-09; 70:L236 | 40 đọc ngược trạng thái *xong* và *đã xóa* từ Google Tasks, trái QĐ-09 (một chiều); 70 lại kiểm *không kéo ngược* | Người dùng quyết; nếu duyệt thì thêm QĐ mới và sửa 70 | 90, 70 |
| 60 | vừa | 30:L36; 01:L87 | Capacitor 8 (30), thiết kế tổng thể ghi Capacitor 7 | Duyệt ĐX-30-01, sửa 01 | 01 |
| 61 | vừa | 30:L303-307; 01:L225 | 01 ghi *không cài ngầm được*; 30 cho phép tự cài khi đủ điều kiện | Duyệt ĐX-30-03, sửa 01 | 01 |
| 62 | vừa | 50:L206; 01:L68 | 01 có container `static` phục vụ giao diện và APK; 50 để cả hai trên R2 | Duyệt đề xuất của 50, sửa sơ đồ 01 | 01 |
| 63 | vừa | 20:L125-133; 01:L136 | Thời gian hiện tại đi trong tin `role: system` riêng (20), trong khi 01 gắn vào tin người dùng | Duyệt ĐX-AI-01, sửa 01 | 01 |
| 64 | vừa | 01:L303-316; 00:L42-52 | Lộ trình ở 01 mục 13 cũ: V1.2 thiếu MoMo, V1.4 thiếu Google, không có V1.7, V1.8 | Điều phối thay bằng tham chiếu tới 00 | 01 |
| 65 | vừa | 20:L725; 00:L27 | 20 hỏi có nên dời gửi Gmail sang V2; 00, 40, 60 để V1.8 | Giữ V1.8 | 20 |
| 66 | nhẹ | 00:L35; 40:L57 (ĐX-G10); 01:L322; 40 ĐX-G9 | Câu *token không hết hạn sau 7 ngày* chưa có văn bản Google xác nhận; câu *hạn mức chi bằng 0* sai, vì ngân sách Google chỉ cảnh báo, không chặn | Điều phối sửa 00 và 01 | 00, 01 |
| 67 | nhẹ | 01:L319-323 | Mục 14 đánh số sai (1, 2, 3, 5, 4) | Sửa | 01 |
| 68 | vừa | 60:L236; 70:L102; 10:L321 (ĐX-KT-03) | 60 và 70 cho bảng con không có `user_id` (nối qua bảng cha); 10 chốt mọi bảng đều có | Theo 10 | 60, 70 |
| 69 | vừa | 60:L242, L394; 10:L324 | RLS: 60 đề xuất bật trước V1.3; 10 để sau | Người dùng hoặc agent kiến trúc chốt | 10 hoặc 60 |

### A6. Số liệu kỹ thuật

| # | Mức | Tệp và dòng | Mô tả | Đề xuất sửa | Tệp phải sửa |
|---|---|---|---|---|---|
| 70 | nặng | 10:L166-167; 50:L304-305; 12:L510; 20:L551-553 (ĐX-AI-11) | Trần AI mỗi ngày: 10, 50, 12 ghi 2 USD mỗi người, 7 USD cả hệ thống; 20 ghi 1 USD và 3 USD. Ngoài ra 7 × 30 = 210 USD, vượt 200 USD của 00 | Người dùng chốt (em đề xuất 1 và 3 USD, cộng `AI_MONTHLY_USD = 200`) | 10, 50, 12 |
| 71 | nặng | 50:L326-328, L466; 60:L183; 11:L748, L824; 01:L285 | Sao lưu: 50 giữ thêm 12 bản tháng và 10 bản trước deploy; 11 và 01 hứa 30 bản, dữ liệu tồn tối đa 60 ngày. Tin nhắn của người khác vì vậy nằm trong bản sao lưu tới 12 tháng, trái lời hứa xóa sau 30 ngày | Người dùng quyết; em đề xuất bản tháng bỏ dữ liệu `tab_inbox_message`, `tab_device_event` (`--exclude-table-data`) | 50, 11, 60 |
| 72 | nặng | 11:L732; 60:L181, L185 | `tab_message` giữ 365 ngày, nên kết quả công cụ hộp tin (tin của người khác) thoát hạn 30 ngày | Thêm việc dọn khối có `contains_third_party` sau 30 ngày | 11 |
| 73 | vừa | 11:L358; 20:L443; 31:L129, L588; 60:L264 | Hạn hành động chờ duyệt: 24 giờ (11, 20, 31) và 10 phút (60) | Chốt 24 giờ, kèm `payload_hash` | 60 |
| 74 | vừa | 12:L522-528; 20:L407; 50:L318; 60:L239 | Hạn URL ký sẵn: tải lên 10 phút, tải về 15 phút (12, 20); 5 phút (50, 60) | Chốt một bộ số | 12 hoặc 50, 60 |
| 75 | vừa | 12:L151-153, L556; 60:L139-147; 50:L353-356 | Giới hạn tần suất lệch nhiều: số sự kiện mỗi lô (12: 100; 60: 50 và 256 KB), thiết bị (12: 60 yêu cầu mỗi phút; 60: 120 sự kiện mỗi phút), đăng nhập (12: 20 mỗi phút mỗi IP; 60: 10 mỗi 15 phút), chung (12: 120; 60: 300 yêu cầu mỗi phút) | Một bảng duy nhất ở 12, 60 dẫn sang | 12, 60 |
| 76 | vừa | 10:L269-271; 12:L687; 40:L197-198, L284; 50:L337 | Chu kỳ đồng bộ Google: Calendar 10 phút (10) và 15 phút ±25% (40); Gmail 10 phút (10, 12) và 5 phút (40); gia hạn kênh mỗi 6 giờ cho kênh còn dưới 24 giờ (10) và mỗi ngày cho kênh còn dưới 48 giờ (40) | Theo 40 (khớp `GOOGLE_SYNC_MIN_SECONDS = 300`) | 10, 12 |
| 77 | nhẹ | 10:L289; 40:L383, L389 | Thử lại: 6 lần, giãn 30 giây × 2^n (10) và 5 lần, 2^n giây, trần 64 giây (40) | Thống nhất | 40 |
| 78 | nhẹ | 10:L266; 50:L229, L345 | Lô xử lý sự kiện thiết bị: 50 (10) và 200 (50) | Thống nhất | 50 |
| 79 | vừa | 20:L250, L551; 11:L319; 10:L303 | Mốc tách phiên chat lúc 04:00 (20), nhưng `local_date` của 11 và ranh giới ngày của 10 hiểu là 00:00 | Người dùng chọn (câu hỏi mở 20-Q1); ghi quy tắc vào 11 | 11 hoặc 20 |
| 80 | vừa | 12:L154; 31:L246 | Độ dài tin chat tối đa: 4.000 ký tự (12) và 1.000 ký tự (31) | Thống nhất | 31 hoặc 12 |
| 81 | vừa | 11:L827; 40:L176; 31:L558 | Đồng bộ Calendar lần đầu: 30 ngày trước tới 365 ngày sau (11); kéo toàn bộ không giới hạn (40); giao diện ghi *Đang lấy lịch 30 ngày* (31) | Thống nhất theo cách chọn ở dòng 11 | 40, 31 |
| 82 | nhẹ | 31:L436, L484 | Thẻ chi phí hiện *1,84 / 200 USD* cho một người, nhưng 200 USD là trần tháng của cả hệ thống | Hiện trần riêng của người | 31 |
| 83 | nhẹ | 12:L302 | Ví dụ 3.120 token vào, 24 token ra ghi 0,0009 USD; giá Haiku 5.5 cho ra khoảng 0,0003 USD | Sửa ví dụ | 12 |
| 84 | nhẹ | 30:L44 và 40:L429; 30:L346 và 60:L125 | Health Connect: bản 1.2.0-alpha06 (30) và 1.1.0 ổn định (40). Hạn khóa ký APK: 10.000 ngày (30) và 30 năm (60) | Thống nhất | 30 hoặc 40, 60 |
| 85 | nhẹ | 20:L665, L697; 70:L257, L273-275 | Bộ câu mẫu AI: đường dẫn `app/ai/tests/eval/` chạy bằng `python -m` (20) và `backend/tests/ai_eval/` chạy bằng `pytest -m ai_eval` (70); 22 câu và *khoảng 20* | Theo 70 (khớp workflow ở 50) | 20 |
| 86 | nhẹ | 70:L153, L185; 11:L403 | Mẫu kiểm thử ghi `kind: internal_transfer`, `direction: chi`; 11 dùng `transfer` | Theo 11 | 70 |

---

## B. Câu hỏi mở đã gộp

**Gia Bảo quyết:**

1. Tên miền API là gì (12-Q1, 50-Q1)?
2. Điện thoại là máy gì, chạy Android mấy, app SMS mặc định là app nào (30-Q1, Q6; 70-Q1)?
3. Thời hạn đăng nhập: 30 phút và 60 ngày, hay mã làm mới 180 ngày (10-Q1)? Đề xuất: 60 ngày.
4. Có cần đăng nhập bằng Google (10-Q2)? Đề xuất: không.
5. Owner xem chi phí AI theo từng người (10-Q3)? Đề xuất: có, chỉ số tiền.
6. Trần AI mỗi ngày là 1 và 3 USD hay 2 và 7 USD (10-Q4, 20-Q3)? Đề xuất: 1 và 3 USD, trần tháng 200 USD.
7. Lịch sử chat giữ 365 ngày rồi xóa, chỉ giữ tóm tắt (11-Q1)? Đề xuất: đồng ý, kèm dọn tin của người khác sau 30 ngày.
8. Mỗi người một hay hai tài khoản Google (11-Q3)? Đề xuất: một.
9. Có cần chi tiết nhiều thẻ, nhiều tài khoản (11-Q4)? Đề xuất: chưa, để sau.
10. Mốc tách phiên chat lúc 04:00 hay 00:00 (20-Q1)? Đề xuất: 04:00.
11. `forget` có cần duyệt (20-Q2)? Đề xuất: không, có nút Hoàn tác.
12. Cho AI đổi cài đặt qua thẻ duyệt không (20-Q4)? Đề xuất: chỉ người quan trọng và từ khóa gấp; app được nghe chỉ đổi tay.
13. Sự kiện có khách mời: có làm ở V1.4 và có duyệt không (20-Q7, xung đột với 40)? Đề xuất: làm, có duyệt.
14. Khi nói *nghĩ kỹ* có cho dùng Sonnet (20-Q8)? Đề xuất: chưa.
15. Khóa API tạo trước hay sau 31/08/2026 (20-Q9)? Chỉ là câu hỏi thông tin.
16. App tự cài APK không hỏi khi sạc và có Wi-Fi (30-Q2)? Đề xuất: mặc định hỏi.
17. Khóa vân tay sau bao lâu ở nền (30-Q3)? Đề xuất: 5 phút.
18. Tài khoản Google cho Android Developer Console đã bật xác minh hai bước và có hồ sơ thanh toán chưa (30-Q4)?
19. Nhận dạng giọng nói trên máy bằng dịch vụ Google có được không (30-Q5)? Đề xuất: được.
20. Người dùng thứ hai trở đi cài app thế nào (30-Q7)? Có cho họ bật nghe thông báo ngân hàng và tin nhắn không (60-Q6)? Họ thấy màn Lịch trình, Báo cáo đầy đủ không (31-Q6)?
21. Bố cục thanh dưới, có nền sáng không, đọc to câu trả lời mặc định bật hay tắt (31-Q1, Q2, Q3)?
22. Người dùng tự chỉnh trần ngày trong app không (31-Q4)? Đề xuất: chỉ xem.
23. Có thông báo hệ thống khi ghi giao dịch ngân hàng lúc app đóng không (31-Q5)? Đề xuất: không, theo QĐ-11.
24. Đồng bộ lịch phụ (40-Q1)? Nguồn nhắc mặc định cho sự kiện tạo trên Google (40-Q3)? Có dùng *Danh bạ khác* (40-Q4)? Gmail chỉ hộp Chính hay thêm Cập nhật (40-Q5)? Có ai dùng tài khoản Workspace (40-Q6)? Người dùng đọc nhãn mức scope trên Console (40-Q7).
25. Có đọc ngược trạng thái *xong* từ Google Tasks không (ĐX-G4, trái QĐ-09)? Đề xuất: có, thêm QĐ mới.
26. Lịch trình: ngày đi mặc định là thứ Bảy gần nhất? Khung chạy đêm? Có cần thời tiết, bảng giờ phà tĩnh, xuất PDF (41-Q1, Q2, Q4, Q5, Q7)?
27. Kiểm sức khỏe từ ngoài; chạy Claude CLI V3 trên VPS hay máy cá nhân; ba bucket R2 và khóa giữ bản sao lưu; dùng chung sao lưu cho gym; dựng ảnh Android SDK từ V1.2 và ổ còn đủ chỗ không (50-Q3 đến Q6, Q8)?
28. Chạy lệnh kiểm trên VPS: cổng 8200, RAM, ổ đĩa (50-Q2), do người dùng hoặc điều phối chạy.
29. Lập hồ sơ đánh giá tác động theo luật dữ liệu cá nhân (60-Q1)? Đề xuất: hỏi luật sư trước khi có người dùng thứ hai.
30. Xác thực hai lớp cho owner (60-Q3)? Đề xuất: V2.
31. Có lưu số dư tài khoản (60-Q4, xung đột với cột ở 11)? Đề xuất: không.
32. Có tài khoản Google thử riêng không; ai gõ lại và che bộ mẫu ngân hàng (70-Q2, Q3)?
33. Ngưỡng chặn nhầm của bộ lọc OTP 10% (70-Q5)? Đề xuất: chấp nhận.
34. Sao lưu tháng giữ 12 tháng có chứa tin nhắn không (A6 dòng 71, câu mới)? Đề xuất: bản tháng bỏ bảng tin nhắn.

**Kỹ thuật tự chốt được:**

- Điểm dừng lưu tọa độ lâu dài (11-Q2): đã giải ở 41 bằng `coord_source`.
- Gmail lưu gì trong hộp tin (11-Q5): đoạn trích, giữ 30 ngày, theo 40.
- Đường quay về app (12-Q2): dùng `troly://cai-dat/...`.
- Tóm tắt hộp tin có stream không (12-Q3): không.
- Có API xuất toàn bộ dữ liệu (12-Q4): có ở V1 (`/me/export`, theo 60).
- Chat có stream ngay V1.0 (20-Q5): có, SSE.
- Sửa cả chuỗi sự kiện lặp (40-Q2): mở Google Calendar.
- Hệ số xe máy 1,2 (41-Q3): chỉnh sau khi dùng thật.
- Điều khoản lưu dữ liệu tuyến đường (41-Q6): đọc lại điều khoản trước khi viết mã.
- S3 giả hay bucket R2 phát triển (50-Q7): S3 giả.
- Thời hạn Anthropic giữ dữ liệu (60-Q2): kiểm trước V1.3.
- Bật RLS (60-Q5): bật trước khi có người dùng thứ hai dùng hộp tin.
- Đặt `testdata/` ở gốc kho (70-Q4): đồng ý, điều phối sửa 02.

---

## C. Đề xuất quyết định đã gộp

**Đề xuất chấp nhận:**

- **Kiến trúc backend:** ĐX-KT-01 đến KT-09.
  - KT-02: làm rõ job riêng của module nằm trong `jobs.py`, việc điều phối nhiều module và sao lưu nằm ở `worker/jobs/`.
  - KT-03: 60 và 70 phải sửa theo (bỏ ngoại lệ bảng con).
  - KT-08 khớp với dịch vụ `migrate` của 50.
- **Cơ sở dữ liệu:** ĐX-CSDL-01, 02, 03, 07, 08, 09.
  - CSDL-09 mở rộng thêm 7 bảng ở A1 dòng 15.
  - CSDL-05: trạng thái chuyến gộp thành `importing`, `draft`, `evaluating`, `planned`, `done`, `failed`.
  - CSDL-04 phải sửa theo ĐX-G6 (chỉ đặt nhắc trên máy cho `remind_source = app`).
  - CSDL-06 chờ người dùng (B mục 7).
- **API:** ĐX-API-01 đến API-08.
  - API-05 đổi chu kỳ Gmail thành 5 phút theo ĐX-G7.
  - API-06 nhận thêm tham số `max_waypoints`.
- **Bộ não AI:** ĐX-AI-01 đến 10.
  - AI-12 chấp nhận phần cột, nhưng đổi tên bảng về `tab_pending_action` và `tab_profile_memory_revision`.
  - AI-09 sửa danh sách theo bảng 60 mục 3.12 (bỏ đổi app được nghe qua AI).
  - AI-11 chờ người dùng.
- **App Android:** ĐX-30-01 đến 30-10. Riêng 30-04 cần người dùng tự mở tài khoản phân phối.
- **Giao diện:** ĐX-31-01 đến 31-07 (31-01, 31-02 là sở thích của người dùng). 31-06 chấp nhận, thay phần App Link của ĐX-G1.
- **Google:** ĐX-G1 (chỉ phần Custom Tab và luồng máy chủ web), G2, G3, G5, G6, G7, G8, G9, G10. G4 chờ người dùng (B mục 25).
- **Lịch trình:** ĐX-T1 đến T6.
- **Hạ tầng (50):** chấp nhận cả 13 đề xuất. Riêng đề xuất *giữ 12 bản sao lưu tháng* chỉ chấp nhận khi bản tháng bỏ bảng tin nhắn, hoặc người dùng đồng ý.
- **Bảo mật (60):** chấp nhận cả 13 đề xuất. Riêng *hạn duyệt 10 phút* không chấp nhận, dùng 24 giờ kèm băm nội dung. *RLS trước V1.3* chỉ áp khi có người dùng thứ hai.
- **Kiểm thử (70):** chấp nhận cả 9 đề xuất.

**Đề xuất không chấp nhận, hoặc sửa trước khi chấp nhận:**

- ĐX-G1 phần App Link (`assetlinks.json` phải đổi theo chữ ký; bản debug ký khóa khác nên không nhận được).
- Câu hỏi mở 20-Q5 (bỏ stream ở V1.0).
- Bảng `tab_ai_pending_action` tách riêng.
- Công cụ `update_setting` đổi `listened_app`.
- `list_drive_files` và `import_drive_file` (trái quyền `drive.file`).
- Ý *đổi mã thiết bị lấy mã truy cập* ở 31:L655.

---

## D. Yêu cầu *Cần agent khác* chưa được đáp ứng

**Đã đáp ứng (bỏ khỏi danh sách):**

- 10 gửi hạ tầng (50, 60): đủ.
- 11 gửi hạ tầng: sao lưu mã hóa, khóa không nằm cùng bản sao lưu, sao lưu trước migration.
- 12 gửi hạ tầng: SSE qua Cloudflare, đường công khai, giới hạn thân 1 MB.
- 20 gửi 31: cách hiện các kiểu hành động.
- 20 gửi 30: plugin Maps nhận `lat`, `lng`, `mode`, `avoid`.
- 20 gửi 41: luật rủi ro chạy bằng mã, giới hạn link.
- 20 gửi 60: lọc OTP lần hai, che số tài khoản.
- 20 gửi 70: tách bài kiểm CI và bộ câu mẫu.
- 30 gửi 60: ECDSA P-256.
- 10 gửi 30: tiêu đề `Device`, xử lý `DEVICE_REVOKED`, mã làm mới sau vân tay.

**Chưa đáp ứng:**

1. **Điều phối:**
   - Cập nhật `01`: mục 4 (Capacitor 8, bỏ `static`), mục 6 (theo 11 và các ĐX), 7.1, 7.5, 8.1, 8.5 (đường dẫn `/api/v1` và câu không cài ngầm), 8.7, mục 12, mục 13, mục 14 bước 5. Yêu cầu từ 11, 12, 20, 30, 31, 41, 40 ĐX-G9.
   - Cập nhật `00` mục 2 (ĐX-G10).
   - Cập nhật `02` (A4 dòng 56): yêu cầu từ 10, 11, 30, 50, 70.
   - Thêm `*.age`, `*.pem`, `*.p12` vào `.gitignore`; đưa bản thông báo xử lý dữ liệu vào V1.0 (60).
   - Báo agent Gamebar rằng tunnel `cloudflared` đang phục vụ thêm troly (50).
2. **Agent kiến trúc (11, 12, 10):** chưa gom yêu cầu của 20, 30, 31, 40, 41, 50, 60, 70 (toàn bộ A1 và A2). Riêng 10 chưa nhận:
   - biến môi trường của 20, 40, 50;
   - ba bucket R2;
   - xác thực bằng mã CI cho đăng bản;
   - DB kiểm thử theo 70;
   - Dockerfile ba đích `base`, `dev`, `prod` (50);
   - job xử lý `reminder_action` và cảnh báo thiết bị im lặng quá 24 giờ (30);
   - khóa tư vấn khi làm mới token (40);
   - việc dọn `tab_place_cache` (41);
   - lệnh `revoke-device`, `reencrypt-tokens`, `unlock-user` (60);
   - bảng ánh xạ trường mã cho bài kiểm chéo, xuất OpenAPI ra `testdata/contracts/` (70).
3. **Agent AI (20):**
   - Hợp đồng `run_turn` và `UserContext`; mã lỗi `AI_BUDGET_EXCEEDED` (10).
   - Tên bảng và cột theo 11 (11).
   - Kiểu `Action` theo 12, nhãn `tool.started`, danh sách `kind`, `usage` trong SSE (12).
   - Kiểu `choices`, danh sách `screen`, cờ `require_unlock`, lời chào lần đầu, đường duyệt theo 12 (30, 31).
   - Tên công cụ Gmail và Contacts (40).
   - Lược đồ bóc tách lịch trình theo 41, `search_places`, luật không tự nghĩ tên quán (41).
   - Đúng tên biến `AI_*`, `AI_INBOX_MAX_ITEMS`, chạy bằng `pytest -m ai_eval` (50).
   - Che số điện thoại, cuộc trò chuyện riêng tư, cờ `contains_third_party`, tóm tắt không chép nguyên văn tin người khác (60).
   - Đường dẫn `cases.yaml` và `FakeClaude` (70).
4. **Agent app Android (30, 31):**
   - Không còn dùng `open_map` (theo A2 dòng 24).
   - Trường hiện nguồn nhắc trên màn sự kiện (40).
   - Bỏ gói `com.google.android.gm` khỏi danh sách nghe khi đã nối Gmail (40).
   - Dòng cảnh báo thời gian xe máy là ước tính bản thử nghiệm; nút *Đưa vào lịch*; danh sách *Điểm cần xác nhận* (41).
   - Vite cổng 5190; hiện trạng thái sao lưu và ổ đĩa cho owner (50).
   - Bộ từ khóa OTP đủ như 60 mục 3.8 (30 đang thiếu *one-time*, *login code*, *2FA*, dạng `G-123456`, luật theo nguồn và theo người gửi SMS); màn đồng ý cho thành viên; bộ đếm OTP riêng; cấu hình bảo mật mạng (60).
   - Đọc `testdata/otp-samples.yaml`; app kiểm phụ cho máy ảo (70).
5. **Agent Google (40, 41):**
   - Đường dẫn theo 12, cách quay về app theo 31, quy ước bảng theo 11 (11, 12, 30, 31).
   - Mã hóa Fernet gắn `user_id` (60).
   - Dùng khung worker và chu kỳ chung (10); `GOOGLE_SYNC_MIN_SECONDS` (50).
   - Tên công cụ, mã lỗi `chua_ket_noi_google`, chỗ đặt công cụ trong module (20).
   - Gửi thư và chia sẻ Drive qua hành động chờ duyệt (60).
   - Mẫu phản hồi Google thật đã che (70).
   - Trong 41: API theo 12, bỏ câu *App tự dựng link* ở 41:L357.
6. **Agent hạ tầng (50, 60, 70):**
   - Biến chứa dấu vân tay chứng chỉ ký để job `apk` so; job `ui` đặt `min_app_version_code`; trang tải APK lần đầu (30).
   - Trang chính sách riêng tư tĩnh; Cloudflare không chặn webhook bằng bước kiểm trình duyệt; `assetlinks.json` không cần nếu dùng `troly://` (40).
   - Quota Maps trong 50, luật lưu dữ liệu Google 30 ngày trong 60, bài thử Maps trên máy thật trong 70 (41).
   - Phạm vi lưu đệm của WebView và hành động nào bắt buộc vân tay khi duyệt (31).
