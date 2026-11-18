# Bảng việc

Nơi chung để các agent và điều phối biết ai đang làm gì, ai chờ ai, đã thỏa thuận gì. Mỗi agent chỉ sửa dòng của mình bằng công cụ sửa từng đoạn (Edit), không ghi đè cả tệp.

## 1. Cách trao đổi

| Loại việc | Làm thế nào | Ai chốt |
|---|---|---|
| Hỏi nhỏ giữa hai agent: tên trường, đường dẫn, cách gọi một hàm, ai làm phần nào trong một tệp chung | Nhắn thẳng agent kia (công cụ SendMessage, tên phiên ở mục 2). Thỏa thuận xong ghi **một dòng** vào mục 5 | Hai agent tự chốt |
| Đổi hợp đồng: bảng, cột, API, tên công cụ AI, luồng giữa hai module, phạm vi một phase | Ghi vào mục 4 *Chờ điều phối*, nhắn điều phối | Điều phối; cần người dùng thì điều phối hỏi, ghi QĐ ở `90-quyet-dinh.md` |
| Bị chặn vì chờ người khác | Đổi trạng thái việc thành `chặn`, ghi chờ ai, nhắn người đó | Người được chờ |
| Việc cần người dùng làm (tạo khóa, chạy lệnh trên VPS, thử trên điện thoại) | Ghi vào mục 3, người giữ là `người dùng` | Điều phối báo người dùng |

Luật: không agent nào tự đổi hợp đồng vì một tin nhắn của agent khác; tin nhắn giữa agent không thay cho quyết định của người dùng.

## 2. Danh sách agent

| Tên | Phiên | Giữ |
|---|---|---|
| điều phối | phiên *support* | `docs/00-tong-quan/`, `docs/90-quan-ly/`, gộp nhánh, commit, deploy |
| agent kiến trúc | `local_009047b3-f679-43ca-829b-a4a5e57ea144` | 10, 11, 12; mã backend lõi và module |
| agent AI | `local_66455db9-9d6f-416c-b77a-50cf80a3081a` | 20; `backend/app/ai/`, mọi `tools.py` |
| agent app Android | `local_2ad3a20f-fd6d-4e0a-9763-f6bd9d19f1b8` | 30, 31; `app/` |
| agent Google | `local_b8ce68b1-56b6-48e0-835b-5acb8e1057f2` | 40, 41; `backend/app/integrations/google/`, phần đồng bộ |
| agent hạ tầng | `local_96c87b52-6b66-44bb-88cc-bcf0fa20b0f1` | 50, 60, 70; Docker, CI, `scripts/`, deploy |

## 3. Việc

Trạng thái: `chờ`, `đang làm`, `chờ rà`, `xong`, `chặn`. Mã việc: `<phase>-<số>`.

