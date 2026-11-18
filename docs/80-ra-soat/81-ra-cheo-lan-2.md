# Rà chéo tài liệu lần 2

Ngày 18/11/2026. Phạm vi: 18 tệp trong `docs/` sau khi năm agent nộp bản 2. Đối chiếu với `80-ra-cheo-lan-1.md` và sổ quyết định QĐ-01 tới QĐ-25.

Ký hiệu: *20:L402* là tệp `20-bo-nao-ai.md`, dòng 402. *Lần 1 #24* là dòng 24 của bảng ở `80-ra-cheo-lan-1.md`. Nguồn chuẩn theo QĐ-25: bảng và cột theo 11; đường dẫn API và giới hạn theo 12; tên công cụ AI và kiểu hành động theo 20; biến môi trường và job theo 10; mạng, cổng, compose theo 50; luật duyệt theo 60 mục 3.12.

Tóm tắt:

- Lần 1 có 86 dòng vênh. **61 dòng đã khớp**, **25 dòng còn vênh**.
- Bản 2 sinh thêm **18 chỗ vênh mới**.
- Tổng còn **43 chỗ**: **5 nặng, 20 vừa, 18 nhẹ** (mục A).
- Nguyên nhân chính: `40` và `41` viết bản 2 theo `11`, `12` bản 1, trong khi `11`, `12` bản 2 lại theo `40`, `41` bản 1. Hai bên đổi chỗ cho nhau ở sự kiện lặp, trạng thái OAuth, mốc cứng chuyến, tên cột điểm dừng.

---

## A. Chỗ còn vênh sau bản 2

### A0. Dòng của lần 1 đã khớp (chỉ đếm)

