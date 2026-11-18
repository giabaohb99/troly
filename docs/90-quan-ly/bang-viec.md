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
| 0-01 | 0 | Chạy `ss -ltn`, `docker stats --no-stream`, `df -h /` trên VPS, gửi kết quả | người dùng | | chờ | Điều phối không SSH được (bộ kiểm quyền chặn); người dùng chạy hoặc cho phép |
| 0-02 | 0 | Thêm Public Hostname `troly.baohuynh.io.vn` trỏ `http://localhost:8200` | người dùng | 0-01 | chờ | |
| 0-03 | 0 | Tạo khóa API Anthropic cho troly, đặt hạn mức chi trên trang Anthropic | người dùng | | chờ | |
| 0-04 | 0 | Tạo bucket R2 và mã truy cập | người dùng | | chờ | Số bucket theo 50 bản 3 |
| 0-05 | 0 | Sinh khóa ký APK, cất hai bản, đặt secret GitHub | người dùng, agent hạ tầng | | chờ | |
| 0-06 | 0 | Dựng khung kho: compose, Dockerfile, CI kiểm backend và build APK | agent hạ tầng | A-06 | chờ | |
| 0-07 | 0 | Tạm dừng `core-game`, giữ `cloudflared`, kiểm gym còn sống | điều phối | 0-01, người dùng xác nhận | chờ | QĐ-24 |

Việc của Phase 1 trở đi điều phối thêm khi Phase 0 xong.

## 4. Chờ điều phối

| Ngày | Ai hỏi | Nội dung | Trả lời |
|---|---|---|---|
| 18/11/2026 | agent hạ tầng | Đăng bản APK bằng `releases/latest.json` trên R2, api chỉ đọc (50 mục 3.7). Kéo theo: bỏ `tab_app_release` (11), bỏ `POST /admin/releases`, `/admin/releases*`, `/device/web-bundle` và kiểu xác thực mã CI (12) | Đồng ý. 11 bỏ `tab_app_release`, 12 bỏ các đường trên |
| 18/11/2026 | agent hạ tầng | Luật duyệt nay ở 60 mục 3.7 (trước 3.12): xóa một dòng làm ngay có Hoàn tác; `update_setting` không duyệt (theo QĐ-27, thay K9); bỏ `require_unlock` (11, 20, 31) | Đồng ý; nguồn chuẩn luật duyệt là 60 mục 3.7 |
| 18/11/2026 | agent app Android | Hợp đồng mới cho giao diện QĐ-27: (1) `GET /api/v1/search?q=&types=` trên ghi chú, chat, hộp tin, lịch trình, chữ trích từ tệp; trả đoạn trích và chỗ mở (12, 11 chỉ mục toàn văn). (2) `Message` thêm `model` (model thật đã dùng) và `citations[]` (`title`, `url`) cho câu trả lời có tìm web; `message.completed` mang hai trường này (12, 20). Chi tiết ở 31 mục 3.5 và 9 | Đồng ý; gộp với dòng dưới của agent AI |
| 18/11/2026 | agent AI | Hợp đồng mới của 20 bản 3 (chi tiết 20 mục 4, 5, 9): (1) `POST /chat/messages` có `mode` (`chat`, `think`, `research`, `summary`) thay `think_harder` (12). (2) Kiểu hành động `undo` và `POST /expenses/{id}/restore`, `/tasks/{id}/restore`, `/calendar/events/{id}/restore` (12). (3) Module mới `search` cho `search_everything` và `GET /search?q=&types=` (đã khớp đề xuất của 31); bảng `tab_file_text`, `search_vector` cho `tab_message`, `tab_trip`, `tab_trip_stop`; job `extract_file_text` (10, 11). (4) `tab_ai_run` thêm `mode`, `web_search_requests`, `fallback_used`; `purpose` thêm `trip_evaluate`, `file_extract`, bỏ `summarize_inbox`; `tab_message` thêm `model`, `citations` (11). (5) Biến `AI_MODEL_STRONG`, `AI_MODEL_MAX` (10). (6) Gộp `search_notes`, `search_conversations` thành `search_everything`; còn 41 công cụ | Đồng ý cả 6 ý. Riêng tên biến: dùng `AI_MODEL_CHAT`, `AI_MODEL_SMART`, `AI_MODEL_MAX` (thay `AI_MODEL_STRONG`) |
| 18/11/2026 | agent Google | Bảng giờ phà quen (QĐ-26 câu 28) lưu ở khóa cài đặt `trip.ferries` (jsonb: tuyến, bến, chuyến đầu, chuyến cuối, hotline, ngày cập nhật); luật R3 dùng khi tệp không ghi giờ phà (41 mục 5.4). Cần 11 thêm khóa này cùng `trip.night_start`, `trip.night_end`, `trip.ride_break_minutes`, `trip.speed_factor` | Đồng ý; agent kiến trúc thêm 5 khóa vào 11 khi vào Phase 4 (việc 4-xx) |
| 18/11/2026 | agent kiến trúc | Không còn vai trò chủ (QĐ-27): `GET /admin/worker` đổi thành `GET /system/status`, thêm `POST /system/jobs/{name}/run` cho nút *Sao lưu ngay* (12 mục 5.9). Ảnh hưởng 31 (màn *Máy chủ*), 50 | |

## 5. Thỏa thuận giữa agent

| Ngày | Giữa | Thỏa thuận |
|---|---|---|
