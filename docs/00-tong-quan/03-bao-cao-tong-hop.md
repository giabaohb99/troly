# Báo cáo tổng hợp tài liệu

Ngày 18/11/2026. Viết cho Gia Bảo đọc trong 10 tới 15 phút để nắm toàn bộ dự án `troly` mà không phải mở từng tài liệu. Mỗi phần ghi tệp nguồn để tra chi tiết.

Số liệu lấy từ bản 2 của các tài liệu. Chỗ các tài liệu còn lệch nhau thì ghi theo nguồn chuẩn của QĐ-25 và có chú thích *(còn lệch)*; danh sách đầy đủ ở [81-ra-cheo-lan-2.md](../80-ra-soat/81-ra-cheo-lan-2.md).

---

## 1. Sản phẩm, phạm vi V1, ngoài phạm vi

Nguồn: [00-ke-hoach.md](00-ke-hoach.md), [01-thiet-ke-tong-the.md](01-thiet-ke-tong-the.md).

**Sản phẩm.** Một app trợ lý cá nhân trên Android (máy Samsung Galaxy S25+). Một chỗ để chat với trợ lý, xem tin nhắn, lịch và việc, chi tiêu, lịch trình, báo cáo và cài đặt. Trợ lý trả lời ngắn, không tự gửi báo cáo. Hiện chỉ một người dùng là Gia Bảo; khung dữ liệu vẫn tách theo người để mở tối đa 4 người sau này.

**Phạm vi V1 (V1.0 tới V1.8):**

| Mảng | Làm gì |
|---|---|
| Trợ lý | Chat, nhớ hồ sơ lõi, gọi công cụ thay người dùng, thẻ duyệt cho việc ra ngoài |
| Hộp tin | Tin Zalo, Telegram, Messenger, SMS (qua thông báo Android) và Gmail gom một chỗ; tin quan trọng lên đầu |
| Lịch và việc | Google Calendar hai chiều, Google Tasks, nhắc kêu ngay trên máy |
| Chi tiêu | Tự ghi từ thông báo Vietcombank, Techcombank, MoMo; ghi bằng câu chat; lọc OTP ngay trên máy |
| Lịch trình | Nhập tệp hoặc mô tả, đánh giá rủi ro, đưa phương án, mở Google Maps chế độ xe máy, xuất Word |
| Báo cáo | Chi tiêu, lịch tuần, tin chưa xử lý, chi phí AI, thiết bị |
| Cài đặt | Kết nối Google, app được nghe, người quan trọng, thiết bị, phiên bản, dữ liệu của tôi |

**Ngoài phạm vi V1:** trả lời tin thay người dùng (V2, có duyệt); module gym và Health Connect (V2); máy chủ MCP (V2); tự phát triển bằng Claude CLI (V3); đặt hàng Shopee; tự thao tác app khác; báo cáo tự gửi; iPhone; Google Photos, Google Keep (API không cho dùng); bản đồ vẽ trong app; thời tiết, xuất PDF lịch trình.

---

## 2. Quyết định đã chốt

Nguồn: [90-quyet-dinh.md](../90-quan-ly/90-quyet-dinh.md).

| Nhóm | Đã chốt | QĐ |
|---|---|---|
| Nền tảng | App Android viết bằng Capacitor (giao diện React, plugin Kotlin); không MacroDroid, không bot Telegram | 01, 02 |
| Nghe tin | Đọc thông báo Android của Zalo, Telegram, Messenger, SMS; không giả lập tài khoản | 03 |
| Chi tiêu | Tự ghi từ Vietcombank, Techcombank, MoMo; OTP bị lọc trên máy, không bao giờ rời điện thoại | 04 |
| AI | Model `claude-haiku-5-5` đặt trong `.env`; bộ não dùng khóa API, phát triển dùng gói đăng ký Claude CLI | 05, 12 |
| Máy chủ | Chạy chung VPS với Gamebar và gymcanhan; FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16; mọi thứ chạy Docker, cả máy cá nhân | 06, 07, 14 |
| Build | APK build trên GitHub Actions | 08 |
| Google | Calendar hai chiều, Google làm gốc; việc do app làm gốc, đẩy sang Tasks và đọc ngược trạng thái *xong*, *đã xóa*; việc có giờ thành sự kiện; tích hợp đủ Calendar, Tasks, Maps, Gmail, Contacts, Drive, Sheets; Health Connect ở V2 | 09, 10, 21 |
| Hành vi | Không tự gửi báo cáo | 11 |
| Cách làm | Một điều phối, năm agent theo mảng | 13 |
| Chi phí AI | Không trần theo ngày; chỉ cảnh báo khi tháng vượt 200 USD, không chặn | 15 |
| Sao lưu | Mỗi tuần một lần (chủ nhật 02:00), giữ 5 bản, gồm bản trước mỗi migration | 16 |
| Lưu giữ | Tin của người khác giữ 180 ngày; không lưu số dư, chỉ số tiền, mã ngân hàng, 4 số cuối | 17, 22 |
| Cập nhật app | Luôn hỏi trước khi cài APK mới | 18 |
| Máy | Galaxy S25+, cài đặt mặc định; nghe cả Samsung Messages và Google Messages; có bước tắt chế độ ngủ của One UI | 19 |
| Chat | Phiên theo ngày tách lúc 04:00 | 20 |
| Mời khách | Sự kiện có khách làm ở V1.4, gửi lời mời phải qua thẻ duyệt | 23 |
| VPS | Tạm dừng `core-game` của Gamebar, giữ `cloudflared`; làm ngay trước lần deploy V1.0 đầu, có người dùng xác nhận | 24 |
| Thống nhất | Nhận các đề xuất ở rà chéo lần 1; nguồn chuẩn khi lệch: bảng theo 11, API và giới hạn theo 12, công cụ và hành động theo 20, biến và job theo 10, mạng và compose theo 50, luật duyệt theo 60 | 25 |

Bản 2 có thêm khoảng 60 đề xuất mới chưa có QĐ (xem mục 17 và `81-ra-cheo-lan-2.md` C2 câu K24).

---

## 3. Kiến trúc và hạ tầng

Nguồn: [01-thiet-ke-tong-the.md](01-thiet-ke-tong-the.md) mục 4, [50-ha-tang-trien-khai.md](../50-ha-tang/50-ha-tang-trien-khai.md), [10-kien-truc-backend.md](../10-backend/10-kien-truc-backend.md) mục 3.1.

```
 Galaxy S25+: app Trợ lý (React trong WebView + plugin Kotlin)
        │ HTTPS /api/v1   (JWT cho giao diện, mã thiết bị cho plugin)
 Cloudflare (DNS, TLS, WAF, tunnel dùng chung của Gamebar)
        │
 VPS: troly-api ─┬─ troly-db (PostgreSQL 16, mạng kín)
      troly-worker┘
        │
 Claude API, Google APIs, Cloudflare R2
```

**Các container của troly:**

| Container | Ảnh | Việc | Trần RAM, CPU |
|---|---|---|---|
| `troly-api` | `troly-backend` (`python:3.12-slim`) | FastAPI, một tiến trình uvicorn, REST và chat SSE | 448 MB, 0,75 |
| `troly-worker` | cùng ảnh | Hàng đợi, đồng bộ Google, sao lưu, dọn dữ liệu | 384 MB, 0,5 |
| `troly-db` | `postgres:16-alpine` | DB, volume `troly-pgdata` | 512 MB, 0,75 |
| `troly-migrate` | cùng ảnh | Chạy migration một lần lúc deploy | |

Một Dockerfile backend ba đích: `base`, `dev` (thêm công cụ kiểm), `prod` (chép mã, user không root).

**VPS chung:**

