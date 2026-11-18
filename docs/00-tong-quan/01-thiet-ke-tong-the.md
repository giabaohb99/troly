# Thiết kế tổng thể: Trợ lý cá nhân

Ngày lập: 18/11/2026. Bản 5: viết lại thành bức tranh chung sau rà chéo lần 1; chi tiết nằm ở tài liệu từng mảng (mục 9). Khi tệp này và tài liệu mảng khác nhau thì tài liệu mảng đúng, theo nguồn chuẩn ở QĐ-25.

## 1. Mục tiêu và phạm vi

Một **app trợ lý cá nhân trên Android** (máy Samsung Galaxy S25+) để xem và làm mọi thứ cá nhân trong một chỗ: chat với trợ lý, hộp tin gom từ Zalo, Telegram, Messenger, SMS, Gmail; lịch và việc đồng bộ Google; chi tiêu tự ghi từ Vietcombank, Techcombank, MoMo; lịch trình mở Google Maps; báo cáo và thông số; cài đặt. Trợ lý trả lời **ngắn**, không tự gửi báo cáo.

Hiện chỉ có **một người dùng** (QĐ-15); khung dữ liệu vẫn tách theo `user_id` để mở tối đa 4 người sau này.

**Ngoài phạm vi V1:** trả lời tin nhắn thay người dùng (V2, có duyệt), đặt hàng Shopee, tự thao tác app khác, báo cáo tự gửi, tự phát triển bằng Claude CLI (V3), module gym và Health Connect (V2), iPhone.

## 2. Quyết định chính

Danh sách đầy đủ ở [90-quyet-dinh.md](../90-quan-ly/90-quyet-dinh.md). Những điểm định hình thiết kế:

| Mục | Chốt |
|---|---|
| Nền tảng | App Android viết bằng Capacitor 8: giao diện React, plugin Kotlin (QĐ-01) |
| Nghe thông báo | Chính app đọc thông báo qua `NotificationListenerService`; không MacroDroid, không bot Telegram (QĐ-02, QĐ-03) |
| Máy chủ | FastAPI, SQLAlchemy 2, PostgreSQL 16, chạy Docker trên VPS chung; tạm tắt Gamebar, giữ tunnel (QĐ-06, QĐ-07, QĐ-14, QĐ-24) |
| AI | `claude-haiku-5-5`; không trần ngày, cảnh báo khi vượt 200 USD mỗi tháng (QĐ-05, QĐ-15) |
| Google | Calendar hai chiều (Google làm gốc, có mời khách qua duyệt); Tasks app làm gốc, đọc ngược trạng thái xong và xóa; Maps, Gmail, Contacts, Drive, Sheets (QĐ-09, QĐ-10, QĐ-21, QĐ-23) |
| Lưu giữ | Tin của người khác 180 ngày; không lưu số dư; sao lưu DB mỗi tuần, giữ 5 bản (QĐ-16, QĐ-17, QĐ-22) |
| Cập nhật app | Giao diện tải gói mới từ máy chủ; APK mới luôn hỏi trước khi cài (QĐ-18) |
| Phiên chat | Tách theo ngày lúc 04:00 (QĐ-20) |

## 3. Nguyên tắc thiết kế

1. **Không bắt AI nhớ, cho AI tra cứu.** Dữ liệu có cấu trúc nằm trong DB và là nguồn sự thật; AI đọc ghi qua công cụ.
2. **Một module, một khuôn.** Mỗi module có cùng bộ tệp (bảng, API, luật nghiệp vụ, công cụ AI). Thêm tính năng là thêm module.
3. **Lớp gốc Android mỏng, giao diện là web.** Kotlin chỉ làm việc web không làm được; đổi giao diện không cần cài lại app.
4. **Mọi truy vấn lọc theo người dùng.** Dữ liệu của người khác coi như không tồn tại.
5. **Phần đầu lời nhắc phải tĩnh** để cache; dữ liệu động đi sau điểm cache.
6. **Hành động ra ngoài phải được duyệt.** Gửi thư, mời khách, trả lời tin, deploy mã mới: trợ lý chuẩn bị, người dùng bấm duyệt.
7. **Chỉ gửi lên máy chủ thứ cần thiết.** Thông báo của app ngoài danh sách bị bỏ trên máy; tin có OTP không bao giờ rời điện thoại.

## 4. Kiến trúc

```
 Samsung Galaxy S25+: app Trợ lý
 ┌───────────────────────────────────────────┐
 │ Giao diện React trong WebView (Capacitor) │  gói giao diện tải từ R2 qua link ký sẵn
 │ Plugin Kotlin: nghe thông báo, hàng đợi,  │
 │   nhắc lịch trên máy, cập nhật, mở Maps   │
 └──────────────────┬────────────────────────┘
                    │ HTTPS /api/v1: JWT (giao diện), mã thiết bị (plugin)
           Cloudflare (DNS, TLS, tunnel dùng chung)
                    │
 VPS chung (Docker) │  Gamebar tạm tắt (giữ cloudflared), gymcanhan chạy bình thường
 ┌──────────────────▼────────────────────────┐
 │ troly-api     FastAPI, REST, chat SSE     │
 │ troly-worker  hàng đợi, đồng bộ Google,   │
 │               sao lưu, dọn dữ liệu        │
 │ troly-db      PostgreSQL 16, mạng kín     │
 └──────┬──────────────┬──────────────┬──────┘
        │              │              │
   Claude API     Google APIs    Cloudflare R2
                                 (tệp, sao lưu, bản phát hành)
```

