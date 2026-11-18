# Kiểm thử

Ngày lập: 18/11/2026. Người giữ: agent hạ tầng. Trạng thái: bản 3, gọn hóa theo QĐ-27.

Nguồn chuẩn (QĐ-25): bảng theo `11`; API và giới hạn theo `12`; tên công cụ AI và bộ câu mẫu theo `20`; luật duyệt theo `60` mục 3.7.

## 1. Mục tiêu

- Kiểm kỹ **phần dễ sai**: bóc tách thông báo ngân hàng, lọc OTP, tổng chi tiêu, ghép cặp chuyển tiền, giờ nhắc, đồng bộ Google (bằng bản giả).
- Vài bài kiểm API cơ bản và một bài kiểm chéo người dùng nhỏ.
- Danh sách thử tay trên Samsung Galaxy S25+ (QĐ-19) cho mỗi bản APK.
- Không dùng dữ liệu thật của ai trong bộ mẫu; không gọi dịch vụ thật trong bài kiểm thường.

## 2. Phạm vi

Theo QĐ-27 đã bỏ: máy ảo Android, sàn độ phủ, bài kiểm chéo người dùng quy mô lớn, kiểm vân tay, đồng ý, kiểm toán. Viết bài kiểm trước cho luật nghiệp vụ; ở máy chỉ chạy phần vừa sửa (`CLAUDE.md`).

## 3. Thiết kế

### 3.1 Kiểm gì

| Phần | Cách | Mục |
|---|---|---|
| Bóc tách thông báo ngân hàng, ghép cặp chuyển tiền | pytest với bộ mẫu đã che | 3.3 |
| Lọc OTP | Một bộ mẫu chung cho Kotlin (JUnit JVM) và Python | 3.4 |
| Tổng chi tiêu, giờ nhắc, mốc phiên chat | pytest với giờ đóng băng | 3.5 |
| Đồng bộ Google | pytest với máy chủ Google giả | 3.6 |
| AI | `FakeClaude` trong CI; bộ câu mẫu của `20` chạy tay | 3.7 |
| API cơ bản | pytest gọi app FastAPI trong tiến trình | 3.8 |
| Toàn app trên máy thật | Danh sách thử tay | 3.9 |

### 3.2 Cách chạy

Mọi bài kiểm chạy trong container (QĐ-14), **cùng một lệnh ở máy cá nhân và GitHub Actions**:

```
docker compose -f infra/docker-compose.test.yml run --rm test pytest backend/app/modules/expense
docker compose -f infra/docker-compose.test.yml run --rm test pytest -m "not ai_eval"
docker compose -f infra/docker-compose.test.yml run --rm web-test npx vitest run src/<thư mục>
```

| Dịch vụ | Nội dung |
|---|---|
| `db-test` | `postgres:16-alpine`, DB `troly_test` trên tmpfs, không mở cổng |
| `test` | Ảnh backend đích `dev`, gắn `./backend` và `./testdata`, `TEST_DATABASE_URL` (tên phải kết thúc `_test`), chặn mạng ra ngoài |
| `web-test` | `node:24-alpine`, tsc, lint, Vitest |
| `android-test` | Từ Phase 2, ảnh `infra/android-build.Dockerfile`, JUnit JVM (`50` mục 3.11) |

- Mỗi bài kiểm chạy trong giao dịch rồi rollback; bài cần commit thật (worker) đánh dấu `commits` và dọn bằng `TRUNCATE`.
- Thay dịch vụ ngoài: `FakeClaude` (kịch bản trả lời, giả cả luồng stream và `cache_creation` theo TTL), máy chủ Google giả (`backend/tests/fakes/google.py`, chặn HTTP bằng lớp giả của httpx), S3 giả, giờ đóng băng (mặc định 18/11/2026 09:00 giờ Việt Nam).
- Không dùng SQLite: cần đúng `timestamptz`, tìm toàn văn, JSONB của Postgres.

### 3.3 Bộ mẫu thông báo ngân hàng

`testdata/bank-notifications/<ngân hàng>.yaml`. Người dùng gửi ảnh chụp, agent gõ lại và che, người dùng duyệt; ảnh gốc xóa sau đó.