| Mục | Giá trị |
|---|---|
| Máy | Ubuntu 24.04, 2 vCPU, 4 GB RAM, ổ khoảng 22 GB dùng được, chỉ mở cổng 22 |
| Cổng | Gamebar `127.0.0.1:8080` (tạm dừng); gymcanhan `127.0.0.1:8100`; troly `127.0.0.1:8200` |
| Mạng | `troly_edge` (bridge, ra Internet); `troly_core` (internal, DB nằm đây, không ra Internet) |
| Tunnel | `cloudflared` nằm trong compose của Gamebar, mạng host; troly chỉ thêm một Public Hostname trỏ `localhost:8200` |
| RAM | Lúc Gamebar tạm dừng, cả máy dùng khoảng 0,9 tới 1,5 GB; trần của troly cộng lại 1,34 GB |
| Cô lập | Chỉ ghi `/opt/troly`; không `docker system prune -a`, không `docker volume prune`; chỉ dọn ảnh có nhãn `com.troly.image=1` |

**R2:** ba bucket `troly-files` (tệp người dùng, khóa `u/<user_id>/...`), `troly-backup` (sao lưu mã hóa), `troly-release` (APK và gói giao diện). URL ký sẵn sống 300 giây *(còn lệch: 50 và 60 ghi 10 phút tải lên, 15 phút tải về)*.

**Máy cá nhân (Windows 11, Docker 29.8.1, Compose v5.5.1):** không cài Python, Postgres, Android SDK.

| Tệp compose | Dùng | Nội dung |
|---|---|---|
| `docker-compose.yml` | VPS và làm nền ở máy | api, worker, db, migrate |
| `docker-compose.dev.yml` | Ghép đè ở máy | Gắn mã, tự nạp lại (bật dò định kỳ vì mã nằm ổ Windows), api cổng 8200, Vite cổng 5190, DB `127.0.0.1:55432`, S3 giả thay R2 |
| `infra/docker-compose.test.yml` | Máy và GitHub Actions | `db-test` trên tmpfs, `test`, `web-test`, `android-test` |

Ảnh Docker có Android SDK để build bản thử ký debug là tùy chọn, đề xuất dựng từ V1.2.

**Deploy:** chạy `bash scripts/deploy.sh` từ máy cá nhân qua SSH (GitHub Actions không SSH vào VPS). Tám bước: kiểm CI xanh, đẩy mã bằng `git archive`, build ảnh với `nice`, sao lưu nếu có migration, chạy migration, đổi ảnh, chờ healthcheck, ghi `releases.log` và dọn. Quay lui bằng `--rollback` dưới 1 phút. Migration luôn tương thích ngược với bản trước.

**Sao lưu:** job `backup_database` chủ nhật 02:00 giờ Việt Nam; `pg_dump` qua ống sang `age` (khóa công khai trên VPS, khóa bí mật chỉ người dùng giữ) rồi lên `troly-backup`. Giữ 5 bản tính cả bản trước migration, luôn còn ít nhất 1 bản tuần. Có nút *Sao lưu ngay*. Quá 8 ngày không có bản tốt thì trạng thái hệ thống đỏ. Mất tối đa 7 ngày dữ liệu, dựng lại dưới 1 giờ. Diễn tập khôi phục trên máy cá nhân ngay sau bản đầu tiên, sau đó mỗi tháng.

**GitHub Actions:** `backend-test.yml` (ruff, migration lên xuống, pytest, pip-audit, dựng ảnh prod); `app-build.yml` (job `ui`, `android-unit`, `android-emulator`, `apk`; đăng bản qua `POST /api/v1/admin/releases` bằng mã CI); `ai-eval.yml` chạy tay.

---

## 4. Backend

Nguồn: [10-kien-truc-backend.md](../10-backend/10-kien-truc-backend.md).

**Tầng lớp trong một module:**

| Tệp | Làm | Không làm |
|---|---|---|
| `models.py` | Bảng | Luật nghiệp vụ |
| `schemas.py` | Dữ liệu vào ra, câu lỗi tiếng Việt | Gọi DB |
| `repo.py` | Truy vấn, mọi hàm nhận `(session, user_id, ...)` | Gọi Google, Claude, `commit` |
| `service.py` | Luật nghiệp vụ; module khác chỉ gọi tệp này | Trả phong bì, `commit` |
| `router.py` | REST, bọc phong bì `{success, message, data}` | SQL |
| `tools.py` | Công cụ cho AI | Nhận `user_id` từ model |
| `jobs.py` | Job chỉ chạm module đó | Tự lặp |

**Luật module:** chỉ import `service` và `schemas` của module khác; không vòng phụ thuộc; `core/`, `integrations/`, `ai/` không import `modules/`; chỉ `app/main.py` và `worker/main.py` ghép mọi thứ. Code đồng bộ (không async). Một yêu cầu một giao dịch; gọi ra ngoài không nằm trong giao dịch dài.

**Module và chiều gọi:**

| Module | Gọi | Ghi chú |
|---|---|---|
| `setting` | | Tầng thấp nhất |
| `file`, `memory`, `expense`, `device`, `calendar`, `inbox` | `setting` | `device` chỉ nhận và lưu sự kiện |
| `task` | `calendar`, `setting` | Việc có giờ tạo sự kiện |
| `trip` | `calendar`, `file`, `setting` | |
| `chat` | `memory`, `file`, `setting` | Gọi `ai.loop.run_turn` |
| `report` | `expense`, `task`, `calendar`, `inbox`, `file`, `setting` | Chỉ đọc |
| `health` (V2) | `setting` | |

Điều phối sự kiện thiết bị (ngân hàng sang chi tiêu, tin nhắn sang hộp tin, bấm nút nhắc) nằm ở `worker/jobs/device_events.py`.

**Đăng nhập, năm loại danh tính:**

| Ai | Tiêu đề | Gọi được |
|---|---|---|
| Giao diện | `Bearer <JWT>` | API của app |
| Plugin | `Device <mã>` | `/device/*`, `/calendar/reminders` |
| GitHub Actions | `CI <mã>` | Chỉ `POST /admin/releases` |
| Máy chạy Claude CLI (V3) | `Runner <mã>` | Chỉ `/dev/jobs/*` |
| Google | `X-Goog-Channel-Token` | Chỉ webhook Calendar |

JWT sống 30 phút; mã làm mới 60 ngày, xoay mỗi lần dùng, dùng lại mã cũ thì thu hồi cả phiên. Mật khẩu bcrypt hệ số 12; sai 5 lần khóa 15 phút. Không có đăng ký tự do: chủ tạo bằng `python -m app.cli create-owner`. Lệnh quản trị khác: `revoke-device`, `unlock-user`, `reencrypt-tokens`, `export-openapi`.

**Worker:** chờ tín hiệu `NOTIFY troly_wake` hoặc 30 giây; khởi động lại thì chạy bù job lỡ giờ. Tránh chạy trùng bằng `SKIP LOCKED` và khóa tư vấn. Thử lại hai mức: trong một lời gọi 2^n giây, trần 64 giây, 5 lần; dòng hàng đợi giãn 30 giây × 2^n.

**Danh sách job (16 job, nguồn chuẩn ở 10 mục 3.9):**

| Job | Lịch | Việc | Bản |
|---|---|---|---|
| `process_device_events` | Mỗi vòng, lô 200 | Thông báo sang chi tiêu, hộp tin; nút nhắc | V1.2 |
| `run_queued_jobs` | Mỗi vòng | Nhập, đánh giá lịch trình; đồng bộ Google lần đầu; xuất, xóa dữ liệu | V1.0 |
| `summarize_previous_day` | 04:05 | Tóm tắt phiên chat hôm trước | V1.0 |
| `expire_pending_actions` | 5 phút | Hành động chờ duyệt quá hạn | V1.0 |
| `backup_database` | Chủ nhật 02:00 | Sao lưu | V1.0 |
| `cleanup_old_data` | 03:30 | Dọn theo bảng thời hạn | V1.0 |
| `disk_check` | 15 phút | Dưới 15 phần trăm ổ trống thì cảnh báo, dưới 8 thì dừng việc ghi nhiều | V1.0 |
| `recover_stuck_items` | 5 phút | Trả lại dòng kẹt quá 10 phút | V1.0 |
| `check_silent_devices` | Mỗi giờ | Máy im lặng quá 24 giờ | V1.2 |
| `push_google_outbox` | Mỗi vòng | Ghi lên Google | V1.4 |
| `sync_google_calendar` | Webhook, quét 15 phút ±25% | Kéo thay đổi lịch | V1.4 |
| `renew_google_watch` | 03:00 | Gia hạn kênh còn dưới 48 giờ | V1.4 |
| `pull_google_tasks_status` | 15 phút | Đọc ngược *xong*, *đã xóa* | V1.4 |
| `cleanup_google_oauth_state` | Mỗi giờ | Dọn trạng thái OAuth | V1.4 |
| `sync_gmail` | 5 phút | Thư vào hộp tin | V1.8 |
| `sync_google_contacts` | 04:00 | Danh bạ, sinh nhật | V1.8 |