Chi tiết: tầng lớp và luật module ở `10-kien-truc-backend.md`; compose, cổng, mạng, deploy ở `50-ha-tang-trien-khai.md`; plugin và quyền ở `30-app-android.md`.

## 5. Luồng chính

| Luồng | Tóm tắt | Chi tiết |
|---|---|---|
| Chat | App gửi tin, máy chủ trả dần chữ và các hành động (mở bản đồ, thẻ duyệt...) qua SSE | `12-api.md`, `20-bo-nao-ai.md`, `31-giao-dien.md` |
| Chi tiêu tự động | Thông báo Vietcombank, Techcombank, MoMo lên hàng đợi; worker bóc tách bằng mẫu cố định, không khớp thì nhờ AI; cặp chuyển ngân hàng sang MoMo ghi là chuyển nội bộ | `30-app-android.md`, `20-bo-nao-ai.md`, `11-co-so-du-lieu.md` |
| Hộp tin | Thông báo tin nhắn và thư Gmail vào hộp tin; luật không tốn AI đánh dấu tin quan trọng; chỉ gọi AI khi người dùng bấm tóm tắt | `31-giao-dien.md`, `40-tich-hop-google.md` |
| Lịch và việc | Google Calendar đồng bộ hai chiều; việc có giờ thành sự kiện; việc không giờ đẩy sang Google Tasks, đọc ngược trạng thái xong; nhắc kêu ngay trên máy | `40-tich-hop-google.md`, `30-app-android.md` |
| Lịch trình | Nhập tệp hoặc mô tả, bóc tách điểm, tìm tọa độ, đánh giá rủi ro, đề xuất phương án, mở Google Maps chế độ xe máy, xuất Word | `41-ban-do-lich-trinh.md` |
| Cập nhật app | App hỏi máy chủ bản mới; gói giao diện tải và kiểm chữ ký; APK mới thì hỏi người dùng rồi mới cài | `30-app-android.md`, `50-ha-tang-trien-khai.md` |

## 6. Dữ liệu và thời hạn giữ

| Dữ liệu | Giữ | Ghi chú |
|---|---|---|
| Tin nhắn, thông báo của người khác | 180 ngày | Kể cả khối chat có chứa tin người khác (QĐ-17) |
| Lịch sử chat | Theo `11-co-so-du-lieu.md` | Phiên cũ còn tóm tắt |
| Chi tiêu | Lâu dài | Không lưu số dư; tài khoản chỉ lưu mã ngân hàng và 4 số cuối (QĐ-22) |
| Tin có OTP | Không lưu | Bị bỏ ngay trên điện thoại |
| Sao lưu DB | 5 bản, mỗi tuần một bản | Thêm bản trước mỗi lần migration, tính trong 5 bản (QĐ-16) |

Toàn bộ bảng, cột và luật dọn dữ liệu ở `11-co-so-du-lieu.md`.

## 7. Bộ não AI

- Model `claude-haiku-5-5` cho mọi việc trong V1; đổi model bằng biến môi trường.
- Thứ tự lời nhắc để cache: công cụ, lời nhắc hệ thống tĩnh, hồ sơ lõi (điểm cache), tóm tắt phiên trước, tin hôm nay. Giờ hiện tại đi trong một tin hệ thống riêng ở cuối, không nằm trong phần đầu.
- Trí nhớ ba tầng: dữ liệu có cấu trúc trong DB, hồ sơ lõi nạp mọi lượt, ghi chú và tóm tắt tra khi cần.
- Phiên theo ngày tách lúc 04:00; phiên dài được tóm tắt.
- Chi phí ghi từng lượt; không trần ngày, cảnh báo khi vượt 200 USD mỗi tháng.

Chi tiết ở `20-bo-nao-ai.md`.

## 8. Bảo mật và kiểm thử

- Đăng nhập mật khẩu và JWT; mở app bằng vân tay; plugin dùng mã thiết bị riêng, thu hồi được.
- Token Google mã hóa khi lưu; bí mật chỉ ở `.env` và GitHub Secrets.
- Mọi bài kiểm chạy trong Docker; có bài kiểm chéo người dùng, bộ mẫu thông báo ngân hàng đã che số, bộ câu mẫu cho AI.

Chi tiết ở `60-bao-mat-rieng-tu.md` và `70-kiem-thu.md`.

## 9. Tài liệu chi tiết

| Chủ đề | Tệp |
|---|---|
| Kế hoạch, lộ trình, phân công | [00-ke-hoach.md](00-ke-hoach.md) |
| Cấu trúc mã nguồn | [02-cau-truc-ma-nguon.md](02-cau-truc-ma-nguon.md) |
| Kiến trúc backend, cơ sở dữ liệu, API | [10-kien-truc-backend.md](../10-backend/10-kien-truc-backend.md), [11-co-so-du-lieu.md](../10-backend/11-co-so-du-lieu.md), [12-api.md](../10-backend/12-api.md) |
| Bộ não AI | [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md) |
| App Android, giao diện | [30-app-android.md](../30-app/30-app-android.md), [31-giao-dien.md](../30-app/31-giao-dien.md) |
| Google, bản đồ và lịch trình | [40-tich-hop-google.md](../40-google/40-tich-hop-google.md), [41-ban-do-lich-trinh.md](../40-google/41-ban-do-lich-trinh.md) |
| Hạ tầng, bảo mật, kiểm thử | [50-ha-tang-trien-khai.md](../50-ha-tang/50-ha-tang-trien-khai.md), [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md), [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md) |
| Rà soát, quyết định | [80-ra-cheo-lan-1.md](../80-ra-soat/80-ra-cheo-lan-1.md), [90-quyet-dinh.md](../90-quan-ly/90-quyet-dinh.md) |
