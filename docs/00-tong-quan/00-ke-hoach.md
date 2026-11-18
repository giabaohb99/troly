# Kế hoạch tổng

Ngày lập: 18/11/2026. Người duyệt: Gia Bảo. Cập nhật theo QĐ-15 tới QĐ-25 (`90-quyet-dinh.md`).

Hiện chỉ có **một người dùng** là Gia Bảo (QĐ-15). Khung nhiều người dùng (tối đa 4) vẫn giữ trong thiết kế để mở sau.

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
| Google Calendar | Lịch, sự kiện, việc có giờ, mời khách qua thẻ duyệt (QĐ-23) | Hai chiều, Google làm gốc | V1.4 |
| Google Tasks | Việc không có giờ | App làm gốc, đẩy sang Google; đọc ngược trạng thái xong và đã xóa (QĐ-21) | V1.4 |
| Google Maps (URL, lệnh Android) | Mở bản đồ, dẫn đường xe máy | Không cần khóa | V1.6 |
| Google Maps Platform | Tọa độ, giờ mở cửa, thời gian di chuyển | Gọi từ máy chủ | V1.6 |
| Gmail | Đọc thư, tóm tắt vào hộp tin; soạn nháp; gửi phải duyệt | Đọc, ghi nháp | V1.8 |
| Google Contacts (People API) | Tên người gửi trong hộp tin, nhắc sinh nhật | Chỉ đọc | V1.8 |
| Google Drive | Lưu tệp xuất (Word, báo cáo); nhập tệp lịch trình | Đọc, ghi trong thư mục của app | V1.8 |
| Google Sheets | Xuất báo cáo chi tiêu | Ghi | V1.8 |
| Health Connect (trên Android) | Bước chân, giấc ngủ, nhịp tim | Chỉ đọc | V2 |

**Không làm:** Google Photos (API chỉ cho đọc ảnh do app tự tạo), Google Keep (API chỉ dành cho Workspace doanh nghiệp).

**Đăng nhập Google:** một dự án Google Cloud dùng chung cho OAuth và Maps. Màn đồng ý OAuth ở trạng thái *Testing* thì mã làm mới hết hạn sau 7 ngày, nên chuyển sang *In production*. Chưa qua xác minh thì người dùng bấm qua màn cảnh báo *ứng dụng chưa được xác minh*; điều kiện cụ thể với từng nhóm quyền (nhạy cảm, hạn chế) ghi ở `40-tich-hop-google.md`, cần thử thật trước khi coi là chắc chắn.

## 3. Lộ trình theo phase

Mỗi phase gom vài bản V1.x, xong phase là có thứ dùng được thật trên Galaxy S25+. Bản V1.5 (tự cập nhật giao diện) bỏ theo QĐ-27; kiểm bản APK mới gộp vào V1.0.