*(Còn lệch: 40 gọi job Tasks là `sync_google_tasks`; 50 ghi lô 50.)*

---

## 5. Cơ sở dữ liệu

Nguồn: [11-co-so-du-lieu.md](../10-backend/11-co-so-du-lieu.md).

Quy ước: bảng tiền tố `tab_`, số ít; khóa `bigint`; mọi bảng nghiệp vụ có `user_id`, kể cả bảng con; tiền là số nguyên VND; giờ lưu UTC; liệt kê bằng `text` + `CHECK`; tìm toàn văn gõ không dấu vẫn ra (`troly_vn`).

**Nhóm bảng chính:**

| Nhóm | Bảng | Vai trò |
|---|---|---|
| Lõi | `tab_user`, `tab_auth_session`, `tab_job_queue`, `tab_job_schedule`, `tab_job_run`, `tab_audit_log`, `tab_consent` | Tài khoản, phiên, hàng đợi việc, lịch job, kiểm toán, đồng ý xử lý dữ liệu |
| AI | `tab_ai_run` | Mỗi lần gọi Claude: token, cache, tiền, lý do dừng |
| Cài đặt, trí nhớ | `tab_setting`, `tab_profile_memory`, `tab_profile_memory_revision`, `tab_note` | Khóa cài đặt; hồ sơ lõi 8.000 ký tự, 50 bản cũ để hoàn tác; ghi chú |
| Chat | `tab_conversation`, `tab_message`, `tab_pending_action` | Phiên theo ngày; tin nguyên khối Claude; hành động chờ duyệt (hạn 24 giờ, băm nội dung) |
| Thiết bị | `tab_device`, `tab_listened_app`, `tab_device_event`, `tab_app_release` | Máy, app được nghe, hàng đợi thông báo, bản phát hành |
| Chi tiêu | `tab_expense_category`, `tab_expense` | `kind` (`expense`, `income`, `transfer`), `account` (mã), `account_last4`; không có số dư |
| Hộp tin | `tab_inbox_message`, `tab_inbox_rule`, `tab_contact`, `tab_gmail_draft` | Tin gom theo `conversation_key`; luật người quan trọng, từ khóa gấp, tắt tiếng, riêng tư |
| Lịch, việc | `tab_event`, `tab_task` | Sự kiện có `remind_source`, khách mời; việc có `due_date` hoặc `due_at` |
| Google | `tab_google_account`, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox` | Token mã hóa Fernet; trạng thái đồng bộ; hàng chờ ghi lên Google |
| Lịch trình | `tab_trip`, `tab_trip_stop`, `tab_trip_option`, `tab_trip_fact`, `tab_place_cache`, `tab_route_cache` | Chuyến, điểm dừng, phương án, mốc cứng, đệm địa điểm và tuyến |
| Báo cáo, tệp | `tab_export`, `tab_file` | Lịch sử xuất; tệp trên R2 |
| Sau V1 | `tab_health_daily` (V2), `tab_dev_job` (V3) | |

*(Còn lệch: 41 muốn bỏ `tab_trip_fact` và đặt tên cột điểm dừng khác; 40 muốn bỏ `tab_google_oauth_state`. Đề xuất giữ theo 11.)*

**Thời hạn giữ dữ liệu:**

| Dữ liệu | Giữ |
|---|---|
| Hộp tin, sự kiện thiết bị | 180 ngày rồi xóa cứng |
| Khối chat có tin người khác | 180 ngày rồi thay nội dung, giữ cấu trúc |
| Lịch sử chat | 365 ngày *(chờ người dùng duyệt)*; tóm tắt phiên giữ mãi |
| Tin có OTP | Không lưu (bỏ trên máy) |
| Chi tiêu, việc, lịch, danh bạ | Tới khi người dùng xóa; dòng xóa mềm giữ 30 ngày |
| Chi phí AI | 13 tháng |
| Nhật ký kiểm toán | 365 ngày |
| Đệm địa điểm | `place_id` giữ mãi; tọa độ, địa chỉ xóa sau 30 ngày |
| Sao lưu | 5 bản; dữ liệu đã xóa còn trong bản sao lưu thêm khoảng 5 tuần |

---

## 6. API

Nguồn: [12-api.md](../10-backend/12-api.md).

**Quy ước:** gốc `https://<api-domain>/api/v1` (riêng `/api/health`); danh từ số nhiều; JSON snake_case; phong bì `{success, message, data}`; lỗi có `data.code` và câu tiếng Việt; phân trang bằng con trỏ (`limit` tối đa 200); thời điểm ISO 8601 có độ lệch.

**Nhóm endpoint:**

| Nhóm | Đường chính | Bản |
|---|---|---|
| Hệ thống, tài khoản | `/auth/*`, `/me/export`, `DELETE /me`, `/consents`, `/users`, `/settings`, `/jobs/{id}` | V1.0 |
| Trí nhớ, chat | `/memory/profile`, `/memory/notes`, `/chat/today`, `/chat/messages` (SSE), `/chat/actions/{id}/approve` | V1.0 |
| Tệp | `/files/upload-url`, `/files/{id}/complete`, `/files/{id}/drive` | V1.0, V1.8 |
| Chi tiêu | `/expenses`, `/expenses/summary`, `/expenses/categories`, `/expenses/{id}/source` | V1.1, V1.2 |
| Thiết bị | `/devices`, `/devices/listened-apps`, `/device/events`, `/device/config`, `/device/heartbeat` | V1.0, V1.2 |
| Hộp tin | `/inbox/conversations`, `/inbox/messages`, `/inbox/rules` | V1.3 |
| Việc, lịch | `/tasks`, `/calendar/events`, `/calendar/reminders` | V1.4 |
| Google | `/google/status`, `/google/connect`, `/google/oauth/callback`, `/google/disconnect`, `/google/sync/{service}`, `/google/outbox`, `/webhooks/google/calendar` | V1.4 |
| Cập nhật, quản trị | `/device/release`, `/device/web-bundle`, `/admin/releases`, `/admin/worker`, `/admin/audit-log` | V1.5, V1.2 |
| Lịch trình | `/trips/import`, `/trips/{id}/evaluate`, `/trips/{id}/map-links`, `/trips/{id}/export-docx`, `/trips/{id}/to-calendar` | V1.6 |
| Báo cáo | `/reports/dashboard`, `/reports/ai-cost`, `/reports/exports` | V1.7, V1.8 |
| Gmail, danh bạ | `/gmail/drafts`, `/gmail/drafts/{id}/send` (tạo thẻ duyệt), `/contacts` | V1.8 |
| Sau V1 | `/device/health` (V2), `/dev/jobs/*` (V3) | |

Việc dài (nhập, đánh giá lịch trình, xuất) trả 202 kèm `job_id`. Tóm tắt hộp tin không có endpoint riêng: nút *Tóm tắt* gửi một câu chat dựng sẵn *(còn lệch: 20 vẫn ghi `/inbox/summarize`)*.

**Chat SSE:** gửi `client_message_id`, `text`, `attachment_file_ids`, `think_harder`. Máy chủ trả lần lượt `message.created`, `text.delta`, `tool.started` (có nhãn như *Đang ghi khoản chi*), `tool.finished`, `action`, `message.completed` (kèm `usage`), hoặc `error`. Ping mỗi 15 giây để Cloudflare không cắt. Mất kết nối thì máy chủ chạy hết lượt và lưu. Có đường lui JSON.

