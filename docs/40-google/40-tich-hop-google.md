# Tích hợp Google

Người giữ: agent Google. Bản 3 (18/11/2026), gọn hóa theo QĐ-26, QĐ-27.

Tài liệu này mô tả cách app nối tài khoản Google, đồng bộ Calendar và Tasks, đọc Gmail và Contacts, ghi Drive và Sheets, gọi Maps Platform. Lịch trình và bản đồ ở [41-ban-do-lich-trinh.md](41-ban-do-lich-trinh.md).

**Nguồn chuẩn (QĐ-25, QĐ-26)** khi tài liệu lệch nhau:

| Nội dung | Tài liệu |
|---|---|
| Bảng, cột | `11-co-so-du-lieu.md` |
| Đường dẫn API | `12-api.md` |
| Công cụ AI | `20-bo-nao-ai.md` |
| Job, biến môi trường | `10-kien-truc-backend.md` |
| Mã hóa token | `60-bao-mat-rieng-tu.md` |

Thông số Google đã đối chiếu với tài liệu chính thức ngày 18/11/2026, nguồn ở mục 13. Chỗ Google không nói rõ được ghi **chưa xác minh**.

## 1. Mục tiêu

- Một người dùng (Gia Bảo) nối một tài khoản Google cá nhân một lần; sau đó mọi thứ chạy ngầm.
- **Lịch:** hai chiều, Google làm gốc (QĐ-09).
- **Việc:** app làm gốc, đọc ngược trạng thái *xong* và *đã xóa* (QĐ-21).
- **Gmail:** vào hộp tin; gửi thư và mời khách phải duyệt (QĐ-23, QĐ-27).
- **Nhắc:** mỗi lời nhắc chỉ kêu ở một nơi.
- **Chi phí:** không phát sinh tiền, không cần Google xác minh ứng dụng.

## 2. Phạm vi

| Phase | Bản | Dịch vụ | Làm | Không làm |
|---|---|---|---|---|
| 3 | V1.4 | Calendar | Lịch chính `primary`, hai chiều; mời khách qua thẻ duyệt | Lịch phụ; trả lời lời mời của người khác (V2); sửa cả chuỗi lặp trong app |
| 3 | V1.4 | Tasks | Danh sách *Trợ lý*: đẩy từ app; đọc ngược xong và đã xóa | Việc người dùng tự thêm thẳng trên Google (bỏ qua) |
| 4 | V1.6 | Maps Platform | Places (New), Routes, Geocoding từ máy chủ | Maps SDK trong app |
| 5 | V1.8 | Gmail | Hộp *Chính* vào hộp tin; tìm, đọc chuỗi thư khi hỏi; nháp; gửi qua thẻ duyệt | Hộp *Cập nhật*, xóa thư, đổi nhãn |
| 5 | V1.8 | Contacts | Đọc tên, email, số điện thoại, sinh nhật | *Danh bạ khác*, sửa danh bạ |
| 5 | V1.8 | Drive, Sheets | Ghi tệp xuất vào thư mục *Trợ lý*; bảng chi tiêu | Tìm tệp của người dùng trên Drive |
| V2 | | Health Connect | Đọc bước, giấc ngủ, nhịp tim trên máy | |

Không làm Google Photos, Google Keep. Chỉ tài khoản Google cá nhân, không Workspace.

## 3. OAuth

### 3.1 Scope và trạng thái dự án

| Gói (`packs`) | Scope | Mức | Nguồn |
|---|---|---|---|
| `base` | `openid email profile` | Không nhạy cảm | N1 |
| `calendar` | `calendar.events` | Nhạy cảm (**chưa xác minh**; xem nhãn trong Console khi dựng V1.4) | N4, N5 |
| `tasks` | `tasks` | Nhạy cảm (**chưa xác minh**) | N6 |
| `gmail` | `gmail.readonly`, `gmail.compose` | **Hạn chế**. `compose` tạo nháp và gửi được; `gmail.send` không tạo được nháp; `gmail.metadata` không đọc được nội dung | N7, N36, N37 |
| `contacts` | `contacts.readonly` | Nhạy cảm (**chưa xác minh**) | N2 |
| `drive` | `drive.file` (cả Drive và Sheets) | Không nhạy cảm; tạo bảng tính bằng scope này được, không cần `spreadsheets` | N9, N10 |

**Trạng thái màn đồng ý:** chuyển **In production**, không xin xác minh.

- **Testing:** quyền cấp hết hạn sau 7 ngày, trừ app chỉ xin `name`, `email`, `profile` [N1][N13].
- **In production chưa xác minh:** người dùng bấm qua màn *Google chưa xác minh ứng dụng này*. App cá nhân (dưới 100 người, đều quen biết) được miễn xác minh, kể cả scope hạn chế, không cần đánh giá CASA [N3][N15][N16].
- **Ghi chú:** dự án chưa xác minh chỉ có tổng 100 người dùng mới trong cả đời dự án [N1]; với một người dùng và một tài khoản thử thì không chạm tới.
- **Chưa xác minh:** không trang nào của Google viết thẳng rằng refresh token ở *In production chưa xác minh* không hết hạn sau 7 ngày. Thử 8 ngày ở V1.4 (mục 11).

**Xin quyền theo gói:**

- Bật gói nào xin scope gói đó, với `include_granted_scopes=true` [N18].
- Người dùng có thể bỏ tích từng quyền, nên máy chủ luôn đọc trường `scope` của phản hồi token. Gói thiếu quyền không bật, trang kết thúc báo `thieu-quyen` [N19].
- Gói đã bật lưu ở `tab_google_account.enabled_packs`; scope được cấp lưu ở `granted_scopes`.