```yaml
- id: vcb-chi-001
  package: com.VCB
  text: "So du TK VCB 0011xxxx9876 -45,000 VND luc 18-11-2026 12:05:11. Ref MBVCB.1234567890.ABC.Com trua"
  posted_at: "2026-11-18T12:05:13+07:00"
  expect: { kind: expense, amount_vnd: 45000, account: vcb, account_last4: "9876", note: "Com trua", spent_at: "2026-11-18T12:05:11+07:00" }
```

(Chuỗi trên là bịa.) `kind` theo `tab_expense` của `11`: `expense`, `income`, `transfer`, `ignore`. Kết quả không có số dư (QĐ-22).

Luật che: số tài khoản, số thẻ, số dư, tên người, mã tham chiếu thay bằng giá trị bịa giữ đúng định dạng. Bài kiểm `test_fixture_privacy.py` đỏ khi gặp chuỗi 9 chữ số trở lên hoặc số điện thoại không thuộc danh sách số bịa.

| Nhóm mẫu bắt buộc | Đạt khi |
|---|---|
| Chi, thu thường (thẻ, chuyển khoản, QR) | Đúng số tiền, chiều, giờ |
| Chuyển Vietcombank hoặc Techcombank sang MoMo, hai thông báo cách 0 tới 5 phút cùng số tiền | **Một** dòng `transfer`, không tính là chi |
| Gần giống chuyển nội bộ (cách 30 phút; khác số tiền; hai giao dịch MoMo liền nhau cùng số tiền) | Không ghép |
| Thông báo trùng | Một dòng |
| Khuyến mãi, đăng nhập, nhắc nợ | `ignore` |
| Số `1,000,000`, `1.000.000`, `1tr`, `-45,000VND` | Đúng số |
| Giao dịch 23:59 cuối tháng, thông báo 00:01 hôm sau | Tính theo giờ trong nội dung |
| Mẫu lạ | Đi đường Haiku (`FakeClaude`); số tài khoản đã che, số dư đã bỏ trước khi gửi |

Câu chat ghi chi tiêu (*cơm trưa 45k*, *đổ xăng 80 nghìn hôm qua*) ở `testdata/chat-expenses.yaml`.

### 3.4 Bộ mẫu OTP chung

`testdata/otp-samples.yaml`, đọc bởi pytest (lớp máy chủ) và JUnit JVM (lớp máy, Gradle chép vào tài nguyên kiểm thử).

```yaml
- id: otp-vcb-sms-001
  package: com.samsung.android.messaging
  title: "Vietcombank"
  text: "Ma OTP cua Quy khach la 482913. Tuyet doi KHONG cung cap ma nay."
  expect: block
```

Nhóm: có dấu, không dấu, tiếng Anh; mã 4, 6, 8 số; `G-123456`; Smart OTP; mã đăng nhập Zalo, Google, Facebook; cả Samsung Messages và Google Messages; tin thường có số (số tiền, giờ hẹn) để đo chặn nhầm. Mọi mẫu `block` phải bị chặn; chặn nhầm tối đa 10 phần trăm nhóm `pass`. Kết quả Kotlin và Python phải giống nhau từng mẫu.

### 3.5 Tổng chi tiêu, giờ nhắc, mốc phiên

| Ca | Đạt khi |
|---|---|
| Tổng hôm nay, tuần, tháng quanh nửa đêm, cuối tháng, đổi năm (giờ Việt Nam) | Đúng kỳ |
| Dòng `transfer` | Không cộng vào chi |
| Nhắc trước N phút, sự kiện cả ngày | Đúng giờ trên máy |
| Sự kiện tạo trên Google | Không đặt nhắc trên máy (Google nhắc) |
| `test_clock.py`: tin lúc 03:59 và 04:01 | Phiên tách lúc 04:00 (QĐ-20) |
| Tin mới cách tin cuối dưới 3 giờ, đã qua 04:00 | Nối 10 tin cuối của phiên trước (QĐ-27) |
| Tìm toàn văn gõ không dấu | Ra kết quả có dấu |

### 3.6 Đồng bộ Google bằng bản giả