**Hành động trả cho app (8 kiểu):** `open_map_navigation`, `open_map_directions`, `open_map_place`, `open_link`, `open_screen`, `confirm`, `memory_changed`, `choices`. Link bản đồ luôn do máy chủ dựng. *(Còn lệch: 20 bọc trường trong `payload`, 12 và 31 để phẳng; đề xuất để phẳng.)*

**Giới hạn tần suất (bảng chung ở 12 mục 3.7):**

| Đường | Mức |
|---|---|
| `/auth/*` ở Cloudflare | 20 yêu cầu mỗi 10 giây mỗi IP |
| Đăng nhập | 10 lần mỗi 15 phút; sai 5 lần liền khóa 15 phút |
| Chat | 20 câu mỗi phút, 60 câu mỗi giờ |
| Sự kiện thiết bị | Lô 1 tới 50, tối đa 256 KB; 120 mỗi phút mỗi máy; 5.000 mỗi ngày |
| Khác | 300 yêu cầu mỗi phút; thân 1 MB; tệp 25 MB; tin chat 4.000 ký tự |

---

## 7. Bộ não AI

Nguồn: [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md).

**Model:** `claude-haiku-5-5` cho mọi việc ở V1. Giá khi lời nhắc dưới 100K token: 0,10 USD mỗi triệu token vào, 0,50 USD mỗi triệu token ra. Effort `low` cho chat thường, `medium` khi bấm *nghĩ kỹ*. Không tắt thinking, không gửi `temperature`. Phải xem lại trang giá chính thức trước khi dựng V1.0.

**Cache:** thứ tự gửi là công cụ, lời nhắc hệ thống tĩnh, hồ sơ lõi, tóm tắt phiên trước, rồi tin hôm nay. Bốn điểm cache: ba điểm đầu TTL 1 giờ, đuôi TTL 5 phút. Giờ hiện tại đi trong một tin `role: system` riêng sau tin người dùng, không nằm trong phần đầu. Có bài kiểm không tốn tiền canh phần đầu không đổi byte nào.

**Trí nhớ ba tầng:**

| Tầng | Ở đâu | Vào lời nhắc |
|---|---|---|
| Dữ liệu có cấu trúc | Bảng nghiệp vụ | Chỉ qua công cụ |
| Hồ sơ lõi | 8 mục cố định, tối đa 8.000 ký tự | Mọi lượt |
| Ghi chú, tóm tắt | `tab_note`, tóm tắt phiên | Khi tra |

`remember`, `forget` không cần duyệt, có nút *Hoàn tác*. Phiên dài quá 30.000 token thì tóm tắt giữa hai lượt, giữ 6 tin cuối.

**Phiên 04:00:** mỗi ngày một phiên, ranh giới 04:00 giờ Việt Nam; chat lúc 01:00 vẫn thuộc hôm trước. Phiên mới mang tóm tắt hôm trước, không mang tin cũ. Báo cáo, chi tiêu, lịch vẫn tính ngày từ 00:00.

**Danh mục công cụ (42 công cụ khi đủ V1.8):**

| Nhóm | Công cụ | Bản | Cần duyệt |
|---|---|---|---|
| memory (4) | `remember`, `forget`, `save_note`, `search_notes` | V1.0 | Không |
| chat (1) | `search_conversations` | V1.0 | Không |
| file (2) | `list_files`, `get_file_link` | V1.0 | Không |
| expense (5) | `add_expense`, `update_expense`, `delete_expense`, `query_expenses`, `list_expense_categories` | V1.1 | Xóa |
| inbox (3 + 5) | `list_inbox`, `summarize_inbox`, `mark_inbox`; V1.8: `search_gmail`, `get_gmail_thread`, `create_gmail_draft`, `send_gmail_draft`, `lookup_contact` | V1.3, V1.8 | Gửi thư |
| task (4) | `add_task`, `update_task`, `list_tasks`, `delete_task` | V1.4 | Xóa |
| calendar (5) | `add_event`, `update_event`, `list_events`, `delete_event`, `set_reminder` | V1.4 | Xóa; có khách mời |
| trip (9) | `import_trip`, `evaluate_trip`, `save_trip`, `list_trips`, `get_trip`, `find_place`, `open_route`, `export_trip_docx`, `delete_trip` | V1.6 | Xóa |
| report (1 + 1) | `get_report`; V1.8: `export_expenses_to_sheets` | V1.7, V1.8 | Không |
| setting (2) | `get_settings`, `update_setting` (chỉ người quan trọng, từ khóa gấp) | V1.7 | Đổi cài đặt |

Không có công cụ đổi app được nghe, kết nối Google, thu hồi thiết bị, tạo tài khoản: chỉ làm tay. Nội dung tin của người khác nằm trong trường `du_lieu_ngoai`, trợ lý không làm theo lệnh trong đó. Câu chat *ok* không duyệt được.

**Bóc tách:** thông báo ngân hàng đi mẫu cố định trước, không khớp mà có dấu hiệu giao dịch mới gọi AI; che số tài khoản, bỏ số dư trước khi gửi. Câu chat chi tiêu do model chat gọi thẳng `add_expense`. Lịch trình dùng lược đồ của 41.

**Chi phí ước tính (một người, 40 lượt mỗi ngày):**

| Khoản | USD mỗi tháng |
|---|---|
| Chat (ghi, đọc cache, lịch sử, đầu ra) | khoảng 3,2 |
| Tóm tắt phiên, bóc tách ngân hàng, lịch trình, tóm tắt hộp tin | khoảng 0,3 |
| **Cộng** | **khoảng 3,5** |
| Trường hợp xấu (không ăn cache, 80 lượt mỗi ngày) | khoảng 10,6 |

Cảnh báo khi tháng vượt 200 USD, không chặn. Cầu chì kỹ thuật: tối đa 8 vòng công cụ mỗi lượt, 60 lượt mỗi giờ. Nên đặt hạn mức chi trên trang Anthropic làm chặn cứng cuối cùng.

**Đo chất lượng:** bộ 24 câu mẫu (nhóm thường và nhóm an toàn) chạy tay bằng `pytest -m ai_eval`, trần 0,5 USD mỗi lần. Đạt khi lần đầu từ 21 trên 24, đạt mọi câu an toàn, giá trung bình dưới 0,005 USD mỗi câu *(còn lệch: 70 ghi 22 câu)*.

---

## 8. App Android

Nguồn: [30-app-android.md](../30-app/30-app-android.md).

**Nền tảng:** Capacitor 8.x (8.6.2), Node 24, JDK 21, `minSdk` 26, `targetSdk` 36, Kotlin 2.2.20, WorkManager 2.12.0, Health Connect 1.1.0 (V2). Mã gói `vn.io.baohuynh.troly`, tên *Trợ lý*; bản gỡ lỗi `.debug` tên *Trợ lý (thử)* cài song song.

**Plugin Kotlin (8):**

| Plugin | Việc |
|---|---|
| Notify | Nghe thông báo, hàng đợi, bộ đếm OTP đã chặn |
| Alarm | Đặt nhắc trên máy |
| Update | Kiểm, tải, hỏi cài APK; tải và kiểm chữ ký gói giao diện |
| Maps | `navigate`, `openUrl`, `isMapsInstalled` |
| Secure | Cất mã thiết bị, mã làm mới trong kho khóa Android; vân tay |
| System | Kiểm quyền, mở trang cài đặt, trang Samsung |
| Voice | Nhận giọng nói tiếng Việt trên máy |
| Health (V2) | Đọc bước chân, giấc ngủ, nhịp tim |

