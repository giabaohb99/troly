# Nhật ký việc

Mỗi mục ghi một việc đã xong, viết cho người không đọc mã cũng hiểu. Mới nhất ở trên.

## 18/11/2026

- **Xong Phase 1 (v0.1).** Chat với Claude thật (Haiku cho việc thường, Sonnet cho research có nguồn), ghi và hỏi chi tiêu qua chat, tìm toàn văn, hồ sơ lõi. Chạy trên VPS ở `assistant.baohuynh.io.vn` (bản 721480a), game và gym không ảnh hưởng. Sao lưu thật lên R2 bằng `pg_dump` 16. APK 1.0.0 đã đăng lên R2, trang `/tai-app` có bản. 267 bài kiểm backend xanh. Lỗi chỉ lộ khi chạy thật đã sửa: tin hệ thống sai chỗ, quá nhiều tham số kiểu hợp, mã quốc gia VN của tìm web, tìm web không trả nguồn, `pg_dump` 17 không khôi phục được vào Postgres 16.

- Vòng 3 gọn hóa xong (QĐ-27, QĐ-28): một người dùng, bỏ khóa vân tay, chia model Haiku, Sonnet, Opus, tìm toàn văn thay RAG, tự quyết kỹ thuật. Tài liệu từ khoảng 8.600 dòng còn khoảng 4.650 dòng (chưa tính báo cáo rà soát). Lập bảng việc chung, lộ trình theo phase. Bỏ báo cáo tổng hợp cũ vì đã lỗi thời; bức tranh chung xem `01-thiet-ke-tong-the.md`.

- Năm agent nộp bản 2 sau rà chéo lần 1; đã commit. Rà chéo lần 2: 61 trên 86 chỗ vênh cũ đã khớp, còn 43 chỗ (5 nặng). Viết báo cáo tổng hợp toàn bộ tài liệu (`03-bao-cao-tong-hop.md`).

- Chia thư mục `docs/` thành thư mục con theo mảng (00 tổng quan, 10 backend, 20 AI, 30 app, 40 Google, 50 hạ tầng, 60 bảo mật, 70 kiểm thử, 80 rà soát, 90 quản lý). Tên tệp giữ nguyên, liên kết giữa các tài liệu đã sửa theo đường dẫn mới.
- Năm agent nộp bản 1 của 11 tài liệu kỹ thuật. Rà chéo lần 1 tìm ra 86 chỗ vênh và 34 câu hỏi mở.

- Dựng thư mục `docs/` làm nơi chứa mọi tài liệu. Viết kế hoạch tổng (lộ trình V1.0 tới V3, tích hợp Google đầy đủ, cách chia việc cho 5 agent), cấu trúc mã nguồn, sổ quyết định. Chuyển bản thiết kế tổng thể vào `docs/00-tong-quan/01-thiet-ke-tong-the.md`.
- Viết bản thiết kế tổng thể đầu tiên và đẩy lên kho.
