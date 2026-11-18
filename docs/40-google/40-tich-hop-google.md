# Tích hợp Google

Ngày lập: 18/11/2026. Người giữ: agent Google. Bản 2: thống nhất với bộ tài liệu theo `80-ra-cheo-lan-1.md` và QĐ-15 tới QĐ-25.

Tài liệu này mô tả cách app nối tài khoản Google và làm việc với Calendar, Tasks, Gmail, Contacts, Drive, Sheets, Maps Platform và Health Connect. Lịch trình và bản đồ có tài liệu riêng: [41-ban-do-lich-trinh.md](41-ban-do-lich-trinh.md).

**Nguồn chuẩn khi lệch (QĐ-25):**

| Nội dung | Tài liệu chuẩn |
|---|---|
| Bảng, cột | [11-co-so-du-lieu.md](../10-backend/11-co-so-du-lieu.md) |
| Đường dẫn API (`/api/v1`, danh từ số nhiều) | [12-api.md](../10-backend/12-api.md) |
| Tên công cụ AI, kiểu hành động trả cho app | [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md) |
| Job, biến môi trường | [10-kien-truc-backend.md](../10-backend/10-kien-truc-backend.md) |
| Mã hóa token, luật duyệt | [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md) |

Tệp này dùng đúng tên ở các tài liệu đó; chỗ cần thêm ghi ở mục *Cần agent khác*.

Mọi thông số Google đã đối chiếu với tài liệu chính thức ngày 18/11/2026, nguồn ở mục 20 ([N1], [N2]...). Điểm tài liệu Google không nói rõ được ghi là **chưa xác minh**.

## 1. Mục tiêu

1. Người dùng nối **một** tài khoản Google một lần, từ màn *Cài đặt*. Hiện chỉ có một người dùng là Gia Bảo (QĐ-15). Khung tối đa 4 người, mỗi người một tài khoản Google, vẫn giữ trong mã. Sau đó lịch, việc, thư, danh bạ, tệp chạy ngầm, không phải đăng nhập lại.
2. Lịch hai chiều với Google Calendar, Google làm gốc (QĐ-09). Mời khách được, nhưng lời mời chỉ gửi khi người dùng bấm duyệt (QĐ-23).
3. Việc: app làm gốc, đẩy sang Google Tasks. Trạng thái *xong* và *đã xóa* được đọc ngược về app (QĐ-21).
4. Gmail vào hộp tin như một nguồn tin. Soạn nháp tự do; gửi phải duyệt (`60-bao-mat-rieng-tu.md` mục 3.12).
5. Mỗi lời nhắc chỉ kêu ở **một** nơi.
6. Không phát sinh tiền: API Google Workspace dùng trong hạn mức miễn phí; Maps Platform nằm trong mức miễn phí hằng tháng và có quota chặn cứng.
7. Không cần Google xác minh ứng dụng: dùng diện miễn xác minh cho ứng dụng cá nhân [N3].

## 2. Phạm vi

| Dịch vụ | Bản | Trong phạm vi | Ngoài phạm vi |
|---|---|---|---|
| OAuth | V1.4 | Nối, làm mới, ngắt kết nối, xin thêm quyền theo dịch vụ | Đăng nhập app bằng Google (`80-ra-cheo-lan-1.md` mục B, câu 4) |
| Calendar | V1.4 | Lịch chính (`primary`), hai chiều; tạo và sửa sự kiện có khách mời qua thẻ duyệt (QĐ-23) | Lịch phụ, lịch được chia sẻ (xem *Câu hỏi mở*); trả lời lời mời của người khác; sửa cả chuỗi sự kiện lặp (mở Google Calendar) |
| Tasks | V1.4 | Một danh sách việc riêng tên *Trợ lý*: đẩy từ app; đọc ngược *xong* và *đã xóa* (QĐ-21) | Việc người dùng tự tạo trên Google |
| Maps Platform | V1.6 | Places API (New), Routes API, Geocoding gọi từ máy chủ | Maps SDK vẽ bản đồ trong app |
| Gmail | V1.8 | Đọc thư hộp *Chính*, đưa đoạn trích vào hộp tin; tìm, đọc chuỗi thư khi được hỏi; soạn nháp; gửi nháp qua thẻ duyệt | Xóa thư, đổi nhãn, gửi tự động |
| Contacts | V1.8 | Đọc tên, email, số điện thoại, sinh nhật | Sửa danh bạ |
| Drive | V1.8 | Ghi tệp xuất vào thư mục *Trợ lý* | Duyệt hay tìm tệp của người dùng trên Drive; chia sẻ tệp cho người khác |
| Sheets | V1.8 | Tạo và ghi bảng chi tiêu | Đọc bảng tính có sẵn |
| Health Connect | V2 | Đọc bước chân, giấc ngủ, nhịp tim trên máy | Ghi dữ liệu sức khỏe |

Không làm Google Photos, Google Keep (`00-ke-hoach.md` mục 2).

## 3. Thiết kế: OAuth, nối tài khoản Google

### 3.1 Trạng thái dự án và mức nhạy cảm của scope

| Scope | Dùng cho | Mức | Nguồn |
|---|---|---|---|
| `openid`, `email`, `profile` | Biết tài khoản nào đã nối | Không nhạy cảm | [N1] |
| `https://www.googleapis.com/auth/calendar.events` | Đọc ghi sự kiện, mời khách | Nhạy cảm (**chưa xác minh** trên bảng chính thức; trang xác minh scope nhạy cảm lấy việc đọc lịch làm ví dụ) | [N4][N5] |
| `https://www.googleapis.com/auth/tasks` | Đọc ghi việc | Nhạy cảm (**chưa xác minh**) | [N6] |
| `https://www.googleapis.com/auth/gmail.readonly` | Đọc thư, tìm thư | **Hạn chế** (restricted) | [N7] |
| `https://www.googleapis.com/auth/gmail.compose` | Tạo nháp, gửi nháp | **Hạn chế** | [N7] |
| `https://www.googleapis.com/auth/contacts.readonly` | Đọc danh bạ | Nhạy cảm (**chưa xác minh**) | [N8] |
| `https://www.googleapis.com/auth/drive.file` | Tệp do app tạo (kể cả bảng tính) | Không nhạy cảm | [N9][N10] |
| `https://www.googleapis.com/auth/spreadsheets` | Không dùng | Nhạy cảm | [N11] |

Mức chính xác của scope Calendar, Tasks, Contacts xem ở trang *Data access* trong Cloud Console khi thêm scope. Console hiện nhãn mức cho từng scope [N12].

**Trạng thái Testing.** App External ở Testing chỉ cho tối đa 100 người thử. Quyền cấp **hết hạn sau 7 ngày**, refresh token hết theo; ngoại lệ duy nhất là app chỉ xin `name`, `email`, `profile` [N1][N13]. App này không thuộc ngoại lệ.

**Trạng thái In production chưa xác minh.**

- Người dùng thấy màn *Google chưa xác minh ứng dụng này* và bấm qua được.
- Dự án bị giới hạn **tổng cộng 100 người dùng mới trong cả đời dự án**, không đặt lại được [N1][N14].
- App dùng cá nhân (dưới 100 người, tất cả quen biết người phát triển) được miễn xác minh, kể cả với scope hạn chế, và không phải làm đánh giá bảo mật CASA [N3][N15][N16].

**Điểm chưa có văn bản.** Google chỉ ghi rõ quy tắc hết hạn 7 ngày cho Testing. Không trang nào viết thẳng rằng refresh token ở In production chưa xác minh không hết hạn [N1][N17]. Thiết kế coi đây là rủi ro, có bài thử 8 ngày (mục 15) và luồng nối lại một chạm (mục 3.5).

Kết luận: màn đồng ý ở **In production**, không xin xác minh, người dùng bấm qua cảnh báo khi cấp quyền. **Không thử bằng nhiều tài khoản rác**, vì mỗi tài khoản đều trừ vào giới hạn 100.

### 3.2 Xin quyền theo dịch vụ

Mỗi dịch vụ là một mục trong `services` của `POST /api/v1/google/connect` (`12-api.md` mục 5.10). Danh sách dịch vụ đang bật lưu ở khóa cài đặt `google.services` (`11-co-so-du-lieu.md` mục 3.5). Scope thật được cấp lưu ở `tab_google_account.scopes`.

| Dịch vụ | Scope | Bật ở bản |
|---|---|---|
| (luôn có) | `openid email profile` | V1.4 |
| `calendar` | `calendar.events` | V1.4 |
| `tasks` | `tasks` | V1.4 |
| `gmail` | `gmail.readonly gmail.compose` | V1.8 |
| `contacts` | `contacts.readonly` | V1.8 |
| `drive` | `drive.file` (dùng cho cả Drive và Sheets) | V1.8 |

- Mỗi lần xin thêm dùng `include_granted_scopes=true` để token mới gồm cả quyền cũ [N18].
- Người dùng có thể bỏ tích từng quyền (granular consent). Máy chủ **luôn đọc trường `scope` trong phản hồi token**. Dịch vụ thiếu scope không được bật, và trang kết thúc báo `ket-qua=thieu-quyen` [N19].

### 3.3 Luồng nối tài khoản từ app Android

Google chặn trang đăng nhập OAuth chạy trong WebView nhúng (lỗi `disallowed_useragent`) [N20][N15]. App mở trang Google bằng **Custom Tabs** (trình duyệt hệ thống, plugin `@capacitor/browser`), không mở trong WebView. Luồng là **luồng máy chủ web**: client OAuth loại *Web application*, redirect https về máy chủ [N18].

1. App gọi `POST /api/v1/google/connect` với `services`.
2. Máy chủ chuẩn bị yêu cầu xin quyền:
   1. Tạo cặp PKCE: `code_verifier` ngẫu nhiên, `code_challenge` kiểu S256 [N20].
   2. Dựng `state` = **chuỗi mã hóa Fernet** bằng vòng khóa `TOKEN_ENCRYPTION_KEYS`, chứa `{user_id, services, code_verifier, nonce, exp = now + 10 phút}`.

      `12-api.md` hiện để `state` *ký* bằng `JWT_SECRET`. Ký thì ai thấy URL cũng đọc được nội dung, mà `code_verifier` phải giữ kín. Mã hóa thì không cần bảng lưu tạm (xem ĐX-G11).
   3. Trả `auth_url`:

      `https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri={PUBLIC_BASE_URL}/api/v1/google/oauth/callback&response_type=code&scope=...&access_type=offline&include_granted_scopes=true&prompt=consent&state=...&code_challenge=...&code_challenge_method=S256&login_hint=<email nếu đã nối>`
3. App mở `auth_url` bằng Custom Tabs.
4. Người dùng chọn tài khoản, bấm *Nâng cao* rồi *Đi tới ...* ở màn chưa xác minh, tích quyền.
5. Google chuyển về `GET /api/v1/google/oauth/callback?code=...&state=...`. Máy chủ:
   1. giải mã `state` và kiểm hạn;
   2. đổi `code` lấy token ở `https://oauth2.googleapis.com/token`, kèm `code_verifier`;
   3. đọc `id_token` lấy `sub`, `email`;
   4. đọc `scope` để biết quyền thật được cấp;
   5. mã hóa refresh token (mục 3.4), lưu `tab_google_account`;
   6. đặt việc `google_initial_sync` vào `tab_job_queue`.