**Quyền:** `POST_NOTIFICATIONS`, truy cập thông báo, *Cho phép cài đặt bị hạn chế*, pin không hạn chế, *Ứng dụng không bao giờ ngủ* của Samsung, `USE_EXACT_ALARM`, `RECEIVE_BOOT_COMPLETED`, cài ứng dụng không rõ nguồn gốc, `UPDATE_PACKAGES_WITHOUT_USER_ACTION`, `USE_BIOMETRIC`, `RECORD_AUDIO`. Không xin vị trí, danh bạ máy, SMS, `QUERY_ALL_PACKAGES`, trợ năng.

**App được nghe:**

| App | Tên gói | Dùng cho |
|---|---|---|
| Vietcombank | `com.VCB` | Chi tiêu |
| Techcombank | `vn.com.techcombank.bb.app` | Chi tiêu |
| MoMo | `com.mservice.momotransfer` | Chi tiêu |
| Zalo | `com.zing.zalo` | Hộp tin |
| Telegram | `org.telegram.messenger` | Hộp tin |
| Messenger | `com.facebook.orca` | Hộp tin |
| Samsung Messages hoặc Google Messages | `com.samsung.android.messaging`, `com.google.android.apps.messaging` | Hộp tin, theo app SMS mặc định thật |

Tên gói phải kiểm lại trên máy thật. Khi đã nối Gmail thì bỏ nghe app Gmail để tránh trùng. *(Còn lệch: 30 lưu hai dòng SMS riêng, 11 lưu một dòng `sms_default`; đề xuất theo 11.)*

**Bộ lọc trên máy (7 bước):** gói ngoài danh sách bị bỏ, không đọc trường nào; thông báo của chính app; thông báo tiến trình, cuộc gọi; tóm tắt nhóm; **OTP**; trùng trong 10 phút; ngân hàng mà rỗng. Chỉ các trường `title`, `text`, `conversation_title`, `messages[]`, `is_group_conversation`, `category`, `notification_key_hash`, `hidden_content` rời máy.

**Lọc OTP (đúng bộ luật của 60):** 15 từ khóa có dấu và không dấu (`OTP`, `mã xác thực`, `Smart OTP`, `verification code`, `2FA`...); số 4 tới 8 chữ số trong cùng câu, dạng `G-123456`; thông báo ngân hàng không khớp mẫu giao dịch thì bỏ hết; SMS từ tên thương hiệu có dãy 4 tới 8 số thì bỏ. Máy chủ chạy lại cùng bộ luật làm lưới an toàn; bộ đếm phía máy chủ phải bằng 0. Android 15 cũng tự che thông báo nghi là OTP.

**Hàng đợi:** Room, tối đa 7 ngày hoặc 5.000 dòng; WorkManager gửi lô 50 sự kiện; mở app thì gửi ngay.

**Nhắc lịch:** máy lấy danh sách nhắc 14 ngày tới từ `/calendar/reminders` (mỗi giờ, khi mở app, khi sửa); chỉ sự kiện `remind_source = app`. Nhắc thường dùng `setExactAndAllowWhileIdle`; nhắc kiểu báo thức (giờ phà, trả phòng) dùng `setAlarmClock`. Đặt lại sau khởi động máy, cập nhật app, đổi giờ. Nút *Xong*, *Đã biết*, *Hoãn 10 phút*.

**Cập nhật hai lớp:**

| Lớp | Cách |
|---|---|
| Giao diện | Tải gói zip, kiểm `sha256` và chữ ký ECDSA P-256 bằng khóa nhúng trong APK; áp dụng ở lần mở sau; không gọi `notifyWebReady` trong 10 giây thì tự quay lui |
| APK | Mở app và mỗi ngày kiểm một lần; luôn hỏi trước khi tải và cài (QĐ-18); kiểm chứng chỉ ký khớp; người dùng đã bấm *Cập nhật* thì không phải bấm lần hai |

Từ năm 2027 Android chặn cài app chưa đăng ký: mở tài khoản phân phối giới hạn trên Android Developer Console và đăng ký tên gói ở V1.5. Khóa ký APK RSA 4096 bit, hạn 30 năm, sinh trên máy cá nhân, cất hai bản ngoại tuyến; mất khóa là không cập nhật được.

**Bước riêng cho Galaxy S25+ (màn *Thiết lập máy*):**

1. Cho phép thông báo.
2. Bật đọc thông báo. App cài ngoài cửa hàng bị khóa xám: vào *Cài đặt > Ứng dụng > Trợ lý > menu ba chấm > Cho phép cài đặt bị hạn chế*, rồi bật lại.
3. Pin không hạn chế.
4. *Ứng dụng không bao giờ ngủ*: nút mở thẳng danh sách; không được thì đi tay *Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > Trợ lý > Thêm*. App không đọc được danh sách này nên người dùng bấm *Đã làm*.
5. Báo thức chính xác (chỉ khi thiếu).
6. Chọn app SMS mặc định.
7. Cài ứng dụng không rõ nguồn gốc: hỏi lần đầu có bản APK mới.

---

## 9. Giao diện

Nguồn: [31-giao-dien.md](../30-app/31-giao-dien.md).

**Phong cách:** giống app gym: nền tối, màu nhấn xanh chanh, thẻ bo tròn, icon lucide; React 19, Vite, Tailwind 4, shadcn, TanStack Query. Không emoji, không hộp thoại của trình duyệt.

**Thanh dưới 5 ô:** Trợ lý, Hộp tin (chấm số tin quan trọng chưa xem), Lịch, Chi tiêu, Thêm. Ô *Thêm* mở tấm trượt: Lịch trình, Báo cáo và thông số, Cài đặt.

**Các màn:**

| Màn | Điểm chính |
|---|---|
| Đăng nhập, đồng ý, khóa | Đăng nhập email và mật khẩu; màn đồng ý chỉ cho thành viên; khóa vân tay |
| Chat | Chữ chạy dần, nhãn *Đang ghi khoản chi*; nút hành động dưới câu trả lời; micro; tối đa 4 tệp; xóa phiên hôm nay |
| Hộp tin | Mỗi dòng là một cuộc trò chuyện; lọc theo app; tóm tắt; cảnh báo khi quá 24 giờ không có tin |
| Lịch và việc | Kiểu ngày, tuần, tháng; nguồn nhắc *App* hoặc *Google*; hộp sửa có khách mời đi qua thẻ duyệt |
| Chi tiêu | Ba thẻ tổng hôm nay, tuần, tháng; mục *Cần xem lại*; 4 số cuối tài khoản, không số dư; chuyển nội bộ chữ mờ |
| Lịch trình | Danh sách chuyến; chi tiết theo ngày, điểm cần xác nhận, rủi ro, nút dẫn đường, xem đường cả ngày từng đoạn, so sánh phương án, đưa vào lịch, xuất Word |
| Báo cáo | Thẻ chi tiêu, lịch tuần, hộp tin, chi phí AI so với mức 200 USD, thiết bị; mỗi thẻ lỗi riêng được |
| Cài đặt | Hồ sơ lõi, kết nối Google, app được nghe, người quan trọng, chi phí AI, kiểm tra máy, thiết bị, khóa và bảo mật, dữ liệu của tôi, máy chủ (chỉ chủ), phiên bản |

**Thẻ duyệt:** hiện đúng nội dung sẽ chạy (người nhận, nguyên văn, số dòng bị xóa), nút *Duyệt* và *Bỏ*, hạn 24 giờ; thẻ cần vân tay thì hỏi vân tay trước.

**Luồng chính:** lần đầu mở app; thiết lập máy; kết nối Google qua Custom Tab rồi quay về bằng `troly://cai-dat/google?ket-qua=`; duyệt hành động; mở bản đồ; cập nhật app.

**Mất mạng:** lưu đệm 7 ngày cho phiên chat hôm nay, 100 cuộc trò chuyện, lịch 14 ngày, chi tiêu tháng này, chuyến đã lên; mọi việc ghi cần mạng, trừ tin chat chờ gửi lại. Đăng xuất xóa hết.

---

## 10. Google

Nguồn: [40-tich-hop-google.md](../40-google/40-tich-hop-google.md).