### 3.2 Luồng nối tài khoản

Google chặn đăng nhập OAuth trong WebView nhúng (`disallowed_useragent`) [N20][N15]. Vì vậy app mở bằng **Custom Tabs**, theo luồng máy chủ web, client loại *Web application* [N18]. Đường dẫn theo `12-api.md` mục 5.7.

1. App gọi `POST /api/v1/google/connect` với `packs`. Máy chủ:
   - tạo `state` ngẫu nhiên và cặp PKCE S256 [N20];
   - lưu `tab_google_oauth_state`: băm `state`, `code_verifier` mã hóa Fernet, hạn 10 phút, dùng một lần;
   - trả `auth_url` với `access_type=offline`, `prompt=consent`, `include_granted_scopes=true`, `code_challenge_method=S256`, `login_hint`.
2. App mở `auth_url` bằng Custom Tabs. Người dùng chọn tài khoản, bấm *Nâng cao > Đi tới...* ở màn chưa xác minh, tích quyền.
3. Google chuyển về `GOOGLE_REDIRECT_URI` (`https://assistant.baohuynh.io.vn/api/v1/google/oauth/callback`). Máy chủ:
   - kiểm `state` và đánh dấu đã dùng;
   - đổi `code` kèm `code_verifier`;
   - đọc `id_token` (`sub`, `email`) và `scope`;
   - mã hóa, lưu token;
   - đặt việc `google_initial_sync`;
   - thu hồi token cũ nếu là nối lại.
4. Trang HTML ngắn chuyển về app bằng `troly://cai-dat/google?ket-qua=ok|huy|thieu-quyen|loi`. Redirect OAuth vẫn là https về máy chủ; `troly://` chỉ là bước từ trang máy chủ về app, nên không đụng việc Google bỏ custom scheme làm redirect [N20].

`sub` khác tài khoản đang nối thì trang hỏi *Thay tài khoản Google?*, không tự ghi đè.

### 3.3 Token

- **Mã hóa** theo `60-bao-mat-rieng-tu.md` mục 3.4: Fernet, vòng khóa `TOKEN_ENCRYPTION_KEYS`, bản rõ `{user_id, provider, token}`. Không lưu token trên điện thoại [N22]. Chính sách Google đòi mã hóa token khi lưu và xóa khi không dùng [N15].
- **Làm mới:**
  - access token còn dưới 5 phút thì làm mới; hạn lấy từ `expires_in`;
  - giữ khóa tư vấn theo `google_account_id` (`10-kien-truc-backend.md` mục 3.9) để `api` và `worker` không cùng làm mới.
- **Giới hạn:** mỗi tài khoản, mỗi client có tối đa 100 refresh token; vượt thì token cũ nhất mất hiệu lực [N17]. Vì vậy nối lại xong thì thu hồi token cũ ngay.
- **Token hỏng** (`invalid_grant`): người dùng thu hồi, 6 tháng không dùng, đổi mật khẩu khi có scope Gmail, Testing 7 ngày, vượt 100 token [N17]. Khi gặp:
  - `status = reauth_required`, tăng `invalid_grant_count`;
  - dừng job của tài khoản; hàng chờ giữ `pending`;
  - API và công cụ AI trả `GOOGLE_REAUTH_REQUIRED`;
  - app hiện một dòng *Kết nối Google đã hết hạn, chạm để nối lại*.
- **Ngắt kết nối** (`POST /api/v1/google/disconnect`, `keep_data`):
  - thu hồi ở `https://oauth2.googleapis.com/revoke` [N20];
  - `channels.stop` kênh Calendar;
  - xóa theo `11-co-so-du-lieu.md` mục 3.15: danh bạ và thư Gmail trong hộp tin bị xóa; sự kiện và việc giữ hay xóa theo `keep_data`.

## 4. Google Calendar (hai chiều, Google làm gốc)

### 4.1 Ánh xạ

| `tab_event` | Google `Event` |
|---|---|
| `title` | `summary` |
| `description`, `location`, `status` | `description`, `location`, `status` |
| `start_at`/`end_at` hoặc `start_date`/`end_date` | `start`/`end`; `timeZone = Asia/Ho_Chi_Minh` |
| `recurrence`, `timezone` | `recurrence` của bản gốc |
| `recurring_event_id`, `original_start_at` | `recurringEventId`, `originalStartTime` (ngoại lệ) |
| `attendees` | `attendees` |
| `remind_minutes`, `remind_source` | `reminders` (mục 4.5) |
| `google_event_id`, `google_etag`, `google_updated_at` | `id`, `etag`, `updated` |
| `id` | `extendedProperties.private.troly_event_id`, chỉ thấy trên bản của lịch này [N25] |

**Chống tạo trùng.** Sự kiện tạo trong app được đặt sẵn `google_event_id` = hex của UUID: Google cho client tự đặt `id` dạng base32hex dài 5 tới 1024 ký tự [N25]. Gửi lại sau lỗi mạng sẽ gặp lỗi trùng; khi đó `events.get` lấy `etag` và coi như đã tạo.

### 4.2 Đồng bộ từ Google về app

**Sự kiện lặp** theo `11-co-so-du-lieu.md` (QĐ-26, câu K1):