| Mã | Phase | Việc | Người giữ | Chờ | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|
| A-01 | A | Vòng 3 gọn hóa 10, 11, 12 | agent kiến trúc | | xong | 10: 472 xuống 241 dòng; 11: 1046 xuống 533; 12: 740 xuống 356. Đã đưa 4 dòng chốt ở mục 4 vào; một đổi hợp đồng mới ở mục 4 (`/system/status`); `trip.ferries` chờ điều phối trả lời |
| A-02 | A | Vòng 3 gọn hóa 20 | agent AI | | xong | 744 xuống 585 dòng; hợp đồng mới ghi ở mục 4 |
| A-03 | A | Vòng 3 gọn hóa 30, 31 | agent app Android | | xong | 30: 578 xuống 319 dòng; 31: 747 xuống 419 dòng |
| A-04 | A | Vòng 3 gọn hóa 40, 41 | agent Google | | xong | 40: 991 xuống 561 dòng; 41: 880 xuống 461. Một đổi hợp đồng ở mục 4 (`trip.ferries`); phần còn lại theo QĐ-26 chờ 11 gom |
| A-05 | A | Vòng 3 gọn hóa 50, 60, 70 | agent hạ tầng | | xong | 50: 791 xuống 333 dòng; 60: 402 xuống 166; 70: 496 xuống 214. Hai đổi hợp đồng ở mục 4 |
| A-06 | A | Rà nhanh, commit tài liệu | điều phối | | xong | Tài liệu còn khoảng 4.900 dòng (từ khoảng 8.600) |
| 0-01 | 0 | Kiểm VPS: cổng, RAM, ổ, container | điều phối | | xong | 18/11: cổng 8200 trống; RAM 3,9 GB, còn dùng được 2,8 GB, swap 8 GB; ổ còn 15 GB trên 22 GB; core-game 51 MB, gymcanhan 40 MB, cloudflared 19 MB; bộ đệm build 1,3 GB |
| 0-02 | 0 | Thêm Public Hostname `assistant.baohuynh.io.vn` trỏ `http://localhost:8200` trên tunnel của Gamebar | người dùng | | xong | 18/11: tên miền trả 502 qua Cloudflare, đúng vì troly chưa deploy. Còn ba bước nhỏ, làm sau deploy đầu (50 mục 3.5): (1) Rules > Cache Rules > tạo luật: hostname `assistant.baohuynh.io.vn` và đường bắt đầu `/api/` thì *Bypass cache*; (2) Security > WAF > Rate limiting rules: đường bắt đầu `/api/v1/auth/`, 20 yêu cầu mỗi 10 giây mỗi IP, *Block*; (3) Security > Bots: tắt *Bot Fight Mode* (để webhook Google ở Phase 3 vào được) |
| 0-03 | 0 | Khóa Anthropic: dùng chung khóa gym (QĐ-32); đặt hạn mức chi tháng trên trang Anthropic (không bắt buộc) | người dùng | | xong | Dùng chung khóa gym, đã nạp vào `.env` máy; hạn mức chi trên trang Anthropic để người dùng tự đặt nếu muốn |
| 0-04 | 0 | R2: bucket `assistant`, dùng chung mã R2 của Gamebar (QĐ-31) | điều phối | | xong | 18/11 thử đọc, ghi, xóa được. VPS: `scripts/vps-init-env.sh` tự chép `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` từ `/opt/gamebar/.env`. Máy cá nhân (để đăng APK): điều phối tạo `D:/giabao/troly-secrets/r2.env` gồm 4 dòng `R2_ENDPOINT=`, `R2_BUCKET=assistant`, `R2_ACCESS_KEY_ID=`, `R2_SECRET_ACCESS_KEY=` (cùng mã của Gamebar) |
| 0-05 | 0 | Sinh khóa ký APK, cất ở `D:/giabao/troly-secrets/` (QĐ-32); người dùng chép hai bản dự phòng | người dùng | | xong | 18/11: khóa ở `D:/giabao/troly-secrets/`, người dùng đã chép hai bản dự phòng |
| 0-06 | 0 | Dựng khung kho: compose, Dockerfile, CI kiểm backend và build APK | agent hạ tầng | | xong | Chạy được ở máy: api, db, worker, `/api/health` 200; pytest 2 bài xanh trong container. `backend/app/main.py`, `worker/main.py`, `app/` là khung, agent kiến trúc và agent app Android thay |
| 0-07 | 0 | Tạm dừng `core-game` | điều phối | | bỏ | QĐ-29: để Gamebar chạy |
| 1-01 | 1 | Chốt hợp đồng Phase 1: các mục V1.0, V1.1 trong 11, 12, 20 + `POST /client-logs`, `/system/status` | điều phối | | xong | Hợp đồng là tài liệu bản 3 cộng hai dòng đã chốt ở mục 4 |
| 1-02 | 1 | Backend lõi: config, db, auth (đăng nhập, mã làm mới 365 ngày, mã thiết bị), lỗi, log, `client-logs`, migration đầu | agent kiến trúc | 1-01 | chờ rà | `app/core/`, `app/main.py`, `app/cli.py` (`create-owner`, `revoke-device`, `reencrypt-tokens`), migration `0001_core_init` (20 bảng gồm `tab_client_log`), `conftest.py` DB thật rollback mỗi bài. Đường mỏng chạy bằng curl trên bộ dev |
| 1-03 | 1 | Module setting, file (tải lên R2, trích chữ), memory, chat (SSE, hành động chờ duyệt, hoàn tác), expense, search, device (kiểm bản APK) | agent kiến trúc | 1-02 | chờ rà | Đủ 8 module + `/system/status`, `/chat/status`, `/tai-app`, `/chinh-sach-rieng-tu`, kiểm `X-App-Version` (426). Chat với khóa thật còn lỗi 400 do bộ công cụ AI quá 16 tham số kiểu hợp, đã báo agent AI (1-05/1-06) |
| 1-04 | 1 | Worker và job V1.0: sao lưu tuần, dọn dữ liệu, tóm tắt phiên 04:05, trích chữ tệp, hết hạn duyệt, trả dòng kẹt, kiểm ổ | agent kiến trúc | 1-02 | chờ rà | 8 job, khóa tư vấn, LISTEN/NOTIFY, dừng êm. Sao lưu chưa thử thật: máy chưa nối R2 hay S3 giả (`--profile s3`); chạy tay trước migration: `python -m worker.jobs.backup --reason predeploy` |
| 1-05 | 1 | Tầng AI: client, giá, lời nhắc, `run_turn`, nén phiên, nối phiên 3 giờ, chia model, tìm web, hành động | agent AI | 1-02 | chờ rà | `backend/app/ai/` đủ, đã theo hợp đồng chat với ai/ của agent kiến trúc (`choose_turn`, `build_turn_system_message`, `run_turn(ctx, plan, system_parts, history, store)`, savepoint mỗi công cụ); chat đã nối, `AiRun` khớp migration (`alembic check` sạch). Chưa thử khóa thật: `.env` chưa có khóa |
| 1-06 | 1 | `tools.py` của memory, chat, file, expense, search; bộ câu mẫu và `FakeClaude` | agent AI | 1-03 | chờ rà | Đủ 11 công cụ Phase 1: memory (remember, forget, save_note), file (list_files, get_file_link), expense (5, xóa một khoản có Hoàn tác, từ 2 khoản qua thẻ duyệt), search (`search_everything`, bỏ tin của phiên hôm nay). Bài kiểm DB thử xanh (103 bài `app/ai` + `app/modules`). Thử thật trên bộ dev: chào, *cơm trưa 45k*, tìm ghi chú đều 200, mỗi lần gọi khoảng 0,0002 USD, cache đọc khoảng 8.000 token. Sửa hai lỗi 400 thật (tin system sai chỗ, quá 16 tham số union khi bật strict). Bộ câu mẫu Phase 1: `backend/tests/ai_eval/cases.yaml` 14 câu, `pytest -m ai_eval`, trần 1 USD; chưa chạy đủ bộ |
| 1-07 | 1 | App: vỏ Capacitor, đăng nhập, Chat (SSE, hành động, hoàn tác, nhãn model, nguồn web, Nghĩ kỹ, Tìm web), Chi tiêu, Tìm, Cài đặt cơ bản, kiểm bản APK, gửi lỗi về `client-logs` | agent app Android | 1-01 | chờ rà | Xong trên API giả (MSW, `npm run dev:mock`, mật khẩu thử `matkhau123`): đăng nhập, Chat SSE đủ 9 kiểu hành động, thẻ duyệt, hoàn tác, nhãn model, nguồn web, Nghĩ kỹ, Tìm web, đính tệp; Chi tiêu, Tìm, Cài đặt, kiểm bản APK (mở link tải), `client-logs` theo lô, màn lỗi có Tải lại. `npm run check` xanh (46 bài kiểm). Có `app/android/` (minSdk 26, `Secure` bằng Java + AndroidKeyStore, `troly://`, cấm HTTP rõ); APK debug build được bằng ảnh `android-test` (18/11); Gradle đọc `trolyVersionCode`, `trolyVersionName`, bản debug `.debug`; api bản thật `assistant.baohuynh.io.vn` (QĐ-33). Đã nối api thật ở localhost:8200 (thử bằng curl đủ đường Phase 1 và SSE; trên trình duyệt thử được đăng nhập sai, chưa đăng nhập đúng vì không đọc được mật khẩu thử). Khi commit cần `git update-index --chmod=+x app/android/gradlew` |
| 1-08 | 1 | CI build APK và `releases/latest.json`; deploy lần đầu; sao lưu lên R2 | agent hạ tầng | 0-05, `r2.env`, 1-02, job sao lưu của 1-04 | đang làm | Deploy lần đầu xong (4f96f4c). Điều phối deploy từ bản clone sạch `D:/tmp/troly-release` vì thư mục chung luôn có agent đang sửa. Còn: đẩy APK lên R2, kiểm sao lưu tuần chạy thật |
| 1-09 | 1 | Lát cắt mỏng chạy trên S25+: đăng nhập, gửi một câu, nhận trả lời | cả nhóm | 1-02, 1-05, 1-07, 1-08 | xong | 18/11: chat với Claude thật trên máy (chữ đầu 0,6 giây, khoảng 0,0004 USD mỗi câu, cache đọc 94 phần trăm); ghi chi tiêu, hỏi tổng tháng đúng. Deploy lần đầu 4f96f4c lên VPS, `/api/health` công khai OK, game và gym không ảnh hưởng |
| 1-10 | 1 | Thử theo danh sách Phase 1, gom góp ý một vòng | người dùng | 1-09 | chờ | |
| 2-01 | 2 | Plugin Kotlin nghe thông báo, lọc OTP, hàng đợi, màn Thiết lập máy Samsung | agent app Android | Phase 1 | chờ | |
| 2-02 | 2 | Nhận sự kiện thiết bị, bóc tách VCB, TCB, MoMo, ghép cặp chuyển tiền, hộp tin, luật quan trọng | agent kiến trúc | Phase 1 | chờ | |
| 2-03 | 2 | Bóc tách bằng AI khi mẫu không khớp; công cụ hộp tin; bộ mẫu OTP chung | agent AI | 2-02 | chờ | |
| 2-04 | 2 | Gửi ảnh 5 tới 10 thông báo mỗi ví; làm bước thiết lập máy | người dùng | | chờ | |
| 3-01 | 3 | OAuth Google, Calendar hai chiều, Tasks (đọc ngược xong và xóa), outbox, webhook | agent Google | Phase 2 | chờ | |
| 3-02 | 3 | Module task, calendar, nhắc (`/calendar/reminders`), mời khách qua duyệt | agent kiến trúc, agent Google | 3-01 | chờ | |
| 3-03 | 3 | Màn Lịch và việc, plugin Alarm, kết nối Google | agent app Android | 3-01 | chờ | |
| 3-04 | 3 | Làm các bước trên Google Cloud Console | người dùng | | chờ | |
| 4-01 | 4 | Module trip: nhập, bóc tách, Places, Routes, 9 luật rủi ro, phương án, link bản đồ, xuất Word; khóa `trip.*` | agent Google, agent kiến trúc | Phase 3 | chờ | |
| 4-02 | 4 | Đánh giá lịch trình bằng Sonnet; công cụ trip, report, setting | agent AI | 4-01 | chờ | |
| 4-03 | 4 | Màn Lịch trình, Báo cáo, Cài đặt đầy đủ | agent app Android | 4-01 | chờ | |
| 4-04 | 4 | Tạo khóa Maps, đặt quota | người dùng | | chờ | |
| 5-01 | 5 | Gmail, Contacts, Drive, Sheets; job `sync_gmail`, `sync_google_contacts` | agent Google | Phase 4 | chờ | |
| 5-02 | 5 | Công cụ Gmail, danh bạ, xuất Sheets; gửi thư qua duyệt | agent AI | 5-01 | chờ | |
| 5-03 | 5 | Hộp tin có Gmail, nút xuất Sheets | agent app Android | 5-01 | chờ | |