6. Máy chủ trả trang HTML ngắn, chuyển hướng về app bằng `troly://cai-dat/google?ket-qua=<giá trị>`:

   | Giá trị | Khi nào |
   |---|---|
   | `ok` | Nối xong |
   | `huy` | Google trả `error=access_denied` |
   | `thieu-quyen` | Thiếu scope của dịch vụ đã chọn |
   | `loi` | Lỗi khác |

   App bắt liên kết qua `@capacitor/app`, đóng Custom Tab, gọi `GET /api/v1/google/account` (`31-giao-dien.md` luồng 3).

**Về custom scheme.** Google bỏ hỗ trợ custom URI scheme làm **redirect OAuth** trên Android [N20]. Ở đây redirect OAuth vẫn là https về máy chủ; `troly://` chỉ là bước nhảy từ trang của máy chủ về app, Google không tham gia. Không dùng App Link, vì `assetlinks.json` phải khớp dấu vân tay chữ ký, mà bản debug ký khóa khác (`80-ra-cheo-lan-1.md` mục C).

**Cách khác không chọn.** `AuthorizationClient` của Google Identity Services trả `serverAuthCode` qua plugin Kotlin [N22]. Cách này cần client Android có SHA-1 của khóa ký và thêm một plugin. Giữ làm dự phòng nếu Google đổi luồng cho app di động.

**Một người, một tài khoản Google.** `tab_google_account` có UQ trên `user_id` và `google_sub`. Nếu `sub` trả về khác tài khoản đang nối, máy chủ không ghi đè: trang kết thúc trả `ket-qua=loi`, kèm câu *Đang nối tài khoản khác, hãy ngắt kết nối trước*.

### 3.4 Lưu và làm mới token

- **Mã hóa** theo `60-bao-mat-rieng-tu.md` mục 3.5:
  - Fernet, vòng khóa `TOKEN_ENCRYPTION_KEYS`, cột `key_version`.
  - Bản rõ là `{user_id, provider: "google", token}`, kiểm `user_id` khi giải mã.
  - Chỉ `core/security.py` giải mã; chỉ `integrations/google/oauth.py` gọi.

  Chính sách Google cũng yêu cầu mã hóa token khi lưu và xóa khi không dùng [N15]. Không lưu refresh token trên điện thoại [N22].
- **Access token** lưu mã hóa ở `access_token_enc`, hạn ở `access_token_expires_at` lấy từ `expires_in`. Không ghi cứng thời hạn trong mã.
- **Làm mới khi cần.** Trước mỗi lời gọi, access token còn dưới 5 phút thì làm mới. Lúc làm mới giữ khóa tư vấn PostgreSQL theo `google_account_id`. Khóa này dùng không gian số riêng, khác khóa đồng bộ ở `10-kien-truc-backend.md` mục 3.9. Như vậy `api` và `worker` không cùng làm mới một lúc.
- **Giới hạn 100 refresh token.** Mỗi tài khoản Google, mỗi client OAuth có tối đa 100 refresh token; vượt thì token cũ nhất mất hiệu lực mà không báo [N17]. Nối lại xong, máy chủ thu hồi token cũ ngay.

### 3.5 Khi token hỏng

Refresh token mất hiệu lực khi [N17]:

- người dùng thu hồi quyền;
- 6 tháng không dùng;
- người dùng đổi mật khẩu Google, với token có scope Gmail;
- quyền có thời hạn đã hết;
- dự án ở Testing (7 ngày);
- vượt giới hạn 100 token.

Xử lý:

1. Gặp `invalid_grant` khi làm mới:
   - `tab_google_account.status = reauth_required`;
   - dừng mọi job đồng bộ của tài khoản; dòng `tab_google_outbox` giữ nguyên `pending`;
   - API và công cụ AI trả lỗi `GOOGLE_REAUTH_REQUIRED` (`12-api.md`); công cụ AI kèm hành động `open_screen` tới `settings_google` (`20-bo-nao-ai.md`).
2. App hiện **một dòng**: *Kết nối Google đã hết hạn, chạm để nối lại.* Chạm thì chạy lại mục 3.3 với đúng `google.services`.
3. Nối lại xong thì hàng chờ chạy tiếp.
4. Đếm số lần `invalid_grant` mỗi tháng. Hết hạn đều đặn khoảng 7 ngày một lần nghĩa là dự án đang bị coi như Testing.

### 3.6 Ngắt kết nối và thu hồi

`POST /api/v1/google/disconnect`:

1. Gọi `POST https://oauth2.googleapis.com/revoke` với refresh token. Thu hồi một token là bỏ hết scope đã cấp cho dự án [N20].
2. `channels.stop` các kênh Calendar [N23].
3. Làm theo `11-co-so-du-lieu.md` mục 3.14:
   - xóa `tab_google_account`, kéo theo `tab_google_sync_state`, `tab_google_outbox`, `tab_contact`;
   - sự kiện và việc giữ lại trong app, cột `google_*` đặt rỗng, `sync_status = local_only`;
   - thư Gmail đã vào hộp tin giữ tới hết hạn 180 ngày (QĐ-17), người dùng xóa tay được;
   - xóa khóa `google.services` và các khóa `google.*` khác.

Người dùng thu hồi từ phía Google thì lần gọi sau gặp `invalid_grant`, đi theo mục 3.5.

Cross-Account Protection (RISC) cho phép Google báo ngay khi token bị thu hồi, nhưng cần điểm nhận riêng và tài khoản dịch vụ [N24]. Để V2.

## 4. Thiết kế: Google Calendar (hai chiều, Google làm gốc)

### 4.1 Dùng để làm gì

- Màn *Lịch* hiện sự kiện lịch `primary` cùng sự kiện tạo trong app.
- Tạo, sửa, xóa trong app thì đẩy lên Google. Sửa trên Google thì về app trong vài giây (có thông báo đẩy), chậm nhất sau một chu kỳ quét.
- Việc có giờ (`tab_task.due_at`) sinh một sự kiện lịch (QĐ-09, `tab_task.event_id`).
- Mời khách (QĐ-23): mục 4.6.

### 4.2 Ánh xạ dữ liệu

| `tab_event` | Google Calendar `Event` |
|---|---|
| `title` | `summary` |
| `description` | `description` |
| `location` | `location` |
| `all_day`, `start_at`, `end_at`, `start_date`, `end_date` | `start.dateTime`/`end.dateTime` kèm `timeZone = Asia/Ho_Chi_Minh`, hoặc `start.date`/`end.date` |
| `status` | `status` |
| `remind_minutes`, `remind_source` | `reminders` (mục 4.7) |
| `id` (bigint) | `extendedProperties.private.troly_event_id` |
| `google_event_id` | `id` |
| `google_recurring_event_id` | `recurringEventId` |
| `google_etag`, `google_updated_at` | `etag`, `updated` |
| `origin` | `app` nếu tạo trong app, `google` nếu kéo về |
| (khách mời) | `attendees[].email`, `organizer.self` |

`extendedProperties.private` chỉ thấy trên bản sự kiện của lịch này, không lộ cho khách mời [N25].

**Mã sự kiện do app đặt, chống tạo trùng.** Google cho client tự đặt `id` cho sự kiện mới, gồm ký tự base32hex (a–v, 0–9), dài 5 tới 1024 ký tự [N25]. Khi tạo sự kiện trong app:

1. Sinh UUID ngẫu nhiên dạng hex 32 ký tự (hex nằm trong base32hex).
2. Ghi vào `google_event_id` ngay, cùng giao dịch với dòng `tab_google_outbox`.
3. Worker gọi `events.insert` với `id` đó. Gửi lại do mạng lỗi sẽ gặp lỗi trùng chứ không sinh hai sự kiện. Gặp lỗi trùng thì `events.get` để lấy `etag`, coi như đã tạo.

### 4.3 Thuật toán đồng bộ từ Google về app

**Sự kiện lặp: chốt `singleEvents=true`**, như `11-co-so-du-lieu.md` và đề xuất của `80-ra-cheo-lan-1.md` mục A1 dòng 11. Lý do:

- Chính hướng dẫn đồng bộ của Google dùng `singleEvents=true` trong ví dụ của cả lần đầu lẫn lần tăng dần [N26].
- Mỗi lần xảy ra là một dòng, nên app không phải tự trải RRULE.
- Sửa hay xóa một lần lặp chỉ là sửa một dòng.

Bản 1 đề xuất `singleEvents=false`; bỏ đề xuất đó.

Đồng bộ tăng dần bằng `syncToken` [N26]:

1. **Lần đầu** (việc `google_initial_sync`, rồi đồng bộ đủ mỗi 30 ngày, bước 5):
   - gọi `events.list(calendarId=primary, singleEvents=true, showDeleted=true, maxResults=2500, timeMin=<now − 30 ngày>)`, lật hết trang theo `pageToken`;
   - lưu `nextSyncToken` ở trang cuối vào `tab_google_sync_state.sync_token`.

   Hướng dẫn của Google cho phép thu hẹp lần đồng bộ đủ bằng tham số, ví dụ mẫu của Google dùng `timeMin` [N26]. Không đặt `timeMax`: lần tăng dần không được dùng `timeMax`, còn lần đầu dùng được hay không thì tài liệu không nói (**chưa xác minh**).
2. **Lần sau:** gọi `events.list(calendarId=primary, singleEvents=true, syncToken=...)`, lật hết trang, lưu token mới. Không dùng kèm `timeMin`, `timeMax`, `orderBy`, `q`, `updatedMin`, `iCalUID`, `privateExtendedProperty`, `sharedExtendedProperty`; dùng kèm là lỗi 400. Không được đặt `showDeleted=false` [N27].
3. **Ghi từng sự kiện nhận về:**
   - `status = cancelled`: đặt `deleted_at` (xóa mềm). Sự kiện đã xóa chỉ chắc chắn có `id` [N25].
   - `etag` trùng `google_etag` đang lưu: bỏ qua, đó là tiếng vọng của lần ghi từ app.
   - Bắt đầu sau `now + 365 ngày`: bỏ qua, không lưu (khung của `11-co-so-du-lieu.md`).
   - Còn lại: ghi đè bản trong app (Google làm gốc). Bản trong app đang có dòng outbox chờ thì xử lý theo mục 4.5.
4. **Lỗi 410 Gone** (`fullSyncRequired`):
   - xóa sự kiện `origin = google` không có dòng outbox chờ;
   - xóa `sync_token`;
   - chạy lại bước 1 [N26][N28].
5. **Đồng bộ đủ định kỳ.** Lần lặp nằm ngoài khung 365 ngày bị bỏ ở bước 3 sẽ không tự về khi khung trôi tới, vì Google chỉ gửi lại khi có thay đổi. Vì vậy khi `last_full_sync_at` quá 30 ngày, `sync_google_calendar` xóa `sync_token` và chạy lại bước 1. Với một người dùng, lần chạy này tốn vài lời gọi.

