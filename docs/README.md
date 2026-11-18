# Tài liệu dự án troly

Mọi tài liệu của dự án nằm trong thư mục này, chia theo mảng. Số đầu thư mục trùng số đầu tệp để tìm nhanh: tệp `41-...` nằm trong thư mục `40-...`.

| Thư mục | Tệp | Nội dung | Người giữ | Trạng thái |
|---|---|---|---|---|
| `00-tong-quan/` | [00-ke-hoach.md](00-tong-quan/00-ke-hoach.md) | Kế hoạch tổng, lộ trình, phân công | điều phối | Đã viết |
| | [01-thiet-ke-tong-the.md](00-tong-quan/01-thiet-ke-tong-the.md) | Thiết kế tổng thể | điều phối | Bản sau rà chéo |
| | [02-cau-truc-ma-nguon.md](00-tong-quan/02-cau-truc-ma-nguon.md) | Cấu trúc mã nguồn và tài liệu | điều phối | Bản sau rà chéo |
| `10-backend/` | [10-kien-truc-backend.md](10-backend/10-kien-truc-backend.md) | Kiến trúc backend | agent kiến trúc | Bản 2 |
| | [11-co-so-du-lieu.md](10-backend/11-co-so-du-lieu.md) | Cơ sở dữ liệu | agent kiến trúc | Bản 2 |
| | [12-api.md](10-backend/12-api.md) | API | agent kiến trúc | Bản 2 |
| `20-ai/` | [20-bo-nao-ai.md](20-ai/20-bo-nao-ai.md) | Bộ não AI | agent AI | Bản 2 |
| `30-app/` | [30-app-android.md](30-app/30-app-android.md) | App Android | agent app Android | Bản 2 |
| | [31-giao-dien.md](30-app/31-giao-dien.md) | Giao diện | agent app Android | Bản 2 |
| `40-google/` | [40-tich-hop-google.md](40-google/40-tich-hop-google.md) | Tích hợp Google | agent Google | Bản 2 |
| | [41-ban-do-lich-trinh.md](40-google/41-ban-do-lich-trinh.md) | Bản đồ và lịch trình | agent Google | Bản 2 |
| `50-ha-tang/` | [50-ha-tang-trien-khai.md](50-ha-tang/50-ha-tang-trien-khai.md) | Hạ tầng, triển khai | agent hạ tầng | Bản 2 |
| `60-bao-mat/` | [60-bao-mat-rieng-tu.md](60-bao-mat/60-bao-mat-rieng-tu.md) | Bảo mật, riêng tư | agent hạ tầng | Bản 2 |
| `70-kiem-thu/` | [70-kiem-thu.md](70-kiem-thu/70-kiem-thu.md) | Kiểm thử | agent hạ tầng | Bản 2 |
| `80-ra-soat/` | [80-ra-cheo-lan-1.md](80-ra-soat/80-ra-cheo-lan-1.md) | Rà chéo lần 1: chỗ vênh, câu hỏi mở | điều phối | Chờ chốt |
| `90-quan-ly/` | [90-quyet-dinh.md](90-quan-ly/90-quyet-dinh.md) | Sổ quyết định | điều phối | Đang cập nhật |
| | [nhat-ky-viec.md](90-quan-ly/nhat-ky-viec.md) | Nhật ký việc | điều phối | Đang cập nhật |

## Quy ước

- Tệp mới đặt vào đúng thư mục mảng, số đầu tệp nằm trong khoảng của thư mục (ví dụ tài liệu thứ ba của mảng app là `32-...` trong `30-app/`).
- Liên kết giữa các tài liệu dùng đường dẫn tương đối, ví dụ `[12-api.md](../10-backend/12-api.md)`.
- Nhắc tới tài liệu khác trong chữ thì ghi tên tệp (`12-api.md`); tên tệp là duy nhất trong cả kho nên tìm bằng tên là ra.
- Ảnh và sơ đồ của một mảng đặt trong thư mục con `hinh/` của mảng đó.