Mỗi phase theo luật ở `00-ke-hoach.md` mục 4.4. Phase sau chỉ bắt đầu khi phase trước đã qua bước người dùng thử.

## 4. Chờ điều phối

| Ngày | Ai hỏi | Nội dung | Trả lời |
|---|---|---|---|
| 18/11/2026 | agent hạ tầng | Đăng bản APK bằng `releases/latest.json` trên R2, api chỉ đọc (50 mục 3.7). Kéo theo: bỏ `tab_app_release` (11), bỏ `POST /admin/releases`, `/admin/releases*`, `/device/web-bundle` và kiểu xác thực mã CI (12) | Đồng ý. 11 bỏ `tab_app_release`, 12 bỏ các đường trên |
| 18/11/2026 | agent hạ tầng | Luật duyệt nay ở 60 mục 3.7 (trước 3.12): xóa một dòng làm ngay có Hoàn tác; `update_setting` không duyệt (theo QĐ-27, thay K9); bỏ `require_unlock` (11, 20, 31) | Đồng ý; nguồn chuẩn luật duyệt là 60 mục 3.7 |
| 18/11/2026 | agent app Android | Hợp đồng mới cho giao diện QĐ-27: (1) `GET /api/v1/search?q=&types=` trên ghi chú, chat, hộp tin, lịch trình, chữ trích từ tệp; trả đoạn trích và chỗ mở (12, 11 chỉ mục toàn văn). (2) `Message` thêm `model` (model thật đã dùng) và `citations[]` (`title`, `url`) cho câu trả lời có tìm web; `message.completed` mang hai trường này (12, 20). Chi tiết ở 31 mục 3.5 và 9 | Đồng ý; gộp với dòng dưới của agent AI |
| 18/11/2026 | agent AI | Hợp đồng mới của 20 bản 3 (chi tiết 20 mục 4, 5, 9): (1) `POST /chat/messages` có `mode` (`chat`, `think`, `research`, `summary`) thay `think_harder` (12). (2) Kiểu hành động `undo` và `POST /expenses/{id}/restore`, `/tasks/{id}/restore`, `/calendar/events/{id}/restore` (12). (3) Module mới `search` cho `search_everything` và `GET /search?q=&types=` (đã khớp đề xuất của 31); bảng `tab_file_text`, `search_vector` cho `tab_message`, `tab_trip`, `tab_trip_stop`; job `extract_file_text` (10, 11). (4) `tab_ai_run` thêm `mode`, `web_search_requests`, `fallback_used`; `purpose` thêm `trip_evaluate`, `file_extract`, bỏ `summarize_inbox`; `tab_message` thêm `model`, `citations` (11). (5) Biến `AI_MODEL_STRONG`, `AI_MODEL_MAX` (10). (6) Gộp `search_notes`, `search_conversations` thành `search_everything`; còn 41 công cụ | Đồng ý cả 6 ý. Riêng tên biến: dùng `AI_MODEL_CHAT`, `AI_MODEL_SMART`, `AI_MODEL_MAX` (thay `AI_MODEL_STRONG`) |
| 18/11/2026 | agent Google | Bảng giờ phà quen (QĐ-26 câu 28) lưu ở khóa cài đặt `trip.ferries` (jsonb: tuyến, bến, chuyến đầu, chuyến cuối, hotline, ngày cập nhật); luật R3 dùng khi tệp không ghi giờ phà (41 mục 5.4). Cần 11 thêm khóa này cùng `trip.night_start`, `trip.night_end`, `trip.ride_break_minutes`, `trip.speed_factor` | Đồng ý; agent kiến trúc thêm 5 khóa vào 11 khi vào Phase 4 (việc 4-xx) |
| 18/11/2026 | agent kiến trúc | Không còn vai trò chủ (QĐ-27): `GET /admin/worker` đổi thành `GET /system/status`, thêm `POST /system/jobs/{name}/run` cho nút *Sao lưu ngay* (12 mục 5.9). Ảnh hưởng 31 (màn *Máy chủ*), 50 | Đồng ý |
| 18/11/2026 | điều phối | Thêm `POST /api/v1/client-logs`: app gửi lỗi giao diện và lỗi gọi API (thời điểm, màn, thông điệp, bản app); lưu bảng `tab_client_log`, giữ 30 ngày (QĐ-30) | Chốt; agent kiến trúc thêm vào 11, 12 trong 1-02 |