Google trải một chuỗi lặp vô hạn ra bao nhiêu lần trong lần đầu thì tài liệu không nói (**chưa xác minh**). Bước 3 chặn ở 365 ngày nên bảng không phình. Đo số dòng ở lần nối thật đầu tiên.

**Sửa sự kiện lặp trong app:** chỉ sửa **một lần** (dòng có `google_recurring_event_id`, `patch` theo `id` của lần đó). Sửa cả chuỗi thì app mở Google Calendar (`80-ra-cheo-lan-1.md` mục B).

### 4.4 Thông báo đẩy và chu kỳ quét

**Kênh thông báo.** Gọi `events.watch` cho lịch `primary` [N23][N29]:

- `address = {PUBLIC_BASE_URL}/api/v1/webhooks/google/calendar`. Địa chỉ phải là HTTPS có chứng chỉ hợp lệ; Cloudflare đáp ứng.
- `token` là chuỗi ngẫu nhiên riêng mỗi kênh. Lưu băm ở `channel_token_hash`.
- `params.ttl` để mặc định 604800 giây (7 ngày). Tài liệu không ghi mức tối đa.

**Nhận thông báo:** theo `12-api.md` mục 5.10.

- Máy chủ kiểm `X-Goog-Channel-ID` và băm của `X-Goog-Channel-Token`.
- Khớp thì đặt `needs_sync = true`, gửi `NOTIFY troly_wake`, trả 200 rỗng trong 1 giây.
- `X-Goog-Resource-State = sync` là lời chào lúc tạo kênh, bỏ qua.
- Thông báo không chứa dữ liệu, nên luôn phải chạy đồng bộ mục 4.3 [N23].

**Job** (tên theo `10-kien-truc-backend.md` mục 3.9; chu kỳ theo `80-ra-cheo-lan-1.md` mục A6 dòng 76):

| Job | Chu kỳ | Việc |
|---|---|---|
| `sync_google_calendar` | Khi `needs_sync = true` (gom các thông báo dồn trong 10 giây); quét dự phòng 15 phút, lệch ngẫu nhiên ±25% | Đồng bộ mục 4.3. Hai lần quét định kỳ của cùng một tài nguyên cách nhau ít nhất `GOOGLE_SYNC_MIN_SECONDS` (300 giây); đồng bộ do webhook không bị giới hạn này |
| `renew_google_watch` | Mỗi ngày | Kênh còn dưới 48 giờ thì tạo kênh mới (mã mới) rồi `channels.stop` kênh cũ. Google không tự gia hạn; hai kênh được chồng nhau một lúc [N23] |

Lệch ngẫu nhiên chu kỳ quét là cách Google khuyên để không dồn giờ [N30].

**Webhook có cần xác minh tên miền không:** hướng dẫn hiện tại chỉ yêu cầu HTTPS hợp lệ (**chưa xác minh**). Nếu `watch` bị từ chối thì thêm tên miền vào mục xác minh của Console.

### 4.5 Từ app lên Google và xử lý xung đột

Theo khung outbox của `10-kien-truc-backend.md` mục 3.9 và bảng `tab_google_outbox` của `11-co-so-du-lieu.md`:

- Sửa trong app ghi `tab_google_outbox` (`resource = calendar_event`, `op = upsert` hoặc `delete`) cùng giao dịch.
- Mỗi sự kiện chỉ có một dòng chờ. Job `push_google_outbox` đọc trạng thái **mới nhất** của dòng gốc lúc đẩy.

| Trạng thái dòng gốc | Lời gọi Google |
|---|---|
| Chưa có `google_etag` | `events.insert` với `id` đặt sẵn (mục 4.2) |
| Có `google_etag` | `events.patch` kèm `If-Match: <google_etag>` |
| `deleted_at` có giá trị | `events.delete` kèm `If-Match` |

Sự kiện có khách mời thêm `sendUpdates=all` (mục 4.6).

**Xung đột:** sự kiện đã đổi trên Google sau lần đồng bộ cuối thì Google trả **412** (`conditionNotMet`) [N31]. Luật xử lý (Google làm gốc):

1. Lấy bản mới nhất từ Google, ghi vào `tab_event`.
2. Chép thay đổi bị bỏ vào `tab_google_outbox.payload`, đặt dòng `status = conflict` (cột và giá trị mới, xem mục 13).
3. App hiện một dòng: *Sự kiện "X" vừa được sửa trên Google, đã lấy bản Google. Chạm để áp lại thay đổi của bạn.* Chạm thì tạo dòng `upsert` mới từ `payload`.

**Xóa trên Google trong khi app đang sửa:** `patch` trả 404 hoặc 410. Coi như đã xóa: đặt `deleted_at`, bỏ dòng outbox, báo một dòng.

**Thử lại:** theo `10-kien-truc-backend.md` mục 3.9. Lỗi tạm (mạng, 5xx, 429, 403 `rateLimitExceeded`) thì `next_attempt_at = now() + 30 giây × 2^(attempts−1)`, tối đa 6 lần. Lỗi vĩnh viễn thì `failed`.

### 4.6 Mời khách (QĐ-23)

- **Công cụ `add_event`** (`20-bo-nao-ai.md`) có `attendee_emails`. Danh sách rỗng thì ghi thẳng như mục 4.5. Có khách thì công cụ **không ghi `tab_event`**. Nó tạo `tab_pending_action` với `kind = invite_event`, kèm `payload_hash`, và trả hành động `confirm` (`require_unlock = true`). Thẻ hiện tiêu đề, giờ, địa điểm và **danh sách email sẽ nhận lời mời**.
- **Duyệt** (`POST /api/v1/chat/actions/{id}/approve`, `12-api.md`):
  - hàm thực thi tạo `tab_event` và dòng outbox;
  - worker gọi `events.insert` với `attendees` và `sendUpdates=all`, để Google gửi thư mời cho mọi khách [N69].
- **Sửa hoặc xóa sự kiện có khách** (người dùng là người tổ chức) cũng phải duyệt (`60-bao-mat-rieng-tu.md` mục 3.12): sửa dùng `kind = invite_event` (công cụ `update_event`), xóa dùng `kind = delete_event`. Thẻ duyệt ghi rõ *Google sẽ báo thay đổi cho N khách*. Lời gọi `patch`, `delete` kèm `sendUpdates=all`.
- **Sự kiện người khác mời** (`organizer.self` không phải `true`): app chỉ cho đổi nguồn nhắc, không sửa nội dung, vì sửa trên bản của khách không đổi được sự kiện gốc. Trả lời lời mời (đồng ý, từ chối) để sau (xem *Câu hỏi mở*).
- **Sự kiện không có khách:** không gửi `sendUpdates`, dùng mặc định. Tài liệu cảnh báo `none` có thể làm sự kiện không đồng bộ sang lịch ngoài [N69].
- **Sửa từ màn Lịch** (không qua chat) mà có khách: giao diện gọi API sửa sự kiện. Máy chủ thấy có khách thì trả `pending_action` để hiện cùng thẻ duyệt, không ghi ngay (xem *Cần agent khác*).

### 4.7 Nhắc trùng giữa Google và app

Trên máy thường có cả app Google Calendar; cả hai cùng nhắc thì một sự kiện kêu hai lần. Luật (ĐX-G6, đã chấp nhận ở QĐ-25): **mỗi sự kiện có một nguồn nhắc**, cột `tab_event.remind_source`.

| Sự kiện tạo ở | `remind_source` mặc định | App làm gì | Gửi lên Google |
|---|---|---|---|
| App (chat, chạm, việc có giờ, lịch trình) | `app` | Đặt nhắc bằng `AlarmManager` theo `remind_minutes` | `reminders.useDefault=false`, `overrides=[]`: Google không nhắc |
| Google | `google` | Không đặt nhắc, chỉ hiển thị | Giữ nhắc của Google |

- `GET /api/v1/calendar/reminders` chỉ trả sự kiện có `remind_source = app` (`80-ra-cheo-lan-1.md` mục A2 dòng 27).
- Người dùng đổi được nguồn nhắc từng sự kiện:
  - đổi sang `app`: app đặt nhắc, đẩy `overrides=[]` lên Google;
  - đổi sang `google`: app bỏ nhắc, đẩy `useDefault=true`.
- Mỗi sự kiện Google cho tối đa 5 nhắc riêng, mỗi nhắc từ 0 tới 40320 phút [N25].

### 4.8 Hạn mức

Calendar API tính 10.000 lời gọi mỗi phút mỗi dự án và 600 mỗi phút mỗi người dùng. Có ngưỡng tính phí 1.000.000 lời gọi mỗi ngày mỗi dự án; Google báo sẽ thu phí sau năm 2026 và báo trước 90 ngày [N30]. Một người dùng, quét 15 phút một lần: khoảng 100 tới 300 lời gọi mỗi ngày.

## 5. Thiết kế: Google Tasks (app làm gốc, đọc ngược trạng thái theo QĐ-21)

### 5.1 Giới hạn của Tasks API

- `due` **chỉ lưu ngày, phần giờ bị bỏ** [N32].
- Không có trường nhắc, giờ, ưu tiên, gắn sao [N32].
- Không có thông báo đẩy; API chỉ có thêm, sửa, xóa, liệt kê, di chuyển, dọn [N33].
- `title` tối đa 1024 ký tự, `notes` tối đa 8192 ký tự [N32].
- `tasks.list` trả tối đa 100 việc mỗi trang [N34].

### 5.2 Đẩy từ app lên Google

1. Khi bật dịch vụ `tasks` lần đầu: `tasklists.insert` danh sách tên *Trợ lý*. Lưu mã vào `tab_google_sync_state` (`resource = tasks`, `resource_id` = mã danh sách).
2. Chỉ việc **không có giờ** mới lên Google Tasks: `due_date` có giá trị, hoặc không có hạn. Việc có `due_at` sinh sự kiện lịch (mục 4), không lên Tasks.
   - Thêm giờ cho việc đang ở Tasks thì xóa bản trên Tasks và tạo sự kiện.
   - Bỏ giờ thì ngược lại.
3. Thay đổi đi qua `tab_google_outbox` (`resource = task`). Job `push_google_outbox` gọi `tasks.insert`, `patch` hoặc `delete`. Trường đẩy lên:

   | Google Tasks | Từ `tab_task` |
   |---|---|
   | `title` | `title` |
   | `notes` | `note`, thêm dòng *Ưu tiên: cao* khi `priority = high` |
   | `due` | `due_date` ở dạng `YYYY-MM-DDT00:00:00.000Z` |
   | `status` | `needsAction` hoặc `completed` |

   Sau mỗi lần đẩy, lưu `etag` và `updated` của Google vào `google_etag`, `google_updated_at` (cột mới, mục 13).

### 5.3 Đọc ngược trạng thái xong và đã xóa (QĐ-21)

Job mới `sync_google_tasks`, chu kỳ 15 phút, lệch ±25%, tôn trọng `GOOGLE_SYNC_MIN_SECONDS`. Thuật toán:

1. **Mốc đọc.** `since = last_sync_at − 2 phút`. Lùi 2 phút để không lọt thay đổi xảy ra đúng lúc đọc; xử lý ở bước 3 là idempotent nên đọc trùng không sao. Lần đầu (`last_sync_at` rỗng) không đặt `updatedMin`.
2. **Đọc.** Gọi `tasks.list(tasklist=<Trợ lý>, updatedMin=since, showCompleted=true, showDeleted=true, showHidden=true, maxResults=100)`, lật hết trang [N34]. Cần `showHidden=true` vì việc xong đã bị *dọn* trong app Google chỉ hiện khi bật cờ này [N34].
3. **Với mỗi việc nhận về:**

   1. Tìm `tab_task` theo `(user_id, google_task_id)`. Không thấy thì bỏ qua: việc người dùng tự thêm thẳng vào danh sách *Trợ lý* không được nhận về (xem *Câu hỏi mở*).
   2. `updated` của Google không mới hơn `google_updated_at` đang lưu: bỏ qua (tiếng vọng của lần đẩy từ app).
   3. Dòng có outbox đang chờ thì áp **luật gộp** (dưới bước 3) rồi mới ghi.
   4. So trạng thái:

      | Google | App | Làm |
      |---|---|---|
      | `deleted = true` | Chưa xóa | Xóa mềm (`deleted_at = now`), giữ 30 ngày. App hiện một dòng *Việc "X" đã bị xóa trên Google Tasks* kèm **Hoàn tác**. Hoàn tác thì bỏ `deleted_at`, xóa `google_task_id`, tạo outbox `upsert`, nên việc được tạo lại trên Google |
      | `status = completed` | `todo` | `status = done`, `completed_at` = `completed` của Google |
      | `status = needsAction` | `done` | `status = todo`, xóa `completed_at` (người dùng bỏ tích trên Google) |
      | Khác `title`, `notes`, `due` | | **Không nhận**. App làm gốc; lần đẩy sau từ app ghi đè. Không tự đẩy lại ngay để tránh vòng lặp |

   5. Ghi `google_etag`, `google_updated_at` mới, `sync_status = synced`. Không tạo dòng outbox cho thay đổi đọc về.

   **Luật gộp khi cả hai phía cùng đổi:**

   - Google *xong*, app đang chờ sửa nội dung: lấy *xong*, giữ sửa nội dung; dòng outbox vẫn đẩy, kèm `status = completed`.
   - Google *đã xóa*, app đang chờ sửa: xóa thắng. Bỏ dòng outbox, báo một dòng kèm **Hoàn tác** như bảng trên.
   - App đang chờ xóa: bỏ qua dữ liệu đọc về.
4. **Kết thúc lượt:** cập nhật `last_sync_at = thời điểm bắt đầu lượt đọc`.
5. **`patch` trả 404 khi đẩy:** xử lý như *đã xóa* ở bước 3.

### 5.4 Nhắc trùng

Google Tasks không có nhắc theo giờ qua API. App nhắc việc bằng `AlarmManager` theo cài đặt trong app. App Google có thể hiện việc có ngày theo cài đặt riêng của người dùng (**chưa xác minh** cách Google nhắc việc chỉ có ngày). Thấy trùng thì tắt thông báo Tasks trong app Google.

### 5.5 Hạn mức

Mặc định 50.000 lời gọi mỗi ngày mỗi dự án [N35]. Quét 15 phút một lần: khoảng 100 lời gọi mỗi ngày.

## 6. Thiết kế: Gmail (hộp tin, tìm thư, nháp, gửi qua thẻ duyệt)

### 6.1 Scope

| Việc | Scope tối thiểu | Mức |
|---|---|---|
| Đọc thư, lịch sử, tìm thư | `gmail.readonly` | Hạn chế |
| Tạo nháp, gửi nháp | `gmail.compose` (scope này gửi được) | Hạn chế |

Nguồn: [N7][N36].

- `gmail.send` chỉ ở mức nhạy cảm, nhưng không tạo được nháp.
- `gmail.metadata` không đọc được nội dung và không dùng được `q` để tìm [N37].

Đọc thư kiểu gì cũng cần scope hạn chế, nên dự án dựa vào diện miễn xác minh cá nhân (mục 3.1).

### 6.2 Đồng bộ vào hộp tin

Job `sync_gmail` (`10-kien-truc-backend.md`), chu kỳ **5 phút**, đúng bằng `GOOGLE_SYNC_MIN_SECONDS` (ĐX-G7, `80-ra-cheo-lan-1.md` mục C).

1. **Lần đầu:**
   - `messages.list(q="in:inbox newer_than:7d", maxResults=100)`;
   - rồi `messages.get(format=metadata, metadataHeaders=[From, Subject, Date])` cho từng thư;
   - lưu `historyId` lớn nhất vào `tab_google_sync_state.history_id` [N38].
2. **Các lần sau:** `history.list(startHistoryId=..., historyTypes=messageAdded, labelId=INBOX)`, lật hết trang, lưu `historyId` mới [N39].
3. **Lỗi 404** (`startHistoryId` quá cũ): chạy lại bước 1. Lịch sử thường giữ ít nhất một tuần, có khi chỉ vài giờ [N38][N39].
4. **Lọc trước khi vào hộp tin:**
   - Bỏ thư có nhãn `CATEGORY_PROMOTIONS`, `CATEGORY_SOCIAL`, `CATEGORY_FORUMS`, `SPAM`, `TRASH` [N40].
   - Bỏ thư chứa mã OTP theo bộ từ khóa của `60-bao-mat-rieng-tu.md` mục 3.8. Lọc ngay khi đọc, không lưu.
5. **Ghi `tab_inbox_message`** theo tên cột của `11-co-so-du-lieu.md`:

   | Cột | Giá trị |
   |---|---|
   | `source`, `app` | `gmail` |
   | `sender` | Tên lấy từ Contacts nếu có (mục 7), không thì tên trong `From` |
   | `sender_key` | `gmail:<email đã chuẩn hóa>` |
   | `contact_id` | Nếu khớp danh bạ |
   | `subject` | Tiêu đề thư |
   | `text` | `snippet` của Gmail, tối đa 4.000 ký tự |
   | `external_id`, `thread_ref` | Mã thư, mã luồng |
   | `posted_at` | Header `Date`, không có thì `internalDate` |
   | `importance`, `importance_reason` | `important` với lý do `gmail_important` khi thư có nhãn `IMPORTANT`; theo `tab_inbox_rule` (`vip_sender`, `urgent_keyword`) |
   | `labels` | Nhãn Gmail (cột mới, mục 13) |
   | `dedupe_hash` | Theo `11-co-so-du-lieu.md` |

6. **Thời hạn:** đoạn trích Gmail trong hộp tin giữ **180 ngày** như mọi tin của người khác (QĐ-17). Hộp tin không lưu nội dung đầy đủ của thư.

**Thông báo đẩy qua Pub/Sub** (`users.watch`) làm được. Nhưng cần chủ đề Pub/Sub, cấp quyền đăng cho `gmail-api-push@system.gserviceaccount.com`, và gọi lại `watch` ít nhất 7 ngày một lần [N41]; Pub/Sub miễn phí 10 GiB mỗi tháng [N42]. V1.8 dùng quét (`12-api.md` mục 5.10, ĐX-API-05). Pub/Sub để dành khi cần báo thư gấp tức thì.

### 6.3 Công cụ AI cho Gmail

Tên theo `20-bo-nao-ai.md`, đặt trong module `inbox`.

| Công cụ | Lời gọi Gmail | Ghi chú |
|---|---|---|
| `search_gmail` | `messages.list(q=...)` rồi `messages.get(format=metadata)` | Trả `thread_id`, người gửi, tiêu đề, `snippet`, ngày |
| `get_gmail_thread` | `threads.get(format=full)` | Bỏ HTML, cắt 4.000 ký tự. Kết quả nằm trong `tab_message` với `contains_third_party = true` và tuân luật dọn của `60-bao-mat-rieng-tu.md` |
| `create_gmail_draft` | `drafts.create` | Mục 6.4 |
| `send_gmail_draft` | `drafts.send` sau khi duyệt | Mục 6.4 |

Chưa nối Gmail thì mọi công cụ trả `GOOGLE_NOT_CONNECTED` kèm `open_screen` tới `settings_google`. Nội dung thư trả cho Claude theo luật bên thứ ba của `60-bao-mat-rieng-tu.md` mục 3.9 (trong `du_lieu_ngoai`, cắt ngắn).

### 6.4 Soạn nháp và gửi qua thẻ duyệt

Gửi thư chỉ có **một đường**: hành động chờ duyệt `tab_pending_action` với `kind = send_gmail` (`80-ra-cheo-lan-1.md` mục A3 dòng 36). Không có API gửi riêng.

1. **Soạn.** `create_gmail_draft` dựng thư RFC 2822; trả lời trong luồng thì có `In-Reply-To`, `References` và tiêu đề trùng [N43]. Sau đó:
   - gọi `drafts.create` [N44];
   - lưu `tab_gmail_draft` (`status = draft`, `body_hash` = SHA-256 của người nhận, tiêu đề, nội dung);
   - trả hành động `open_link` (`kind = gmail`) để xem nháp trong Gmail.

   Soạn nháp không cần duyệt (`60-bao-mat-rieng-tu.md` mục 3.12).
2. **Xin gửi.** `send_gmail_draft(draft_id)`:
   - tạo `tab_pending_action` (`kind = send_gmail`, `payload_hash` = `body_hash`, hạn 24 giờ);
   - trả `confirm`, hiện người nhận, tiêu đề, đoạn đầu; `require_unlock = true` (đòi vân tay).

   Claude không được nói *đã gửi*.
3. **Duyệt.** `POST /api/v1/chat/actions/{id}/approve`. Hàm thực thi:
   1. kiểm chủ sở hữu, hạn, trạng thái;
   2. gọi `drafts.get`, tính lại băm của bản đang có trên Gmail. Băm khác `payload_hash` (nháp bị sửa trên Gmail sau khi tạo thẻ) thì **không gửi**: đặt hành động `failed` với câu *Nháp đã bị sửa, hãy xem lại và xin gửi lại*;
   3. khớp thì `drafts.send` [N44], lưu `sent_message_id`, `tab_gmail_draft.status = sent`.
4. **Bỏ** (`/reject`): hành động `rejected`. Nháp vẫn nằm trong Gmail để người dùng tự xử lý.

Gmail cá nhân giới hạn 500 người nhận mỗi thư và 500 thư mỗi ngày [N45]. Ở đây gửi từng thư một nên không chạm tới.

### 6.5 Hạn mức

Từ 01/05/2026: 1.200.000 đơn vị mỗi phút mỗi dự án và 6.000 đơn vị mỗi phút mỗi người dùng [N46].

| Lời gọi | Đơn vị |
|---|---|
| `history.list` | 2 |
| `messages.list` | 5 |
| `messages.get` dạng `metadata` | 20 |
| `messages.get` dạng `full` | 60 |
| `threads.get` (dạng `full`) | 40 (120) |
| `drafts.create` | 10 |
| `drafts.send` | 100 |
| `watch` | 100 |

Một người, 50 thư mỗi ngày: 288 lần quét × 2, cộng 50 thư × 20, cộng vài lần đọc chuỗi. Tổng khoảng 2.000 tới 3.000 đơn vị mỗi ngày.

### 6.6 Trùng với thông báo Android

Nghe cả ứng dụng Gmail qua thông báo thì một thư vào hộp tin hai lần. Luật:

- Khi dịch vụ `gmail` đã bật, gói `com.google.android.gm` bị loại khỏi danh sách nghe (`30-app-android.md`).
- Trước khi nối, người dùng có thể nghe Gmail qua thông báo.
- Lúc chuyển sang Gmail API, tin trùng gộp theo `dedupe_hash` và theo (người gửi, tiêu đề, cách nhau dưới 10 phút).

## 7. Thiết kế: Google Contacts (People API, chỉ đọc)

- **Dùng để:**
  - đổi email hoặc số điện thoại thành tên trong hộp tin (`tab_inbox_message.contact_id`);
  - chọn *người quan trọng* (`tab_inbox_rule.kind = vip_sender`) từ danh bạ;
  - nhắc sinh nhật;
  - công cụ `lookup_contact` (`20-bo-nao-ai.md`).
- **Scope:** `contacts.readonly`.
- **Job:** `sync_google_contacts` (`10-kien-truc-backend.md`), mỗi ngày 04:00.
  1. **Lần đầu:** `people.connections.list(resourceName=people/me, personFields=names,emailAddresses,phoneNumbers,birthdays, pageSize=1000, requestSyncToken=true)`. Trang cuối có `nextSyncToken` [N47].
  2. **Lần sau:** gọi với `syncToken` và **cùng tham số như lần đầu**. Liên hệ đã xóa có `metadata.deleted = true`; xóa dòng `tab_contact` tương ứng [N47].
  3. **Sync token hết hạn** 7 ngày sau lần đồng bộ đủ, lỗi `EXPIRED_SYNC_TOKEN`; khi đó đồng bộ đủ lại. Tài liệu mẫu xử lý bằng mã 410, trang tham chiếu chỉ ghi tên lỗi, nên mã xử lý cả hai [N47][N48]. Quét mỗi ngày thì nằm trong hạn 7 ngày.
- **Sinh nhật không có năm:** lưu năm 1900 như `11-co-so-du-lieu.md`. Giao diện không hiện tuổi khi năm là 1900.
- **Không đọc** *Danh bạ khác* (`otherContacts`); muốn có thì thêm scope `contacts.other.readonly` (xem *Câu hỏi mở*).
- **Nhắc trùng sinh nhật:** Google Calendar có sẵn lịch *Sinh nhật* lấy từ danh bạ. Nhắc sinh nhật của app mặc định **tắt** (`tab_contact.remind_birthday = false`, cột mới); người dùng bật cho từng người.
- **Hạn mức:** tài liệu không ghi con số cho lời gọi đọc (**chưa xác minh**; xem trang Quotas của Console). Trang đầu của lần đồng bộ đủ có quota riêng không tăng được, vượt thì 429 [N47].

## 8. Thiết kế: Google Drive và Google Sheets

### 8.1 Drive: chỉ dùng `drive.file`

- **Mức quyền:**
  - `drive.file` là scope **không nhạy cảm**, chỉ thấy tệp do app tạo, tệp người dùng mở bằng app, và tệp được chia cho app qua hộp chọn [N9].
  - `drive`, `drive.readonly` là scope hạn chế, không dùng [N9].
  - Vì vậy không có công cụ AI duyệt hay tìm tệp Drive của người dùng. Hai công cụ `list_drive_files`, `import_drive_file` đã bị bỏ (`80-ra-cheo-lan-1.md` mục C).
- **Thư mục *Trợ lý*.** Bật dịch vụ `drive` lần đầu thì tạo thư mục *Trợ lý* (`mimeType = application/vnd.google-apps.folder`) [N49]. Mã thư mục lưu ở khóa cài đặt `google.drive_folder_id` (mới, mục 13).
- **Lưu tệp lên Drive.** Tệp xuất (Word lịch trình, báo cáo) tải lên thư mục này:
  - tệp tới 5 MB tải `multipart`, lớn hơn tải `resumable` [N50];
  - mã tệp ghi vào `tab_file.drive_file_id`.

  Giữ dạng `.docx`. Chuyển sang Google Docs làm được bằng cách đặt `mimeType` đích [N50], nhưng không bật mặc định.
- **Nhập tệp từ Drive** (ví dụ tệp lịch trình): dùng **hộp chọn tệp của Android** (Storage Access Framework, `ACTION_OPEN_DOCUMENT`).
  - Hộp chọn hiện cả nguồn lưu trên mạng, không cần quyền hệ thống, không cần scope Drive [N51].
  - App đọc tệp rồi tải lên như mọi tệp khác.
  - Google Drive có hiện trong hộp chọn hay không thì tài liệu Android không nêu tên (**chưa xác minh**, thử trên máy).
- **Google Picker không dùng.** Picker không hiện trong WebView nhúng, và trên Android phải đi qua `AuthorizationRequest` gốc, chỉ với `drive.file` [N52][N53].
- **Chia sẻ tệp cho người khác** không có ở V1.8. Nếu làm thì phải qua thẻ duyệt (`60-bao-mat-rieng-tu.md` mục 3.12).
- **Hạn mức** (từ 01/05/2026): 1.000.000 đơn vị mỗi phút mỗi dự án; `files.create` tốn 50 đơn vị, `files.get` tốn 5 [N54].

### 8.2 Sheets: tạo bằng `drive.file`

- `spreadsheets.create` chấp nhận scope `drive.file` [N10]. App tạo bảng tính *Chi tiêu – Trợ lý* trong thư mục *Trợ lý* và ghi mãi vào bảng đó, vì là tệp do app tạo. Không cần scope `spreadsheets` [N11].
- **Luồng xuất:**
  1. Công cụ `export_expenses_to_sheets` (`20-bo-nao-ai.md`) hoặc màn *Báo cáo* gọi `POST /api/v1/reports/exports` với `kind = expense_sheet` (`12-api.md`).
  2. Job `run_queued_jobs` chạy việc `export_report`.
  3. Kết quả ghi `tab_export` (`google_file_id`, `url`).

  Mã bảng tính dùng lại lưu ở khóa `google.expense_spreadsheet_id` (mới).
- **Ghi:** mỗi tháng một trang tính `YYYY-MM`. Ghi lại cả trang bằng `values.batchUpdate`, không nối từng dòng, để sửa trong app thì bảng cũng khớp.
- **Chiều:** chỉ ghi. Sửa trên Sheets thì lần xuất sau bị ghi đè; dòng đầu trang tính ghi rõ điều này.
- **Hạn mức:** đọc và ghi đều là 300 lời gọi mỗi phút mỗi dự án và 60 mỗi phút mỗi người dùng. Vượt thì 429; lời gọi quá 180 giây bị cắt [N55].

## 9. Thiết kế: Google Maps Platform (gọi từ máy chủ)

Chi tiết cho lịch trình ở [41-ban-do-lich-trinh.md](41-ban-do-lich-trinh.md). Phần chung:

- **Một khóa API cho máy chủ** (`GOOGLE_MAPS_API_KEY`, `10-kien-truc-backend.md`):
  - giới hạn theo IP của VPS;
  - chỉ cho Places API (New), Routes API, Geocoding API.

  Khóa dịch vụ web không được lộ ở phía client [N56].
- **Mở bản đồ không cần khóa:** Maps URLs và lệnh Android `google.navigation` không cần khóa, không tính tiền [N57][N58].
- **Mức miễn phí:** từ 01/03/2025 Google bỏ khoản tín dụng 200 USD hằng tháng, thay bằng mức miễn phí riêng mỗi SKU mỗi tháng [N59][N60]:

  | Tầng SKU | Miễn phí mỗi tháng |
  |---|---|
  | Essentials | 10.000 |
  | Pro | 5.000 |
  | Enterprise | 1.000 |

- **Vẫn phải gắn tài khoản thanh toán** [N61].
- **Ngân sách không chặn chi tiêu.** Chặn cứng bằng quota theo ngày ở trang *Quotas*; chạm quota thì API đó lỗi tới hết ngày [N62]. Mức đặt ở mục 11.

## 10. Thiết kế: lỗi và thử lại

Theo khung của `10-kien-truc-backend.md` mục 3.9 (`80-ra-cheo-lan-1.md` mục A6 dòng 77): không có cơ chế thử lại riêng cho Google.

| Lỗi Google | Nghĩa | Xử lý |
|---|---|---|
| 401 | Access token hết hạn | Làm mới một lần rồi gọi lại ngay, không tính là thử lại |
| `invalid_grant` khi làm mới | Refresh token hỏng | Mục 3.5; mã lỗi API `GOOGLE_REAUTH_REQUIRED` |
| 403 `insufficientPermissions` | Thiếu scope của dịch vụ | Tắt dịch vụ đó, báo *Cấp quyền*; mã lỗi `GOOGLE_REAUTH_REQUIRED` |
| 403 `userRateLimitExceeded`, `rateLimitExceeded`, 429, 5xx, hết thời gian | Lỗi tạm | Dòng hàng chờ: `30 giây × 2^(attempts−1)`, tối đa 6 lần. Job đồng bộ: dừng lượt này, giữ `needs_sync`, lượt sau chạy lại. Mã lỗi `EXTERNAL_SERVICE_ERROR` nếu người dùng đang chờ |
| 403 `quotaExceeded`, `dailyLimitExceeded` | Hết quota ngày | Dừng dịch vụ tới ngày mai, ghi `tab_google_sync_state.last_error` |
| 404, 410 | Đã xóa, hoặc token đồng bộ hết hạn | Theo từng dịch vụ (4.3, 4.5, 5.3, 6.2, 7) |
| 412 | Xung đột `etag` | Mục 4.5 |

Chưa nối Google: API và công cụ AI cùng trả `GOOGLE_NOT_CONNECTED` (ĐX-AI-16).

Dòng outbox `failed` hoặc `conflict` hiện ở *Cài đặt > Google > Lỗi đồng bộ*, có nút *Thử lại*. API cho màn này nằm trong yêu cầu gửi `12-api.md` (mục 18).

## 11. Thiết kế: bước người dùng tự làm trên Google Cloud Console

Làm một lần, bằng tài khoản Google chủ dự án. Không bước nào cần xác minh với Google.

1. **Tạo dự án** `troly` tại `console.cloud.google.com`. Gắn tài khoản thanh toán (Maps Platform bắt buộc). Tài khoản mới có tín dụng dùng thử 300 USD trong 90 ngày [N61].
2. **Bật API** (*APIs & Services > Library*): Google Calendar API, Google Tasks API, Gmail API, People API, Google Drive API, Google Sheets API, Places API (New), Routes API, Geocoding API.
3. **Màn đồng ý** (*Google Auth Platform*):
   1. *Branding*:
      - tên app *Trợ lý*, email hỗ trợ;
      - tên miền được phép `baohuynh.io.vn`;
      - đường dẫn trang chủ và chính sách riêng tư: trang tĩnh do agent hạ tầng dựng.
   2. *Audience*: **External**. Trong lúc dựng, thêm email của người dùng vào *Test users*.
   3. *Data access*: thêm các scope ở mục 3.2. Ghi lại nhãn mức Console hiện cho Calendar, Tasks, Contacts để cập nhật bảng 3.1.
   4. Khi V1.4 chạy ổn: *Audience > Publish app*, chuyển **In production**. Không gửi xác minh.
