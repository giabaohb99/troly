# CLAUDE.md: kho troly

Trợ lý cá nhân của Gia Bảo: app Android (Capacitor, giao diện React, plugin Kotlin), máy chủ FastAPI + PostgreSQL, bộ não Claude API. Đọc `docs/00-ke-hoach.md` và `docs/01-thiet-ke-tong-the.md` trước khi làm bất cứ việc gì.

## Luật làm việc với người dùng

- Gọi người dùng là **đại ca**, xưng **em**. Tiếng Việt, ngắn gọn.
- **Không emoji** ở bất cứ đâu (giao diện, tài liệu, commit). Không dùng ngoặc kép góc; thay bằng in đậm hoặc in nghiêng.
- Tài liệu viết giọng trung tính (không "đại ca", không "em").

## Tài liệu

- Mọi tài liệu ở `docs/`. Mục lục và người giữ từng tệp ở `docs/README.md`.
- Chỉ sửa tệp mình được giao. Cần đổi tệp của người khác thì ghi vào mục *Cần agent khác* cuối tệp mình.
- Quyết định mới ghi ở mục *Đề xuất quyết định*; chỉ điều phối được ghi vào `docs/90-quyet-dinh.md`.

## Mã nguồn

- Cấu trúc theo `docs/02-cau-truc-ma-nguon.md`. Module không import ruột module khác.
- Tên hàm, biến, tệp tiếng Anh; hàm là động từ. Chuỗi hiển thị và chú thích tiếng Việt.
- Bảng tiền tố `tab_`, số ít, snake_case. Mọi hàm đọc ghi nhận `user_id` và lọc theo nó.
- API trả phong bì `{success, message, data}`, câu lỗi tiếng Việt.
- Viết bài kiểm trước cho luật nghiệp vụ. Chỉ chạy bài kiểm phần vừa sửa.

## Git

- Agent không commit, không đổi nhánh, trừ khi điều phối giao rõ.
- Điều phối commit: `git add` đúng tệp, gộp bằng merge (không rebase), cuối commit có dòng `Co-Authored-By`.
- Bí mật (`.env`, khóa ký APK, token Google) không bao giờ lên git.
