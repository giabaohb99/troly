# Kế hoạch tổng

Ngày lập: 18/11/2026. Người duyệt: Gia Bảo.

## 1. Mục tiêu sản phẩm

**Một app duy nhất** trên Android để xem và làm mọi thứ cá nhân, thay cho việc mở nhiều app khác nhau:

| Mảng | Trong app |
|---|---|
| Trợ lý | Chat, trả lời ngắn, nhớ hồ sơ lõi, gọi công cụ thay người dùng |
| Hộp tin | Tin nhắn Zalo, Telegram, Messenger, SMS, Gmail gom một chỗ, tin quan trọng lên đầu |
| Lịch và việc | Google Calendar, Google Tasks, nhắc trên máy |
| Chi tiêu | Tự ghi từ Vietcombank, Techcombank, MoMo; ghi bằng câu chat |
| Lịch trình | Nhập, đánh giá, tối ưu, mở Google Maps, xuất Word |
| Báo cáo và thông số | Bảng điều khiển: chi tiêu, lịch tuần, tin chưa xử lý, chi phí AI, sức khỏe (V2) |
| Cài đặt | Kết nối Google, app được nghe, người quan trọng, ngân sách AI, thiết bị, phiên bản |

## 2. Tích hợp Google

| Dịch vụ | Dùng để | Chiều đồng bộ | Bản |
|---|---|---|---|
| Google Calendar | Lịch, sự kiện, việc có giờ | Hai chiều, Google làm gốc | V1.4 |
| Google Tasks | Việc không có giờ | Một chiều từ app sang Google, app làm gốc | V1.4 |
| Google Maps (URL, lệnh Android) | Mở bản đồ, dẫn đường xe máy | Không cần khóa | V1.6 |
| Google Maps Platform | Tọa độ, giờ mở cửa, thời gian di chuyển | Gọi từ máy chủ | V1.6 |
| Gmail | Đọc thư, tóm tắt vào hộp tin; soạn nháp; gửi phải duyệt | Đọc, ghi nháp | V1.8 |
| Google Contacts (People API) | Tên người gửi trong hộp tin, nhắc sinh nhật | Chỉ đọc | V1.8 |
| Google Drive | Lưu tệp xuất (Word, báo cáo); nhập tệp lịch trình | Đọc, ghi trong thư mục của app | V1.8 |
| Google Sheets | Xuất báo cáo chi tiêu | Ghi | V1.8 |
| Health Connect (trên Android) | Bước chân, giấc ngủ, nhịp tim | Chỉ đọc | V2 |

**Không làm:** Google Photos (API chỉ cho đọc ảnh do app tự tạo), Google Keep (API chỉ dành cho Workspace doanh nghiệp).

**Đăng nhập Google:** một dự án Google Cloud dùng chung cho OAuth và Maps. Màn đồng ý OAuth chuyển sang trạng thái *In production* để token không hết hạn sau 7 ngày; dùng cá nhân không cần Google xác minh, chỉ bấm qua cảnh báo một lần.

## 3. Lộ trình

| Giai đoạn | Nội dung | Xong khi |
|---|---|---|
| **A. Tài liệu** | Kế hoạch, thiết kế tổng thể, tài liệu kỹ thuật từng mảng | Đủ các tệp ở [docs/README.md](README.md), đã rà chéo, người dùng duyệt |
| **V1.0** | Backend nền (core, ai, memory, chat) + vỏ app Capacitor có màn Chat + CI build APK | Cài APK, đăng nhập, chat được, hồ sơ lõi được nạp |
| **V1.1** | Chi tiêu qua chat | Nhắn "cơm trưa 45k" là ghi đúng; hỏi tổng tháng trả đúng |
| **V1.2** | Plugin nghe thông báo + chi tiêu từ Vietcombank, Techcombank, MoMo | Giao dịch thật tự thành một dòng chi tiêu, chuyển sang MoMo không bị tính hai lần |
| **V1.3** | Hộp tin từ thông báo + tổng hợp | Hỏi "hôm nay có tin gì quan trọng" trả đúng, không lộ OTP |
| **V1.4** | Lịch, việc, nhắc trên máy + Google Calendar, Google Tasks | Thêm lịch trong app thấy trên Google Calendar và ngược lại |
| **V1.5** | Tự cập nhật app | Đăng bản mới thì app báo và cài được |
| **V1.6** | Lịch trình và bản đồ | Tệp Phước Hải – Trà Vinh vào thì ra đủ 3 ngày, chỉ ra rủi ro, bấm điểm là Maps mở chế độ xe máy |
| **V1.7** | Báo cáo, thông số, cài đặt đầy đủ | Bảng điều khiển hiện đủ các số ở mục 1 |
| **V1.8** | Gmail, Contacts, Drive, Sheets | Thư quan trọng vào hộp tin; xuất báo cáo chi tiêu ra Sheets |
| **V2** | Trả lời tin qua thông báo (có duyệt), máy chủ MCP, module gym, Health Connect | |
| **V3** | Tự phát triển bằng Claude CLI có cửa duyệt | |