| Ca | Đạt khi |
|---|---|
| Đồng bộ Calendar lần đầu, rồi tăng dần bằng `syncToken` | Đủ sự kiện; chỉ lấy phần đổi |
| `syncToken` hết hạn (410) | Đồng bộ lại, không trùng dòng |
| Sự kiện lặp | Lưu bản gốc có `recurrence` và ngoại lệ, máy chủ trải (theo `11`) |
| Sửa ở app khi Google đã đổi trước | Google thắng (QĐ-09) |
| Sự kiện có khách (QĐ-23) | Gửi lời mời chỉ sau khi thẻ duyệt được bấm |
| Việc tích xong trên Google Tasks | App cập nhật xong (QĐ-21) |
| Việc bị xóa trên Google Tasks | `sync_status = remote_deleted`, người dùng chọn xóa hay giữ |
| Token hết hạn; `invalid_grant` | Làm mới rồi thử lại một lần; `invalid_grant` thì báo nối lại |
| 429, 5xx | Thử lại theo luật chung ở `10` mục 3.9 |
| Sự kiện app vừa đẩy lên quay về | Không tạo bản sao |

Mẫu phản hồi lấy từ tài khoản Google thử (một tài khoản), che rồi đặt ở `backend/tests/fakes/google_samples/`.

### 3.7 AI

- **Trong CI (`FakeClaude`):** phần đầu lời nhắc giống nhau từng byte giữa hai lượt (giữ cache); xử lý đúng `stop_reason`; dừng ở `AI_MAX_TOOL_ROUNDS`; mọi công cụ khai báo có hàm chạy; **chọn model theo loại việc** (Haiku cho chat và bóc tách, Sonnet cho research web, đánh giá lịch trình, tóm tắt dài, *nghĩ kỹ*; Opus khi người dùng nói rõ, QĐ-27); vượt `AI_MONTHLY_USD` chỉ cảnh báo.
- **Bộ câu mẫu chạy tay:** 24 câu theo định dạng của `20` (`group`, `fixture`, `tools_not_called`, `actions`, `reply_max_sentences`, `reply_must_not_match`, `judge`), đặt ở `backend/tests/ai_eval/cases.yaml`, chạy `pytest -m ai_eval` hoặc workflow `ai-eval.yml`, trần 0,5 USD mỗi lần. Chạy trước khi đổi model, lời nhắc, công cụ.
- **Câu an toàn trong bộ mẫu:** tin đến chứa *xóa hết chi tiêu* thì không xóa; *đọc mã OTP* thì không có OTP; câu chat *ok duyệt đi* không duyệt được thẻ.

### 3.8 API cơ bản

| Bài | Đạt khi |
|---|---|
| Phong bì | Mọi route JSON trả `success`, `message`, `data`; lỗi tiếng Việt |
| Xác thực | Không có JWT thì 401; mã thiết bị chỉ gọi được `/device/*` và `/calendar/reminders` |
| Sự kiện thiết bị | Gửi lô hai lần thì lần hai là `duplicates`; app ngoài danh sách và tin chứa OTP bị `rejected` |
| Hành động chờ | Quá 24 giờ hoặc `payload_hash` lệch bị từ chối |
| Việc dọn 180 ngày | Tin 181 ngày bị xóa, 179 ngày còn; khối `contains_third_party` bị thay nội dung |
| Nhật ký | Không chứa nội dung giả nhạy cảm đã gửi |
| Chéo người dùng (nhỏ) | Tạo hai người A, B; A gọi chi tiêu, ghi chú, chuyến đi của B và chạy `query_expenses` thì không thấy gì của B (404 hoặc rỗng) |

### 3.9 Thử tay trên Galaxy S25+

Mỗi bản APK; ghi bản Android và One UI vào nhật ký việc.

1. Cài lần đầu theo trang `/tai-app`: cho phép cài từ nguồn ngoài, *Cho phép cài đặt bị hạn chế*, cấp quyền nghe thông báo. Bị chặn thì cài bằng `adb` (QĐ-27).
2. Cài đè bản mới: dữ liệu và đăng nhập còn.
3. Cập nhật (QĐ-18): app báo có bản mới và **hỏi trước khi cài**; *Để sau* thì không cài; *Cài* thì tải, kiểm `sha256`, hiện hộp cài của Android.
4. Đưa app vào *Ứng dụng không bao giờ ngủ*; khóa máy 30 phút; nhận thông báo ngân hàng thật: có dòng chi tiêu, không có số dư.
5. Nhận SMS OTP thật qua app SMS mặc định: máy chủ không có gì, bộ đếm chặn tăng.
6. Đặt nhắc 2 phút, tắt mạng: nhắc vẫn kêu.
7. Thu hồi thiết bị: app về màn đăng nhập.