| Nhóm ở lần 1 | Số dòng | Đã khớp | Còn vênh |
|---|---|---|---|
| A1 Bảng và cột | 20 | 10 | 10 (#1, 2, 4, 9, 10, 11, 14, 15, 16, 17) |
| A2 API | 15 | 10 | 5 (#24, 25, 32, 33, 35) |
| A3 Tên công cụ AI | 9 | 9 | 0 |
| A4 Module, thư mục, biến | 14 | 10 | 4 (#50, 51, 55, 56) |
| A5 Mâu thuẫn quyết định | 11 | 11 | 0 |
| A6 Số liệu kỹ thuật | 17 | 11 | 6 (#74, 75, 77, 78, 84, 85) |
| **Cộng** | **86** | **61** | **25** |

### A1. Bảng chỗ còn vênh

| # | Mức | Tệp và dòng | Mô tả | Sửa theo nguồn chuẩn | Tệp phải sửa |
|---|---|---|---|---|---|
| 1 | nặng | 11:L587, L1043; 12:L511; 40:L199-203, L216-245, L912 (lần 1 #11) | Sự kiện lặp đổi chiều. 11 (ĐX-CSDL-10) lưu bản gốc có `recurrence`, `singleEvents=false`, máy chủ tự trải; ghi là *theo 40*. 40 (ĐX-G12) chốt `singleEvents=true`, ghi là *như 11*. API ở 12 dựng theo mô hình bản gốc (`occurrence_start`). 40 còn dùng `origin`, `google_recurring_event_id` thay `source`, `recurring_event_id` | Theo 11 (bảng) và 12 (API). Chờ chốt ở mục C, câu K1 | 40 |
| 2 | nặng | 10:L282; 11:L676-685; 12:L534; 40:L99-101, L680, L911 (lần 1 #15) | Trạng thái OAuth. 10, 11, 12 dùng bảng `tab_google_oauth_state` (băm `state`, `code_verifier` mã hóa, dùng một lần) và job dọn. 40 (ĐX-G11) bỏ bảng, nhét `state` mã hóa Fernet; lý do *12 ký bằng `JWT_SECRET`* không còn đúng với 12 bản 2 | Theo 11, 12 (bảng đã nhận ở CSDL-09) | 40 |
| 3 | nặng | 11:L805-816; 41:L108, L595, L828 (lần 1 #15, #16) | Mốc cứng chuyến. 11 có bảng `tab_trip_fact` (`kind` 5 giá trị). 41 (ĐX-T7) bỏ bảng, dùng cột `tab_trip.hard_facts` jsonb, `kind` thêm `opening_hours`, `other` | Theo 11; 11 thêm hai giá trị `kind` nếu cần | 41, 11 |
| 4 | nặng | 11:L770-774, L795-800; 41:L165, L175, L303, L313, L316-319, L359, L388-392, L455, L596, L604, L611, L623-624 (lần 1 #16) | Tên cột module trip. 11 dùng `planned_start`, `planned_end`, `stay_minutes`, `fixed`, `plan`, `total_ride_minutes`. 41 dùng `planned_time`, `duration_minutes`, `is_fixed_time`, `stops`, `total_minutes` và ghi *giữ tên của 11*. 41 thêm `tab_trip.evaluation`, `tab_trip_stop.address` mà 11 không có. Cấu trúc rủi ro: 41 dùng `message`, `suggestion`, `checked_at`; 11 ghi `text`, `hint` | Tên cột theo 11. Cấu trúc rủi ro chốt theo 41 mục 6.3 (ĐX-T9) rồi 11 ghi lại. 11 thêm `tab_trip.evaluation` | 41, 11 |
| 5 | nhẹ | 11:L818-830; 41:L261, L635-643 (lần 1 #17) | `tab_place_cache`: 41 có cột `id`, `address`, `coord_expires_at`; 11 khóa chính `(query_norm, bias_key)`, `formatted_address`, `fetched_at` | Theo 11 | 41 |
| 6 | nặng | 12:L176-187; 20:L402, L406, L411; 31:L86-97 (lần 1 #24) | Vỏ hành động. 20 ghi `{id, type, label, payload}` *theo 12 mục 5.5* (mục này không có). 12 ghi rõ *trường phẳng, không bọc `payload`*; 31 cũng phẳng; ví dụ SSE ở 12:L421 phẳng. 20 có `fallback_url` cho `open_map_navigation` và `kind` trong `confirm`; 12 không có | QĐ-25 để 20 làm nguồn, nhưng 20 dẫn sang mục không tồn tại. Chờ chốt ở mục C, câu K6 | 20 hoặc 12, 31 |
| 7 | vừa | 11:L404-424; 12:L433; 20:L95, L333, L345, L360, L417-425, L431, L560; 40:L300, L304, L457, L466, L658; 60:L266 (lần 1 #1) | Hành động chờ duyệt. 20, 40 vẫn dùng cột `kind` (`send_gmail`, `invite_event`, `delete_*`) và `payload`; 20 mục 4 ghi *giữ `kind`, `title`, `payload`*. 11, 12, 60 chỉ có `tool_name`, `input`. Băm: 11, 60 băm `tool_name` + `input`; 20 băm `payload`; 40 lấy `body_hash` | Theo 11 | 20, 40 |
| 8 | nhẹ | 11:L392; 20:L562, L593 (lần 1 #2) | 20 còn dùng cột `is_visible`; 11 là `hidden` | Theo 11 | 20 |
| 9 | vừa | 11:L433; 12:L477; 20:L495, L508-509, L572, L596, L744; 31:L283, L675 (lần 1 #4, #33) | Tóm tắt hộp tin. 12 bỏ `/inbox/summarize`, tóm tắt là lượt chat `purpose = chat`. 20 vẫn có `POST /api/v1/inbox/summarize` và `purpose = summarize_inbox`. 11 thiếu `purpose = trip_evaluate` mà 20 dùng. 31 vẫn ghi *theo A2 dòng 33* | Theo 12 (API); 11 thêm `trip_evaluate` | 20, 11, 31 |
| 10 | vừa | 11:L231, L665-669; 12:L293; 40:L78, L96, L139, L160, L174, L651, L689 (lần 1 #9) | `tab_google_account`: 40 dùng khóa cài đặt `google.services`, cột `scopes`, `access_token_expires_at`, tham số `services`. 11 đã bỏ `google.services`, dùng `granted_scopes`, `enabled_packs`, `access_expires_at`; 12 dùng `packs` | Theo 11, 12 | 40 |
| 11 | vừa | 11:L136, L715-721; 12:L606; 40:L277, L340, L344, L547, L653, L718 (lần 1 #10) | Hàng chờ Google. 40 dùng `resource`, `op = upsert`, ghi giá trị của 11 *đủ dùng*; Drive, Sheets đi qua `tab_job_queue` việc `export_report`. 11 dùng `service`, `local_type`, `op` gồm `insert`, `patch`, `delete`, `file_upload`, `sheet_write`; không có việc `export_report`; 12 cho Sheets đi qua outbox | Theo 11, 12 | 40 |
| 12 | nhẹ | 11:L558; 40:L515, L798 (lần 1 #14) | Sinh nhật không năm: 40 lưu năm 1900, 11 để `birthday_year` rỗng | Theo 11 | 40 |
| 13 | vừa | 12:L292, L296, L298, L352; 31:L579, L676; 40:L78, L123, L255, L440, L688, L702, L705; 50:L476 (lần 1 #25) | Đường dẫn Google và phát hành. 31, 40 gọi `GET /google/account` (12: `/google/status`). 40 đề nghị `POST /google/sync` với `resource` (12: `/google/sync/{service}`) và `/outbox/{id}/reapply` (12: `retry` có `reapply`). 31 gọi `/events` (12: `/calendar/events`). 50 ghi `PATCH /api/v1/releases/{id}` (12: `/admin/releases/{id}`) | Theo 12 | 40, 31, 50 |
| 14 | vừa | 12:L189, L261-263; 31:L68, L106, L280-281, L675, L726 (lần 1 #32) | Hộp tin: 31 dùng `/hop-tin/:threadKey`, màn `inbox_thread` với `thread_key`, `GET /inbox/threads`. 12 dùng `/inbox/conversations/{conversation_key}` và màn `inbox_conversation` | Theo 12 | 31 |
| 15 | nhẹ | 20:L406; 30:L119; 41:L800 (lần 1 #35) | 20 gọi hàm plugin `openNavigation`; 30 là `Maps.navigate` | Theo 30 (41 bảng nguồn) | 20 |
| 16 | vừa | 10:L187; 40:L610, L914; 50:L345, L763, L766 (lần 1 #50) | Biến redirect OAuth ba kiểu: 10 `GOOGLE_REDIRECT_URI`; 50 `GOOGLE_OAUTH_REDIRECT_URI`; 40 (ĐX-G14) bỏ biến, dựng từ `PUBLIC_BASE_URL` | Theo 10 | 50, 40 |
| 17 | vừa | 10:L170; 20:L503, L535, L606, L719 (lần 1 #51) | 10 chốt `AI_EFFORT_CHAT` (ghi *tên theo 20*); 20 vẫn dùng `AI_EFFORT_DEFAULT` và xin 10 thêm tên này | Theo 10 | 20 |
| 18 | vừa | 10:L279; 40:L357, L713-716, L868 (lần 1 #55) | Job đọc ngược Tasks: 40 gọi `sync_google_tasks`, 10 là `pull_google_tasks_status`. Bảng job ở 40 còn ghi *10 ghi 10 phút, đề nghị đổi* dù 10 đã đổi | Theo 10 | 40 |
| 19 | nhẹ | 02:L25, L167-176, L197, L226-237 (lần 1 #56) | 02 còn thiếu `ai/models.py` (11:L75), danh sách `worker/jobs/*.py` và `backend/tests/cross_user_fields.py` (10:L450), `app/android/testhelper/` (30:L100), `backend/tests/fakes/` (70:L217), `modules/expense/parsers/` (20:L448). 02 ghi `infra/android-builder/`; 30:L42, 50:L616, 70:L54 ghi `infra/android-build.Dockerfile` | Theo 50 cho hạ tầng, 10, 11 cho backend | 02 |
| 20 | vừa | 10:L181; 12:L160; 50:L328-330, L685, L711, L784; 60:L239 (lần 1 #74) | URL ký sẵn: 10, 12 một số 300 giây (`R2_PRESIGN_SECONDS`). 50 tách hai biến 10 phút và 15 phút; 60 ghi 10 phút và 15 phút; trang `/tai-app` ghi 15 phút | Theo 12, 10 | 50, 60 |
| 21 | vừa | 10:L199-205; 12:L143-152; 50:L244, L364; 60:L132, L138 (lần 1 #75) | Giới hạn tần suất. 60 nói *theo bảng duy nhất ở 12* nhưng chép số bản 1 (100 sự kiện mỗi lô, đăng nhập 20 mỗi phút, 120 yêu cầu mỗi phút). 12 bản 2: lô 50, đăng nhập 10 mỗi 15 phút, chung 300 mỗi phút. WAF: 12 ghi 20 mỗi 10 giây; 50, 60 ghi 20 mỗi phút. 50 ghi giới hạn *không đặt trong `.env`*, 10 có biến `RATE_*` | Theo 12, 10 | 60, 50 |
| 22 | nhẹ | 10:L308-309; 40:L296, L585 (lần 1 #77) | Thử lại: 10 cho `tab_google_outbox` tối đa 5 lần và dẫn mức trong lời gọi sang *40 mục 10*; 40 mục 10 ghi tối đa 6 lần, không có mức trong lời gọi | Theo 10; 10 bỏ câu dẫn sang 40 | 40, 10 |
| 23 | nhẹ | 10:L192; 50:L235, L357 (lần 1 #78) | Lô sự kiện thiết bị: 10 là 200, 50 là 50 | Theo 10 | 50 |
| 24 | nhẹ | 30:L369; 60:L127 (lần 1 #84) | Hạn khóa ký APK đổi chỗ: 30 ghi 10950 ngày (30 năm) *khớp 60*; 60 ghi 10.000 ngày *theo 30* | Chốt 10950 ngày | 60 |
| 25 | nhẹ | 20:L633-683; 70:L257, L262-272 (lần 1 #85) | Bộ câu mẫu AI: 20 có 24 câu, ngưỡng 21 trên 24; 70 ghi 22 câu. Định dạng `cases.yaml` ở 70 (`setup.expenses`, `reply_max_chars`) khác 20 (`group`, `fixture`, `reply_max_sentences`, `judge`) | Theo 20 (70:L21 giao nội dung cho agent AI) | 70 |
| 26 | vừa | 10:L82, L86, L358, L400, L424; 12:L434; 20:L79-89, L100-106 | Mới. Khuôn công cụ và hàm vòng chat lệch. 10: `input_schema`, `handler(session, user_id, input) -> dict`, `needs_approval`, `execute_approved`; `run_turn(session_factory, ctx: UserContext, text, attachments, client_message_id, think_harder)`. 20: `input_model`, `run(ctx, data) -> ToolOutput`, `approval`, `prepare`, `execute`; `run_turn(ctx: ToolContext, system_parts, history, store, effort)` | Theo 20 (ĐX-AI-13, 14; tệp giữ thư mục `ai/`) | 10, 12 |
| 27 | vừa | 11:L418; 20:L419-425; 31:L116-118; 60:L251-252 | Mới. Luật vân tay khi xóa. 60 (nguồn chuẩn): xóa một dòng không cần; xóa nhiều dòng, xóa chuyến, xóa tệp cần. 20: bốn công cụ xóa, kể cả `delete_trip`, `require_unlock = false`. 11: `true` với mọi hành động `danger` (công cụ xóa đều `danger`). 31: chỉ khi xóa từ 2 dòng | Theo 60 mục 3.12 | 20, 11, 31 |
| 28 | vừa | 11:L411, L544; 20 mục 3.7 (L289-398); 31:L118, L121; 40:L41, L539; 60:L251-262 | Mới. Công cụ không có trong danh mục. 11 cho `tool_name` gồm `delete_note`, `delete_file`, `share_drive_file`; 31, 60 nêu xóa ghi chú, xóa tệp, chia sẻ Drive qua thẻ duyệt. 20 không có ba công cụ này; 40 để chia sẻ Drive ngoài V1.8. Ngược lại, 60 mục 3.12 thiếu dòng `update_setting` dù 20:L396 và 11:L544 bắt duyệt | Tên công cụ theo 20; luật duyệt theo 60 | 11, 31, 60 |
| 29 | vừa | 11:L644, L1044; 12:L285, L506; 31:L337; 40:L370, L380, L779, L916 | Mới. Việc bị xóa trên Google Tasks. 11, 12: `sync_status = remote_deleted`, người dùng chọn xóa hay giữ (`resolve-remote-delete`). 40 (ĐX-G16): xóa mềm ngay, có Hoàn tác. 31: việc *biến mất* | Theo 11, 12 | 40, 31 |
| 30 | vừa | 11:L914; 12:L295, L540; 40:L166-176 | Mới. Ngắt kết nối Google. 11, 12 có `keep_data`, xóa danh bạ và thư Gmail trong hộp tin. 40 không có `keep_data`, giữ thư Gmail tới hết 180 ngày, dẫn *11 mục 3.14* (nay là 3.15) | Theo 11, 12 | 40 |
| 31 | vừa | 11:L265, L272; 12:L642; 30:L154-165, L419, L542; 31:L501, L549, L562 | Mới. App SMS mặc định. 11, 12 dùng một dòng `sms_default`, plugin tự thay gói. 30 (ĐX-30-12), 31 dùng hai dòng riêng (Samsung Messages, Google Messages), giao diện bật một dòng bằng `PATCH` | Theo 11; chờ chốt ĐX-30-12 ở mục C, câu K14 | 30, 31 |
| 32 | vừa | 11:L235-256; 12:L342-343; 30:L416, L445-446, L529 | Mới. 30 xin thêm `manufacturer`, `default_sms_package`, `otp_blocked_today` cho `tab_device` và `heartbeat`; `/device/config` trả phiên bản bộ luật OTP, danh sách tên thương hiệu SMS, cờ đồng ý. 11, 12 chưa có | Gom vào 11, 12 | 11, 12 |
| 33 | nhẹ | 12:L189; 31:L112 | Mới. Màn chi phí AI: 12 `settings_ai_budget`, 31 `settings_ai_cost` | Chốt `settings_ai_cost` (QĐ-15 bỏ ngân sách ngày; khớp đường `/cai-dat/chi-phi-ai`) | 12 |
| 34 | vừa | 10:L287; 11:L902, L1018; 41:L253, L266, L269 | Mới. Tọa độ điểm dừng lấy từ Google: 11 đặt rỗng sau 60 ngày chưa làm mới; 41 và điều khoản Places cho tối đa 30 ngày. Job `cleanup_old_data` ở 10 không nhắc `tab_trip_stop` | Theo 41 (điều khoản Google) | 11, 10 |
| 35 | nhẹ | 11:L566-583; 40:L662-678 | Mới. `tab_gmail_draft`: 40 dùng `to_emails`, `cc_emails`, `google_draft_id` bắt buộc, trạng thái `failed`, nội dung giữ 180 ngày; 11 dùng `to_addrs`, `cc_addrs`, `google_draft_id` rỗng được, trạng thái `sending`, giữ 30 ngày sau khi gửi hoặc bỏ | Theo 11 | 40 |
| 36 | nhẹ | 11:L204, L213-231, L694; 40:L528, L550, L659 | Mới. 40 thêm khóa `google.drive_folder_id`, `google.expense_spreadsheet_id`; 11 không có (khóa lạ bị 400), nhưng 11 đã cho `tab_google_sync_state.resource_id` giữ id thư mục và id bảng tính | Theo 11 | 40 |
| 37 | nhẹ | 12:L317, L575-579; 41:L495, L683, L686, L829 | Mới. 41 (ĐX-T8) muốn `/map-links` trả mỗi điểm `lat`, `lng`, `fallback_url`, `view_url`; 12 trả đối tượng hành động, không có `fallback_url`. Tham số `save_to_drive` của `/export-docx` chưa có ở 12 | Gom vào 12 nếu chốt; đi cùng câu K6 | 12 |
| 38 | vừa | 10:L143, L176-205, L422; 50:L321-371; 60:L175 | Mới. `.env.example` ở 50 khác bảng 10 ngoài các dòng 16, 20, 23: `BACKUP_WEEKDAY=sun` (10: `6`); thiếu `BACKUP_MINUTE`, `R2_ENDPOINT`, `INBOX_RETENTION_DAYS`, `DEVICE_EVENT_RETENTION_DAYS`, `THIRD_PARTY_CHAT_RETENTION_DAYS`, `CHAT_RETENTION_DAYS`, `RATE_*`; có `THIRD_PARTY_RETENTION_DAYS` mà 10 không có (60 cũng dùng). Bài kiểm `test_config.py` của 10 sẽ đỏ | Theo 10 | 50, 60 |
| 39 | nhẹ | 10:L308; 20:L65, L110, L402; 30:L205, L302; 31:L86; 40:L78, L170, L255, L440; 41:L313, L664; 50:L246, L450, L492, L561; 60:L316; 70:L7, L104, L142 | Mới. Dẫn sai mục. SSE ở 12 mục 5.3 (không phải 5.5); API thiết bị ở 12 mục 5.12 (không phải 5.15); Google ở 5.7 (không phải 5.10); lịch trình ở 5.8 (không phải 5.11); quản trị ở 5.13 (không phải 5.17); bảng thời hạn ở 11 mục 3.15 (không phải 3.14); lệnh quản trị ở 10 mục 3.17; `tab_ai_run` không ở 10 mục 7; 01 không còn mục 12, 14; danh sách bảng hệ thống ở 11 mục 3.1 | Sửa số mục | 10, 20, 30, 31, 40, 41, 50, 60, 70 |
| 40 | nhẹ | 31:L484, L501; 50:L241-250, L403; 60:L124 | Mới. Trình bày: 50 mục 3.6 đánh số 1-7, 9, 10, 8; 50 ghi *ba job* nhưng bảng có bốn; 31 ghi *App được nghe 7* trong khi nói 8 app; 60 ghi `.gitignore` *có ba mẫu đầu*, thực tế đã có `*.age`, `*.pem`, `*.p12`, chỉ thiếu `age-key*.txt` | Sửa chữ | 50, 31, 60 |
| 41 | nhẹ | 12:L537; 31:L78, L586-588; 40:L121 | Mới. 31 thiếu `ket-qua=loi` (12, 40 có). Luồng 3 còn ghi khoảng đồng bộ *theo cách 11 và 40 chốt (A2 dòng 11, 81)* | Theo 12 | 31 |
| 42 | nhẹ | 12:L401; 20:L525, L718 | Mới. 20 nói `usage` của `message.completed` có `cache_read_tokens`; 12 chỉ có `input_tokens`, `output_tokens`, `cost_usd` | Theo 12 (sự kiện SSE); 12 thêm trường nếu nhận đề nghị của 20 | 12 hoặc 20 |
| 43 | nhẹ | 10:L346; 11:L926; 60:L242, L399 | Mới. Mốc bật RLS: 10, 11 *trước khi có người dùng thứ hai dùng hộp tin*; 60 *trước khi tạo tài khoản thứ hai* | Đề xuất theo 60 (chặt hơn) | 10, 11 |

---

## B. Yêu cầu *Cần agent khác* chưa được đáp ứng

Chỉ ghi việc tệp đích chưa làm. Việc trùng một dòng ở mục A thì ghi số dòng.

**Điều phối**

| Từ | Đích | Việc chưa làm |
|---|---|---|
| 10, 11 | `02` | `ai/models.py`; tên tệp trong `worker/jobs/` (`device_events`, `queue`, `google_outbox`, `backup`, `cleanup`, `disk`); `backend/tests/cross_user_fields.py` (A#19) |
| 30 | `02` | Thư mục `app/android/testhelper/` |
| 50 | `02` | Tên `infra/android-build.Dockerfile`; `scripts/deploy.sh`, `scripts/restore-db.sh` ghi rõ tên |
| 70 | `02` | `backend/tests/fakes/` |
| 60 | `00` | Đưa trang `/chinh-sach-rieng-tu` vào việc của V1.0 (lộ trình V1.0 chưa nêu) |
| 60 | `.gitignore` | Thêm `age-key*.txt` |
| 50 | ngoài tài liệu | Báo agent Gamebar: troly dùng chung tunnel `cloudflared`; `core-game` sẽ tạm dừng; deploy Gamebar làm nó chạy lại. Chưa có dòng nào ở nhật ký việc |

**Agent kiến trúc (10, 11, 12)**

| Từ | Đích | Việc chưa làm |
|---|---|---|
| 20 | `10` | Hợp đồng `run_turn`, `TurnStore`, `ToolContext` theo 20 mục 3.2 (A#26) |
| 50 | `10`, `12` | Hai trang tĩnh `/chinh-sach-rieng-tu`, `/tai-app` do api phục vụ: 10 chưa nhắc, bảng đường dẫn 12 chưa có |
| 41 | `10`, `11` | `cleanup_old_data` xóa tọa độ `tab_trip_stop` nguồn `google` theo hạn 30 ngày (A#34) |
| 20 | `11` | `purpose = trip_evaluate` (A#9) |
| 30 | `11` | Ba cột `tab_device`; 8 dòng mặc định `tab_listened_app` (A#31, #32) |
| 20 | `12` | `usage` thêm `cache_read_tokens` (A#42); vỏ `{id, type, label, payload}` và `PendingAction.kind` (A#6, #7, chờ chốt) |
| 30 | `12` | `/device/config` trả phiên bản bộ luật OTP, danh sách tên thương hiệu SMS, cờ đồng ý; ghi rõ bỏ `com.google.android.gm` khi Gmail đã nối; `heartbeat` nhận ba trường mới (A#32) |
| 31 | `12` | `GoogleStatus` trả câu trạng thái đồng bộ lần đầu để giao diện hiện |
| 41 | `12` | `save_to_drive` cho `/export-docx`; `fallback_url` trong `/map-links`; cấu trúc `risks` dẫn sang 41 mục 6.3 (A#37) |

**Agent AI (20)**

| Từ | Việc chưa làm |
|---|---|
| 10, 50 | Tên biến `AI_EFFORT_CHAT` (A#17); ghi tên job `summarize_previous_day` (20 chỉ ghi *job lúc 04:05*) |
| 11 | Cột `hidden` thay `is_visible` (A#8); bỏ `kind`, `payload` khỏi mục 4 phần `tab_pending_action` (A#7) |
| 12 | Bỏ bảng đường dẫn riêng ở mục 5, trong đó còn `POST /api/v1/inbox/summarize` (A#9) |
| 41 | Tên hàm plugin `Maps.navigate` (A#15) |
| 60 | `require_unlock` theo cột cuối 60 mục 3.12 (A#27) |
| 40 | Ghi rõ xóa sự kiện có khách cũng gửi `sendUpdates=all` |

**Agent app Android (30, 31)**

| Từ | Đích | Việc chưa làm |
|---|---|---|
| 50 | `30` | Ghi tên trường `troly.minNativeVersionCode` trong `app/package.json` và tên biến `ANDROID_SIGNING_CERT_SHA256`; nội dung các bước cài ở trang `/tai-app` |
| 12 | `31` | Nút *Tóm tắt* gửi câu chat dựng sẵn; hộp tin gọi `/inbox/conversations` (A#9, #14) |
| 20 | `31` | Khi nhận `message.completed` thì thay bóng chữ bằng chữ cuối (trường hợp bị từ chối giữa chừng) |
| 40 | `31` | Giá trị `ket-qua=loi` (A#41); sự kiện người khác mời chỉ cho đổi nguồn nhắc; dòng báo khi việc bị xóa trên Google (A#29); màn *Lỗi đồng bộ* có *Thử lại*, *Áp lại* |
| 50 | `31` | Nút *Sao lưu ngay* ở màn *Máy chủ* (có trạng thái sao lưu nhưng chưa có nút) |
| 60 | `31` | Bảng *Cần vân tay* theo 60 mục 3.12: xóa chuyến, xóa tệp luôn cần vân tay (A#27) |

**Agent Google (40, 41)**

| Từ | Việc chưa làm |
|---|---|
| 10 | Tên job `pull_google_tasks_status` (A#18); biến `GOOGLE_REDIRECT_URI` (A#16); thử lại hai mức, hàng chờ tối đa 5 lần (A#22) |
| 11 | Tên cột 11 mục 3.12 (`granted_scopes`, `enabled_packs`, `access_expires_at`, `service`, `local_type`); `tab_event.source`, `recurring_event_id`, `original_start_at`; `birthday_year` rỗng (A#10, #11, #12, #1) |
| 12 | `/google/status`, `packs`, `/files/{id}/drive` (A#10, #13) |

**Agent hạ tầng (50, 60, 70)**

| Từ | Đích | Việc chưa làm |
|---|---|---|
| 10 | `50` | `.env.example` đúng bảng 10 mục 3.6 (A#16, #20, #23, #38) |
| 12 | `50` | `/api/v1` ở mọi chỗ (L476); WAF dẫn sang 12; `GOOGLE_REDIRECT_URI` (A#13, #16, #21) |
| 30 | `50` | Nêu app kiểm phụ `testhelper` trong job `android-emulator` |
| 12 | `60` | Bỏ con số riêng ở mục 3.7, chỉ dẫn sang 12; URL ký sẵn 300 giây (A#20, #21) |
| 10 | `70` | Nêu `test_clock.py` với mốc 04:00 |
| 20 | `70` | Trường `group`, `tools_not_called`, `actions`, `reply_max_sentences`, `reply_must_not_match`, `judge` trong `cases.yaml`; `FakeClaude` giả luồng stream và `cache_creation` theo TTL (A#25) |
| 40 | `70` | Ca kiểm mời khách |

---

## C. Câu hỏi mở còn lại

### C1. Gia Bảo quyết

| # | Câu | Nguồn | Đề xuất |
|---|---|---|---|
| 1 | Tên miền con cho api là gì? | 12-Q1, 50-Q1 | `troly.baohuynh.io.vn`. Cần trước lần deploy V1.0 |
| 2 | Mã làm mới 60 ngày, mã truy cập 30 phút có được không? | 10-Q1 | Giữ |
| 3 | Có đăng nhập bằng Google thay mật khẩu không? | 10-Q2 | Không |
| 4 | Lịch sử chat giữ 365 ngày rồi xóa, chỉ giữ tóm tắt? | 11-Q1 | Đồng ý |
| 5 | Có cần tách nhiều thẻ, nhiều tài khoản cùng ngân hàng? | 11-Q2 | Chưa; mã ngân hàng cộng 4 số cuối là đủ |
| 6 | Nói *nghĩ kỹ* thì có chuyển sang Sonnet 5.5? | 20-Q1 | Chưa; chỉ nâng effort |
| 7 | Lời chào lần đầu là câu cố định hay trợ lý soạn? | 20-Q2 | Câu cố định (ĐX-AI-18) |
| 8 | Khóa API Anthropic tạo trước hay sau 31/08/2026? | 20-Q3 | Chỉ để biết, không đổi thiết kế |
| 9 | Khóa vân tay sau bao lâu ở nền? | 30-Q1 | 5 phút |
| 10 | Tài khoản Google cho Android Developer Console đã bật xác minh hai bước và có hồ sơ thanh toán chưa? | 30-Q2 | Chuẩn bị trước V1.5 |
| 11 | Nhận giọng nói bằng dịch vụ Google trên máy? | 30-Q3 | Đồng ý |
| 12 | App SMS mặc định, bản Android và One UI trên máy? | 30-Q4, Q5; 70-Q1 | Chỉ để chuẩn bị bộ mẫu và thử intent |
| 13 | Có cần nền sáng? | 31-Q1 | Chỉ nền tối ở V1 |
| 14 | Đọc to câu trả lời mặc định bật hay tắt? | 31-Q2 | Tắt |
| 15 | Có thông báo hệ thống khi ghi giao dịch lúc app đóng? | 31-Q3 | Không (QĐ-11) |
| 16 | Đồng bộ lịch phụ? | 40-Q1 | Chỉ lịch chính |
| 17 | Sự kiện tạo trên Google do ai nhắc? | 40-Q2 | Google nhắc |
| 18 | Trả lời lời mời của người khác trong app ở bản nào? | 40-Q3 | V2 |
| 19 | Việc tự thêm thẳng vào danh sách *Trợ lý* trên Google Tasks có nhận về không? | 40-Q4 | Bỏ qua ở V1.4 |
| 20 | Dùng *Danh bạ khác* để đặt tên người gửi Gmail? | 40-Q5 | Không |
| 21 | Gmail chỉ hộp *Chính* hay thêm *Cập nhật*? | 40-Q6 | Chỉ *Chính*, xem lại sau 2 tuần dùng |
| 22 | Có nối tài khoản Workspace không? | 40-Q7 | Chỉ tài khoản cá nhân |
| 23 | Đọc nhãn mức của scope Calendar, Tasks, Contacts trên Console | 40-Q8 | Người dùng làm ở bước dựng V1.4 |
| 24 | Có tài khoản Google thử riêng? | 40-Q9, 70-Q2 | Có, một tài khoản; dùng ghi mẫu phản hồi thật |
| 25 | Ngày đi mặc định khi tệp chỉ ghi thứ? | 41-Q1 | Gợi ý thứ Bảy gần nhất, người dùng bấm xác nhận |
| 26 | Khung chạy đêm 18:00 tới 05:30, đỏ từ 03:00 tới 05:00? | 41-Q2 | Giữ |
| 27 | Cần thời tiết, triều cường ở V1.6? | 41-Q3 | Chưa |
| 28 | Nhập bảng giờ phà quen làm dữ liệu tĩnh? | 41-Q4 | Có, người dùng nhập ba tuyến |
| 29 | Cần xuất PDF? | 41-Q5 | Chưa |
| 30 | Kiểm VPS: cổng 8200, RAM thật, ổ trống | 50-Q2 | Người dùng chạy `ss -ltn`, `docker stats --no-stream`, `df -h /` |
| 31 | Sao lưu Gamebar trước khi dừng? Mở lại theo điều kiện nào? | 50-Q3 | Sao lưu ngay; mở lại khi RAM đo thật còn dư hơn 600 MB |
| 32 | Kiểm sức khỏe api từ ngoài? | 50-Q4 | Workflow GitHub chạy 2 giờ một lần |
| 33 | V3: Claude CLI chạy trên VPS hay máy cá nhân? | 50-Q5 | Container `troly-dev` trên VPS; chốt lại khi tới V3 |
| 34 | Bật khóa giữ cho bucket `troly-backup`? | 50-Q6 | Chưa ở V1 |
| 35 | Dựng ảnh Android SDK trên máy từ V1.2? Ổ còn 10 GB? | 50-Q7 | Có, nếu ổ đủ |
| 36 | Trang `/tai-app` công khai hay đặt Cloudflare Access? | 50-Q8 | Công khai |
| 37 | Dùng chung cách sao lưu cho gym? | 50-Q9 | Ngoài phạm vi troly, để sau |
| 38 | Lập hồ sơ đánh giá tác động theo Luật 91/2025? | 60-Q1 | Hỏi luật sư trước khi có người dùng thứ hai |
| 39 | Xác thực hai lớp cho chủ? | 60-Q2 | V2 |
| 40 | Người dùng thứ hai có được nghe thông báo ngân hàng, tin nhắn? | 60-Q3 | Để khi có người thứ hai |
| 41 | Danh sách hành động cần vân tay có hợp ý? | 60-Q4 | Theo 60 mục 3.12: xóa một dòng không cần |
| 42 | Bộ mẫu ngân hàng: ai gõ lại và che? | 70-Q3 | Người dùng gửi ảnh, agent gõ và che, người dùng duyệt; ảnh xóa sau đó |
| 43 | Ngưỡng chặn nhầm của bộ lọc OTP 10 phần trăm? | 70-Q4 | Chấp nhận |
| 44 | `DEV_JOB_DAILY_USD = 5` là trần chi phí AI theo ngày cho V3 (10:L208). Có coi là ngoại lệ của QĐ-15? | Mới | Giữ làm ngoại lệ, ghi bằng QĐ mới khi tới V3 |

### C2. Kỹ thuật, đề xuất chốt

| # | Việc | Đề xuất chốt | Tệp sửa |
|---|---|---|---|
| K1 | Sự kiện lặp (A#1) | Theo 11: lưu bản gốc có `recurrence` cộng ngoại lệ, `singleEvents=false`, máy chủ trải. Lý do: 11 là nguồn bảng, 12 đã dựng API theo cách này. Bỏ ĐX-G12 | 40 |
| K2 | Trạng thái OAuth (A#2) | Giữ bảng `tab_google_oauth_state`: `code_verifier` đã mã hóa, `state` dùng một lần nên chống phát lại, việc mà chuỗi tự chứa không làm được. Bỏ ĐX-G11 | 40 |
| K3 | Biến redirect (A#16) | Giữ `GOOGLE_REDIRECT_URI` (máy cá nhân dùng client và địa chỉ riêng). Bỏ ĐX-G14 | 40, 50 |
| K4 | Mốc cứng chuyến (A#3) | Giữ bảng `tab_trip_fact` (đã nhận ở CSDL-09); thêm `opening_hours`, `other` vào `kind`. Bỏ ĐX-T7 | 41, 11 |
| K5 | Cột trip (A#4, #5) | Tên cột theo 11 bản 2; 11 thêm `tab_trip.evaluation jsonb`; cấu trúc rủi ro theo 41 mục 6.3 (nhận ĐX-T9) | 41, 11 |
| K6 | Vỏ hành động (A#6, #37) | Trường phẳng như 12, 31, thêm `id`; 12 thêm `fallback_url` cho `open_map_navigation`; `confirm` không có `kind`. Lý do: hai tệp và ví dụ SSE đã phẳng, rà lần 1 đã chọn phẳng. Điều phối ghi rõ vì QĐ-25 để 20 làm nguồn | 20, 12 |
| K7 | Hành động chờ duyệt (A#7) | Chỉ `tool_name`, `input`; băm `tool_name` cộng `input`. Bảng *kind* ở 20 mục 3.8 đổi thành bảng theo `tool_name` | 20, 40 |
| K8 | Vân tay (A#27) | Theo 60 mục 3.12 | 20, 11, 31 |
| K9 | Công cụ không tồn tại (A#28) | Bỏ `delete_note`, `delete_file`, `share_drive_file` khỏi CK của 11 tới khi 20 có công cụ; 60 thêm dòng `update_setting` (duyệt, không cần vân tay) | 11, 31, 60 |
| K10 | Tóm tắt hộp tin (A#9) | Lượt chat, `purpose = chat` (ĐX-API-09); 20 bỏ `summarize_inbox` khỏi `purpose`; 11 thêm `trip_evaluate` | 20, 11, 31 |
| K11 | Việc bị xóa trên Google (A#29) | `remote_deleted` và người dùng chọn (ĐX-CSDL-11). Bỏ phần xóa mềm của ĐX-G16 | 40, 31 |
| K12 | Ngắt kết nối (A#30) | Theo 11: có `keep_data`; danh bạ và thư Gmail trong hộp tin bị xóa | 40 |
| K13 | Xuất Sheets, Drive (A#11, #36) | Đi qua `tab_google_outbox` (`sheet_write`, `file_upload`); id thư mục và bảng tính ở `tab_google_sync_state.resource_id` | 40 |
| K14 | App SMS (A#31) | Theo 11: một dòng `sms_default`, máy chủ biết gói thật qua `tab_device.default_sms_package`. Tự theo khi người dùng đổi app SMS mặc định. Không nhận ĐX-30-12 | 30, 31 |
| K15 | Trường thiết bị (A#32) | Nhận cả ba cột và ba trường `/device/config` của 30 | 11, 12 |
| K16 | Khuôn công cụ (A#26) | Theo 20 (ĐX-AI-13, 14) | 10, 12 |
| K17 | Số liệu, tên biến, tên job (A#17, #18, #20-23, #38) | Theo 10 và 12: URL ký sẵn 300 giây; WAF 20 yêu cầu mỗi 10 giây; lô 200; hàng chờ Google thử tối đa 5 lần; `AI_EFFORT_CHAT`; `pull_google_tasks_status`; ba biến thời hạn 180 ngày | 20, 40, 50, 60 |
| K18 | Tên màn (A#14, #33) | `inbox_conversation` với `conversation_key`; `settings_ai_cost` | 31, 12 |
| K19 | Tọa độ điểm dừng (A#34, 11-Q3) | Đặt rỗng tọa độ nguồn `google` quá 30 ngày chưa làm mới, theo điều khoản Places | 11, 10 |
| K20 | Khóa ký APK (A#24) | 10950 ngày (30 năm) | 60 |
| K21 | Bộ câu mẫu (A#25) | 24 câu, định dạng của 20 | 70 |
| K22 | Trang tĩnh | 12 thêm hai trang vào bảng đường dẫn (ngoài `/api`); 00 ghi trang chính sách vào V1.0 | 12, 00 |
| K23 | RLS (A#43) | Bật trước khi tạo tài khoản thứ hai | 10, 11 |
| K24 | Đề xuất mới của bản 2 chưa có QĐ: ĐX-KT-10 tới 13, ĐX-CSDL-10 tới 13, ĐX-API-09 tới 12, ĐX-AI-13 tới 22, ĐX-30-11 tới 14, ĐX-31-08 tới 11, ĐX-G11 tới 16, ĐX-T7 tới 10, bảng đề xuất của 50, 60, 70 | Ghi một QĐ-26: nhận hết, trừ ĐX-G11, G12, G14, phần xóa mềm của G16, ĐX-T7, ĐX-30-12, phần vỏ `payload` của ĐX-AI-15, và đề xuất *URL ký sẵn 10 và 15 phút* của 50 | 90 |
| K25 | Việc kiểm trước khi viết mã | Thời hạn Anthropic giữ dữ liệu (trước V1.3); điều khoản lưu dữ liệu Maps và Routes (trước V1.6); các điểm *chưa xác minh* của 40 (thử thật ở V1.4) | 20, 41, 40 |

---

## D. Chỗ trái QĐ-15 tới QĐ-25

| QĐ | Kết quả | Chỗ trái hoặc cần xem |
|---|---|---|
| QĐ-15 | Gần khớp | 10:L208 `DEV_JOB_DAILY_USD = 5` là trần chi phí AI theo ngày (cho V3). 10 ghi *không thuộc QĐ-15*. Cần người dùng xác nhận (C1 câu 44). Còn lại: không còn trần ngày ở đâu; `AI_MONTHLY_USD` chỉ cảnh báo ở 10, 12, 20, 31, 50 |
| QĐ-16 | Khớp | 10, 11, 50, 60, 70 cùng chủ nhật 02:00, 5 bản gồm bản trước migration. 50:L336 ghi `sun` thay `6` chỉ là cách ghi (A#38) |
| QĐ-17 | Khớp | Không còn mức 30 ngày cho tin người khác |
| QĐ-18 | Khớp | 30, 31, 50, 70 đều hỏi trước khi cài; 11 đã bỏ `app.auto_install_update` |
| QĐ-19 | Khớp | 30, 31, 60, 70 có cả hai app SMS và bước *Ứng dụng không bao giờ ngủ*. Cách lưu khác nhau giữa 11 và 30 (A#31), cả hai đều đúng QĐ |
| QĐ-20 | Khớp | 10, 11, 20, 31 cùng mốc 04:00 |
| QĐ-21 | Gần khớp | 70:L237 còn ghi *việc không giờ đẩy một chiều sang Tasks*; chữ *một chiều* là phần QĐ-21 đã sửa. 40 và 11 cùng đọc ngược nhưng xử lý *đã xóa* khác nhau (A#29) |
| QĐ-22 | Khớp | Không còn cột hay trường số dư |
| QĐ-23 | Khớp | 11, 12, 20, 31, 40, 60 cùng tạo hành động chờ duyệt cho sự kiện có khách |
| QĐ-24 | Khớp | 50 chỉ `docker stop core-game`, giữ `cloudflared`, chờ người dùng xác nhận. Việc báo agent Gamebar chưa làm (mục B) |
| QĐ-25, nguồn chuẩn bảng | Trái | 20 (A#7, #8, #9), 30 (A#31), 40 (A#1, #2, #10, #11, #12, #30, #35, #36), 41 (A#3, #4, #5) không theo 11 |
| QĐ-25, nguồn chuẩn API | Trái | 20 (`/inbox/summarize`), 31 (`/inbox/threads`, `/events`, `/google/account`), 40 (`/google/account`, `/google/sync`), 50 (`/api/v1/releases`) không theo 12 (A#9, #13, #14) |
| QĐ-25, công cụ và hành động | Trái | 11, 31, 60 nêu công cụ không có ở 20 (A#28). 12, 31 dùng vỏ hành động khác 20; riêng chỗ này đề xuất sửa 20 (C2 K6) |
| QĐ-25, biến và job | Trái | 20 (`AI_EFFORT_DEFAULT`), 40 (`sync_google_tasks`, bỏ `GOOGLE_REDIRECT_URI`), 50 (`.env.example`), 60 (`THIRD_PARTY_RETENTION_DAYS`) không theo 10 (A#16, #17, #18, #38) |
| QĐ-25, giới hạn | Trái | 50, 60 không theo bảng 12 mục 3.7 (A#20, #21) |
| QĐ-25, luật duyệt | Trái | 11, 20, 31 không theo 60 mục 3.12 về vân tay (A#27) |
| QĐ-25, đề xuất lần 1 đã nhận | Trái | QĐ-25 nhận CSDL-09 (thêm `tab_google_oauth_state`, `tab_trip_fact`...). 40 (ĐX-G11) và 41 (ĐX-T7) đề nghị bỏ lại hai bảng này. QĐ-25 nhận AI-12 phần cột (`tool_name`, `input`); 20 vẫn giữ `kind`, `payload` |
| QĐ-25, dẫn chéo | Cần sửa | 11 mục 3.13 nói bảng trip theo 41 mục 12; 41 mục 12 nói giữ tên của 11; nội dung hai bên khác nhau. Tương tự 11 ĐX-CSDL-10 và 40 ĐX-G12 về sự kiện lặp |
