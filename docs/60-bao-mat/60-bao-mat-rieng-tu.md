# Bảo mật và riêng tư

Ngày lập: 18/11/2026. Người giữ: agent hạ tầng. Trạng thái: bản 3, gọn hóa theo QĐ-27 (một người dùng).

Nguồn chuẩn (QĐ-25): tệp này là nguồn chuẩn cho **luật duyệt hành động**, nay ở **mục 3.7** (bản 2 là mục 3.12). Bảng theo `11`; đường dẫn API và giới hạn tần suất theo `12-api.md` mục 3.7; biến môi trường theo `10` mục 3.6.

## 1. Mục tiêu

- Mã OTP không bao giờ rời điện thoại.
- Token Google, khóa API, khóa ký APK không lộ qua kho mã, nhật ký hay bản sao lưu.
- Không có gì gửi ra ngoài (thư, lời mời, tệp chia sẻ, trả lời tin) và không xóa hàng loạt khi người dùng chưa bấm duyệt.
- Tin của người khác giữ 180 ngày rồi tự xóa (QĐ-17), và luôn là dữ liệu không tin cậy với AI.

## 2. Phạm vi

Một người dùng (QĐ-15). Cột `user_id` và việc lọc theo nó vẫn giữ trong mã. Theo QĐ-27 đã bỏ: khóa vân tay, vai trò thành viên, màn đồng ý, nhật ký kiểm toán, xuất và xóa tài khoản, Row-Level Security, khóa tài khoản khi sai mật khẩu, danh tính mã CI và mã runner.

## 3. Thiết kế

### 3.1 Mối đe dọa chính

| Mối đe dọa | Biện pháp |
|---|---|
| Mất điện thoại | Thu hồi thiết bị (`DELETE /api/v1/devices/{id}`); cần cắt ngay thì đổi `JWT_SECRET` |
| Dò mật khẩu qua Internet | Chỉ HTTPS qua Cloudflare; WAF và giới hạn tần suất theo `12` mục 3.7; không có đăng ký tự do |
| Chèn lệnh qua tin nhắn đến | Tin người khác là dữ liệu không tin cậy (mục 3.6); gửi ra ngoài chỉ qua thẻ duyệt bấm bằng nút (mục 3.7) |
| Lộ VPS (chạy chung máy với app khác) | Container không chạy root; DB ở mạng internal; token Google mã hóa |
| Lộ kho mã | Không bí mật nào trên git; quét bí mật trong CI |

### 3.2 Đăng nhập và mã thiết bị

- Đăng nhập một lần bằng mật khẩu (bcrypt hệ số 12). Tài khoản tạo bằng `python -m app.cli create-owner`; không có đăng ký tự do.
- Mã truy cập JWT 30 phút; mã làm mới 365 ngày (QĐ-27), xoay mỗi lần dùng, lưu băm SHA-256 trong `tab_auth_session`.
- Plugin Kotlin dùng mã thiết bị riêng (`Authorization: Device <mã>`), chỉ gọi được nhóm `/api/v1/device/*` (và `/calendar/reminders`), máy chủ lưu băm SHA-256. Mã cất trong `AndroidKeyStore`; `android:allowBackup="false"`.

### 3.3 Bí mật và khóa ký APK

| Bí mật | Chỗ cất |
|---|---|
| `JWT_SECRET`, `TOKEN_ENCRYPTION_KEYS`, `POSTGRES_PASSWORD`, `ANTHROPIC_API_KEY`, mã R2 của VPS, `GOOGLE_CLIENT_SECRET`, `GOOGLE_MAPS_API_KEY` | `/opt/troly/.env` (quyền 600) và một bản trong trình quản lý mật khẩu |
| Keystore và mật khẩu, mã R2 của CI (chỉ `troly-release`) | GitHub Secrets, Environment `release` |
| Khóa SSH vào VPS | Máy cá nhân |

- Tệp không lên git: `.env`, `*.keystore`, `*.jks`, `*.age`, `*.pem`, `*.p12`, `age-key*.txt` (điều phối thêm mẫu còn thiếu vào `.gitignore`). CI chạy `gitleaks`.
- **Khóa ký APK:** tạo một lần trên máy cá nhân bằng `keytool` trong container JDK, RSA 4096, hiệu lực 10950 ngày (30 năm). Không tạo trên GitHub Actions. Cất hai bản ngoại tuyến (trình quản lý mật khẩu và một ổ khác). Dấu vân tay SHA-256 ghi vào nhật ký việc và biến `ANDROID_SIGNING_CERT_SHA256` để job `apk` so. Mất khóa thì không cập nhật đè được, phải gỡ ra cài lại.

### 3.4 Mã hóa token Google

- Fernet, **một khóa** trong `TOKEN_ENCRYPTION_KEYS` (dạng `v1:<khóa>`). Cần xoay thì thêm khóa mới lên đầu và chạy `python -m app.cli reencrypt-tokens`.
- Chỉ `core/security.py` giải mã; token không trả qua API, không vào lời nhắc, không ghi nhật ký, không lưu trên điện thoại.
- Ngắt kết nối Google thì gọi thu hồi token của Google rồi xóa bản mã.
- Khóa không nằm trong DB nên bản sao lưu chỉ có bản mã; mất khóa thì nối lại Google.