4. **Tạo client OAuth** (*Clients > Create client*):
   - loại **Web application**;
   - redirect URI `https://<api-domain>/api/v1/google/oauth/callback`. Đây là `PUBLIC_BASE_URL` cộng đường dẫn cố định; máy chủ dựng từ `PUBLIC_BASE_URL`, không có biến riêng (ĐX-G14). Máy dựng dùng một client riêng có redirect về địa chỉ thử; kiểm luật redirect localhost của Google khi dựng;
   - ghi `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` vào `.env` của VPS. Không gửi qua chat.
5. **Tạo khóa Maps** (*Credentials > Create credentials > API key*):
   - *Application restrictions*: IP addresses, nhập IP công khai của VPS;
   - *API restrictions*: Places API (New), Routes API, Geocoding API;
   - ghi `GOOGLE_MAPS_API_KEY` vào `.env`.
6. **Chặn chi tiêu** (*Google Maps Platform > Quotas*), quota mỗi ngày:

   | API | Quota mỗi ngày |
   |---|---|
   | Places API (New) | 300 lời gọi |
   | Routes API, Compute Routes | 30 lời gọi (SKU Enterprise khi đi xe hai bánh, 1.000 mỗi tháng) |
   | Routes API, Compute Route Matrix | 300 phần tử |
   | Geocoding API | 300 lời gọi |

   Thêm *Billing > Budgets & alerts*: ngân sách 1 USD, cảnh báo ở 50% và 100%. Cách tính ở `41-ban-do-lich-trinh.md` mục 7.3.
7. **Người dùng** mở app, vào *Cài đặt > Kết nối Google*, chọn tài khoản, bấm qua cảnh báo chưa xác minh, tích đủ quyền.

## 12. Thiết kế: Health Connect (V2, ghi trước)

Health Connect chạy trên điện thoại, không qua OAuth hay máy chủ Google.

- **Máy hỗ trợ:**
  - Android 14 trở lên có sẵn trong hệ điều hành; Samsung Galaxy S25+ của người dùng (QĐ-19) thuộc nhóm này.
  - Android 9 tới 13 phải cài app Health Connect từ Play.
  - Cần Google Play services [N63][N64].
- **Thư viện:** `androidx.health.connect:connect-client`, gọi từ plugin `health/`. Bản ổn định hiện là 1.1.0, cần compileSdk 36. Bản mới nhất là 1.2.0-alpha06 [N68]. Phiên bản dùng do `30-app-android.md` chốt.
- **Quyền:**
  - khai `android.permission.health.READ_STEPS`, `READ_SLEEP`, `READ_HEART_RATE`;
  - Android 13 trở xuống cần activity nhận `androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE`;
  - Android 14 trở lên cần activity-alias cho `VIEW_PERMISSION_USAGE` [N63].
- **Lịch sử:** chỉ đọc được 30 ngày trước lần cấp quyền đầu, trừ khi xin `READ_HEALTH_DATA_HISTORY`. Đọc khi app chạy ngầm cần `READ_HEALTH_DATA_IN_BACKGROUND` [N65].
- **Đồng bộ:** mỗi loại dữ liệu một token thay đổi. Token không dùng hết hạn trong 30 ngày, nên phải có đường đọc lại [N66]. Gửi lên máy chủ chỉ số tổng hợp theo ngày (`tab_health_daily`).
- **Rủi ro lớn nhất:** Google yêu cầu khai báo ứng dụng sức khỏe khi phát hành qua Play [N67]. Tài liệu không nói APK cài ngoài Play có được cấp quyền không (**chưa xác minh**). Phải dựng thử trên máy thật trước khi thiết kế chi tiết V2.

## 13. Dữ liệu cần

Bảng gốc ở `11-co-so-du-lieu.md` mục 3.10 tới 3.12; tệp này dùng đúng tên ở đó. Dưới đây chỉ là **phần thêm hoặc sửa**, mọi khóa và id là `bigint` theo quy ước của 11.

| Bảng | Thêm hoặc sửa | Lý do |
|---|---|---|
| `tab_google_account` | Không đổi | Dịch vụ đang bật nằm ở khóa `google.services` |
| `tab_google_sync_state` | Không đổi. Tasks dùng `last_sync_at` làm mốc `updatedMin`; `resource_id` của `tasks` là mã danh sách *Trợ lý* | |
| `tab_google_outbox` | Thêm `payload jsonb` (rỗng khi bình thường; giữ thay đổi bị bỏ khi xung đột) và giá trị `status = conflict`. Giữ `processing` theo 11 (bỏ tên `running` của bản 1) | Mục 4.5. Giá trị `resource`, `op` của 11 đủ dùng: Gmail đi qua `tab_pending_action`, Drive và Sheets đi qua `tab_job_queue` |
| `tab_event` | Thêm `remind_source text NN CK ('app','google') default 'app'`. Dòng kéo từ Google đặt `google` | Mục 4.7 (ĐX-G6) |
| `tab_task` | Thêm `google_etag text`, `google_updated_at timestamptz` | Mục 5.3 |
| `tab_inbox_message` | Thêm `labels text[] NN default '{}'` | Mục 6.2 |
| `tab_contact` | Thêm `remind_birthday boolean NN default false` | Mục 7 |
| `tab_pending_action` | Dùng `kind` của `20-bo-nao-ai.md` mục 3.8: `send_gmail`, `invite_event` (tạo, sửa sự kiện có khách), `delete_event` | Mục 4.6, 6.4 |
| `tab_setting` | Khóa mới `google.drive_folder_id` (chữ), `google.expense_spreadsheet_id` (chữ) | Mục 8 |
| Chính sách xóa | `tab_inbox_message` giữ 180 ngày (QĐ-17) | |

**`tab_gmail_draft`** (mới, V1.8, đặt ở `integrations/google/models.py` hoặc module `inbox` do agent kiến trúc chọn):

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| (cột chung) | | | |
| google_account_id | bigint | NN, FK `tab_google_account` CASCADE | |
| google_draft_id | text | NN | |
| thread_ref | text | | Trả lời trong luồng |
| to_emails, cc_emails | citext[] | NN, default `{}` | |
| subject | text | NN | |
| body | text | NN | Giữ 180 ngày như tin của người khác khi là thư trả lời |
| body_hash | text | NN | SHA-256 của người nhận, tiêu đề, nội dung |
| status | text | NN, CK `draft`, `sent`, `failed`, `discarded` | |
| pending_action_id | bigint | FK `tab_pending_action` SET NULL | |
| sent_message_id | text | | |

UQ `(user_id, google_draft_id)`.

**Không cần** bảng `tab_google_oauth_state` của bản 1: `state` được mã hóa (ĐX-G11).

## 14. API hoặc giao tiếp

**REST** (theo `12-api.md`, tiền tố `/api/v1`, phong bì `{success, message, data}`):

| Phương thức, đường dẫn | Dùng ở mục |
|---|---|
| `GET /api/v1/google/account` | 3.3, màn *Cài đặt > Google* |
| `POST /api/v1/google/connect` (`services`) | 3.2, 3.3 |
| `GET /api/v1/google/oauth/callback` | 3.3; trả HTML chuyển về `troly://cai-dat/google?ket-qua=...` |
| `POST /api/v1/google/disconnect` | 3.6 |
| `POST /api/v1/webhooks/google/calendar` | 4.4 |
| `GET /api/v1/calendar/reminders` | 4.7; chỉ `remind_source = app` |
| `POST /api/v1/chat/actions/{id}/approve`, `/reject` | 4.6, 6.4 |
| `POST /api/v1/reports/exports` (`kind = expense_sheet`) | 8.2 |
| `GET /api/v1/jobs/{id}` | Đồng bộ lần đầu, xuất |

**Đề nghị thêm vào `12-api.md`** (mục 18):

| Phương thức, đường dẫn | Dùng ở mục |
|---|---|
| `POST /api/v1/google/sync` (`resource`) | Người dùng bấm *Đồng bộ ngay* |
| `GET /api/v1/google/outbox?status=failed,conflict` | Màn *Lỗi đồng bộ* |
| `POST /api/v1/google/outbox/{id}/retry` | Thử lại một dòng |
| `POST /api/v1/google/outbox/{id}/reapply` | Áp lại thay đổi bị bỏ khi xung đột |
| `PATCH /api/v1/calendar/events/{id}` | Khi sự kiện có khách thì trả `{pending_action}` thay vì ghi ngay (4.6) |

**Job** (tên theo `10-kien-truc-backend.md` mục 3.9):

| Job | Chu kỳ | Ghi chú |
|---|---|---|
| `push_google_outbox` | Mỗi vòng, lô 20 | Calendar, Tasks |
| `sync_google_calendar` | Webhook; quét 15 phút ±25% | 10 ghi 10 phút; đề nghị đổi |
| `renew_google_watch` | Mỗi ngày, kênh còn dưới 48 giờ | 10 ghi 6 giờ, dưới 24 giờ; đề nghị đổi |
| `sync_google_tasks` | 15 phút ±25% | **Mới**, QĐ-21 |
| `sync_gmail` | 5 phút | 10 ghi 10 phút; đề nghị đổi |
| `sync_google_contacts` | Mỗi ngày 04:00 | |
| `run_queued_jobs` | | Kiểu `google_initial_sync`, `export_report` |

**Chỗ đặt mã:**

- `integrations/google/` giữ client từng dịch vụ, `oauth.py`, và bảng `tab_google_*` (`integrations/google/models.py`, theo `11-co-so-du-lieu.md`).
- `integrations/google/` không đọc ghi bảng nghiệp vụ (`tab_event`, `tab_task`, `tab_inbox_message`...).
- Module `calendar`, `task`, `inbox`, `report`, `trip` gọi `integrations.google.*` và ghi `tab_google_outbox` trong `service.py` của mình.
- Job đặt trong `jobs.py` của module hoặc ở `worker/jobs/` theo ĐX-KT-02.

**Công cụ AI** (tên theo `20-bo-nao-ai.md`):

| Module | Công cụ |
|---|---|
| `inbox` | `search_gmail`, `get_gmail_thread`, `create_gmail_draft`, `send_gmail_draft` (duyệt), `lookup_contact` |
| `report` | `export_expenses_to_sheets` |
| `calendar` | `add_event` (duyệt khi có `attendee_emails`), `update_event` (duyệt khi sự kiện có khách) |

Không có công cụ Drive.

**Hành động trả cho app** (theo `20-bo-nao-ai.md` mục 3.8): `open_link` (`kind = gmail` cho nháp, `sheet` cho bảng tính), `open_screen` (`settings_google`), `confirm`.