- lưu **bản gốc** có `recurrence`, cộng **ngoại lệ** (lần lặp bị sửa hoặc hủy riêng);
- `singleEvents=false`; máy chủ tự trải lần lặp khi liệt kê.

**Thuật toán** (đồng bộ tăng dần bằng `syncToken` [N26]):

1. **Đồng bộ đủ** (việc `google_initial_sync`, hoặc khi gặp 410):
   - gọi `events.list(primary, singleEvents=false, showDeleted=true, maxResults=2500, timeMin=now − 30 ngày)`, lật hết `pageToken`;
   - trang cuối có `nextSyncToken`, lưu vào `tab_google_sync_state.sync_token`.

   Google cho thu hẹp lần đồng bộ đủ bằng tham số, ví dụ mẫu dùng `timeMin` [N26]. `timeMin` lọc theo giờ kết thúc; bản gốc của chuỗi lặp còn chạy có về hay không thì **chưa xác minh**, kiểm ở lần nối thật đầu tiên. Nếu không về thì bỏ `timeMin`.
2. **Tăng dần:** `events.list(primary, singleEvents=false, syncToken=...)`, lật hết trang, lưu token mới. Không gửi kèm `timeMin`, `timeMax`, `orderBy`, `q`, `updatedMin`, `iCalUID`, `privateExtendedProperty`, `sharedExtendedProperty` (lỗi 400); không đặt `showDeleted=false` [N27].
3. **Ghi từng sự kiện:**
   - `status = cancelled`: bản gốc thì đặt `deleted_at`; ngoại lệ thì ghi ngoại lệ hủy, để lần lặp đó biến mất khi trải. Sự kiện bị xóa chỉ chắc có `id` [N25].
   - `etag` trùng `google_etag`: bỏ qua (tiếng vọng của lần ghi từ app).
   - Còn lại: ghi đè bản trong app. Dòng có lệnh chờ trong hàng đợi thì xử lý theo mục 4.3.
4. **Lỗi 410** (`fullSyncRequired`): xóa sự kiện `source = google` không có lệnh chờ, xóa `sync_token`, chạy lại bước 1 [N26][N28].

**Trải lần lặp:** dùng `dateutil.rrule` theo `recurrence` (gồm `EXDATE`) và `timezone`. Ngoại lệ thay lần lặp có cùng `original_start_at`.

**Sửa trong app:**

- **Một lần lặp:** gửi kèm `occurrence_start` (`12-api.md`). Máy chủ gọi `events.instances(id, timeMin, timeMax)` quanh giờ đó để lấy `id` của lần lặp, rồi `patch` hoặc `delete` lần đó.
- **Cả chuỗi:** trả `RECURRING_SERIES_EDIT` kèm link mở Google Calendar.

**Thông báo đẩy** [N23][N29]:

- `events.watch` cho `primary`, `address = https://assistant.baohuynh.io.vn/api/v1/webhooks/google/calendar`. Địa chỉ phải là HTTPS có chứng chỉ hợp lệ; Cloudflare đáp ứng.
- `token` ngẫu nhiên mỗi kênh, lưu băm. `ttl` để mặc định 604800 giây; tài liệu không ghi mức tối đa.
- Webhook xử lý theo `12-api.md` mục 5.7: kiểm kênh và token, đặt `needs_sync`, trả 200 trong 1 giây.
- Thông báo không chứa dữ liệu, nên luôn phải chạy đồng bộ tăng dần.
- Google không tự gia hạn kênh; hai kênh được chồng nhau một lúc.
- Webhook có cần xác minh tên miền không thì **chưa xác minh**; tài liệu hiện tại chỉ đòi HTTPS hợp lệ.

### 4.3 Từ app lên Google, xung đột

Mọi lệnh ghi đi qua `tab_google_outbox` (`service = calendar`, `local_type = event`), ghi cùng giao dịch. Job `push_google_outbox` đọc trạng thái mới nhất của dòng gốc lúc đẩy.

| Lệnh | Lời gọi |
|---|---|
| `insert` | `events.insert` với `id` đặt sẵn |
| `patch` | `events.patch` kèm `If-Match: <google_etag>` |
| `delete` | `events.delete` kèm `If-Match` |

Có khách thì thêm `sendUpdates=all` (lưu trong `payload`).

**Xung đột (412 `conditionNotMet`)** [N31]: Google làm gốc.

1. Lấy bản Google mới nhất, ghi vào `tab_event`.
2. Dòng hàng chờ `status = conflict`, `last_error` giữ thay đổi bị bỏ.
3. App báo một dòng; người dùng chọn *Áp lại* qua `POST /api/v1/google/outbox/{id}/retry` với `reapply = true`.

`patch` gặp 404 hoặc 410 thì coi như sự kiện đã bị xóa trên Google.

### 4.4 Mời khách (QĐ-23)

Gửi lời mời là gửi ra ngoài, nên phải duyệt (QĐ-27).

- **Tạo hoặc sửa sự kiện có khách** (`add_event`, `update_event` có `attendee_emails`; hoặc `POST`, `PATCH /api/v1/calendar/events` có `attendees`): tạo `tab_pending_action` (`tool_name`, `input`, băm `tool_name` cộng `input`), trả thẻ `confirm`. Thẻ hiện giờ, địa điểm và **danh sách email sẽ nhận thư**.
- **Duyệt:** mới ghi `tab_event` và lệnh hàng chờ; lời gọi có `sendUpdates=all`, Google gửi thư mời [N69].
- **Xóa sự kiện có khách** cũng qua thẻ duyệt, vì Google gửi thư hủy.
- **Sự kiện không có khách:** không gửi `sendUpdates`. Tài liệu cảnh báo giá trị `none` có thể làm sự kiện không đồng bộ sang lịch ngoài [N69].
- **Sự kiện người khác mời** (không phải `organizer.self`): app chỉ cho đổi nguồn nhắc.