| Dịch vụ | Dùng để | Chiều | Bản |
|---|---|---|---|
| Calendar | Lịch chính, sự kiện, mời khách qua thẻ duyệt | Hai chiều, Google làm gốc; webhook và quét 15 phút | V1.4 |
| Tasks | Việc không giờ, danh sách riêng *Trợ lý* | App làm gốc, đẩy lên; đọc ngược *xong*, *đã xóa* mỗi 15 phút | V1.4 |
| Maps (URL, lệnh Android) | Mở bản đồ, dẫn đường xe máy | Không cần khóa | V1.6 |
| Maps Platform | Tọa độ, giờ mở cửa, thời gian chạy | Gọi từ máy chủ | V1.6 |
| Gmail | Thư hộp *Chính* vào hộp tin, tìm, đọc chuỗi thư, soạn nháp; gửi qua thẻ duyệt | Đọc, ghi nháp; quét 5 phút | V1.8 |
| Contacts | Tên người gửi, người quan trọng, sinh nhật | Chỉ đọc, mỗi ngày | V1.8 |
| Drive | Lưu tệp xuất vào thư mục *Trợ lý* (quyền `drive.file`) | Ghi | V1.8 |
| Sheets | Bảng chi tiêu theo tháng | Chỉ ghi | V1.8 |
| Health Connect | Bước chân, giấc ngủ, nhịp tim (trên máy) | Chỉ đọc | V2 |

**Xin quyền theo gói:** `calendar`, `tasks`, `gmail` (scope hạn chế), `contacts`, `drive`; xin thêm dần, đọc lại quyền thật được cấp. Màn đồng ý để *In production* mà không xin xác minh: người dùng bấm qua cảnh báo *chưa xác minh*. Dự án chưa xác minh chỉ có tổng 100 người dùng mới trong cả đời, nên không thử bằng tài khoản rác. Chưa có văn bản Google xác nhận token ở trạng thái này không hết hạn: có bài thử 8 ngày và luồng nối lại một chạm.

**Nhắc trùng:** mỗi sự kiện một nguồn nhắc. Tạo ở app thì app nhắc và tắt nhắc của Google; tạo trên Google thì Google nhắc.

**Việc người dùng tự làm trên Google Cloud Console (một lần, trước V1.4):**

1. Tạo dự án `troly`, gắn tài khoản thanh toán (Maps bắt buộc).
2. Bật Calendar, Tasks, Gmail, People, Drive, Sheets, Places (New), Routes, Geocoding.
3. Màn đồng ý: tên *Trợ lý*, tên miền `baohuynh.io.vn`, trang chính sách riêng tư; *External*; thêm scope; ghi lại nhãn mức của từng scope; khi ổn thì *Publish app*.
4. Tạo client OAuth loại *Web application*, redirect `https://<api-domain>/api/v1/google/oauth/callback`; ghi `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` vào `.env` của VPS.
5. Trước V1.6: tạo khóa Maps giới hạn theo IP VPS và ba API.
6. Đặt quota mỗi ngày: Places 300, Compute Routes 30, Route Matrix 300 phần tử, Geocoding 300; ngân sách 1 USD có cảnh báo 50 và 100 phần trăm (ngân sách chỉ cảnh báo, quota mới chặn).

*(Còn lệch: cách lưu sự kiện lặp, trạng thái OAuth, biến redirect, xử lý việc bị xóa trên Google giữa 40 và 11, 12, 10. Đề xuất theo 11, 12, 10.)*

---

## 11. Lịch trình và bản đồ

Nguồn: [41-ban-do-lich-trinh.md](../40-google/41-ban-do-lich-trinh.md).

**Luồng:** nhập (Word, PDF, ảnh, link Maps, câu mô tả) → bóc tách bằng Claude theo một lược đồ → tìm địa điểm (link trong tệp trước, rồi đệm, rồi Places) → đánh giá → 2 tới 3 phương án → chọn → link bản đồ, xuất Word, đưa vào lịch. Nhập và đánh giá chạy nền.

**Tìm địa điểm cho rẻ:** Text Search chỉ xin `places.id` (miễn phí), rồi Place Details Essentials (10.000 miễn phí mỗi tháng); giờ mở cửa chỉ xin lúc đánh giá (Enterprise, 1.000 miễn phí). Không chắc thì đưa vào danh sách *Điểm cần xác nhận*. Theo điều khoản Google: giữ `place_id` mãi, tọa độ tối đa 30 ngày, không lưu giờ mở cửa.

**Thời gian chạy:** Routes API chế độ xe hai bánh (bản thử nghiệm, Việt Nam có hỗ trợ), tránh cao tốc, nhân hệ số 1,2; mỗi ngày 1 tới 2 lời gọi (1.000 miễn phí mỗi tháng). Giao diện và Word luôn có dòng *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.*

**Chín luật rủi ro chạy bằng mã:** R1 trễ giờ, R2 giờ mở cửa, R3 phà, R4 chạy liên tục quá 90 phút, R5 chạy đêm (18:00 tới 05:30, đỏ từ 03:00 tới 05:00), R6 tổng giờ chạy trong ngày, R7 nhận và trả phòng, R8 chưa định vị, R9 thứ không khớp ngày. AI chỉ viết câu tóm tắt, không đổi số.

**Ba phương án:** *Đúng giờ, ít rủi ro*; *Nhiều điểm*; *Nhàn*. Mỗi phương án có km, giờ chạy, giờ chạy đêm, số rủi ro đỏ và vàng.

**Bản đồ:** máy chủ dựng mọi link. Nút *Dẫn đường* mở `google.navigation` chế độ `l` (xe hai bánh), `avoid=h`. *Xem đường cả ngày* chia đoạn, tối đa 9 điểm dừng (3 khi máy không có Google Maps), link dưới 2.048 ký tự, ưu tiên cắt ở khách sạn, điểm nghỉ dài. Việt Nam có nhận chế độ xe máy hay không là bài thử đầu tiên trên máy thật.

**Xuất Word:** đúng kiểu tệp mẫu (Arial, màu tiêu đề `1F3864`, bảng giờ 2 cột), link bấm được; có thể lưu lên Drive.

**Xong khi (V1.6):** tệp *Lich-trinh-Phuoc-Hai-Tra-Vinh.docx* ra đủ 3 ngày; chỉ ra rủi ro Bảo tàng Văn hóa Khmer thứ Hai và giờ phà Vũng Tàu – Cần Giờ; bấm điểm là Maps mở chế độ xe máy. Chi phí Maps ước 0 USD.

---

## 12. Bảo mật và riêng tư

Nguồn: [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md).

| Chủ đề | Cách làm |
|---|---|
| Đăng nhập | Không đăng ký tự do; JWT 30 phút; mã làm mới 60 ngày xoay vòng; cắt ngay bằng đổi `JWT_SECRET` |
| Thiết bị | Mã thiết bị riêng, chỉ gọi nhóm `/device/*`; cất trong kho khóa Android; thu hồi được |
| Token Google | Mã hóa Fernet, vòng khóa có phiên bản, bản rõ gắn `user_id`; chỉ một chỗ giải mã |
| Bí mật | Chỉ ở `.env` (quyền 600) và GitHub Secrets; khóa giải mã sao lưu chỉ người dùng giữ; quét bí mật bằng `gitleaks` |
| OTP | Bỏ cả thông báo trên máy; máy chủ chạy lại bộ luật làm lưới |
| Tin người khác | Giữ 180 ngày; chỉ gửi Claude khi người dùng hỏi; mỗi tin cắt 500 ký tự, che số điện thoại; đánh dấu cuộc trò chuyện *riêng tư* để không bao giờ gửi Claude; công tắc tắt AI cho hộp tin |
| Chèn lệnh | Nội dung tin đi vào dạng dữ liệu không tin cậy; mọi việc ra ngoài phải bấm duyệt |
| Cô lập | Lọc `user_id` mọi nơi; dữ liệu người khác trả 404; RLS bật trước khi có người dùng thứ hai |
| Nhật ký | Không ghi nội dung tin, chat, token; che dãy 9 số trở lên; nhật ký kiểm toán giữ 365 ngày |
| App | Chỉ HTTPS; `allowBackup=false`; gói giao diện phải đúng chữ ký |