**Biến môi trường** (theo `10-kien-truc-backend.md`): `PUBLIC_BASE_URL`, `TOKEN_ENCRYPTION_KEYS`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_MAPS_API_KEY`. Cộng `GOOGLE_SYNC_MIN_SECONDS` (của `50-ha-tang-trien-khai.md`, mặc định 300): khoảng cách tối thiểu giữa hai lần quét định kỳ của cùng một tài nguyên.

## 15. Kiểm thử

Bài kiểm luật viết trước. Không gọi Google thật: dùng máy chủ Google giả của `70-kiem-thu.md` mục 3.6.

1. **OAuth:**
   - `state` sai, hết hạn hoặc giải mã không được thì từ chối;
   - `code_verifier` không lộ trong URL;
   - thiếu scope thì trả `ket-qua=thieu-quyen`, dịch vụ không bật;
   - `invalid_grant` thì `reauth_required` và dừng job của tài khoản;
   - nối lại thì thu hồi token cũ;
   - hai tiến trình làm mới cùng lúc chỉ gọi Google một lần;
   - bản mã token chép sang dòng người khác không giải mã được.
2. **Calendar:**
   - lần đầu có `timeMin`, `singleEvents=true`, lật trang, lưu `nextSyncToken`;
   - lần tăng dần không gửi `timeMin`;
   - lần lặp quá 365 ngày không lưu;
   - quá 30 ngày thì đồng bộ đủ lại;
   - 410 thì xóa và đồng bộ lại, giữ dòng outbox chờ;
   - `cancelled` thì xóa mềm;
   - `etag` trùng thì bỏ qua;
   - 412 thì lấy bản Google, dòng outbox `conflict` có `payload`;
   - tạo lại với `id` trùng thì coi như thành công;
   - webhook sai token bị bỏ qua;
   - kênh còn dưới 48 giờ thì được gia hạn.
3. **Mời khách:**
   - `add_event` có khách không ghi `tab_event` mà tạo `pending_action`;
   - duyệt thì `insert` kèm `sendUpdates=all`;
   - sửa sự kiện có khách qua API trả `pending_action`;
   - sự kiện người khác mời không sửa được nội dung.
4. **Nhắc trùng:**
   - sự kiện tạo ở app gửi `overrides=[]` và có trong `/calendar/reminders`;
   - sự kiện từ Google không có trong `/calendar/reminders`;
   - đổi nguồn nhắc thì cập nhật cả hai phía.
5. **Tasks (QĐ-21):**
   - việc có `due_at` không lên Tasks;
   - `due` đúng dạng ngày;
   - Google `completed` thì app `done`;
   - Google bỏ tích thì app `todo`;
   - Google `deleted` thì app xóa mềm, Hoàn tác thì tạo lại;
   - đổi tên trên Google không nhận về;
   - `updated` không mới hơn thì bỏ qua;
   - cùng đổi hai phía theo luật gộp;
   - không tạo dòng outbox cho thay đổi đọc về;
   - việc lạ trong danh sách bị bỏ qua.

   Bài kiểm *không kéo ngược* ở `70-kiem-thu.md` mục 3.6 phải thay bằng các ca này.
6. **Gmail:**
   - thư quảng cáo, mạng xã hội bị bỏ;
   - thư có OTP bị bỏ, không lưu;
   - 404 history thì đồng bộ đủ lại;
   - cột ghi đúng tên của 11;
   - `send_gmail_draft` chỉ tạo `pending_action`;
   - duyệt khi nháp đã bị sửa thì không gửi;
   - người A không duyệt được hành động của người B.
7. **Contacts:**
   - sync token hết hạn (cả 400 `EXPIRED_SYNC_TOKEN` lẫn 410) thì đồng bộ đủ lại;
   - số điện thoại chuẩn hóa +84;
   - năm 1900 không hiện tuổi.
8. **Sheets, Drive:**
   - tạo bảng tính bằng token chỉ có `drive.file`;
   - ghi lại trang tháng không nhân đôi dòng;
   - dùng lại `google.expense_spreadsheet_id`.
9. **Mẫu phản hồi Google** cho máy chủ giả (`70-kiem-thu.md` yêu cầu *phản hồi thật đã che*):
   - bản đầu dựng theo ví dụ trong tài liệu Google, vì agent không gọi API Google thật;
   - phản hồi thật ghi lại sau, bằng một lần chạy tay với tài khoản Google thử (câu hỏi B mục 32 ở `80-ra-cheo-lan-1.md`).
10. **Thử tay trên máy thật:**
    - nối qua Custom Tabs và quay về bằng `troly://`;
    - bấm qua màn chưa xác minh;
    - sau 8 ngày token vẫn còn;
    - hộp chọn tệp Android thấy Google Drive;
    - đo số dòng sự kiện ở lần đồng bộ đầu.

## 16. Rủi ro

| Rủi ro | Mức | Giảm nhẹ |
|---|---|---|
| Refresh token vẫn hết hạn ở In production chưa xác minh | Trung bình | Thử 8 ngày; luồng nối lại một chạm; đếm `invalid_grant` |
| Google đổi chính sách miễn xác minh cá nhân cho scope Gmail hạn chế | Thấp | Gmail tách được; mất thì quay lại nghe thông báo Gmail trên máy |
| Lãng phí giới hạn 100 người dùng mới | Thấp | Chỉ thử bằng tài khoản thật và một tài khoản thử |
| Quota Google đổi (Gmail, Drive, Calendar đổi 01/05/2026; Calendar dự kiến thu phí) | Thấp | Đọc quota ở Console khi dựng; mức dùng thấp hơn ngưỡng nhiều bậc |
| Lần lặp vô hạn làm phình `tab_event` | Thấp | Khung 365 ngày, đồng bộ đủ mỗi 30 ngày; đo ở lần đầu |
| Xung đột sửa cùng lúc làm mất thay đổi trong app | Thấp | Giữ ở `payload`, áp lại một chạm |
| Gửi lời mời nhầm người | Trung bình | Thẻ duyệt hiện đủ email; không gửi nếu chưa duyệt (QĐ-23) |
| Nhắc trùng, hoặc không nhắc khi người dùng tắt nhắc ở Google | Trung bình | Một nguồn nhắc mỗi sự kiện, hiện rõ trên màn sự kiện |
| Đọc ngược Tasks gây vòng lặp đẩy qua lại | Thấp | Không tạo outbox cho thay đổi đọc về; so `google_updated_at` |
| Thông báo đẩy Calendar bị rơi | Thấp | Quét 15 phút |
| Health Connect không cấp quyền cho APK ngoài Play | Cao (V2) | Thử trên máy thật trước khi thiết kế V2 |
| Nội dung thư của người khác đi qua Claude API | Trung bình | Hộp tin chỉ giữ đoạn trích; chuỗi thư chỉ đọc khi được hỏi; luật bên thứ ba của `60-bao-mat-rieng-tu.md` |

## 17. Câu hỏi mở

Đã chốt từ bản 1, không hỏi lại:

| Câu | Chốt ở |
|---|---|
| Đọc ngược Tasks | QĐ-21 |
| Mời khách | QĐ-23 |
| Sửa cả chuỗi lặp: mở Google Calendar | `80-ra-cheo-lan-1.md` mục B |
| Một tài khoản Google mỗi người | QĐ-15, `80` B mục 8 |

Còn mở:

1. **Lịch phụ:** chỉ lịch chính, hay cho chọn thêm lịch phụ? Chọn lịch phụ cần thêm scope đọc danh sách lịch.
2. **Nguồn nhắc mặc định** cho sự kiện tạo trên Google: để Google nhắc như mục 4.7, hay app nhắc hết (khi đó phải tắt thông báo app Google Calendar)?
3. **Trả lời lời mời** của người khác (đồng ý, từ chối) trong app: cần ở bản nào?
4. **Việc người dùng tự thêm** vào danh sách *Trợ lý* trên Google Tasks: bỏ qua như mục 5.3, hay nhận về thành việc trong app?
5. **Danh bạ khác** (`contacts.other.readonly`) để đặt tên người gửi Gmail chưa lưu danh bạ?
6. **Gmail:** chỉ hộp *Chính*, hay thêm nhóm *Cập nhật* (hóa đơn, xác nhận đơn hàng)?
7. **Tài khoản Workspace:** có nối tài khoản công ty không? Quản trị viên Workspace có thể chặn app chưa xác minh.
8. **Mức nhạy cảm** của scope Calendar, Tasks, Contacts: chờ đọc nhãn trong Console (mục 11 bước 3.3).
9. **Tài khoản Google thử riêng** để ghi phản hồi thật cho bộ mẫu (`80` B mục 32).

## 18. Cần agent khác

- **Agent kiến trúc:**
  - `11-co-so-du-lieu.md`:
    - gom phần thêm ở mục 13;
    - chọn chỗ đặt `tab_gmail_draft`;
    - đổi thời hạn `tab_inbox_message` thành 180 ngày;
    - bỏ đánh dấu *[Đối chiếu: agent Google]* ở các mục đã khớp (`singleEvents=true`, khung 30 ngày trước tới 365 ngày sau, ngắt kết nối, năm 1900).
  - `12-api.md`:
    - thêm các đường dẫn ở mục 14;
    - đổi `state` từ *ký bằng `JWT_SECRET`* sang *mã hóa Fernet* (ĐX-G11);
    - đổi đường quay về app thành `troly://cai-dat/google?ket-qua=ok|huy|thieu-quyen|loi` (đang ghi `troly://google/connected?status=`);
    - `/calendar/reminders` chỉ trả `remind_source = app`;
    - đổi ĐX-API-05 thành 5 phút.
  - `10-kien-truc-backend.md`:
    - thêm job `sync_google_tasks`;
    - đổi chu kỳ ba job ở mục 14;
    - thêm khóa tư vấn khi làm mới token;
    - ghi `GOOGLE_SYNC_MIN_SECONDS` vào bảng biến.
- **Agent hạ tầng:**
  - `50-ha-tang-trien-khai.md`:
    - bỏ biến `GOOGLE_REDIRECT_URI`, máy chủ dựng từ `PUBLIC_BASE_URL` (ĐX-G14);
    - sửa đường dẫn ở L333 thành `/api/v1/...`;
    - quota Maps theo mục 11.
  - Trang chính sách riêng tư tĩnh.
  - Cloudflare không chặn `/api/v1/webhooks/google/*` và `/api/v1/google/oauth/callback` bằng bước kiểm trình duyệt.
  - Không cần `assetlinks.json`.
  - `70-kiem-thu.md`:
    - thay ca *Sửa Tasks trên Google: không kéo ngược* bằng các ca ở mục 15 bước 5;
    - thêm ca mời khách.
- **Agent app Android:**
  - `31-giao-dien.md`: thêm `ket-qua=loi`; trường nguồn nhắc trên màn sự kiện; sự kiện người khác mời chỉ đổi được nguồn nhắc; dòng *Hoàn tác* khi việc bị xóa trên Google; màn *Lỗi đồng bộ* có *Thử lại* và *Áp lại*.
  - `30-app-android.md`: loại `com.google.android.gm` khỏi danh sách nghe khi bật Gmail; chốt phiên bản Health Connect.
- **Agent AI** (`20-bo-nao-ai.md`):
  - đã khớp: tên công cụ Gmail, Contacts, Sheets; `kind` `send_gmail`, `invite_event`; mã lỗi `GOOGLE_NOT_CONNECTED`; `export_expenses_to_sheets` đi qua `/reports/exports`;
  - còn: ghi rõ xóa sự kiện có khách cũng gửi `sendUpdates=all`; bỏ hẳn `list_drive_files`, `import_drive_file` nếu còn sót.

## 19. Đề xuất quyết định