### 4.5 Một nguồn nhắc

| Sự kiện tạo ở | `remind_source` | App | Gửi lên Google |
|---|---|---|---|
| App (chat, màn Lịch, việc có giờ, lịch trình) | `app` | Nhắc bằng `AlarmManager` | `reminders.useDefault=false`, `overrides=[]` |
| Google | `google` (QĐ-26: Google nhắc) | Không nhắc, chỉ hiện | Giữ nguyên |

- `/api/v1/calendar/reminders` chỉ trả sự kiện `remind_source = app`.
- Đổi nguồn nhắc thì cập nhật cả hai phía.
- Google cho tối đa 5 nhắc riêng, mỗi nhắc từ 0 tới 40320 phút [N25].

## 5. Google Tasks (app làm gốc, QĐ-21)

**Giới hạn của Tasks API:**

- `due` chỉ lưu ngày, phần giờ bị bỏ [N32];
- không có trường nhắc, giờ, ưu tiên [N32];
- không có thông báo đẩy [N33];
- `title` tối đa 1024 ký tự, `notes` tối đa 8192 [N32];
- `tasks.list` tối đa 100 việc mỗi trang [N34].

**Đẩy lên:**

1. Bật gói `tasks` lần đầu thì `tasklists.insert` danh sách *Trợ lý*. Mã danh sách lưu ở `tab_google_sync_state.resource_id`.
2. Chỉ việc có `due_date` hoặc không có hạn mới lên Tasks. Việc có `due_at` sinh sự kiện lịch (QĐ-09). Thêm hoặc bỏ giờ thì chuyển qua lại giữa hai nơi.
3. Đẩy qua hàng chờ (`service = tasks`). Trường đẩy lên:

   | Google Tasks | `tab_task` |
   |---|---|
   | `title` | `title` |
   | `notes` | `note`, thêm dòng *Ưu tiên: cao* khi `priority = high` |
   | `due` | `due_date` dạng `YYYY-MM-DDT00:00:00.000Z` |
   | `status` | `needsAction` hoặc `completed` |

   Sau mỗi lần đẩy, lưu `google_etag`, `google_updated_at`.

**Đọc ngược** (job `pull_google_tasks_status`, 15 phút):

1. Gọi `tasks.list(tasklist=Trợ lý, updatedMin=updated_min − 2 phút, showCompleted=true, showDeleted=true, showHidden=true, maxResults=100)`, lật hết trang [N34].
   - Lần đầu không đặt `updatedMin`.
   - Cần `showHidden=true` vì việc xong đã *dọn* trong app Google chỉ hiện khi bật cờ này [N34].
   - Lùi 2 phút để không lọt; bước 2 là idempotent nên đọc trùng không sao.
2. Với mỗi việc:
   1. Không khớp `google_task_id` nào: bỏ qua (QĐ-26: việc tự thêm trên Google không nhận ở V1.4).
   2. `updated` không mới hơn `google_updated_at`: bỏ qua (tiếng vọng).
   3. So trạng thái:

      | Google | App | Làm |
      |---|---|---|
      | `deleted = true` | Chưa xóa | `sync_status = remote_deleted`. App hỏi *xóa* hay *giữ*: `POST /api/v1/tasks/{id}/resolve-remote-delete` với `keep`. Giữ thì bỏ liên kết Google |
      | `completed` | `todo` | `status = done`, `completed_at`, `completed_source = google` |
      | `needsAction` | `done` | `status = todo` (người dùng bỏ tích trên Google) |
      | Khác `title`, `notes`, `due` | | Không nhận. App làm gốc; lần đẩy sau ghi đè |

   4. Ghi `google_etag`, `google_updated_at`. Không tạo lệnh hàng chờ cho thay đổi đọc về, nên không có vòng lặp.
3. Lưu `updated_min` = lúc bắt đầu lượt đọc.

**Luật gộp khi hai phía cùng đổi:**

- Google *xong* và app đang chờ sửa: giữ cả hai (lệnh đẩy kèm `completed`).
- Google *đã xóa* và app đang chờ sửa: `remote_deleted`, bỏ lệnh chờ.
- `patch` gặp 404: xử lý như *đã xóa*.

**Nhắc:** Tasks không có nhắc theo giờ qua API; app tự nhắc. Google nhắc việc chỉ có ngày ra sao thì **chưa xác minh**; thấy trùng thì tắt thông báo Tasks trong app Google.

## 6. Gmail

**Đồng bộ** (job `sync_gmail`, 5 phút):

1. **Lần đầu:**
   - `messages.list(q="in:inbox newer_than:7d")`;
   - `messages.get(format=metadata, metadataHeaders=[From, Subject, Date])` từng thư;
   - lưu `historyId` lớn nhất [N38].
2. **Sau đó:** `history.list(startHistoryId, historyTypes=messageAdded, labelId=INBOX)`, lật hết trang [N39].
3. **Gặp 404:** chạy lại bước 1. Lịch sử thường giữ ít nhất một tuần, có khi chỉ vài giờ [N38].
4. **Lọc:**
   - bỏ nhãn `CATEGORY_PROMOTIONS`, `CATEGORY_SOCIAL`, `CATEGORY_FORUMS`, `CATEGORY_UPDATES`, `SPAM`, `TRASH`. Chỉ hộp *Chính* (QĐ-26), xem lại sau 2 tuần dùng [N40];
   - bỏ thư có OTP theo bộ lọc của `60-bao-mat-rieng-tu.md`; không lưu.