**Hành động phải duyệt (nguồn chuẩn 60 mục 3.12):**

| Hành động | Duyệt | Vân tay |
|---|---|---|
| Xóa một dòng qua trợ lý | Có | Không |
| Xóa nhiều dòng, xóa chuyến, xóa tệp | Có | Có |
| Gửi thư Gmail | Có (soạn nháp thì không) | Có |
| Gửi lời mời, sửa sự kiện có khách | Có | Có |
| Chia sẻ tệp Drive | Có | Có |
| Trả lời tin qua thông báo (V2) | Có | Có |
| Xuất ra Drive, Sheets của chính mình; đổi phương án lịch trình | Không | Không |
| Đổi app được nghe, tạo tài khoản | Chỉ làm tay | |
| Gộp mã và deploy (V3) | Có | Có |

*(Còn lệch: 20, 11, 31 chưa theo đúng cột vân tay khi xóa.)*

**Luật Việt Nam:** đã đối chiếu Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP. Lịch sử giao dịch ngân hàng là dữ liệu nhạy cảm. Gửi dữ liệu cho Claude, Google, R2 là chuyển ra nước ngoài. Cách làm: thu nhỏ dữ liệu, giữ ngắn, có quyền xuất và xóa, đồng ý của thành viên, quy trình sự cố có mốc 72 giờ. Có cần lập hồ sơ đánh giá tác động cho app cá nhân không thì hỏi luật sư trước khi có người dùng thứ hai.

---

## 13. Kiểm thử

Nguồn: [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md).

| Tầng | Công cụ | Chạy |
|---|---|---|
| Backend | pytest trên PostgreSQL 16 thật trong Docker, mỗi bài rollback | Máy và CI, cùng một lệnh |
| Chéo người dùng | Tự quét mọi đường dẫn và mọi công cụ AI | Máy và CI |
| Giao diện | Vitest, Testing Library, MSW | Máy và CI |
| Kotlin | JUnit trên JVM; máy ảo khi sửa phần gốc hoặc đăng bản | CI |
| AI | `FakeClaude` trong CI; bộ câu mẫu gọi Claude thật chạy tay | |
| Máy thật | Danh sách thử tay trên Galaxy S25+ mỗi bản APK | Tay |
| Hạ tầng | `docker compose config`, deploy chạy thử, sao lưu với S3 giả, diễn tập khôi phục | CI và tay |

**Bộ mẫu dùng chung (`testdata/` ở gốc kho):** thông báo ngân hàng đã che số (người dùng gom 5 tới 10 mẫu thật mỗi bên); mẫu OTP cho cả Samsung Messages và Google Messages; mẫu câu chat chi tiêu; hợp đồng API thiết bị. Kotlin và Python đọc cùng tệp OTP, phải cho cùng kết quả. Mẫu cần chặn phải chặn 100 phần trăm; chặn nhầm chỉ đo, ngưỡng 10 phần trăm.

**Google giả** trong bộ nhớ cho mọi bài kiểm thường; kiểm với Google thật chỉ chạy tay bằng tài khoản thử. Sàn độ phủ 90 phần trăm nhánh cho phần dễ sai: bóc tách ngân hàng, lọc OTP, tổng chi tiêu, ghép cặp chuyển tiền, giờ nhắc. Ở máy chỉ chạy bài kiểm phần vừa sửa; CI chạy đủ; deploy từ chối commit chưa xanh.

---

## 14. Lộ trình

Nguồn: [00-ke-hoach.md](00-ke-hoach.md) mục 3.

| Bản | Nội dung | Xong khi |
|---|---|---|
| A. Tài liệu | Kế hoạch, thiết kế, tài liệu từng mảng | Đủ tệp, đã rà chéo, người dùng duyệt |
| V1.0 | Backend nền (core, ai, memory, chat), vỏ app có màn Chat, CI build APK | Cài APK, đăng nhập, chat được, hồ sơ lõi được nạp |
| V1.1 | Chi tiêu qua chat | Nhắn *cơm trưa 45k* là ghi đúng; hỏi tổng tháng trả đúng |
| V1.2 | Plugin nghe thông báo, chi tiêu từ Vietcombank, Techcombank, MoMo | Giao dịch thật tự thành một dòng; chuyển sang MoMo không tính hai lần |
| V1.3 | Hộp tin từ thông báo, tổng hợp | Hỏi *hôm nay có tin gì quan trọng* trả đúng, không lộ OTP |
| V1.4 | Lịch, việc, nhắc trên máy, Google Calendar, Google Tasks, mời khách | Thêm lịch trong app thấy trên Google Calendar và ngược lại |
| V1.5 | Tự cập nhật app | Đăng bản mới thì app báo và cài được |
| V1.6 | Lịch trình và bản đồ | Tệp Phước Hải – Trà Vinh ra đủ 3 ngày, chỉ ra rủi ro, bấm điểm là Maps mở chế độ xe máy |
| V1.7 | Báo cáo, thông số, cài đặt đầy đủ | Bảng điều khiển hiện đủ các số |
| V1.8 | Gmail, Contacts, Drive, Sheets | Thư quan trọng vào hộp tin; xuất chi tiêu ra Sheets |
| V2 | Trả lời tin qua thông báo (có duyệt), máy chủ MCP, module gym, Health Connect | Chưa đặt |
| V3 | Tự phát triển bằng Claude CLI, có cửa duyệt | Chưa đặt |

---

## 15. Rủi ro chính

| Rủi ro | Mức | Cách giảm | Nguồn |
|---|---|---|---|
| Từ 2027 Android chặn cài và cập nhật app chưa đăng ký | Cao | Tài khoản phân phối giới hạn, đăng ký ở V1.5; đường lùi `adb` | 30 |
| One UI cho app ngủ: báo thức, việc nền bị chặn | Cao | Bước *Ứng dụng không bao giờ ngủ*; cảnh báo khi im lặng quá 24 giờ | 30 |
| Chiếm VPS qua app chạy chung | Cao | Container không root, DB mạng kín, token mã hóa, khóa sao lưu không trên VPS | 60 |
| Ổ 22 GB đầy vì ảnh Docker | Cao | Giữ 3 thẻ ảnh, dọn bộ đệm 3 ngày, `disk_check` | 50 |
| Dừng nhầm `cloudflared` khi tạm tắt Gamebar | Cao | Chỉ `docker stop core-game`, kiểm gym ngay sau | 50 |
| Mất khóa ký APK | Cao | Hai bản cất ngoại tuyến | 30, 60 |
| Không có lịch phà | Cao | Luật R3 luôn nhắc gọi hotline | 41 |
| Health Connect không cấp quyền cho APK ngoài Play | Cao (V2) | Thử trên máy thật trước khi thiết kế V2 | 40 |
| Lộ OTP vì mẫu tin mới của ngân hàng | Trung bình | Lọc hai lớp, bộ đếm máy chủ, cập nhật bộ mẫu | 60 |
| Token Google vẫn hết hạn ở *In production* chưa xác minh | Trung bình | Bài thử 8 ngày, nối lại một chạm | 40 |
| Không trần AI theo ngày, lỗi lặp đốt tiền | Trung bình | Giới hạn vòng và lượt, cảnh báo tháng, hạn mức chi trên trang Anthropic | 10, 20 |
| Cache hỏng âm thầm làm tiền AI tăng | Trung bình | Bài kiểm cache, cảnh báo khi không đọc được cache | 20 |
| Google Maps ở Việt Nam bỏ qua chế độ xe máy | Trung bình | Link luôn kèm tránh cao tốc; thử đầu V1.6 | 41 |
| Mất tới 7 ngày dữ liệu khi hỏng DB | Trung bình | Sao lưu tay trước việc lớn, sao lưu trước migration | 50 |
| Tài liệu còn 43 chỗ vênh (5 nặng) | Trung bình | Sửa theo `81-ra-cheo-lan-2.md` trước khi viết mã V1.0 | 81 |