| Phase | Bản | Nội dung | Agent chính | Xong khi | Người dùng làm |
|---|---|---|---|---|---|
| **A. Tài liệu** | | Kế hoạch, thiết kế, tài liệu từng mảng, gọn hóa (QĐ-27) | cả năm | Rà nhanh sau vòng 3 không còn chỗ vênh nặng | Duyệt |
| **0. Chuẩn bị** | | Tên miền `assistant.baohuynh.io.vn`, kiểm VPS, khóa Anthropic, bucket R2, khóa ký APK, secret GitHub, tạm dừng `core-game` | hạ tầng | VPS sẵn chỗ, CI chạy được | Chạy 3 lệnh kiểm VPS, tạo khóa và bucket, xác nhận dừng `core-game` |
| **1. Nền và chat** | V1.0, V1.1 | Backend nền, đăng nhập, chat SSE, hồ sơ lõi, chia model, research web, tìm tài liệu toàn văn, chi tiêu qua chat; vỏ app, màn Chat, Chi tiêu, Cài đặt cơ bản; CI build APK; deploy | kiến trúc, AI, app Android, hạ tầng | Cài APK, đăng nhập, chat được; nhắn *cơm trưa 45k* là ghi đúng; hỏi research có nguồn; tìm được tệp đã tải lên | Cài APK, dùng thử vài ngày |
| **2. Nghe thông báo** | V1.2, V1.3 | Plugin nghe thông báo, lọc OTP, chi tiêu tự động Vietcombank, Techcombank, MoMo; hộp tin Zalo, Telegram, Messenger, SMS | app Android, kiến trúc, AI | Giao dịch thật tự thành một dòng, chuyển sang MoMo không tính hai lần; hỏi *hôm nay có tin gì quan trọng* trả đúng, không lộ OTP | Gửi ảnh 5 tới 10 thông báo mỗi ví, làm bước thiết lập máy Samsung |
| **3. Lịch và việc** | V1.4 | Lịch, việc, nhắc trên máy, Google Calendar hai chiều, Google Tasks, mời khách qua duyệt | Google, app Android | Thêm lịch trong app thấy trên Google Calendar và ngược lại; nhắc kêu đúng giờ khi mất mạng | Làm các bước trên Google Cloud Console |
| **4. Lịch trình và báo cáo** | V1.6, V1.7 | Lịch trình, Google Maps, xuất Word; báo cáo, thông số, cài đặt đầy đủ | Google, app Android, AI | Tệp Phước Hải – Trà Vinh ra đủ 3 ngày, chỉ ra rủi ro, bấm điểm là Maps mở chế độ xe máy; bảng điều khiển đủ số | Tạo khóa Maps, đặt quota |
| **5. Gmail và Drive** | V1.8 | Gmail, Contacts, Drive, Sheets | Google | Thư quan trọng vào hộp tin; xuất chi tiêu ra Sheets | Nối thêm quyền Google |
| **Sau V1** | V2, V3 | Trả lời tin qua thông báo (có duyệt), máy chủ MCP, module gym, Health Connect, cập nhật giao diện không cần cài lại; tự phát triển bằng Claude CLI | | | Cân nhắc VPS mạnh hơn |

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

1. Đọc `CLAUDE.md`, `docs/00-tong-quan/00-ke-hoach.md`, `docs/00-tong-quan/01-thiet-ke-tong-the.md`, `docs/00-tong-quan/02-cau-truc-ma-nguon.md` trước khi viết.
2. **Chỉ sửa tệp mình giữ.** Cần đổi tệp của agent khác thì ghi vào mục *Cần agent khác* cuối tệp mình.
3. **Không commit, không đổi nhánh.** Điều phối gộp và commit.
4. Bảng do module của mình cần thì mô tả trong tệp mình ở mục *Dữ liệu cần*; agent kiến trúc gom vào `11-co-so-du-lieu.md`.
5. Quyết định mới hoặc khác với thiết kế tổng thể thì ghi ở mục *Đề xuất quyết định* cuối tệp, kèm lý do. Điều phối đưa vào `90-quyet-dinh.md` khi người dùng duyệt.
6. Mỗi tài liệu có đủ các mục: Mục tiêu, Phạm vi, Thiết kế, Dữ liệu cần, API hoặc giao tiếp, Kiểm thử, Rủi ro, Câu hỏi mở, Cần agent khác, Đề xuất quyết định.

### 4.3 Cách làm mỗi phase mã

0. **Bảng việc chung** ở `docs/90-quan-ly/bang-viec.md`: mọi việc, người giữ, chờ ai, trạng thái; hỏi nhỏ thì agent nhắn thẳng nhau rồi ghi lại, đổi hợp đồng thì qua điều phối.
1. **Chốt hợp đồng trước.** Điều phối chốt schema, API và tên công cụ của phase theo 11, 12, 20; agent không tự đổi giữa chừng.
2. **Chia theo vùng mã, làm chung một thư mục** `D:/giabao/troly`, không hai agent sửa cùng một tệp; điều phối commit:

| Agent | Vùng mã |
|---|---|
| agent kiến trúc | `backend/app/core/`, `backend/app/modules/*/` (trừ `tools.py`), `backend/alembic/`, `backend/worker/` |
| agent AI | `backend/app/ai/`, mọi `tools.py`, `backend/tests/ai_eval/` |
| agent app Android | `app/` (giao diện React và plugin Kotlin) |
| agent Google | `backend/app/integrations/google/`, phần đồng bộ trong module `calendar`, `task`, `trip`, `inbox` khi tới phase của mình (báo trước cho agent kiến trúc) |
| agent hạ tầng | `docker-compose*.yml`, `backend/Dockerfile`, `infra/`, `scripts/`, `.github/workflows/` |