5. **Ghi `tab_inbox_message`:**
   - `source = gmail`, `app = gmail`;
   - `subject`, `text` = `snippet`, `external_id`, `thread_ref`, `labels`;
   - `sender` lấy từ Contacts nếu có;
   - `importance = important` khi có nhãn `IMPORTANT` hoặc khớp luật người quan trọng.

   Đoạn trích giữ 180 ngày (QĐ-17); không lưu nội dung đầy đủ.

Pub/Sub (`users.watch`) làm được, nhưng cần chủ đề Pub/Sub và gọi lại `watch` ít nhất 7 ngày một lần [N41]. Quét 5 phút là đủ, nên chưa dùng.

**Công cụ AI** (tên theo `20-bo-nao-ai.md`):

| Công cụ | Lời gọi Gmail |
|---|---|
| `search_gmail` | `messages.list(q)` |
| `get_gmail_thread` | `threads.get(format=full)`, bỏ HTML, cắt 4.000 ký tự |
| `create_gmail_draft` | `drafts.create` |
| `send_gmail_draft` | Gửi qua thẻ duyệt, bên dưới |

**Gửi thư:** một đường duy nhất là thẻ duyệt.

1. `create_gmail_draft` hoặc màn soạn thư (`POST /api/v1/gmail/drafts`):
   - dựng thư RFC 2822; trả lời trong luồng thì có `In-Reply-To`, `References`, tiêu đề trùng [N43];
   - `drafts.create` [N44];
   - lưu `tab_gmail_draft` kèm `body_hash`.
2. `send_gmail_draft` hoặc `POST /api/v1/gmail/drafts/{id}/send`: tạo `tab_pending_action` (`tool_name = send_gmail_draft`), trả thẻ hiện người nhận, tiêu đề, đoạn đầu.
3. Duyệt (`POST /api/v1/chat/actions/{id}/approve`):
   1. `status = sending`;
   2. `drafts.get` rồi so băm với `body_hash`; khác (nháp bị sửa trên Gmail) thì không gửi, báo *Nháp đã bị sửa, hãy xem lại*;
   3. khớp thì `drafts.send` [N44], `status = sent`.

Gmail cá nhân giới hạn 500 người nhận mỗi thư và 500 thư mỗi ngày [N45].

**Quota** (từ 01/05/2026) [N46]:

- 6.000 đơn vị mỗi phút mỗi người dùng;
- `history.list` 2, `messages.list` 5, `messages.get` 20 (dạng `full` 60), `threads.get` 40 (120), `drafts.create` 10, `drafts.send` 100.

Một ngày khoảng 2.000 tới 3.000 đơn vị.

**Trùng với thông báo Android:** đã bật gói `gmail` thì app không nghe gói `com.google.android.gm` nữa. Tin trùng gộp theo `dedupe_hash`.

## 7. Contacts

Job `sync_google_contacts`, mỗi ngày 04:00:

1. **Lần đầu:** `people.connections.list(people/me, personFields=names,emailAddresses,phoneNumbers,birthdays, pageSize=1000, requestSyncToken=true)` [N47].
2. **Sau đó:** gọi với `syncToken` và **cùng tham số như lần đầu**. Liên hệ bị xóa có `metadata.deleted = true`, đặt `deleted_at`.
3. **Sync token hết hạn** 7 ngày sau lần đồng bộ đủ (`EXPIRED_SYNC_TOKEN`). Tài liệu mẫu xử lý bằng mã 410, nên mã bắt cả 400 lẫn 410 [N47][N48]. Quét mỗi ngày thì nằm trong hạn.

Dùng để:

- đặt tên người gửi trong hộp tin;
- chọn người quan trọng;
- `lookup_contact`;
- nhắc sinh nhật: mặc định tắt (`remind_birthday`), vì Google Calendar đã có lịch *Sinh nhật*. Không rõ năm sinh thì `birthday_year` để rỗng.

Quota đọc của People API: tài liệu không ghi con số (**chưa xác minh**).

## 8. Drive và Sheets

Chỉ dùng `drive.file`: thấy tệp do app tạo và tệp người dùng chọn cho app [N9]. Không có công cụ tìm tệp Drive.

- **Thư mục *Trợ lý*:** tạo khi bật gói `drive` (`mimeType = application/vnd.google-apps.folder`) [N49]. Mã thư mục lưu ở `tab_google_sync_state` (`service = drive`, `resource_id`).
- **Lưu tệp lên Drive:** `POST /api/v1/files/{id}/drive` đặt lệnh `file_upload` vào hàng chờ.
  - Tệp tới 5 MB tải `multipart`, lớn hơn tải `resumable` [N50].
  - Giữ dạng `.docx`, không đổi sang Google Docs.
  - Chia sẻ tệp cho người khác thì phải qua thẻ duyệt; V1.8 chưa làm.