---

## 16. Việc người dùng cần chuẩn bị

| Khi | Việc |
|---|---|
| **Trước V1.0** | Chọn tên miền con cho api |
| | Chạy trên VPS và gửi kết quả: `ss -ltn` (cổng 8200), `docker stats --no-stream`, `df -h /` |
| | Xác nhận thời điểm tạm dừng `core-game`; chọn có sao lưu Gamebar ngay không; chọn điều kiện mở lại |
| | Thêm Public Hostname trên Cloudflare trỏ `http://localhost:8200`; tắt kiểm trình duyệt cho đường webhook và callback Google |
| | Tạo khóa API Anthropic cho bộ não, một khóa riêng cho đánh giá; đặt hạn mức chi trên trang Anthropic |
| | Tạo ba bucket R2 và mã truy cập (mã của app cho `troly-files`, `troly-backup`; mã của CI chỉ cho `troly-release`) |
| | Tạo cặp khóa `age`; cất khóa bí mật và bản `.env` (nhất là `TOKEN_ENCRYPTION_KEYS`) trong trình quản lý mật khẩu |
| | Sinh khóa ký APK (30 năm) và khóa ký gói giao diện; dán vào GitHub Secrets; cất hai bản ngoại tuyến |
| | Đặt các secret GitHub theo 50 mục 3.8 |
| | Sau deploy: tạo tài khoản chủ, đổi mật khẩu tạm; cài APK từ trang `/tai-app`; làm diễn tập khôi phục sau bản sao lưu đầu |
| **Trước V1.2** | Gom 5 tới 10 thông báo thật mỗi bên Vietcombank, Techcombank, MoMo (gồm cặp chuyển sang MoMo) để làm bộ mẫu đã che |
| | Làm đủ bước *Thiết lập máy* trên S25+, gồm *Ứng dụng không bao giờ ngủ* |
| | Chọn có dựng ảnh Android SDK trên máy không (cần khoảng 10 GB ổ) |
| **Trước V1.3** | Đánh dấu các cuộc trò chuyện riêng tư nếu có; chọn người quan trọng, từ khóa gấp |
| **Trước V1.4** | Làm các bước Google Cloud Console ở mục 10 (dự án, thanh toán, API, màn đồng ý, client OAuth) |
| | Chuẩn bị một tài khoản Google thử riêng |
| | Sau khi chạy ổn: *Publish app* sang *In production* |
| **Trước V1.5** | Tài khoản Google cho Android Developer Console: bật xác minh hai bước, có hồ sơ thanh toán; mở tài khoản phân phối giới hạn; đăng ký tên gói và chứng chỉ ký |
| **Trước V1.6** | Tạo khóa Google Maps, đặt quota mỗi ngày và ngân sách cảnh báo |
| | Gửi tệp lịch trình mẫu; nhập bảng giờ phà quen nếu muốn |
| **Trước V1.8** | Nối thêm gói Gmail, Contacts, Drive khi có bản; chọn hộp Gmail sẽ lấy |
| **Trước V2** | Hỏi luật sư về hồ sơ đánh giá tác động nếu sắp thêm người dùng thứ hai; thử Health Connect trên máy thật |
| **Trước V3** | Chọn nơi chạy Claude CLI; tạo khóa deploy SSH chỉ cho kho `troly`; bật bảo vệ nhánh `main` |

---

## 17. Câu hỏi còn chờ Gia Bảo

Lấy từ [81-ra-cheo-lan-2.md](../80-ra-soat/81-ra-cheo-lan-2.md) mục C1. Cột cuối là đề xuất; đồng ý thì chỉ cần trả lời *theo đề xuất*.

| # | Câu | Đề xuất |
|---|---|---|
| 1 | Tên miền con cho api | `troly.baohuynh.io.vn` |
| 2 | Mã làm mới 60 ngày, mã truy cập 30 phút | Giữ |
| 3 | Đăng nhập bằng Google thay mật khẩu | Không |
| 4 | Lịch sử chat giữ 365 ngày rồi xóa, giữ tóm tắt | Đồng ý |
| 5 | Tách nhiều thẻ, nhiều tài khoản cùng ngân hàng | Chưa |
| 6 | *Nghĩ kỹ* chuyển sang Sonnet 5.5 | Chưa |
| 7 | Lời chào lần đầu | Câu cố định |
| 8 | Khóa API tạo trước hay sau 31/08/2026 | Chỉ để biết |
| 9 | Khóa vân tay sau bao lâu ở nền | 5 phút |
| 10 | Tài khoản Android Developer Console có xác minh hai bước, hồ sơ thanh toán | Chuẩn bị trước V1.5 |
| 11 | Nhận giọng nói bằng dịch vụ Google | Đồng ý |
| 12 | App SMS mặc định, bản Android, One UI | Chỉ để biết |
| 13 | Nền sáng | Chỉ nền tối ở V1 |
| 14 | Đọc to câu trả lời mặc định | Tắt |
| 15 | Thông báo khi ghi giao dịch lúc app đóng | Không |
| 16 | Đồng bộ lịch phụ | Chỉ lịch chính |
| 17 | Ai nhắc sự kiện tạo trên Google | Google |
| 18 | Trả lời lời mời người khác | V2 |
| 19 | Việc tự thêm vào danh sách *Trợ lý* trên Google Tasks | Bỏ qua ở V1.4 |
| 20 | Dùng *Danh bạ khác* | Không |
| 21 | Gmail chỉ *Chính* hay thêm *Cập nhật* | Chỉ *Chính* |
| 22 | Nối tài khoản Workspace | Chỉ tài khoản cá nhân |
| 23 | Đọc nhãn mức scope trên Console | Làm ở V1.4 |
| 24 | Tài khoản Google thử riêng | Có |
| 25 | Ngày đi mặc định của lịch trình | Gợi ý thứ Bảy gần nhất, bấm xác nhận |
| 26 | Khung chạy đêm 18:00 tới 05:30, đỏ 03:00 tới 05:00 | Giữ |
| 27 | Thời tiết, triều cường ở V1.6 | Chưa |
| 28 | Bảng giờ phà tĩnh | Có |
| 29 | Xuất PDF | Chưa |
| 30 | Kiểm cổng, RAM, ổ trên VPS | Người dùng chạy ba lệnh |
| 31 | Sao lưu Gamebar trước khi dừng; điều kiện mở lại | Sao lưu ngay; mở lại khi RAM còn dư hơn 600 MB |
| 32 | Kiểm sức khỏe api từ ngoài | Workflow 2 giờ một lần |
| 33 | Claude CLI V3 chạy ở đâu | Container trên VPS, chốt khi tới V3 |
| 34 | Khóa giữ bucket sao lưu | Chưa |
| 35 | Ảnh Android SDK trên máy từ V1.2 | Có, nếu ổ đủ |
| 36 | Trang `/tai-app` | Công khai |
| 37 | Sao lưu chung cho gym | Để sau |
| 38 | Hồ sơ đánh giá tác động | Hỏi luật sư trước người dùng thứ hai |
| 39 | Xác thực hai lớp cho chủ | V2 |
| 40 | Người dùng thứ hai nghe ngân hàng, tin nhắn | Để khi có người thứ hai |
| 41 | Danh sách cần vân tay | Theo 60 mục 3.12 |
| 42 | Ai gõ và che bộ mẫu ngân hàng | Người dùng gửi ảnh, agent gõ và che, người dùng duyệt |
| 43 | Ngưỡng chặn nhầm OTP 10 phần trăm | Chấp nhận |
| 44 | `DEV_JOB_DAILY_USD = 5` cho V3 có coi là ngoại lệ QĐ-15 | Giữ, ghi QĐ mới khi tới V3 |

Ngoài các câu trên, 25 việc kỹ thuật (sự kiện lặp, trạng thái OAuth, vỏ hành động, tên cột lịch trình...) đã có đề xuất chốt ở `81-ra-cheo-lan-2.md` mục C2; điều phối ghi thành QĐ-26 nếu Gia Bảo đồng ý.
