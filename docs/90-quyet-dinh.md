# Sổ quyết định

Mỗi dòng là một quyết định đã chốt. Đổi quyết định thì thêm dòng mới, ghi rõ thay cho dòng nào.

| Số | Ngày | Quyết định | Lý do |
|---|---|---|---|
| QĐ-01 | 18/11/2026 | App Android làm gốc, viết bằng Capacitor (giao diện React, plugin Kotlin) | Cần nghe thông báo và chạy ngầm; giao diện React cập nhật không cần cài lại |
| QĐ-02 | 18/11/2026 | Không dùng MacroDroid, không dùng bot Telegram | Không tin bên thứ ba; app tự nghe thông báo |
| QĐ-03 | 18/11/2026 | Nghe tin nhắn qua thông báo Android (Zalo, Telegram, Messenger, SMS), không giả lập tài khoản | Hợp lệ, không bị khóa số; chỉ đọc được phần hiện trên thông báo |
| QĐ-04 | 18/11/2026 | Chi tiêu tự động từ Vietcombank, Techcombank, MoMo; OTP bị lọc bỏ trên máy | Nhu cầu người dùng; OTP không bao giờ rời điện thoại |
| QĐ-05 | 18/11/2026 | Model `claude-haiku-5-5` cho V1, đặt trong `.env` | Rẻ, nhanh, đủ đúng ở app gym |
| QĐ-06 | 18/11/2026 | Chạy chung VPS với Gamebar và gymcanhan, tên miền con do người dùng gán | Tận dụng hạ tầng sẵn có |
| QĐ-07 | 18/11/2026 | Backend FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 | Stack đã thạo; Postgres có tìm toàn văn và pgvector |
| QĐ-08 | 18/11/2026 | Build APK bằng GitHub Actions, máy cá nhân không cần Android SDK để build | Máy chưa có SDK |
| QĐ-09 | 18/11/2026 | Google Calendar làm gốc cho lịch (đồng bộ hai chiều); app làm gốc cho việc, đẩy một chiều sang Google Tasks; việc có giờ tạo thành sự kiện lịch | Google Tasks không lưu giờ, không có ưu tiên |
| QĐ-10 | 18/11/2026 | Tích hợp Google đầy đủ: Calendar, Tasks, Maps, Gmail, Contacts, Drive, Sheets; Health Connect ở V2 | Một app xem hết mọi thứ |
| QĐ-11 | 18/11/2026 | Không tự gửi báo cáo; chỉ trả lời ngắn khi được hỏi | Yêu cầu người dùng |
| QĐ-12 | 18/11/2026 | Claude CLI tự phát triển dùng gói đăng ký; bộ não chat dùng khóa API | Điều khoản dùng gói; tách chi phí |
| QĐ-13 | 18/11/2026 | Làm việc bằng một điều phối và năm agent theo mảng tài liệu | Tài liệu nhiều mảng, viết song song |
