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
| QĐ-14 | 18/11/2026 | Mọi thứ chạy trên Docker, cả môi trường phát triển trên máy cá nhân và VPS; bài kiểm chạy trong container | Môi trường giống nhau, máy cá nhân đã có Docker, không phải cài Python và Postgres riêng |
| QĐ-15 | 18/11/2026 | Hiện chỉ có **một người dùng** (Gia Bảo). Không đặt trần chi phí AI theo ngày. Chỉ giữ một mức cảnh báo tháng `AI_MONTHLY_USD = 200`: vượt thì báo trong app, không chặn. Khung nhiều người dùng (tối đa 4, lọc `user_id`, bài kiểm chéo) vẫn giữ trong mã; khi thêm người dùng mới sẽ đặt trần riêng | Một người dùng, cần thoáng |
| QĐ-16 | 18/11/2026 | Sao lưu DB **mỗi tuần một lần** (chủ nhật 02:00 giờ Việt Nam) lên R2, giữ tối đa **5 bản**; thêm một bản ngay trước mỗi lần chạy migration (tính trong 5 bản). Bỏ bản tháng và bản giữ 12 tháng | Một người dùng, không cần nhiều bản |
| QĐ-17 | 18/11/2026 | Tin nhắn của người khác (hộp tin, sự kiện thiết bị, khối nội dung chat có chứa tin người khác) giữ **180 ngày** rồi tự xóa. Thay cho mức 30 ngày ở các tài liệu bản 1 | Người dùng muốn tra lại tin lâu hơn |
| QĐ-18 | 18/11/2026 | App luôn **hỏi trước khi cài** bản APK mới; không cài ngầm | Người dùng chọn |
| QĐ-19 | 18/11/2026 | Máy của người dùng: **Samsung Galaxy S25+**, cài đặt mặc định. App nghe cả Samsung Messages (`com.samsung.android.messaging`) và Google Messages (`com.google.android.apps.messaging`), bật theo app SMS mặc định thật trên máy. Tài liệu Android phải có bước tắt chế độ ngủ của One UI (*Ứng dụng không bao giờ ngủ*) | Thông tin người dùng; One UI tắt app chạy nền mạnh hơn Android gốc |
| QĐ-20 | 18/11/2026 | Phiên chat theo ngày tách lúc **04:00** giờ Việt Nam | Chat quá nửa đêm không bị cắt đôi |
| QĐ-21 | 18/11/2026 | Google Tasks: app vẫn làm gốc, nhưng **đọc ngược trạng thái xong và đã xóa** từ Google Tasks về app. Sửa phần *một chiều* của QĐ-09 | Tích xong trên máy khác thì app cũng biết |
| QĐ-22 | 18/11/2026 | **Không lưu số dư** tài khoản ngân hàng; chỉ lưu số tiền giao dịch, mã ngân hàng và 4 số cuối tài khoản | Giảm dữ liệu nhạy cảm |
| QĐ-23 | 18/11/2026 | Sự kiện có **mời khách** làm ở V1.4, gửi lời mời phải qua thẻ duyệt | Người dùng cần; gửi ra ngoài phải duyệt |
| QĐ-24 | 18/11/2026 | **Tạm tắt Gamebar** trên VPS để nhường tài nguyên cho troly; mở lại sau. Chỉ dừng container `core-game`, **giữ `cloudflared`** vì tunnel đang nằm trong compose của Gamebar và gymcanhan dùng chung. Thời điểm tắt: ngay trước lần deploy V1.0 đầu tiên, có người dùng xác nhận | Người dùng yêu cầu; tránh làm sập gym |
| QĐ-25 | 18/11/2026 | Chấp nhận các đề xuất ở `80-ra-cheo-lan-1.md` mục C (và mục *Kỹ thuật tự chốt được* ở mục B), trừ chỗ đã thay bằng QĐ-15 tới QĐ-24. Nguồn chuẩn khi các tài liệu lệch nhau: bảng và cột theo `11-co-so-du-lieu.md`; đường dẫn API theo `12-api.md` (tiền tố `/api/v1`, danh từ số nhiều); tên công cụ AI và kiểu hành động trả cho app theo `20-bo-nao-ai.md`; biến môi trường và danh sách job theo `10-kien-truc-backend.md`; mạng, cổng, compose theo `50-ha-tang-trien-khai.md`; giới hạn tần suất theo bảng chung ở `12-api.md`; luật duyệt hành động theo `60-bao-mat-rieng-tu.md` mục 3.12 | Người dùng giao điều phối thống nhất tài liệu |