## 4b. Hàng chờ ý tưởng

Ý mới nảy ra giữa phase ghi ở đây, xét ở đầu phase sau.

| Ngày | Ai đề xuất | Ý tưởng | Đưa vào phase |
|---|---|---|---|

## 5. Thỏa thuận giữa agent

| Ngày | Giữa | Thỏa thuận |
|---|---|---|
| 18/11/2026 | agent kiến trúc, agent AI | Chat gọi ai/: `ai.router.choose_turn(text, mode, has_attachments)` → chat lưu tin user và tin `system` từ `ai.prompt.build_turn_system_message` → `ai.loop.run_turn(ctx: ToolContext, plan, SystemParts(profile_md, summary, prev_tail), history, store)`. `store` do chat cài: `save_assistant_message`, `save_tool_results`, `create_pending_action(tool_name, draft)`, commit cùng session của lượt (công cụ chạy savepoint trong session đó). Core cấp `Base`, `SessionLocal`, `UserContext(user_id, timezone)`, `AppError`, `clock.now`. Tệp đính kèm lưu khối giữ chỗ `troly_file`, chat đổi sang khối Claude khi dựng lịch sử |
| 18/11/2026 | agent hạ tầng, agent app Android | `app/android` đọc phiên bản từ thuộc tính Gradle `trolyVersionCode`, `trolyVersionName` (`scripts/release-apk.sh` truyền); bản debug có `applicationIdSuffix ".debug"`; khóa ký truyền bằng `android.injected.signing.*`. Build thử bằng ảnh `troly-android-builder` 18/11: debug và bản ký 0.1.0 (versionCode 100) đều xanh. Khi commit cần `git update-index --chmod=+x app/android/gradlew` |
| 18/11/2026 | agent kiến trúc, agent app Android | App theo api thật ở localhost:8200: `client-logs` thân `{items: [{level, kind (`ui`, `api`), screen, message, detail (đối tượng chứa api_path, http_status, error_code, request_id, stack, app_version_code, platform, user_agent), app_version (versionName), occurred_at}]}` tối đa 50 mục, nhận cả khi chưa đăng nhập; CORS cho `https://localhost`, `http://localhost:5190`, lộ `X-Request-ID`, `Retry-After`; kết quả `/search` có `open` là hành động `open_screen`, thêm màn `note_detail` (`note_id`), `file_detail` (`file_id`), `chat` mở phiên cũ bằng `conversation_id`; `Expense.category` là `{id, name, kind}` hoặc null, ghi bằng `category_id`; thời điểm trả UTC, app đổi sang giờ Việt Nam |
| 18/11/2026 | agent hạ tầng, agent kiến trúc | Sao lưu: agent kiến trúc giữ `worker/jobs/backup.py` (tiền tố `backups/weekly/`, `backups/premigrate/`, `backups/manual/`; giữ 5 bản, không xóa bản weekly mới nhất). `scripts/vps-deploy.sh` gọi `python -m worker.jobs.backup --reason predeploy --label <sha>` trước migration. Config chỉ còn `R2_BUCKET=assistant` (QĐ-31) |