## 4. Cách làm: một điều phối, nhiều agent

Mỗi agent là một phiên Claude Code riêng, gom trong nhóm **agent trợ lý** ở thanh bên. Phiên tạo kế hoạch này là **điều phối**: giao việc, rà chéo, gộp và commit.

### 4.1 Giai đoạn A: phân công tài liệu

| Agent | Viết tệp | Nội dung chính |
|---|---|---|
| **agent kiến trúc** | `10-kien-truc-backend.md`, `11-co-so-du-lieu.md`, `12-api.md` | Tầng lớp, luật module, lỗi, đăng nhập, worker; toàn bộ bảng; toàn bộ API |
| **agent AI** | `20-bo-nao-ai.md` | Lời nhắc, cache, trí nhớ, công cụ, hành động trả cho app, chi phí, đo chất lượng |
| **agent app Android** | `30-app-android.md`, `31-giao-dien.md` | Capacitor, plugin Kotlin, quyền, nhắc, cập nhật; mọi màn hình và luồng |
| **agent Google** | `40-tich-hop-google.md`, `41-ban-do-lich-trinh.md` | OAuth, từng dịch vụ ở mục 2, đồng bộ, hạn mức; lịch trình và bản đồ |
| **agent hạ tầng** | `50-ha-tang-trien-khai.md`, `60-bao-mat-rieng-tu.md`, `70-kiem-thu.md` | VPS chung, Docker, Cloudflare, GitHub Actions, sao lưu; bảo mật; chiến lược kiểm thử |

Điều phối giữ: `00-ke-hoach.md`, `01-thiet-ke-tong-the.md`, `02-cau-truc-ma-nguon.md`, `90-quyet-dinh.md`, `nhat-ky-viec.md`, `README.md`, `CLAUDE.md`.

### 4.2 Luật cho agent

1. Đọc `CLAUDE.md`, `docs/00-ke-hoach.md`, `docs/01-thiet-ke-tong-the.md`, `docs/02-cau-truc-ma-nguon.md` trước khi viết.
2. **Chỉ sửa tệp mình giữ.** Cần đổi tệp của agent khác thì ghi vào mục *Cần agent khác* cuối tệp mình.
3. **Không commit, không đổi nhánh.** Điều phối gộp và commit.
4. Bảng do module của mình cần thì mô tả trong tệp mình ở mục *Dữ liệu cần*; agent kiến trúc gom vào `11-co-so-du-lieu.md`.
5. Quyết định mới hoặc khác với thiết kế tổng thể thì ghi ở mục *Đề xuất quyết định* cuối tệp, kèm lý do. Điều phối đưa vào `90-quyet-dinh.md` khi người dùng duyệt.
6. Mỗi tài liệu có đủ các mục: Mục tiêu, Phạm vi, Thiết kế, Dữ liệu cần, API hoặc giao tiếp, Kiểm thử, Rủi ro, Câu hỏi mở, Cần agent khác, Đề xuất quyết định.

### 4.3 Giai đoạn mã

Sau khi tài liệu được duyệt, mỗi bản V1.x giao cho agent giữ mảng đó; điều phối rà và commit. Hai agent không sửa cùng một tệp trong cùng lúc.

## 5. Ngân sách

| Khoản | Mức |
|---|---|
| Claude API cho bộ não | Tối đa 200 USD mỗi tháng, ước dưới 10 USD với Haiku 5.5 cho một người |
| Claude CLI cho phát triển | Gói đăng ký |
| Google Maps Platform | Trong mức miễn phí hằng tháng, đặt hạn mức chi thấp |
| VPS, R2, tên miền | Dùng chung hạ tầng sẵn có |