3. **Thứ tự trong phase:** backend và hạ tầng đi trước; agent AI viết `tools.py` khi `service.py` đã có; app chạy song song bằng API giả rồi nối thật.
4. **Kiểm trong Docker:** mỗi agent chạy bài kiểm phần mình sửa; CI chạy đủ và build APK.
5. **Điều phối rà**, chạy lại bài kiểm, commit, đẩy `main`.
6. **Deploy:** điều phối chạy `scripts/deploy.sh`. Không đụng Gamebar, gym, tunnel (QĐ-29).
7. **Người dùng thử trên S25+** theo danh sách thử tay của phase; lỗi thì sửa vòng nhỏ rồi mới sang phase sau.
8. **Ghi lại:** nhật ký việc, và sửa tài liệu nếu mã khác thiết kế.

### 4.4 Luật mỗi phase (QĐ-30)

Rút từ app gym: đổi một người sang nhiều người giữa chừng, ba lần sửa lỗi điện thoại kẹt bản cũ và màn đen, đổi luật tài khoản ba lần trong một ngày, làm lại màn tập và ô nhập kg nhiều lần.

| Luật | Cụ thể |
|---|---|
| **Chốt trước khi viết mã** | Danh sách việc của phase, hợp đồng (bảng, API, công cụ AI) và khung màn hình chốt trên bảng việc. Giữa phase chỉ sửa lỗi chặn; ý mới ghi vào *Hàng chờ ý tưởng*, làm ở phase sau |
| **Lát cắt mỏng trước** | Ngày đầu phase dựng một đường chạy từ đầu tới cuối trên Galaxy S25+ (app, API, DB, AI), rồi mới làm dày từng màn |
| **Đường cập nhật và lỗi có từ Phase 1** | App báo lỗi giao diện và lỗi gọi API về máy chủ (`POST /api/v1/client-logs`); kiểm bản APK mới và thử cập nhật đè trên máy thật ở mọi phase; không có màn trắng hay đen: lỗi luôn hiện câu và nút *Tải lại* |
| **Dữ liệu đúng từ đầu** | Bảng theo 11; migration chỉ đi tiến, không đổi tên cột tùy hứng; sửa dữ liệu thật trên VPS phải sao lưu trước và đi bằng lệnh có sẵn, không gõ SQL tay |
| **Giao diện một vòng** | Phase có màn mới thì có khung màn trước; người dùng thử xong gom góp ý một lần, sửa một vòng; không sửa lẻ từng nút qua nhiều lần đẩy |
| **Đo AI trước khi chốt** | Câu lệnh, công cụ, model chạy bộ câu mẫu trước khi đưa lên máy; đổi model dựa trên số đo |
| **Xong phase là** | Bài kiểm phần dễ sai xanh; CI build APK; deploy; người dùng thử theo danh sách tối đa 10 mục; lỗi gom thành một vòng sửa; nhật ký, tài liệu, bảng việc cập nhật; gắn thẻ bản (`v0.1`, `v0.2`...) để quay lui |

## 5. Ngân sách

| Khoản | Mức |
|---|---|
| Claude API cho bộ não | Không đặt trần ngày (QĐ-15). Mức cảnh báo tháng 200 USD, vượt thì báo, không chặn. Haiku 5.5 cho việc thường, Sonnet 5.5 cho research và việc khó, Opus 5.5 khi gọi rõ (QĐ-27); ước vài USD tới khoảng 20 USD mỗi tháng |
| Claude CLI cho phát triển | Gói đăng ký |
| Google Maps Platform | Trong mức miễn phí hằng tháng. Đặt cảnh báo ngân sách trên Google Cloud (cảnh báo không tự chặn chi) và giới hạn số lần gọi mỗi ngày cho từng API |
| VPS, R2, tên miền | Dùng chung hạ tầng sẵn có; tạm tắt Gamebar để nhường tài nguyên (QĐ-24) |