- **Nhập tệp từ Drive:** dùng hộp chọn tệp Android (`ACTION_OPEN_DOCUMENT`): hiện cả nguồn lưu trên mạng, không cần scope [N51]. Drive có hiện trong hộp chọn hay không thì **chưa xác minh**, thử trên máy. Google Picker không chạy trong WebView [N52].
- **Sheets:** `spreadsheets.create` nhận scope `drive.file` [N10].
  1. `POST /api/v1/reports/exports` với `kind = expense_sheet` ghi `tab_export` và một lệnh `sheet_write`.
  2. Mã bảng tính lưu ở `tab_google_sync_state` (`service = sheets`).
  3. Mỗi tháng một trang tính `YYYY-MM`, ghi lại cả trang bằng `values.batchUpdate`.
  4. Chỉ ghi một chiều: sửa trên Sheets sẽ bị ghi đè; dòng đầu trang tính ghi rõ điều này.
- **Quota:**
  - Sheets: 60 lời gọi đọc và 60 lời gọi ghi mỗi phút mỗi người dùng [N55];
  - Drive: `files.create` tốn 50 đơn vị [N54].

## 9. Maps Platform

Chi tiết dùng ở `41-ban-do-lich-trinh.md`.

- **Một khóa máy chủ** `GOOGLE_MAPS_API_KEY`:
  - giới hạn theo IP của VPS;
  - chỉ cho Places API (New), Routes API, Geocoding API;
  - không đưa vào app [N56].
- **Mở bản đồ** bằng Maps URLs và lệnh `google.navigation`: không cần khóa, không tính tiền [N57][N58].
- **Giá:** từ 01/03/2025 không còn tín dụng 200 USD mỗi tháng; mỗi SKU có mức miễn phí riêng mỗi tháng [N59][N60]:

  | Tầng SKU | Miễn phí mỗi tháng |
  |---|---|
  | Essentials | 10.000 |
  | Pro | 5.000 |
  | Enterprise | 1.000 |

  Vẫn phải gắn tài khoản thanh toán [N61].
- **Chặn chi tiêu:** ngân sách (budget) chỉ cảnh báo, không chặn. Chặn cứng bằng quota theo ngày ở trang *Quotas*; chạm quota thì API đó lỗi tới hết ngày [N62].

## 10. Lỗi, thử lại, job

Theo `10-kien-truc-backend.md` mục 3.9.

**Thử lại:**

- **Trong một lời gọi** (429, 5xx, `rateLimitExceeded`): chờ `2^n` giây cộng ngẫu nhiên tối đa 1 giây, trần 64 giây, tối đa 5 lần [N30].
- **Dòng hàng chờ:** chờ `30 giây × 2^(attempts−1)`, tối đa 5 lần, rồi `failed`.

**Lỗi riêng:**

| Lỗi | Xử lý |
|---|---|
| 401 | Làm mới token một lần rồi gọi lại |
| `invalid_grant` | Mục 3.3 |
| 403 `insufficientPermissions` | `GOOGLE_SCOPE_MISSING`, tắt gói |
| 403 `quotaExceeded` | Dừng dịch vụ tới ngày mai |
| 404, 410 | Theo từng dịch vụ |
| 412 | Mục 4.3 |

**Job:**

| Job | Chu kỳ |
|---|---|
| `push_google_outbox` | Mỗi vòng |
| `sync_google_calendar` | Webhook (gộp 10 giây), hoặc 15 phút ±25% |
| `renew_google_watch` | Mỗi ngày 03:00; kênh còn dưới 48 giờ |
| `pull_google_tasks_status` | 15 phút |
| `sync_gmail` | 5 phút |
| `sync_google_contacts` | Mỗi ngày 04:00 |
| `cleanup_google_oauth_state` | Mỗi giờ |

Quét định kỳ cách nhau ít nhất `GOOGLE_SYNC_MIN_SECONDS` (300 giây); đồng bộ do webhook không bị giới hạn này. Lệch ngẫu nhiên chu kỳ là cách Google khuyên để không dồn giờ [N30].

**Hạn mức đủ dư** cho một người dùng:

- Calendar: 600 lời gọi mỗi phút mỗi người dùng; Google dự kiến tính phí trên 1.000.000 lời gọi mỗi ngày mỗi dự án [N30];
- Tasks: 50.000 lời gọi mỗi ngày [N35].

## 11. Bước người dùng tự làm trên Google Cloud Console

1. **Tạo dự án** `troly`, gắn tài khoản thanh toán. Tài khoản mới có 300 USD dùng thử trong 90 ngày [N61].
2. **Bật API:** Calendar, Tasks, Gmail, People, Drive, Sheets, Places API (New), Routes, Geocoding.
3. **Google Auth Platform:**
   1. *Branding*:
      - tên *Trợ lý*, email hỗ trợ;
      - tên miền được phép `baohuynh.io.vn`;
      - đường dẫn trang chính sách riêng tư tĩnh (agent hạ tầng dựng).
   2. *Audience*: External. Thêm email của mình và tài khoản thử vào *Test users* trong lúc dựng.
   3. *Data access*: thêm scope ở mục 3.1. Ghi nhãn mức Console hiện cho Calendar, Tasks, Contacts.
   4. V1.4 chạy ổn thì *Publish app* sang **In production**. Không gửi xác minh.
4. **Client OAuth** loại *Web application*:
   - redirect `https://assistant.baohuynh.io.vn/api/v1/google/oauth/callback`; máy cá nhân dùng client và địa chỉ riêng;
   - ghi `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` vào `.env`.
5. **Khóa Maps:**
   - giới hạn IP của VPS;
   - chỉ ba API Places (New), Routes, Geocoding;
   - ghi `GOOGLE_MAPS_API_KEY`.