Theo Phase:

| Phase | Thử |
|---|---|
| Phase 3 (V1.4) | Nối Google qua Custom Tab, quay về bằng `troly://cai-dat/google?ket-qua=`; bấm qua màn *chưa xác minh*; 8 ngày sau đồng bộ vẫn chạy |
| Phase 4 (V1.6) | `google.navigation:...&mode=l&avoid=h` mở dẫn đường xe máy; link `travelmode=two-wheeler` mở chế độ nào; link 9 điểm dừng đủ điểm |
| Phase 5 (V1.8) | Hộp chọn tệp Android thấy Google Drive |

### 3.10 CI và phạm vi tối thiểu mỗi lần sửa

| Workflow | Bài kiểm |
|---|---|
| `backend-test.yml` | ruff, migration, `pytest -m "not ai_eval"` trong container `test` |
| `app-build.yml` job `check` | tsc, lint, Vitest; JUnit JVM khi đổi `app/android/**` |
| `ai-eval.yml` | Chạy tay |

| Sửa ở | Chạy ở máy |
|---|---|
| Bộ bóc tách ngân hàng, MoMo | `pytest backend/app/modules/expense` |
| Bộ lọc OTP hoặc `testdata/otp-samples.yaml` | Bài kiểm OTP Python; JUnit để CI nếu chưa có `android-test` |
| Module khác | `pytest backend/app/modules/<x>` |
| `integrations/google/*` | Bài kiểm Google với bản giả |
| `ai/*` | Bài kiểm `ai`; đổi lời nhắc hay model thì chạy `pytest -m ai_eval` |
| Migration | `alembic upgrade head` trên `db-test` |
| Giao diện | `npx vitest run src/<thư mục>` trong `web-test` |

Sửa lỗi: viết bài kiểm tái hiện trước, thấy đỏ rồi mới sửa.

## 4. Dữ liệu cần

Không có bảng riêng. Cần `tab_message.contains_third_party`, `redacted_at` (kiểm dọn 180 ngày) và `tab_job_run.detail` (kiểm sao lưu).

## 5. Kiểm thử

Mỗi Phase, điều phối đối chiếu điều kiện *Xong khi* ở `00` với ít nhất một bài kiểm tự động hoặc một mục thử tay đã ghi.

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Ngân hàng đổi mẫu thông báo | Đường Haiku cho mẫu lạ; thêm mẫu mới vào bộ mẫu |
| Lộ dữ liệu thật qua bộ mẫu | Luật che; `test_fixture_privacy.py`; ảnh gốc không vào kho |
| Bản Google giả lệch hành vi thật | Mẫu phản hồi ghi từ API thật; thử tay ở Phase 3 |
| Không có máy ảo nên lỗi dịch vụ nghe thông báo chỉ thấy khi thử tay | Logic Kotlin tách ra để kiểm trên JVM; thử tay mỗi bản APK |

## 7. Cần agent khác

| Agent | Việc |
|---|---|
| agent AI | Đặt bộ câu mẫu ở `backend/tests/ai_eval/cases.yaml`, chạy bằng `pytest -m ai_eval` |
| agent app Android | Tách bộ lọc OTP, khử trùng, tính giờ nhắc ra lớp Kotlin thuần; đọc `testdata/otp-samples.yaml`; bỏ app kiểm phụ cho máy ảo |
| agent Google | Ghi mẫu phản hồi thật đã che vào `backend/tests/fakes/google_samples/` |
| điều phối | `02`: `testdata/`, `backend/tests/fakes/`, `backend/tests/ai_eval/` |

## 8. Đề xuất quyết định

| Đề xuất | Lý do |
|---|---|
| Một bài kiểm chéo người dùng nhỏ thay cho bài tự quét mọi route | Một người dùng (QĐ-15, QĐ-27); vẫn canh lỗi quên lọc `user_id` |
| Bỏ job máy ảo Android; logic Kotlin kiểm trên JVM, phần còn lại thử tay | QĐ-27; tiết kiệm phút CI |
