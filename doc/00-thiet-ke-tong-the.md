# Thiết kế tổng thể: Trợ lý cá nhân

Ngày lập: 18/11/2026. Bản 3: thêm MoMo, module lịch trình và bản đồ, cách build APK, kho `giabaohb99/troly`.
Bản 2: chuyển sang app Android làm gốc, bỏ MacroDroid và bot Telegram.
Trạng thái: đã chốt hướng, chờ dựng V1.0.

## 1. Mục tiêu

Một **app trợ lý cá nhân trên Android**, dùng hằng ngày. Trợ lý ghi nhận và trả lời về mọi mảng của một người: lịch, việc, chi tiêu, tập luyện, ghi chú, định hướng cá nhân. Ngoài ra trợ lý **nghe thông báo trên điện thoại**, gồm tin nhắn Zalo, Telegram, Messenger, SMS và thông báo ngân hàng, rồi tổng hợp tin quan trọng khi người dùng hỏi.

Trả lời **ngắn gọn**, không tự gửi báo cáo. Phục vụ 1 người trước, thiết kế sẵn cho tối đa 4 người, dữ liệu tách riêng từng người.

### Phạm vi bản đầu (V1)

- App Android: khung chat, lịch, chi tiêu, hồ sơ.
- Hồ sơ lõi (giống CLAUDE.md của mỗi người) nạp vào mọi lượt chat.
- Chi tiêu: nhắn một câu là ghi (số tiền, khoản gì, ở đâu, lúc nào); hỏi là trả lời tổng. Thông báo biến động số dư Vietcombank, Techcombank và MoMo tự thành dòng chi tiêu.
- Lịch trình: đưa tệp hoặc mô tả chuyến đi, trợ lý bóc ra các điểm, đánh giá, đề xuất phương án tối ưu, lưu lại; bấm là mở Google Maps chỉ đường.
- Việc cần làm, lịch, nhắc lịch bằng thông báo ngay trên máy.
- Nghe thông báo tin nhắn (Zalo, Telegram, Messenger, SMS), lưu lại, tổng hợp khi được hỏi.
- Tệp (ảnh, ghi âm, tài liệu) lưu trên Cloudflare R2.
- App tự kiểm và cập nhật phiên bản mới.

### Ngoài phạm vi V1

- Trả lời tin nhắn thay người dùng (V2, luôn qua bước duyệt).
- Đặt hàng Shopee, tự thao tác app khác.
- Báo cáo định kỳ tự gửi.
- Tự phát triển bằng Claude CLI (V3).
- Module gym (chuyển từ app gymcanhan sang ở V2).
- iPhone (iOS không cho đọc thông báo của app khác).

## 2. Quyết định đã chốt

| Mục | Chốt |
|---|---|
| Nền tảng | App Android làm gốc. Không dùng MacroDroid, không dùng bot Telegram |
| Nghe tin nhắn | Tự app đọc thông báo bằng dịch vụ nghe thông báo của Android (`NotificationListenerService`) |
| Máy chủ | Chạy chung VPS với Gamebar và gymcanhan, Cloudflare Tunnel |
| Tên miền | Tên miền con của `baohuynh.io.vn`, người dùng tự gán (tạm gọi `<api-domain>` trong tài liệu) |
| Model AI | `claude-haiku-5-5` cho mọi việc trong V1 |
| Ngân hàng, ví | Vietcombank, Techcombank, MoMo |
| Bản đồ | Mở Google Maps bằng URL và lệnh gọi app trên Android (không cần khóa). Tìm tọa độ, giờ mở cửa, thời gian di chuyển bằng Google Maps Platform (khóa riêng, phạm vi dùng cá nhân nằm trong mức miễn phí hằng tháng) |
| Build APK | GitHub Actions, máy cá nhân không cần cài Android SDK để build. Cài Android SDK trên máy chỉ khi cần gỡ lỗi trực tiếp |
| Kho mã | `https://github.com/giabaohb99/troly` |
| Tự phát triển | Claude CLI trên VPS đăng nhập bằng gói đăng ký (dùng thử gói hiện có, lâu dài chuyển gói riêng) |

## 3. Nguyên tắc thiết kế