6. **Quota mỗi ngày** (*Google Maps Platform > Quotas*). Cách tính ở `41-ban-do-lich-trinh.md` mục 7.3.

   | API | Quota mỗi ngày |
   |---|---|
   | Places API (New) | 300 |
   | Compute Routes | 30 |
   | Route Matrix | 300 phần tử |
   | Geocoding | 300 |

   Thêm ngân sách 1 USD có cảnh báo.
7. **Trong app:** *Cài đặt > Kết nối Google*. Thử 8 ngày sau khi publish: token vẫn chạy thì khẳng định không bị coi là Testing.

## 12. Dữ liệu, API, kiểm thử, rủi ro

**Dữ liệu:** dùng đúng bảng ở `11-co-so-du-lieu.md` mục 3.10 tới 3.12, gồm `tab_google_account`, `tab_google_oauth_state`, `tab_google_sync_state`, `tab_google_outbox`, `tab_event`, `tab_task`, `tab_contact`, `tab_gmail_draft`, `tab_inbox_message`, `tab_pending_action`. Không xin thêm cột.

**API:** dùng đúng `12-api.md` mục 5.1, 5.5 tới 5.7, 5.9, 5.10: `/google/status`, `/google/connect`, `/google/oauth/callback`, `/google/disconnect`, `/google/sync/{service}`, `/google/outbox`, `/webhooks/google/calendar`, `/calendar/*`, `/tasks/*`, `/gmail/drafts*`, `/reports/exports`, `/files/{id}/drive`. Không xin thêm đường.

**Kiểm thử** (QĐ-27: chỉ phần dễ sai, Google giả theo `70-kiem-thu.md`; mẫu phản hồi thật ghi bằng tài khoản thử):

- **Calendar:**
  - lần đầu lưu `nextSyncToken`;
  - lần tăng dần không gửi `timeMin`;
  - 410 thì đồng bộ lại nhưng giữ lệnh chờ;
  - `cancelled` của bản gốc và của ngoại lệ;
  - trải RRULE có `EXDATE` và ngoại lệ;
  - `etag` trùng bỏ qua;
  - 412 thì `conflict` và áp lại được;
  - tạo trùng `id` thì coi như thành công.
- **Mời khách:** chưa duyệt thì không ghi; duyệt thì gửi `sendUpdates=all`.
- **Nhắc:** sự kiện `remind_source = google` không có trong `/calendar/reminders`.
- **Tasks:**
  - việc có giờ không lên Tasks;
  - Google xong thì `done`; bỏ tích thì `todo`;
  - Google xóa thì `remote_deleted`;
  - đổi tên trên Google không nhận;
  - không sinh lệnh hàng chờ cho thay đổi đọc về.
- **Gmail:** thư quảng cáo và thư OTP bị bỏ; 404 history thì đồng bộ đủ; nháp bị sửa thì không gửi.
- **OAuth:** `state` dùng hai lần bị từ chối; thiếu scope thì `thieu-quyen`; `invalid_grant` thì `reauth_required`.
- **Thử tay trên Galaxy S25+:**
  - nối qua Custom Tabs, về bằng `troly://`;
  - token còn sau 8 ngày;
  - hộp chọn tệp thấy Drive;
  - bản gốc sự kiện lặp có về với `timeMin`.

**Rủi ro:**

| Rủi ro | Giảm nhẹ |
|---|---|
| Refresh token vẫn hết hạn ở In production chưa xác minh | Thử 8 ngày; nối lại một chạm |
| Google bỏ diện miễn xác minh cá nhân cho scope Gmail | Gmail tách được; quay về nghe thông báo Gmail |
| Mời nhầm người | Thẻ duyệt hiện đủ email |
| Nhắc trùng | Một nguồn nhắc mỗi sự kiện |
| Health Connect (V2) không cấp quyền cho APK ngoài Play | Dựng thử trên máy trước khi thiết kế V2 |

**Health Connect (V2, ghi trước):**

- Android 14 trở lên có sẵn trong hệ điều hành; cần Google Play services [N63][N64].
- Khai quyền `READ_STEPS`, `READ_SLEEP`, `READ_HEART_RATE`; chỉ đọc được 30 ngày trước lần cấp quyền đầu, trừ khi xin thêm `READ_HEALTH_DATA_HISTORY` [N65].
- Google đòi khai báo trên Play Console khi phát hành qua Play [N67]. APK cài ngoài Play có được cấp quyền không thì **chưa xác minh**.

**Việc kiểm khi dựng V1.4** (QĐ-26, câu K25):

- nhãn mức scope trong Console;
- token sau 8 ngày;
- bản gốc sự kiện lặp với `timeMin`;
- webhook có cần xác minh tên miền không;
- Drive trong hộp chọn tệp.


## 13. Nguồn

Truy cập ngày 18/11/2026.