### 3.5 Lọc OTP trên máy

Mọi thông báo chứa OTP **bị bỏ cả tin** trên điện thoại, trước khi vào hàng đợi (QĐ-04). Chặn nhầm vài tin thường thì chấp nhận được (tối đa 10 phần trăm tin thường có số).

| Luật | Ví dụ |
|---|---|
| Từ khóa (không phân biệt hoa thường, so cả bản bỏ dấu) | `OTP`, `Smart OTP`, `mã xác thực`, `mã xác nhận`, `mã xác minh`, `mã kích hoạt`, `mật khẩu một lần`, `không cung cấp mã`, `verification code`, `passcode`, `one-time`, `login code`, `2FA` |
| Mẫu số | Chuỗi 4 tới 8 chữ số đứng riêng cùng câu với từ khóa; dạng `G-123456`, `123-456` |
| Theo nguồn | Thông báo của app ngân hàng, ví không khớp mẫu giao dịch |
| SMS | Người gửi là tên thương hiệu ngân hàng, ví, dịch vụ đăng nhập và có chuỗi 4 tới 8 chữ số; áp cho app SMS mặc định thật trên máy (QĐ-19) |

Máy chủ chạy lại cùng bộ luật làm lưới an toàn: khớp thì bỏ, chỉ tăng bộ đếm `otp_blocked_server` (phải bằng 0). Bộ mẫu chung ở `testdata/otp-samples.yaml` (`70` mục 3.4).

### 3.6 Tin của người khác

| Chỗ | Giữ (QĐ-17) |
|---|---|
| Hàng đợi trên máy | Tới khi gửi được, tối đa 7 ngày |
| `tab_device_event` | 180 ngày (`DEVICE_EVENT_RETENTION_DAYS`) |
| `tab_inbox_message`, gồm thư Gmail | 180 ngày (`INBOX_RETENTION_DAYS`) |
| Khối `tab_message` có `contains_third_party` | 180 ngày (`THIRD_PARTY_CHAT_RETENTION_DAYS`): job `cleanup_old_data` thay nội dung, đặt `redacted_at` |
| Bản sao lưu | Thêm tối đa khoảng 5 tuần (5 bản tuần) |

Với AI:

- Nội dung tin người khác đi vào lời nhắc trong khối đánh dấu **dữ liệu không tin cậy**; lời nhắc hệ thống cấm làm theo chỉ dẫn nằm trong tin.
- Chỉ gửi khi người dùng hỏi; mỗi tin chỉ gồm app, tên người gửi, tên cuộc trò chuyện, giờ, nội dung cắt 500 ký tự; số điện thoại che còn 3 số cuối; tối đa `AI_INBOX_MAX_ITEMS` tin.
- Cuộc trò chuyện đánh dấu *riêng tư* không bao giờ gửi Claude. Tóm tắt phiên không chép nguyên văn tin người khác.
- Thông báo ngân hàng: chỉ lưu số tiền, mã ngân hàng và 4 số cuối tài khoản; không lưu số dư (QĐ-22).
- Dữ liệu Google Maps: tọa độ từ Google giữ tối đa 30 ngày, `place_id` giữ lâu dài (`41`).

### 3.7 Duyệt trước khi gửi ra ngoài và xóa hàng loạt (QĐ-27)

Bảng này là nguồn chuẩn cho luật duyệt.

| Hành động | Bản | Cách làm |
|---|---|---|
| Gửi thư Gmail | V1.8 | Thẻ duyệt; soạn nháp thì không cần |
| Gửi lời mời sự kiện, sửa sự kiện có khách (QĐ-23) | V1.4 | Thẻ duyệt |
| Chia sẻ tệp Drive cho người khác | V1.8 | Thẻ duyệt (khi có công cụ ở `20`) |
| Trả lời tin nhắn | V2 | Thẻ duyệt, hiện nguyên văn và người nhận |
| Xóa nhiều dòng một lần, xóa cả chuyến đi | V1 | Thẻ duyệt |
| Xóa một dòng (chi tiêu, việc, sự kiện, ghi chú) | V1 | Làm ngay, có nút *Hoàn tác* |
| Đổi cài đặt qua AI (`update_setting`), xuất ra Drive, Sheets của chính mình, `remember`, `forget` | V1 | Làm ngay, báo một dòng; QĐ-27 thay dòng *duyệt* của K9 ở `81` |
| Đổi danh sách app được nghe | V1 | Chỉ đổi tay trên màn Cài đặt, không qua AI |
| Gộp mã và deploy | V3 | Thẻ duyệt, kèm tóm tắt thay đổi và kết quả CI |

Cơ chế:

- Công cụ cần duyệt tạo một dòng `tab_pending_action` (`tool_name`, `input`, `payload_hash` = SHA-256 của `tool_name` cộng `input`), hạn 24 giờ, dùng một lần.
- Duyệt bằng nút trên thẻ, gọi `POST /api/v1/chat/actions/{id}/approve`. Máy chủ kiểm còn `pending`, chưa quá hạn, `payload_hash` khớp. **Câu chat như *ok*, *đồng ý* không duyệt được.**
- Không có bước vân tay (QĐ-27).

### 3.8 Sao lưu

Theo `50` mục 3.9: mỗi tuần, giữ 5 bản, **không mã hóa `age`**, nằm trong bucket R2 riêng tư `troly-backup`; chỉ mã R2 của VPS đọc được. Token Google trong bản sao lưu vẫn là bản mã Fernet.

### 3.9 Nhật ký

Không ghi nội dung tin nhắn, thông báo, câu chat, câu trả lời của Claude, token, mật khẩu, mã thiết bị, đầu `Authorization`, URL ký sẵn. Bộ lọc nhật ký che chuỗi giống token và chuỗi 9 chữ số trở lên.

### 3.10 Luật dữ liệu cá nhân

Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP có hiệu lực từ 01/01/2026 (văn bản trên chinhphu.vn). Điều 1 của Luật không có khoản miễn cho mục đích cá nhân; lịch sử giao dịch ngân hàng là dữ liệu nhạy cảm (Nghị định 356, Điều 4); gửi dữ liệu sang Claude API, R2, Google là chuyển dữ liệu ra nước ngoài (Luật, Điều 20). Với một người dùng tự xử lý dữ liệu của mình, troly giữ cách làm thận trọng: thu ít (lọc OTP, không lưu số dư), giữ có hạn (180 ngày), không chia sẻ, có trang `/chinh-sach-rieng-tu`. Trước khi có người dùng thứ hai thì hỏi luật sư. Đây không phải ý kiến pháp lý.

## 4. Dữ liệu cần

| Bảng | Việc |
|---|---|
| `tab_pending_action` | `tool_name`, `input`, `payload_hash`, `expires_at` (24 giờ); bỏ `require_unlock` |
| `tab_message` | `contains_third_party`, `redacted_at` |
| `tab_inbox_rule` | `kind = private_conversation` |
| `tab_expense` | `account`, `account_last4`; không có cột số dư |
| Bỏ (QĐ-27) | `tab_audit_log`, `tab_consent`; cột khóa tài khoản trên `tab_user` |

## 5. API hoặc giao tiếp

| Đường | Ghi chú |
|---|---|
| `POST /api/v1/auth/login`, `/auth/refresh` | Giới hạn theo `12` mục 3.7 |
| `GET /api/v1/devices`, `DELETE /api/v1/devices/{id}` | Thu hồi thiết bị |
| `POST /api/v1/device/events` | Mã thiết bị; máy chủ lọc OTP lần hai, bỏ `client_event_id` trùng |
| `POST /api/v1/chat/actions/{id}/approve`, `/reject` | Chỉ từ thẻ duyệt |
| Bỏ (QĐ-27) | `/me/export`, `DELETE /me`, `/consents`, `/admin/audit-log` |

## 6. Kiểm thử

Xem `70`: bộ mẫu OTP chung cho Kotlin và Python; việc dọn 180 ngày; hành động chờ quá 24 giờ hoặc `payload_hash` lệch bị từ chối; câu chat không duyệt được; nhật ký không chứa nội dung giả nhạy cảm.

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| OTP lọt vì mẫu tin mới | Hai lớp lọc; bộ đếm máy chủ phải bằng 0; thêm mẫu khi gặp |
| Lộ mã R2 của VPS thì đọc được bản sao lưu không mã hóa | Bucket riêng tư; mã chỉ ở `.env`; token Google vẫn mã hóa |
| Giữ tin người khác 180 ngày làm tăng phần bị lộ nếu DB lộ | Người dùng chọn (QĐ-17); không gửi AI khi không hỏi; dọn đúng hạn cả khối chat |
| Mất khóa ký APK | Hai bản ngoại tuyến |

## 8. Cần agent khác

| Agent | Việc |
|---|---|
| agent kiến trúc | `10`, `11`, `12`: bỏ các bảng, cột, đường dẫn nêu ở mục 4, 5; đổi mọi chỗ dẫn *60 mục 3.12* thành *60 mục 3.7* |
| agent AI | `20`: bỏ `require_unlock`; luật duyệt theo mục 3.7 (xóa một dòng làm ngay có Hoàn tác; `update_setting` không cần duyệt) |
| agent app Android | `30`, `31`: bỏ khóa vân tay, màn đồng ý, bước vân tay trên thẻ duyệt; bộ lọc OTP đủ luật mục 3.5 |
| điều phối | `.gitignore` thêm `age-key*.txt` |

## 9. Đề xuất quyết định

| Đề xuất | Lý do |
|---|---|
| Luật duyệt chuyển sang mục 3.7 của tệp này | Tệp gọn lại; các tệp khác dẫn số mục mới |
| Một khóa Fernet, xoay bằng lệnh `reencrypt-tokens` khi cần | Đủ cho một người dùng; vẫn xoay được |