1. **Không bắt AI nhớ, cho AI tra cứu.** Dữ liệu có cấu trúc nằm trong DB và là nguồn sự thật. AI đọc ghi qua công cụ.
2. **Một module, một khuôn.** Mỗi module có cùng bộ tệp, tự khai báo bảng, API, trang và công cụ AI. Thêm tính năng là thêm module theo khuôn.
3. **Lớp gốc Android mỏng, giao diện là web.** Phần Android chỉ làm những gì web không làm được (nghe thông báo, nhắc lịch trên máy, chạy ngầm). Giao diện viết bằng React, nên đổi giao diện không cần cài lại app.
4. **Mọi truy vấn lọc theo người dùng.** Hàm đọc ghi luôn nhận `user_id`; dữ liệu của người khác coi như không tồn tại.
5. **Phần đầu lời nhắc phải tĩnh** để cache: thời gian hiện tại và dữ liệu động không nằm trong lời nhắc hệ thống.
6. **Hành động ra ngoài phải được duyệt.** Gửi tin, trả lời thay, deploy mã mới: trợ lý chuẩn bị, người dùng bấm duyệt.
7. **Chỉ gửi lên máy chủ thứ cần thiết.** Thông báo của app không nằm trong danh sách cho phép bị bỏ ngay trên điện thoại, không rời máy.

## 4. Kiến trúc

```
 Điện thoại Android: app "Trợ lý"                      VPS chung (Docker Compose, Cloudflare Tunnel)
 ┌─────────────────────────────────────────┐          ┌──────────────────────────────────────────┐
 │ Lớp giao diện: React (WebView Capacitor)│──HTTPS──>│ api     FastAPI: REST, chat, sự kiện     │
 │   chat, lịch, chi tiêu, hồ sơ           │          │ worker  xử lý sự kiện, sao lưu           │
 │ Lớp gốc Kotlin (plugin Capacitor):      │          │ db      PostgreSQL 16                    │
 │   - nghe thông báo, lọc theo danh sách  │──HTTPS──>│ static  bản build giao diện + tệp APK    │
 │   - hàng đợi gửi lên (WorkManager)      │          └──────┬────────────────┬──────────────────┘
 │   - nhắc lịch trên máy (AlarmManager)   │                 │                │
 │   - kiểm và tải bản cập nhật            │           Claude API       Cloudflare R2
 └─────────────────────────────────────────┘        (khóa API riêng)  (tệp, sao lưu, APK)
```

### Vì sao chọn Capacitor

| Cách | Ưu | Nhược |
|---|---|---|
| **Capacitor: giao diện React + plugin Kotlin** (chọn) | Viết giao diện bằng React như app gym. Giao diện cập nhật không cần cài lại APK. Plugin Kotlin làm được mọi việc gốc | Cần viết một plugin Kotlin cho phần nghe thông báo |
| Kotlin + Jetpack Compose thuần | Mạnh nhất, mượt nhất | Viết lại toàn bộ giao diện bằng Kotlin; mọi thay đổi phải build APK mới |
| React Native | Cùng hệ JavaScript | Phức tạp hơn Capacitor, vẫn cần mã gốc cho phần nghe thông báo |

### Lựa chọn công nghệ

| Phần | Chọn |
|---|---|
| App | Capacitor 7, React 19, Vite, TypeScript, Tailwind 4, shadcn, TanStack Query. Plugin gốc Kotlin |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| DB | PostgreSQL 16 (tìm kiếm toàn văn tiếng Việt; sau này thêm pgvector) |
| Xử lý nền | Tiến trình `worker` riêng, quét bảng hàng đợi mỗi 30 giây |
| Tệp | Cloudflare R2 qua API S3, tải lên bằng URL ký sẵn |
| Bản đồ | Google Maps URLs, lệnh `google.navigation` của Android; Google Maps Platform (Geocoding, Places, Routes) gọi từ máy chủ |
| Xuất tài liệu | python-docx (Word), giữ kiểu trình bày như tệp lịch trình mẫu |
| AI | Claude API qua SDK `anthropic` (Python), khóa API riêng |

## 5. Cấu trúc mã nguồn