**Trạng thái các đề xuất bản 1:**

| Số | Nội dung | Trạng thái |
|---|---|---|
| ĐX-G1 | Custom Tabs, luồng máy chủ web | Đã chấp nhận (QĐ-25); phần App Link thay bằng `troly://` |
| ĐX-G2 | In production, không xác minh | Đã chấp nhận |
| ĐX-G3 | Xin quyền theo dịch vụ | Đã chấp nhận |
| ĐX-G4 | Đọc ngược Tasks | Thành QĐ-21 |
| ĐX-G5 | Danh sách *Trợ lý* | Đã chấp nhận |
| ĐX-G6 | Một nguồn nhắc | Đã chấp nhận |
| ĐX-G7 | Gmail quét 5 phút | Đã chấp nhận |
| ĐX-G8 | Chỉ `drive.file` | Đã chấp nhận |
| ĐX-G9 | Sửa hướng dẫn Console ở 01 | Đã chấp nhận, điều phối sửa |
| ĐX-G10 | Sửa câu 7 ngày ở 00 | Đã chấp nhận, điều phối sửa |

**Đề xuất mới:**

| Số tạm | Đề xuất | Lý do |
|---|---|---|
| ĐX-G11 | `state` OAuth là chuỗi mã hóa Fernet (vòng khóa `TOKEN_ENCRYPTION_KEYS`) chứa `code_verifier`, thay cho chuỗi ký bằng `JWT_SECRET`; không cần bảng lưu tạm | Chuỗi ký thì ai thấy URL cũng đọc được `code_verifier`, làm PKCE mất tác dụng |
| ĐX-G12 | Calendar: `singleEvents=true`; lần đầu `timeMin = now − 30 ngày`; bỏ lần lặp quá 365 ngày; đồng bộ đủ lại mỗi 30 ngày | Khớp 11 và ví dụ của Google; lấp lần lặp mới vào khung mà không cần `timeMax` |
| ĐX-G13 | Xung đột 412 giữ thay đổi bị bỏ ở `tab_google_outbox.payload`, `status = conflict`, cho áp lại một chạm | Google làm gốc mà người dùng không mất công sửa |
| ĐX-G14 | Bỏ biến `GOOGLE_REDIRECT_URI`; redirect dựng từ `PUBLIC_BASE_URL + /api/v1/google/oauth/callback` | Một nguồn sự thật; 10 đã ghi `PUBLIC_BASE_URL` dùng dựng link callback |
| ĐX-G15 | Sự kiện người khác mời: app chỉ cho đổi nguồn nhắc; sửa, xóa sự kiện có khách đều qua thẻ duyệt kèm `sendUpdates=all` | QĐ-23 và `60-bao-mat-rieng-tu.md` mục 3.12 |
| ĐX-G16 | Thuật toán đọc ngược Tasks ở mục 5.3: bỏ tích trên Google cũng về app; xóa trên Google thì xóa mềm kèm Hoàn tác; không nhận đổi nội dung | Cụ thể hóa QĐ-21, tránh vòng lặp |

## 20. Nguồn

Tất cả truy cập ngày 18/11/2026.

| Mã | Nội dung | Địa chỉ |
|---|---|---|
| N1 | Đối tượng ứng dụng, Testing tối đa 100 người, hết hạn 7 ngày, 100 người mới cho app chưa xác minh | https://support.google.com/cloud/answer/15549945 |
| N2 | Danh sách scope OAuth 2.0 | https://developers.google.com/identity/protocols/oauth2/scopes |
| N3 | Ngoại lệ xác minh, dùng cá nhân | https://support.google.com/cloud/answer/13464323 |
| N4 | Scope Calendar | https://developers.google.com/workspace/calendar/api/auth |
| N5 | Xác minh scope nhạy cảm | https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification |
| N6 | Scope Tasks | https://developers.google.com/workspace/tasks/auth |
| N7 | Scope Gmail và mức | https://developers.google.com/workspace/gmail/api/auth/scopes |
| N8 | Scope People API | https://developers.google.com/identity/protocols/oauth2/scopes |
| N9 | Scope Drive và mức | https://developers.google.com/workspace/drive/api/guides/api-specific-auth |
| N10 | `spreadsheets.create` chấp nhận `drive.file` | https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/create |
| N11 | Scope Sheets và mức | https://developers.google.com/workspace/sheets/api/scopes |
| N12 | Nhãn nhạy cảm hiện trong Console | https://developers.google.com/identity/protocols/oauth2/scopes |
| N13 | Refresh token 7 ngày ở Testing | https://developers.google.com/identity/protocols/oauth2 |
| N14 | Màn ứng dụng chưa xác minh | https://support.google.com/cloud/answer/7454865 |
| N15 | Chính sách OAuth: dùng cá nhân, cấm user agent nhúng, lưu token | https://developers.google.com/identity/protocols/oauth2/policies |
| N16 | Xác minh scope hạn chế, CASA | https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification |
| N17 | Giới hạn 100 refresh token, các lý do token hết hiệu lực | https://developers.google.com/identity/protocols/oauth2 |
| N18 | Luồng máy chủ web, `access_type`, `include_granted_scopes`, `prompt=consent` | https://developers.google.com/identity/protocols/oauth2/web-server |
| N19 | Quyền chi tiết (granular consent) | https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions |
| N20 | Ứng dụng cài trên máy: `disallowed_useragent`, PKCE, bỏ custom scheme làm redirect, thu hồi | https://developers.google.com/identity/protocols/oauth2/native-app |
| N22 | Ủy quyền trên Android, `requestOfflineAccess`, không lưu refresh token trên máy | https://developer.android.com/identity/authorization |
| N23 | Calendar thông báo đẩy | https://developers.google.com/workspace/calendar/api/guides/push |
| N24 | Cross-Account Protection (RISC) | https://developers.google.com/identity/protocols/risc |
| N25 | Tài nguyên Event: `id`, `extendedProperties`, `reminders`, `cancelled` | https://developers.google.com/workspace/calendar/api/v3/reference/events |
| N26 | Đồng bộ Calendar tăng dần; ví dụ `singleEvents=true`, `timeMin` cho lần đầu; 410 | https://developers.google.com/workspace/calendar/api/guides/sync |
| N27 | `events.list`: tham số cấm dùng với `syncToken`, `singleEvents`, `maxResults` | https://developers.google.com/workspace/calendar/api/v3/reference/events/list |
| N28 | Lỗi Calendar | https://developers.google.com/workspace/calendar/api/guides/errors |
| N29 | `events.watch`, `ttl` | https://developers.google.com/workspace/calendar/api/v3/reference/events/watch |
| N30 | Quota Calendar (mới từ 01/05/2026), lệch chu kỳ, thử lại | https://developers.google.com/workspace/calendar/api/guides/quota |
| N31 | Phiên bản tài nguyên, `If-Match`, 412 | https://developers.google.com/workspace/calendar/api/guides/version-resources |
| N32 | Tài nguyên Task: `due` chỉ lưu ngày, các trường | https://developers.google.com/workspace/tasks/reference/rest/v1/tasks |
| N33 | Danh sách phương thức Tasks API | https://developers.google.com/workspace/tasks/reference/rest |
| N34 | `tasks.list`: `updatedMin`, `showHidden`, `showDeleted`, `maxResults` | https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/list |
| N35 | Hạn mức Tasks | https://developers.google.com/workspace/tasks/limits |
| N36 | `messages.send`, `drafts.create` và scope chấp nhận | https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send |
| N37 | Dạng thư `minimal`, `metadata`, `full`, `raw` | https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format |
| N38 | Đồng bộ Gmail | https://developers.google.com/workspace/gmail/api/guides/sync |
| N39 | `history.list` | https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list |
| N40 | Nhãn hệ thống Gmail | https://developers.google.com/workspace/gmail/api/guides/labels |
| N41 | Gmail thông báo đẩy | https://developers.google.com/workspace/gmail/api/guides/push |
| N42 | Giá Pub/Sub | https://cloud.google.com/pubsub/pricing |
| N43 | Gửi thư, trả lời trong luồng | https://developers.google.com/workspace/gmail/api/guides/sending |
| N44 | Nháp Gmail | https://developers.google.com/workspace/gmail/api/guides/drafts |
| N45 | Giới hạn gửi Gmail | https://support.google.com/mail/answer/22839 |
| N46 | Quota Gmail (mới từ 01/05/2026) | https://developers.google.com/workspace/gmail/api/reference/quota |
| N47 | `people.connections.list`, sync token 7 ngày | https://developers.google.com/people/api/rest/v1/people.connections/list |
| N48 | Hướng dẫn đọc danh bạ (mẫu xử lý 410) | https://developers.google.com/people/v1/contacts |
| N49 | Thư mục Drive | https://developers.google.com/workspace/drive/api/guides/folder |
| N50 | Tải tệp lên Drive, chuyển đổi | https://developers.google.com/workspace/drive/api/guides/manage-uploads |
| N51 | Storage Access Framework | https://developer.android.com/training/data-storage/shared/documents-files |
| N52 | Google Picker, không chạy trong WebView | https://developers.google.com/workspace/drive/picker/guides/overview |
| N53 | Picker trên máy tính và điện thoại | https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker |
| N54 | Hạn mức Drive | https://developers.google.com/workspace/drive/api/guides/limits |
| N55 | Hạn mức Sheets | https://developers.google.com/workspace/sheets/api/limits |
| N56 | Bảo mật khóa API Maps | https://developers.google.com/maps/api-security-best-practices |
| N57 | Maps URLs không cần khóa | https://developers.google.com/maps/documentation/urls/get-started |
| N58 | Lệnh Android cho Google Maps | https://developer.android.com/guide/components/google-maps-intents |
| N59 | Thay đổi giá từ 03/2025 | https://developers.google.com/maps/billing-and-pricing/march-2025 |
| N60 | Mức miễn phí theo SKU | https://developers.google.com/maps/billing-and-pricing/faq |
| N61 | Bắt đầu với Maps Platform, cần tài khoản thanh toán | https://developers.google.com/maps/get-started |
| N62 | Quản lý chi phí, quota chặn cứng | https://developers.google.com/maps/billing-and-pricing/manage-costs |
| N63 | Health Connect: bắt đầu | https://developer.android.com/health-and-fitness/guides/health-connect/develop/get-started |
| N64 | Health Connect: khả dụng | https://developer.android.com/health-and-fitness/health-connect/availability |
| N65 | Health Connect: đọc dữ liệu, 30 ngày, đọc ngầm | https://developer.android.com/health-and-fitness/guides/health-connect/develop/read-data |
| N66 | Health Connect: đồng bộ, token thay đổi 30 ngày | https://developer.android.com/health-and-fitness/guides/health-connect/develop/sync-data |
| N67 | Health Connect: khai báo khi phát hành | https://developer.android.com/health-and-fitness/health-connect/publish |
| N68 | Thư viện `connect-client` | https://developer.android.com/jetpack/androidx/releases/health-connect |
| N69 | `events.insert`: `sendUpdates` (`all`, `externalOnly`, `none`), `attendees`, scope chấp nhận | https://developers.google.com/workspace/calendar/api/v3/reference/events/insert |