| Mã | Nội dung | Địa chỉ |
|---|---|---|
| N1 | Testing 100 người, hết hạn 7 ngày; 100 người mới khi chưa xác minh | https://support.google.com/cloud/answer/15549945 |
| N2 | Danh sách scope | https://developers.google.com/identity/protocols/oauth2/scopes |
| N3 | Ngoại lệ xác minh, dùng cá nhân | https://support.google.com/cloud/answer/13464323 |
| N4 | Scope Calendar | https://developers.google.com/workspace/calendar/api/auth |
| N5 | Xác minh scope nhạy cảm | https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification |
| N6 | Scope Tasks | https://developers.google.com/workspace/tasks/auth |
| N7 | Scope Gmail và mức | https://developers.google.com/workspace/gmail/api/auth/scopes |
| N9 | Scope Drive và mức | https://developers.google.com/workspace/drive/api/guides/api-specific-auth |
| N10 | `spreadsheets.create` nhận `drive.file` | https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/create |
| N13 | Refresh token 7 ngày ở Testing | https://developers.google.com/identity/protocols/oauth2 |
| N15 | Chính sách OAuth: dùng cá nhân, cấm user agent nhúng, lưu token | https://developers.google.com/identity/protocols/oauth2/policies |
| N16 | Xác minh scope hạn chế, CASA | https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification |
| N17 | Giới hạn 100 refresh token, lý do token hết hiệu lực | https://developers.google.com/identity/protocols/oauth2 |
| N18 | Luồng máy chủ web | https://developers.google.com/identity/protocols/oauth2/web-server |
| N19 | Quyền chi tiết | https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions |
| N20 | App cài trên máy: `disallowed_useragent`, PKCE, custom scheme, thu hồi | https://developers.google.com/identity/protocols/oauth2/native-app |
| N22 | Ủy quyền trên Android | https://developer.android.com/identity/authorization |
| N23 | Calendar thông báo đẩy | https://developers.google.com/workspace/calendar/api/guides/push |
| N25 | Tài nguyên Event | https://developers.google.com/workspace/calendar/api/v3/reference/events |
| N26 | Đồng bộ Calendar tăng dần, 410 | https://developers.google.com/workspace/calendar/api/guides/sync |
| N27 | `events.list` | https://developers.google.com/workspace/calendar/api/v3/reference/events/list |
| N28 | Lỗi Calendar | https://developers.google.com/workspace/calendar/api/guides/errors |
| N29 | `events.watch` | https://developers.google.com/workspace/calendar/api/v3/reference/events/watch |
| N30 | Quota Calendar, lệch chu kỳ, thử lại | https://developers.google.com/workspace/calendar/api/guides/quota |
| N31 | `If-Match`, 412 | https://developers.google.com/workspace/calendar/api/guides/version-resources |
| N32 | Tài nguyên Task | https://developers.google.com/workspace/tasks/reference/rest/v1/tasks |
| N33 | Phương thức Tasks API | https://developers.google.com/workspace/tasks/reference/rest |
| N34 | `tasks.list` | https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/list |
| N35 | Hạn mức Tasks | https://developers.google.com/workspace/tasks/limits |
| N36 | Scope nhận cho `messages.send`, `drafts.create` | https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send |
| N37 | Dạng thư | https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format |
| N38 | Đồng bộ Gmail | https://developers.google.com/workspace/gmail/api/guides/sync |
| N39 | `history.list` | https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list |
| N40 | Nhãn Gmail | https://developers.google.com/workspace/gmail/api/guides/labels |
| N41 | Gmail đẩy qua Pub/Sub | https://developers.google.com/workspace/gmail/api/guides/push |
| N43 | Gửi thư, trả lời trong luồng | https://developers.google.com/workspace/gmail/api/guides/sending |
| N44 | Nháp Gmail | https://developers.google.com/workspace/gmail/api/guides/drafts |
| N45 | Giới hạn gửi Gmail | https://support.google.com/mail/answer/22839 |
| N46 | Quota Gmail | https://developers.google.com/workspace/gmail/api/reference/quota |
| N47 | `people.connections.list`, sync token 7 ngày | https://developers.google.com/people/api/rest/v1/people.connections/list |
| N48 | Đọc danh bạ (mẫu 410) | https://developers.google.com/people/v1/contacts |
| N49 | Thư mục Drive | https://developers.google.com/workspace/drive/api/guides/folder |
| N50 | Tải tệp lên Drive | https://developers.google.com/workspace/drive/api/guides/manage-uploads |
| N51 | Storage Access Framework | https://developer.android.com/training/data-storage/shared/documents-files |
| N52 | Google Picker | https://developers.google.com/workspace/drive/picker/guides/overview |
| N54 | Hạn mức Drive | https://developers.google.com/workspace/drive/api/guides/limits |
| N55 | Hạn mức Sheets | https://developers.google.com/workspace/sheets/api/limits |
| N56 | Bảo mật khóa Maps | https://developers.google.com/maps/api-security-best-practices |
| N57 | Maps URLs | https://developers.google.com/maps/documentation/urls/get-started |
| N58 | Lệnh Android cho Google Maps | https://developer.android.com/guide/components/google-maps-intents |
| N59 | Đổi giá từ 03/2025 | https://developers.google.com/maps/billing-and-pricing/march-2025 |
| N60 | Mức miễn phí theo SKU | https://developers.google.com/maps/billing-and-pricing/faq |
| N61 | Bắt đầu với Maps Platform | https://developers.google.com/maps/get-started |
| N62 | Quản lý chi phí, quota | https://developers.google.com/maps/billing-and-pricing/manage-costs |
| N63 | Health Connect: bắt đầu | https://developer.android.com/health-and-fitness/guides/health-connect/develop/get-started |
| N64 | Health Connect: khả dụng | https://developer.android.com/health-and-fitness/health-connect/availability |
| N65 | Health Connect: đọc dữ liệu | https://developer.android.com/health-and-fitness/guides/health-connect/develop/read-data |
| N67 | Health Connect: phát hành | https://developer.android.com/health-and-fitness/health-connect/publish |
| N69 | `events.insert`, `sendUpdates` | https://developers.google.com/workspace/calendar/api/v3/reference/events/insert |