```
troly/
  CLAUDE.md                 luật code cho người và cho Claude CLI
  docker-compose.yml
  .env.example
  backend/
    app/
      main.py
      core/                 cấu hình, DB session, đăng nhập JWT, lỗi, ghi log
      ai/
        client.py           gọi Claude, đo token, tính tiền
        prompt.py           lời nhắc hệ thống tĩnh + ghép hồ sơ lõi
        loop.py             vòng gọi công cụ
        compaction.py       tóm tắt phiên dài
        registry.py         gom công cụ của mọi module
      modules/
        memory/             hồ sơ lõi + ghi chú
        expense/            chi tiêu + bóc tách thông báo ngân hàng
        inbox/              tin nhắn nghe từ thông báo, tổng hợp
        task/               việc cần làm
        calendar/           lịch + nhắc
        device/             đăng ký thiết bị, nhận sự kiện, phiên bản app
        file/               tệp trên R2
        trip/               lịch trình, điểm dừng, bản đồ, xuất Word
        <tên>/
          models.py  schemas.py  repo.py  service.py  router.py  tools.py  test_*.py
    worker/main.py
    alembic/
  app/                      app Android
    src/modules/<tên>/{api,components,hooks,pages,types}
    src/shared/  src/core/
    android/                dự án Android do Capacitor sinh
      app/src/main/java/.../notify/   plugin Kotlin nghe thông báo
  doc/
    00-thiet-ke-tong-the.md
    nhat-ky-viec.md
```

Luật module: module không import ruột module khác; cần dùng chung thì đưa lên `core/`.

## 6. Dữ liệu

Bảng tiền tố `tab_`, số ít, snake_case. Mọi bảng nghiệp vụ có `user_id`, `created_at`, `updated_at`. Tiền lưu số nguyên VND. Thời gian lưu `timestamptz`, hiển thị giờ Việt Nam.

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `tab_user` | id, name, email, password_hash, timezone, role | role: owner hoặc member |
| `tab_device` | id, user_id, name, token_hash, app_version, last_seen_at | Mỗi điện thoại một mã, thu hồi được |
| `tab_profile_memory` | user_id, content (Markdown), version | Hồ sơ lõi, trần 8.000 ký tự |
| `tab_note` | id, user_id, title, body, tags, search_vector | |
| `tab_conversation` | id, user_id, started_at, summary, summary_upto_id | Mỗi ngày một phiên |
| `tab_message` | id, conversation_id, role, content (JSON), input_tokens, output_tokens | Lưu nguyên khối nội dung Claude trả về |
| `tab_expense` | id, user_id, amount_vnd, direction, category, merchant, place, note, spent_at, source, source_ref | direction: chi hoặc thu; source: chat, bank_notification, manual |
| `tab_expense_category` | id, user_id, name, keywords | |
| `tab_inbox_message` | id, user_id, device_id, app, sender, conversation_title, text, posted_at, status, importance | status: new, seen, done; giữ 30 ngày |
| `tab_inbox_rule` | id, user_id, kind, value, effect | Người quan trọng, từ khóa gấp, app tắt |
| `tab_task` | id, user_id, title, due_at, status, priority, note | |
| `tab_event` | id, user_id, title, start_at, end_at, location, remind_minutes | |
| `tab_device_event` | id, user_id, device_id, kind, app_package, payload, received_at, status | Hàng đợi sự kiện chưa xử lý |
| `tab_trip` | id, user_id, title, start_date, end_date, travel_mode, origin_text, status, source_file_id, notes | travel_mode: motorbike, car, walk; status: draft, planned, done |
| `tab_trip_stop` | id, trip_id, day_no, seq, planned_time, title, category, place_query, lat, lng, place_id, phone, cost_note, alternatives (JSON), note | category: an_uong, nghi, tham_quan, pha, di_chuyen |
| `tab_trip_option` | id, trip_id, name, summary, total_km, total_minutes, risks (JSON), chosen | Các phương án trợ lý đề xuất |
| `tab_place_cache` | query, lat, lng, place_id, opening_hours (JSON), fetched_at | Giảm số lần gọi Google |
| `tab_app_release` | id, version_code, version_name, r2_key, sha256, notes, created_at | Bản APK để app tự cập nhật |
| `tab_file` | id, user_id, r2_key, mime, size, purpose | |
| `tab_ai_run` | id, user_id, purpose, model, input_tokens, cache_read_tokens, output_tokens, cost_usd | |
| `tab_dev_job` | id, prompt, branch, status, summary, cost_usd | V3 |

## 7. Bộ não AI

### 7.1 Ghép lời nhắc (theo thứ tự, để cache)

1. **Công cụ:** danh sách công cụ của mọi module, sắp cố định theo tên.
2. **Lời nhắc hệ thống tĩnh:** vai trò, luật trả lời ngắn, luật hỏi lại trước khi hành động ra ngoài.
3. **Hồ sơ lõi** của người dùng. Đặt **điểm cache** ngay sau khối này.
4. **Tóm tắt phiên trước** (nếu có).
5. **Tin nhắn phiên hôm nay.** Thời gian hiện tại gắn vào **tin nhắn mới nhất** của người dùng.

Kiểm `usage.cache_read_input_tokens` trong `tab_ai_run`: bằng 0 nhiều lượt liền là có thứ làm hỏng cache. Lưu ý Haiku 5.5 chỉ cache khi phần đầu đủ dài theo ngưỡng tối thiểu của model.

### 7.2 Model

- Mọi việc dùng `claude-haiku-5-5`, `effort: low` cho chat thường, `medium` khi người dùng nói "nghĩ kỹ".
- Model đặt trong `.env` (`AI_MODEL_CHAT`, `AI_MODEL_EXTRACT`), đổi không cần sửa mã.
- Luôn kiểm `stop_reason` trước khi đọc nội dung; bị từ chối thì báo một dòng.
- Ước tính chi phí: dưới 10 USD mỗi tháng cho một người. Ngân sách 200 USD còn dư nhiều cho việc tự phát triển và thử model mạnh hơn khi cần.

### 7.3 Trần chi phí

Trần mỗi người mỗi ngày (`AI_USER_DAILY_USD`) và trần toàn hệ thống (`AI_DAILY_USD`), đếm từ `tab_ai_run`.

### 7.4 Trí nhớ, ba tầng

| Tầng | Ở đâu | Cách dùng |
|---|---|---|
| Dữ liệu có cấu trúc | Bảng nghiệp vụ | AI gọi công cụ truy vấn |
| Hồ sơ lõi | `tab_profile_memory` | Nạp mọi lượt. AI sửa qua `remember` / `forget`; người dùng xem và sửa tay trên app |
| Ghi chú và tóm tắt | `tab_note`, `tab_conversation.summary` | AI tìm bằng `search_notes` khi cần |

Phiên dài vượt khoảng 30.000 token thì tóm tắt lượt cũ. Sang ngày mới mở phiên mới, mang theo tóm tắt hôm trước.

### 7.5 Công cụ V1

| Module | Công cụ |
|---|---|
| memory | `remember`, `forget`, `save_note`, `search_notes` |
| expense | `add_expense`, `update_expense`, `delete_expense`, `query_expenses` |
| inbox | `list_inbox` (lọc theo app, người gửi, thời gian, trạng thái), `summarize_inbox`, `mark_inbox` |
| task | `add_task`, `update_task`, `list_tasks` |
| calendar | `add_event`, `update_event`, `list_events`, `set_reminder` |
| file | `list_files`, `get_file_link` |
| trip | `import_trip` (từ tệp hoặc lời mô tả), `evaluate_trip`, `save_trip`, `list_trips`, `get_trip`, `open_route` (trả hành động mở bản đồ cho app), `export_trip_docx` |

Công cụ khai `strict: true`. Công cụ xóa trả về bản nháp, người dùng bấm duyệt mới chạy.

## 8. App Android

### 8.1 Màn hình

- **Chat** (màn chính): khung chat, gửi chữ, ghi âm, ảnh.
- **Hộp tin:** tin nhắn nghe được, nhóm theo người gửi; tin quan trọng đứng đầu; nút *Tóm tắt* gọi trợ lý.
- **Lịch:** ngày, tuần, tháng; chạm để thêm hoặc sửa.
- **Chi tiêu:** tổng hôm nay, tuần, tháng; danh sách có lọc; sửa nhanh danh mục.
- **Lịch trình:** danh sách chuyến; mỗi chuyến chia theo ngày; mỗi điểm có nút *Dẫn đường*; mỗi ngày có nút *Mở cả ngày trên bản đồ*; nút *Xuất Word*.
- **Hồ sơ:** sửa hồ sơ lõi, danh sách app được nghe, người quan trọng, chi phí AI tháng này, phiên bản app.

### 8.2 Nghe thông báo

- Plugin Kotlin dùng `NotificationListenerService`. Người dùng cấp quyền một lần trong *Cài đặt > Thông báo > Quyền truy cập thông báo*.
- **Danh sách app được nghe** lưu trên máy và đồng bộ từ máy chủ. Mặc định:

| App | Tên gói (kiểm lại trên máy khi cài) | Dùng để |
|---|---|---|
| Vietcombank | `com.VCB` | Chi tiêu tự động |
| Techcombank | `vn.com.techcombank.bb.app` | Chi tiêu tự động |
| MoMo | `com.mservice.momotransfer` | Chi tiêu tự động |
| Zalo | `com.zing.zalo` | Hộp tin |
| Telegram | `org.telegram.messenger` | Hộp tin |
| Messenger | `com.facebook.orca` | Hộp tin |
| Tin nhắn SMS | ứng dụng SMS mặc định của máy | Hộp tin, mã giao dịch bị lọc bỏ |

- Thông báo của app ngoài danh sách bị bỏ ngay trên máy, không gửi đi.
- Lọc trên máy trước khi gửi: bỏ thông báo trùng, bỏ thông báo đang tiến trình (tải tệp, cuộc gọi), **bỏ mọi tin chứa mã OTP**.
- Sự kiện vào hàng đợi trên máy, gửi lên bằng WorkManager; mất mạng thì gửi lại sau.
- Nội dung đọc được chỉ là những gì hiện trên thông báo. Nếu Zalo cài ẩn nội dung tin thì chỉ biết có tin mới, không biết nội dung.

### 8.3 Xử lý trên máy chủ

- **Thông báo ngân hàng và MoMo:** một giao dịch chuyển từ ngân hàng sang MoMo sinh hai thông báo; nhận ra cặp này (cùng số tiền, cách nhau vài phút) và chỉ ghi một lần, đánh dấu là chuyển tiền nội bộ chứ không phải chi tiêu.
- **Thông báo ngân hàng:** bóc tách bằng mẫu cố định trước (nhanh, không tốn tiền), không khớp mẫu thì nhờ Haiku. Kết quả thành dòng `tab_expense` với `source = bank_notification`, báo xác nhận một dòng trong app.
- **Tin nhắn:** lưu vào `tab_inbox_message`. Đánh dấu quan trọng bằng luật không tốn AI (người quan trọng, từ khóa như *gấp*, *hôm nay*, *họp*). Chỉ gọi AI khi người dùng hỏi tổng hợp.
- Tin nhắn giữ 30 ngày rồi tự xóa.

### 8.4 Nhắc lịch

- Nhắc chạy **ngay trên máy** bằng `AlarmManager` (kêu đúng giờ kể cả khi mất mạng). Máy chủ đồng bộ danh sách nhắc xuống mỗi khi lịch đổi.
- Không cần Firebase hay bên thứ ba để đẩy tin.

### 8.5 Cập nhật app

Hai lớp, cập nhật khác nhau:

| Lớp | Cách cập nhật |
|---|---|
| Giao diện (React) | App tải bản build giao diện mới từ máy chủ khi mở, kiểm chữ ký số. Không cần cài lại |
| Lớp gốc (Kotlin, quyền) | App gọi `GET /api/device/release` lúc mở; có `version_code` mới thì tải APK từ R2, kiểm `sha256`, hiện hộp cài đặt của Android. Android bắt buộc người dùng bấm *Cài đặt*, không cài ngầm được |

APK ký bằng một khóa ký cố định, cất ngoài kho mã. Mất khóa này thì không cập nhật đè được, phải gỡ ra cài lại.

### 8.6 Lưu ý khi cài trên máy

- Cài APK ngoài cửa hàng: cho phép *Cài ứng dụng không rõ nguồn gốc* cho trình duyệt hoặc trình quản lý tệp.
- Từ Android 13, app cài ngoài cửa hàng muốn có quyền đọc thông báo phải mở *Thông tin ứng dụng > menu ba chấm > Cho phép cài đặt bị hạn chế* trước.
- Tắt tối ưu pin cho app để dịch vụ nghe không bị tắt.

### 8.7 Lịch trình và bản đồ

**Nhập lịch trình.** Người dùng gửi tệp Word, PDF, ảnh chụp, link, hoặc gõ mô tả (ví dụ *đi Trà Vinh 2 ngày bằng xe máy, muốn ăn bún nước lèo, xem chùa*).

1. Lấy chữ: Word qua python-docx (kể cả link trong tệp); PDF và ảnh gửi thẳng cho Claude đọc.
2. Bóc tách bằng đầu ra có cấu trúc: ngày, giờ, tên điểm, loại điểm, ghi chú, phương án dự phòng.
3. Tìm tọa độ từng điểm qua Places API, lưu `tab_place_cache`. Điểm tìm không chắc thì hỏi lại người dùng.

**Đánh giá.** Trợ lý kiểm từng chặng và trả về danh sách rủi ro:

- Thời gian di chuyển thật giữa hai điểm (Routes API, chế độ xe hai bánh nếu có, không thì ô tô) so với giờ dự kiến.
- Giờ mở cửa (Places API): ví dụ bảo tàng đóng cửa thứ Hai.
- Mốc cứng: chuyến phà cuối, giờ nhận phòng, giờ trả phòng.
- An toàn khi đi xe máy: chạy liên tục quá 1,5 tiếng, chạy đêm trên quốc lộ nhiều xe tải.

**Tối ưu.** Đưa ra 2 tới 3 phương án, ví dụ *Đúng giờ, ít rủi ro*, *Nhiều điểm hơn*, *Nhàn*. Mỗi phương án ghi tổng km, tổng giờ chạy, rủi ro còn lại. Các điểm không cố định giờ được sắp lại thứ tự cho đỡ đi vòng. Người dùng chọn một phương án thì lưu thành `tab_trip`.

**Mở bản đồ.** App tự dựng link, không cần khóa API:

| Nút | Cách mở |
|---|---|
| Dẫn đường tới một điểm | Lệnh Android `google.navigation:q=<lat>,<lng>&mode=l&avoid=h`: mở thẳng chế độ dẫn đường, xe hai bánh, tránh cao tốc |
| Xem đường cả ngày | `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=a|b|c&travelmode=two-wheeler` |
| Xem một điểm | `https://www.google.com/maps/search/?api=1&query=<tên>&query_place_id=<place_id>` |

Ngày có nhiều điểm hơn mức Google Maps cho phép trong một link thì chia thành nhiều đoạn, như cách tệp lịch trình mẫu đang làm. Cách này sửa luôn lưu ý trong tệp mẫu là phải tự bấm chọn xe máy.

**Trong chat.** Hỏi *chỉ đường tới chỗ ăn trưa* thì trợ lý tìm điểm kế tiếp trong lịch trình hôm nay và trả về nút mở bản đồ. Công cụ `open_route` không tự mở bản đồ; nó trả hành động cho app hiển thị thành nút, người dùng chạm mới mở.

**Lưu và xuất.** Chuyến đi lưu trong DB, hỏi *lấy lịch trình Trà Vinh* là ra. Xuất Word theo kiểu tệp mẫu (bảng giờ, link bấm được) khi người dùng cần chia sẻ; tệp lưu lên R2.

## 9. Tự phát triển bằng Claude CLI (V3)

1. Người dùng nhắn yêu cầu tính năng trong app.
2. Worker tạo `tab_dev_job`, chạy `claude -p` trong một worktree git ở nhánh riêng, bằng user Linux riêng, với `CLAUDE.md` của kho làm luật.
3. Claude CLI viết module theo khuôn và bài kiểm. Bài kiểm phải xanh.
4. Gửi tóm tắt thay đổi về app, kèm nút Duyệt hoặc Bỏ.
5. Duyệt: sao lưu DB lên R2, gộp nhánh, deploy backend, build giao diện mới. Thay đổi lớp Kotlin thì build APK trên GitHub Actions và đăng `tab_app_release`.
6. Hỏng thì quay về bản trước.

Ràng buộc: Claude CLI đăng nhập bằng `claude setup-token` (biến `CLAUDE_CODE_OAUTH_TOKEN`); bộ não chat vẫn dùng khóa API. User Linux của Claude CLI không vào được DB đang chạy và không đọc được `.env` của app. Có trần chi phí mỗi việc và mỗi ngày.

## 10. Bảo mật và riêng tư

- Đăng nhập app bằng mật khẩu băm (bcrypt) và JWT, phiên có hạn; mở app bằng vân tay.
- Mã thiết bị lưu dạng băm ở máy chủ, lưu trong kho khóa an toàn của Android trên máy.
- Tin nhắn của người khác có đi qua Claude API khi tổng hợp. Khóa API thương mại mặc định không dùng dữ liệu để huấn luyện. Vẫn giữ nguyên tắc chỉ gửi phần cần thiết và xóa sau 30 ngày.
- Mọi tin chứa mã OTP bị bỏ trên máy, không bao giờ rời điện thoại.
- Không có công cụ nào đụng vào app ngân hàng ngoài việc đọc thông báo.
- Khóa API, mã R2, khóa ký APK chỉ ở `.env` hoặc kho bí mật, không lên git.
- Sao lưu DB mỗi đêm lên R2, giữ 30 bản.

## 11. Triển khai

- Docker Compose trên VPS chung: thêm `troly-api`, `troly-worker`, `troly-db` vào cạnh Gamebar và gymcanhan, không đụng dịch vụ của hai app đó.
- Cloudflare Tunnel cho tên miền con do người dùng gán.
- Build APK bằng GitHub Actions trên kho `giabaohb99/troly`, đẩy APK lên R2. Khóa ký APK cất trong GitHub Secrets.
- Máy cá nhân chỉ cần Node để chạy giao diện. Cài Android Studio (hoặc bộ công cụ dòng lệnh Android và JDK 21) khi cần cắm điện thoại gỡ lỗi plugin Kotlin.
- Migration bằng Alembic.

## 12. Kiểm thử

- Bài kiểm luật nghiệp vụ viết trước: bóc tách thông báo Vietcombank và Techcombank (bộ mẫu thật, đã che số tài khoản), tổng chi tiêu theo kỳ, giờ nhắc, lọc OTP.
- Bài kiểm chéo người dùng: người A không đọc được dữ liệu người B qua API lẫn công cụ AI.
- Bài kiểm mọi công cụ khai báo đều có hàm chạy.
- Bộ câu mẫu cho AI (khoảng 20 câu thật) để đo độ đúng và giá của Haiku.
- Plugin Kotlin: bài kiểm bộ lọc (app ngoài danh sách, OTP, trùng lặp) chạy trên máy ảo Android.

## 13. Lộ trình

| Bản | Nội dung | Xong khi |
|---|---|---|
| **V1.0** | Backend nền (core, ai, memory) + app Android vỏ Capacitor có màn Chat | Cài APK, đăng nhập, chat được; hồ sơ lõi được nạp |
| **V1.1** | Chi tiêu (chat) | Nhắn "cơm trưa 45k" là ghi đúng; hỏi tổng tháng trả đúng |
| **V1.2** | Plugin nghe thông báo + chi tiêu từ Vietcombank, Techcombank | Có giao dịch thật thì app tự ghi một dòng chi tiêu |
| **V1.3** | Hộp tin (Zalo, Telegram, Messenger, SMS) + tổng hợp | Hỏi "hôm nay có tin gì quan trọng" thì trả đúng, không lộ OTP |
| **V1.4** | Việc, lịch, nhắc trên máy | Đặt nhắc 15:00 thì 15:00 máy kêu, kể cả khi tắt mạng |
| **V1.5** | Tự cập nhật app | Đăng bản mới thì app báo và cài được |
| **V1.6** | Lịch trình và bản đồ | Đưa tệp lịch trình Phước Hải – Trà Vinh vào thì ra 3 ngày đủ điểm, chỉ ra được rủi ro bảo tàng thứ Hai và giờ phà; bấm một điểm là Google Maps mở chế độ xe máy |
| **V2** | Trả lời tin nhắn qua nút trả lời của thông báo (có duyệt), máy chủ MCP, module gym | Trả lời được một tin Zalo từ trong app sau khi bấm duyệt |
| **V3** | Tự phát triển có cửa duyệt | Một tính năng nhỏ đi từ tin nhắn tới deploy sau một lần bấm Duyệt |

## 14. Việc cần người dùng chuẩn bị

1. Gán tên miền con trên Cloudflare cho API.
2. Tạo kho riêng tư trên GitHub cá nhân.
3. Gom 5 tới 10 thông báo biến động số dư thật của Vietcombank, Techcombank và MoMo (chụp màn hình, che số tài khoản) làm bộ mẫu bóc tách.
5. Tạo dự án Google Cloud, gắn tài khoản thanh toán, bật Geocoding API, Places API, Routes API và tạo một khóa giới hạn theo IP của VPS. Đặt hạn mức chi bằng 0 hoặc thấp để không phát sinh tiền.
4. Bật Chế độ nhà phát triển trên điện thoại để cài và gỡ lỗi APK.
