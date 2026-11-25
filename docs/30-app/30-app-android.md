# App Android

Ngày lập: 18/11/2026. Người giữ: agent app Android. Trạng thái: bản 3, gọn hóa theo QĐ-26, QĐ-27 và `80-ra-soat/81-ra-cheo-lan-2.md`.

Lớp gốc của app: Capacitor, plugin Kotlin, quyền, nhắc, cập nhật, build. Màn hình ở [31-giao-dien.md](31-giao-dien.md). Nguồn nền tảng ở mục 11, tra ngày 18/11/2026. Nguồn chuẩn khi lệch (QĐ-25): bảng theo `11`, API theo `12` (`/api/v1`), kiểu hành động theo `20` (vỏ phẳng, QĐ-26), cổng và compose theo `50`, luật OTP theo `60` mục 3.8.

## 1. Mục tiêu

- Một APK cài ngoài cửa hàng, chạy ổn định trên **Samsung Galaxy S25+, cài đặt mặc định** (QĐ-19), một người dùng (QĐ-15, QĐ-27).
- Lớp gốc **mỏng**: nghe thông báo, nhắc đúng giờ khi mất mạng, cài bản APK mới, mở Google Maps, cất mã trong kho khóa Android.
- Không thông báo nào ngoài danh sách cho phép, không mã OTP nào rời điện thoại.
- Build trên GitHub Actions; máy cá nhân chạy mọi thứ trong Docker (QĐ-14).

## 2. Phạm vi

| Phase | Bản | Phần lớp gốc |
|---|---|---|
| 1 | V1.0, V1.1 | Vỏ Capacitor, cất mã, kiểm và cài bản APK mới, nói với trợ lý |
| 2 | V1.2, V1.3 | Dịch vụ nghe thông báo, bộ lọc, hàng đợi gửi lên, các bước quyền và Samsung |
| 3 | V1.4 | Nhắc lịch trên máy |
| 4 | V1.6, V1.7 | Mở Google Maps |
| V2 | | Health Connect, gói giao diện tải riêng có ký số, trả lời tin qua thông báo |

Ở tài liệu khác: màn hình (`31`), bảng và API (`11`, `12`), bóc tách ngân hàng (backend), luật OTP gốc và lớp 2 (`60`), đồng bộ Google và nguồn nhắc (`40`), link bản đồ (`41`), workflow và bí mật CI (`50`).

## 3. Thiết kế

### 3.1 Nền tảng

| Thành phần | Chọn | Nguồn |
|---|---|---|
| Capacitor | 8.x (ổn định mới nhất 8.6.2, 12/11/2026; 9.0.0 mới ở rc) | [N1][N2] |
| Node, JDK | Node 24 (dịch vụ `web` của `50`); JDK 21 | Capacitor 8 cần Node từ 22 [N3]; Capacitor 8.6.2 build bằng Java 21 [N4] |
| `minSdk`, `compileSdk`, `targetSdk` | 26, 36, 36 | [N3][N4] |
| Kotlin, AGP, Gradle | 2.2.20, 8.13.0, 8.14.3 | [N3] |
| WorkManager | `androidx.work:work-runtime-ktx` 2.12.0 | [N9] |
| Android Studio (chỉ khi gỡ lỗi) | Otter 2025.2.1 trở lên | [N3] |

Máy đích chạy One UI 7 (Android 15) trở lên, nên các thay đổi của Android 13, 14, 15 dưới đây đều áp dụng. Capacitor 8 bỏ `adjustMarginsForEdgeToEdge` (giao diện dùng `env(safe-area-inset-*)`) và cần `density` trong `android:configChanges` [N3].

### 3.2 Định danh và cấu hình

| Mục | Giá trị |
|---|---|
| `applicationId` | `vn.io.baohuynh.troly`; bản gỡ lỗi thêm `.debug`, tên *Trợ lý (thử)* |
| Tên hiển thị | **Trợ lý** |
| Phiên bản | `versionName` từ thẻ `vX.Y.Z`; `versionCode = X*10000 + Y*100 + Z` |
| Địa chỉ api | `https://assistant.baohuynh.io.vn` (QĐ-26), gắn lúc build |
| Đường dẫn sâu | `troly://` (thông báo nhắc; trang kết nối Google `troly://cai-dat/google?ket-qua=ok\|huy\|thieu-quyen\|loi`) |
| Bảo vệ | `android:allowBackup="false"`; `network_security_config` cấm HTTP rõ, không ghim chứng chỉ; WebView chỉ nạp nội dung của app, link ngoài mở trình duyệt hệ thống; chỉ activity chính và dịch vụ nghe thông báo được `exported` |

### 3.3 Cấu trúc dự án

```
app/
  package.json, vite.config.ts  Vite cổng 5190, server.watch.usePolling trong container
  capacitor.config.ts
  src/core/native/              lớp bọc plugin, mỗi plugin một tệp + bản giả cho trình duyệt
  src/core/api, src/core/offline, src/app, src/shared, src/modules   (xem 31)
  android/app/src/main/java/vn/io/baohuynh/troly/
    MainActivity.kt             registerPlugin(...)
    notify/                     dịch vụ nghe, NotificationFilter, OtpDetector, DedupeCache
    queue/                      hàng đợi Room, UploadWorker
    alarm/                      ReminderStore, ReminderScheduler, ReminderReceiver, BootReceiver
    update/                     ApkUpdater
    maps/  secure/  system/  voice/
    plugin/                     các lớp Plugin nối phần trên với giao diện
  android/app/src/test/         JUnit JVM; đọc testdata/otp-samples.yaml
```

Luật kiểm được (lọc, OTP, trùng lặp, giờ nhắc) viết thành hàm Kotlin thuần để kiểm bằng JUnit trên JVM. Plugin là lớp cục bộ trong app. Bản giả cho trình duyệt giúp làm giao diện ở dịch vụ `web` không cần điện thoại. Plugin chính thức dùng thêm: `@capacitor/app`, `@capacitor/browser`, `@capacitor/network`, `@capacitor/preferences`.

### 3.4 Plugin

| Plugin | Phương thức | Sự kiện |
|---|---|---|
| **Notify** (P2) | `getStatus()` trả `{listenerGranted, listenerConnected, lastEventAt, queueSize, droppedToday, otpBlockedToday}`; `flushQueue()` | `listenerStateChanged`, `queueChanged` |
| **Alarm** (P3) | `sync()` (lớp gốc tự tải `/calendar/reminders` bằng mã thiết bị); `getScheduled()` trả `{count, revision, lastSyncAt, exactAllowed, next[]}`; `canScheduleExact()` | `reminderAction` |
| **Update** (P1) | `checkApk()`; `downloadAndInstall()` (chỉ gọi sau khi người dùng bấm *Cập nhật*); `getVersion()` | `downloadProgress`, `installState` |
| **Files** (QĐ-41) | `open({url, name, mime})` tải link tải tạm https về `cacheDir/exports` (tối đa 50 MB, giữ 20 tệp) rồi mở bằng `ACTION_VIEW` qua FileProvider, cấp quyền đọc; không có app mở được thì trả `opened = false`; `share({path, mime})` gửi `ACTION_SEND` | |
| **Maps** (P4) | `navigate({lat, lng, query, mode, avoid, uri, fallbackUrl})`; `openUrl({url})`; `isMapsInstalled()` | |
| **Secure** (P1) | `storeDeviceToken`, `hasDeviceToken`, `saveRefreshToken`, `loadRefreshToken`, `clearAll` | `deviceRevoked` |
| **System** (P1, P2) | `getPermissions()`; `openSettings({target})` (`notification_listener`, `app_details`, `battery`, `samsung_never_sleeping`, `exact_alarm`, `unknown_sources`, `notifications`); `getDeviceInfo()` trả `{manufacturer, model, androidSdk, defaultSmsPackage}` | `permissionsChanged` |
| **Voice** (1.0.6) | `start({lang: 'vi-VN'})` (xin `RECORD_AUDIO` khi bấm lần đầu), `stop()`, `cancel()` bằng `SpeechRecognizer` (WebView không có Web Speech); `speak({text})`, `stopSpeaking()`, `ttsStatus()`, `openTtsSettings()` bằng `TextToSpeech` tiếng Việt của máy. Câu lỗi tiếng Việt ở `voice/VoiceText` (có JUnit). Manifest khai `<queries>` cho `RecognitionService` và `TTS_SERVICE` | `partial`, `final`, `error` {code, message}, `end`, `speakEnd` |

Hai danh tính (`10` mục 3.7): giao diện gọi API bằng JWT, làm mới bằng mã làm mới (365 ngày, QĐ-27); lớp gốc gọi nhóm `/api/v1/device/*` và `/calendar/reminders` bằng `Authorization: Device <mã thiết bị>`. Mã thiết bị không đổi lấy JWT, không trả về JavaScript. Mọi yêu cầu gửi `X-App-Version`.

### 3.5 Đăng nhập và cất mã (Phase 1)

- Đăng nhập một lần bằng mật khẩu (`POST /api/v1/auth/login`); mã làm mới 365 ngày, xoay vòng mỗi lần làm mới (QĐ-27). Không có khóa vân tay.
- Sau lần đăng nhập đầu, giao diện gọi `POST /api/v1/devices`, nhận **mã thiết bị** một lần và chuyển ngay cho `Secure.storeDeviceToken`.
- Mã thiết bị và mã làm mới mã hóa AES-256-GCM bằng khóa sinh trong `AndroidKeyStore`, vật liệu khóa không ra khỏi kho [N17]; bản mã ở bộ nhớ riêng của app. Khóa không gắn xác thực người dùng, nên việc nền chạy được khi màn hình khóa.
- 401 `DEVICE_REVOKED` hoặc mã làm mới hỏng: `Secure.clearAll()`, về màn đăng nhập.

### 3.6 Dịch vụ nghe thông báo (Phase 2)

**Khai báo.** `NotificationListenerService` có `permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"`, `intent-filter` `android.service.notification.NotificationListenerService`, `meta-data` `disabled_filter_types = ongoing` [N5]. Không chặn loại `silent`.

**Vòng đời.** `onListenerConnected` ghi thời điểm; `onNotificationPosted` chạy bộ lọc trên luồng nền (hàm gọi lại chạy trên luồng chính từ Android 7 [N5]) rồi ghi hàng đợi; `onListenerDisconnected` gọi `requestRebind` [N5]. Không dùng dịch vụ tiền cảnh; trên Samsung, việc giữ dịch vụ sống dựa vào mục 3.10.

**Dữ liệu đọc** (chỉ khi gói qua bước 1 của bộ lọc): `title` (`EXTRA_TITLE`), `text` (`EXTRA_BIG_TEXT`, không có thì `EXTRA_TEXT`), `conversation_title` và `messages[]` (`MessagingStyle`: người gửi, chữ, thời điểm), `is_group_conversation`, `category`, `notification_key_hash` (SHA-256 của `sbn.key`), `hidden_content`. `messages[]` giúp chỉ lấy tin mới khi Zalo, Messenger cập nhật cùng một thông báo.

**Danh sách app được nghe** (`tab_listened_app`, máy chủ là gốc, chỉ đổi ở màn Cài đặt):

| App | Tên gói | Mục đích |
|---|---|---|
| Vietcombank | `com.VCB` | Chi tiêu |
| Techcombank | `vn.com.techcombank.bb.app` | Chi tiêu |
| MoMo | `com.mservice.momotransfer` | Chi tiêu |
| Zalo | `com.zing.zalo` | Hộp tin |
| Telegram | `org.telegram.messenger` | Hộp tin |
| Messenger | `com.facebook.orca` | Hộp tin |
| App SMS mặc định | `sms_default` | Hộp tin |

- `sms_default` (K14, theo `11`): plugin thay bằng gói SMS mặc định thật của máy (`Telephony.Sms.getDefaultSmsPackage()`), gửi gói này qua `heartbeat` để máy chủ lưu `tab_device.default_sms_package`. Người dùng đổi app SMS mặc định thì plugin tự theo. Trên S25+ đó là Samsung Messages (`com.samsung.android.messaging`) hoặc Google Messages (`com.google.android.apps.messaging`), QĐ-19.
- Khai `<queries>` cho 6 gói trên, hai gói SMS và `com.google.android.apps.maps` [N13]; không dùng `QUERY_ALL_PACKAGES`.
- Plugin lấy danh sách và bộ luật OTP bằng `GET /api/v1/device/config` (304 khi không đổi). Khi Gmail đã nối, máy chủ bỏ `com.google.android.gm` khỏi danh sách.

### 3.7 Bộ lọc trên máy (lớp 1)

Hàm thuần `filterNotification(input, rules, now)` trả `Drop(lý do)` hoặc `Keep(sự kiện)`, theo thứ tự:

1. Gói không có trong danh sách đang bật: bỏ, không đọc trường nào, không ghi tên gói; tăng `droppedToday`.
2. Thông báo của chính app.
3. Thông báo tiến trình: cờ `FLAG_ONGOING_EVENT`, `FLAG_FOREGROUND_SERVICE`; `category` `progress`, `call`, `transport`, `service`, `navigation`; có `EXTRA_PROGRESS_MAX > 0`.
4. Tóm tắt nhóm (`FLAG_GROUP_SUMMARY`).
5. **OTP** (bảng dưới): bỏ cả thông báo, tăng `otpBlockedToday`, không lưu nội dung.
6. Trùng: cùng băm `(gói, tiêu đề, chữ)` trong 10 phút, hoặc tin trong `messages[]` đã gửi (bộ đệm 24 giờ, tối đa 2.000 mục).
7. Rỗng với app ngân hàng, ví: bỏ. App tin nhắn rỗng thì giữ với `hidden_content = true`.

Sau đó cắt `text` tối đa 2.000 ký tự, gắn `client_event_id` (UUID), ghi hàng đợi.

**Luật OTP**, đúng `60` mục 3.8; máy chủ chạy cùng bộ luật ở lớp 2:

| Luật | Nội dung |
|---|---|
| Từ khóa (không phân biệt hoa thường, so cả bản bỏ dấu) | `OTP`, `mã xác thực`, `mã xác nhận`, `mã xác minh`, `mã kích hoạt`, `mật khẩu một lần`, `Smart OTP`, `không cung cấp mã`, `không chia sẻ mã`, `verification code`, `passcode`, `one-time`, `security code`, `login code`, `2FA` |
| Mẫu số | Chuỗi 4 tới 8 chữ số đứng riêng cùng câu với một từ khóa, hoặc dạng `123-456`; `G-123456` luôn chặn. Không tính là mã khi dính ngày, giờ, số tiền có dấu ngăn, hay mã tham chiếu có dấu chấm (chỉ loại khi dấu chấm, dấu phẩy nối tiếp chữ số; `445566,` vẫn là mã) |
| Theo nguồn | Thông báo của app mục đích *Chi tiêu* không có dấu hiệu số tiền thì bỏ cả tin, có mã hay không. Dấu hiệu số tiền: số có dấu ngăn nghìn `\d{1,3}([.,]\d{3})+`, hoặc số kèm *vnd*, *dong*, *d* (theo `backend/app/modules/device/otp.py` bản 2026-11-18.3). Mục đích lấy theo 7 app mặc định |
| Theo người gửi SMS | Tiêu đề là tên thương hiệu ngân hàng, ví, sàn thương mại điện tử, dịch vụ đăng nhập và nội dung có chuỗi 4 tới 8 chữ số. Danh sách tên nằm trong bộ luật gửi qua `/device/config` |

Android 15 tự che nội dung thông báo có OTP với app nghe thông báo [N12]; máy đích luôn có lớp này, thông báo bị che coi như rỗng. Bộ mẫu chung `testdata/otp-samples.yaml` dùng cho cả JUnit và bài kiểm Python.

### 3.8 Hàng đợi gửi lên

- Bảng Room `device_event_queue`, giữ tối đa 7 ngày hoặc 5.000 dòng.
- WorkManager, việc duy nhất `upload-events`, cần mạng, lùi lũy thừa từ 30 giây [N9]. Mỗi lô tối đa 50 sự kiện, 256 KB, tới `POST /api/v1/device/events` (`12` mục 5.12).
- Máy chủ trả `accepted`, `duplicates`, `rejected[]`; máy xóa cả lô. `rejected` mã `OTP_DETECTED` nghĩa là lớp 1 để lọt: ghi mã sự kiện (không ghi nội dung) để sửa luật.
- Mạng lỗi, 5xx: thử lại; 429: chờ `Retry-After`; 401 `DEVICE_REVOKED`: dừng, xóa mã; 426: giữ hàng đợi, chờ cập nhật.
- Doze hoãn việc nền và mạng tới cửa sổ bảo trì [N8]; mở app thì `Notify.flushQueue()` gửi ngay. Dịch vụ nghe không gọi mạng trực tiếp (Android 15 chặn mạng ngoài vòng đời tiến trình [N12]).

**`payload` của sự kiện `notification`:** `title`, `text`, `conversation_title`, `messages[]`, `is_group_conversation`, `category`, `notification_key_hash`, `hidden_content`; `app_package`, `posted_at` ở cấp sự kiện. **`reminder_action`:** `reminder_key`, `source`, `source_id`, `action` (`done`, `ack`, `snooze`), `at`.

### 3.9 Nhắc lịch trên máy (Phase 3)

- App chỉ nhắc sự kiện `remind_source = app` và việc có hạn; sự kiện tạo trên Google do Google nhắc (`40` mục 4.6, QĐ-26).
- Đồng bộ `GET /api/v1/calendar/reminders?days=14` (U/D, `If-None-Match`, 304) khi mở app, khi quay lại tiền cảnh, ngay sau khi sửa lịch hoặc việc, và WorkManager mỗi 1 giờ. Mỗi nhắc có `key` ổn định.
- Quyền `USE_EXACT_ALARM` (cấp khi cài, dành cho app lịch) và `SCHEDULE_EXACT_ALARM` với `maxSdkVersion="32"` [N6][N7]. Luôn kiểm `canScheduleExactAlarms()` [N6].
- Nhắc mặc định là **thông báo thường** kêu một tiếng như tin nhắn (QĐ-39), hẹn đúng giờ bằng `setExactAndAllowWhileIdle` (trong Doze tối đa một lần mỗi 9 phút [N8]). **Kiểu báo thức** chỉ khi nhắc có cờ `alarm: true` (người dùng nói rõ *báo thức*): `setAlarmClock`, kênh `bao-thuc`, hiện toàn màn hình nếu máy cho phép, kêu liên tục tới khi bấm [N7][N8]. Thiếu quyền chính xác: `setWindow` 10 phút.
- Sau mỗi lượt chat có chạy công cụ, khi quay lại tiền cảnh, sau khi sửa lịch hoặc việc: app tải `/calendar/reminders` ngay trên luồng phụ (không chờ WorkManager) để nhắc chỉ còn vài phút cũng kịp đặt.
- Trợ lý trả lời lúc app không ở màn hình (QĐ-41): stream xong mà app ở nền thì app tự báo ngay (kênh `tro-ly-tra-loi`); gửi tin rồi rời app khi lượt chưa xong thì lớp gốc hỏi `/device/notices` khoảng 20 giây một lần, tối đa 15 lần, dừng khi thấy `chat_done`. Chống báo trùng theo `message_id`. Bấm mở `troly://?phien=<id>&tin=<id>`, nút *Mở tệp* thêm `mo-tep=<file_id>`. Công tắc ở Cài đặt, Thông báo (`notify.chat_done` và cờ trên máy).
- Cài đặt, Thông báo (QĐ-38): kêu và rung, giờ yên lặng lưu trên máy (`NotifyPrefs`); kênh `giao-dich`, `tin-quan-trong` cho thông báo máy chủ báo qua `GET /device/notices` (hỏi mỗi 15 phút và sau mỗi lô sự kiện).
- Đặt lại khi: `BOOT_COMPLETED` [N7], `MY_PACKAGE_REPLACED`, `TIME_SET`, `TIMEZONE_CHANGED`, `ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED` [N6], và khi mở app (Android 15 hủy mọi `PendingIntent` khi buộc dừng [N12]).
- Kênh thông báo `nhac-lich`, `bao-thuc`, `cap-nhat`, `he-thong`; cần `POST_NOTIFICATIONS` [N15]. Nút **Xong** hoặc **Đã biết**, **Hoãn 10 phút**; bấm nút ghi sự kiện `reminder_action`. Chạm mở `troly://lich/su-kien/<id>` hoặc `troly://lich/viec/<id>`.
- Trên máy (`alarm/`): `ReminderStore` giữ danh sách, `revision`, phần đã bấm Xong hoặc Đã biết, phần hoãn; `ReminderPlan` tính báo thức cần đặt (thuần Kotlin, có JUnit), tối đa 400 báo thức; nhắc lỡ giờ do máy tắt thì hiện bù nếu chưa quá 15 phút. Nhắc của việc (`source = task`) có nút **Xong**, của sự kiện có nút **Đã biết**. Đăng xuất hoặc `DEVICE_REVOKED` thì bỏ danh sách và hủy mọi báo thức.
- Samsung hạn chế báo thức của app đang ngủ [N28], nên bước *Ứng dụng không bao giờ ngủ* là bắt buộc để nhắc chắc kêu.

Đặt chỗ từ email (QĐ-49): notice `booking_added` `{id, title, body, deep_link, booking_id, event_id}` hiện ở kênh *Nhắc lịch*, chạm mở sự kiện trên màn Lịch, nút *Hoàn tác* (`alarm/BookingUndoReceiver`) đổi thông báo thành *Đang hoàn tác* rồi WorkManager gọi `POST /device/bookings/{id}/undo` bằng mã thiết bị khi có mạng; xong (hoặc 404) thì *Đã bỏ ... khỏi Lịch*, máy chủ từ chối thì hiện câu của máy chủ (`BookingUndoPlan`, có JUnit). Đã thống nhất với agent Google (20/11): 409 khi sự kiện đã sửa, `event_id` là sự kiện nhận phòng hoặc khởi hành; vé máy bay, xe, tàu chỉ vào Lịch, không gắn điểm.

### 3.10 Quyền và các bước Samsung

| Quyền | Dùng cho | Phase |
|---|---|---|
| `INTERNET`, `USE_EXACT_ALARM`, `RECEIVE_BOOT_COMPLETED` | Tự có khi cài | P1, P3 |
| `POST_NOTIFICATIONS` (lúc chạy, Android 13+ [N15]) | Nhắc, báo bản mới | P1 |
| `RECORD_AUDIO` (lúc chạy) | Nói với trợ lý | P1 |
| `REQUEST_INSTALL_PACKAGES` (*Cài ứng dụng không rõ nguồn gốc*) | Cài APK mới | P1 |
| Truy cập thông báo (truy cập đặc biệt) | Hộp tin, chi tiêu tự động | P2 |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Pin *Không hạn chế* | P2 |

Không xin: vị trí, danh bạ máy, SMS, `QUERY_ALL_PACKAGES`, dịch vụ tiền cảnh, trợ năng, sinh trắc.

**Các bước thiết lập máy** (Phase 2, màn *Thiết lập máy* ở `31`), mỗi bước một nút mở đúng trang; app kiểm lại mỗi khi quay lại tiền cảnh:

1. **Thông báo:** hộp hỏi `POST_NOTIFICATIONS`; kiểm bằng `areNotificationsEnabled()` [N15].
2. **Đọc thông báo:** mở `ACTION_NOTIFICATION_LISTENER_SETTINGS`; kiểm bằng `isNotificationListenerAccessGranted`. App cài từ trình duyệt trên Android 13 trở lên bị **cài đặt bị hạn chế**, công tắc khóa xám [N10][N11]. Hướng dẫn: bấm bật một lần, bị chặn thì vào *Cài đặt > Ứng dụng > Trợ lý > menu ba chấm > Cho phép cài đặt bị hạn chế*, xác nhận, quay lại bật [N10].
3. **Pin không hạn chế:** `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` hiện hộp hỏi của hệ thống; kiểm bằng `isIgnoringBatteryOptimizations()` [N8]. Google Play cấm cách này trừ khi chức năng cốt lõi bị ảnh hưởng [N8]; app cài ngoài và nghe thông báo là cốt lõi.
4. **Ứng dụng không bao giờ ngủ (Samsung):** One UI cho app ngủ sau khoảng 3 ngày không dùng (hạn chế Job, Alarm, dịch vụ tiền cảnh) và ngủ sâu sau 16 ngày (không chạy nền, không gửi thông báo) [N28]. Nút mở thẳng danh sách bằng intent Samsung công bố: action `com.samsung.android.sm.ACTION_OPEN_CHECKABLE_LISTACTIVITY`, package `com.samsung.android.lool`, extra `activity_type = 2` [N28]. Mở không được thì hướng dẫn tay: *Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > Trợ lý > Thêm* [N29]. App không đọc được danh sách này: người dùng bấm *Đã làm*; app còn theo dõi gián tiếp (quá 24 giờ không có sự kiện).
5. **Báo thức chính xác** (Phase 3): chỉ hiện khi `canScheduleExactAlarms()` sai, mở `ACTION_REQUEST_SCHEDULE_EXACT_ALARM` [N6].

### 3.11 Cập nhật và cài APK (Phase 1)

**V1 chỉ cập nhật bằng APK** (QĐ-27): giao diện React nằm trong APK; mọi thay đổi giao diện đi kèm một APK mới. Gói giao diện tải riêng có ký số để V2.

1. Khi mở app và mỗi ngày một lần: `GET /api/v1/device/release?current_version_code=` (`12` mục 5.12) trả `{update_available, required, latest: {version_code, version_name, download_url, sha256, size_bytes, notes}}`.
2. Có bản mới: dải *Có bản x.y.z* trong app. **Không tải, không cài khi người dùng chưa bấm *Cập nhật*** (QĐ-18).
3. Bấm *Cập nhật* (sửa lỗi 1.0.9, bản 1.1.0): **gọi lại `/device/release` ngay lúc bấm** để có link mới (máy chủ ký `download_url` mới mỗi lần gọi, sống `download_expires_in` giây, 1.800; link lấy lúc mở app có thể đã hết hạn). Plugin `Update` (`plugin/UpdatePlugin.kt`, luật ở `update/ApkCheck`, có JUnit) tải bằng `HttpURLConnection` vào `filesDir/updates/troly-<version_code>.apk` (không qua trình duyệt: Custom Tab tải tệp trên Samsung không chắc), báo sự kiện `progress` `{done, total, percent}`, băm `sha256` trong lúc tải, đọc tên gói bằng `getPackageArchiveInfo`; sai mã kiểm hoặc khác gói đang chạy thì xóa tệp và báo. Tệp đã tải đúng thì lần bấm sau dùng lại. Rồi `canRequestPackageInstalls()`: sai thì mở `ACTION_MANAGE_UNKNOWN_APP_SOURCES` của riêng Trợ lý (dải báo ghi *bật Cho phép cài từ nguồn này rồi quay lại*), quay về đã bật thì cài tiếp. Cài bằng `ACTION_VIEW` với link `FileProvider` (`files-path` `updates/`), hộp cài của Android hỏi người dùng. Dải báo hiện phần trăm; lỗi mạng, link hết hạn, sai mã kiểm thì *Thử lại* (lấy link mới); luôn có *Tải bằng trình duyệt* mở `https://assistant.baohuynh.io.vn/tai-app` bằng trình duyệt hệ thống (không dùng link ký; trang có thể trỏ `GET /tai-app/apk`, không cần đăng nhập, 302 sang link ký mới). Mã lỗi plugin: `network`, `http`, `sha`, `package`, `size`, `storage`, `not_allowed`, `settings`. Không còn bản mới thì xóa tệp đã tải (`cleanup`). Máy đang ở 1.0.9 phải cài bản sửa một lần bằng cáp hoặc `/tai-app`.
4. `required = true`: chặn app, chỉ còn nút *Cập nhật*.
5. Cài xong: `MY_PACKAGE_REPLACED` đặt lại báo thức, thông báo *Đã cập nhật lên x.y.z*.

**Cài lần đầu:** mở trang `https://assistant.baohuynh.io.vn/tai-app` (công khai, `50`) trên trình duyệt Samsung hoặc Chrome, tải APK, cho phép trình duyệt *Cài ứng dụng không rõ nguồn gốc*, cài, mở app, đăng nhập, làm thiết lập máy.

**Khi Android chặn cài.** Từ năm 2027 Android chặn cài và cập nhật app chưa đăng ký với chương trình xác minh nhà phát triển trên máy được chứng nhận [N20][N21]. Chỉ làm khi gặp (QĐ-27): cài bằng `adb install` (không bị chặn [N21]), hoặc mở tài khoản phân phối giới hạn miễn phí trên Android Developer Console và đăng ký tên gói cùng khóa ký [N23].

### 3.12 Mở Google Maps (Phase 4)

| Hành động | Cách mở |
|---|---|
| `open_map_navigation` | Có `uri` (máy chủ dựng sẵn) thì mở thẳng; không thì `google.navigation:q=<lat>,<lng>&mode=l&avoid=h`, `setPackage("com.google.android.apps.maps")` (`l` xe hai bánh, `h` tránh cao tốc) [N24]. Không có tọa độ (thường gặp từ QĐ-36, V1 không có Maps Platform) thì `q=<tên đã mã hóa>`; màn Lịch trình dùng `place_query`, thiếu thì tên điểm |
| `open_map_directions`, `open_map_place` | Mở URL do máy chủ dựng (`/trips/{id}/map-links`, `12` mục 5.8) [N25] |

Luôn `resolveActivity` trước; không có Maps thì mở `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>&travelmode=two-wheeler&dir_action=navigate` bằng trình duyệt [N24][N25]. App gửi `max_waypoints = 9` nếu có Maps, `3` nếu không (URL chỉ đường cho tối đa 3 điểm dừng trên trình duyệt di động, 9 ở nơi khác) [N25]. Chế độ `two-wheeler` chỉ có ở quốc gia được hỗ trợ [N25]: thử trên máy thật.

### 3.12c Chia sẻ vào Trợ lý (QĐ-51 bước 2)

`MainActivity` có intent-filter `ACTION_SEND` (chữ, ảnh, PDF, DOCX) và `ACTION_SEND_MULTIPLE` (ảnh, PDF). Plugin `ShareIn` (`plugin/ShareInPlugin.kt`) đọc intent lúc mở app và lúc `onNewIntent`, chép tối đa 4 tệp (mỗi tệp tới 25 MB, loại như ô đính kèm của chat; luật ở `share/SharePlan`, có JUnit) vào `cacheDir/shared/`, rồi phát sự kiện `shared` `{text, files: [{path, name, mime, size}], skipped}` giữ tới khi giao diện nghe. Giao diện mở `/chia-se`; tải xong thì `cleanup()` xóa tệp đệm.

### 3.13 Khóa ký và build

- Khóa ký: sinh một lần bằng `keytool` trong container JDK, RSA 4096, `-validity 10950` (30 năm; Android khuyên từ 25 năm) [N26]. Mất khóa thì không cập nhật đè được [N26]. Cất theo `60` mục 3.6; không lên git.
- Workflow `app-build.yml` theo `50`. Thẻ `vX.Y.Z` chạy job `apk`: Node 24, `npm ci`, `npm run build`, `npx cap sync android`, JDK 21, giải mã kho khóa ra tệp tạm, `./gradlew testReleaseUnitTest assembleRelease`, `apksigner verify --print-certs` so với biến `ANDROID_SIGNING_CERT_SHA256`, đẩy `releases/troly-<versionName>.apk` lên bucket `troly-release`, đăng bản qua API, xóa kho khóa tạm. Đổi `app/android/**` hoặc `testdata/**` chạy job JUnit JVM.
- Bí mật: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `R2_RELEASE_ACCESS_KEY_ID`, `R2_RELEASE_SECRET_ACCESS_KEY`, `R2_ENDPOINT`; mã đăng bản theo `50`.

### 3.14 Gỡ lỗi

Thường ngày không cần Android Studio: dịch vụ `web` (Vite 5190, proxy `/api` sang 8200) với bản giả plugin; JUnit trong dịch vụ `android-test` hoặc CI. Khi plugin sai trên máy thật:

1. Android Studio Otter trở lên [N3]. Trên S25+: *Cài đặt > Thông tin điện thoại > Thông tin phần mềm*, chạm *Số hiệu bản tạo* 7 lần, bật *Gỡ lỗi USB*.
2. `npx cap sync android`, `npx cap open android`, chạy biến thể `debug`.
3. `adb logcat -s Troly` (không ghi nội dung thông báo); `chrome://inspect` cho WebView bản gỡ lỗi.
4. Thử Doze: `adb shell dumpsys deviceidle force-idle`, thoát bằng `unforce` [N8]. Giả thông báo: `adb shell cmd notification post -t "<tiêu đề>" <tag> "<nội dung>"` (bản gỡ lỗi có công tắc nghe gói `com.android.shell`).

## 4. Dữ liệu cần

**Máy chủ** (`11` đã nhận theo K15): `tab_device` có `listener_connected`, `notifications_enabled`, `exact_alarm_allowed`, `queue_size`, `manufacturer`, `default_sms_package`, `otp_blocked_today`; `tab_device_event.kind` gồm `notification`, `reminder_action`; `tab_listened_app` 7 dòng mặc định ở mục 3.6.

**Trên máy** (Room): `device_event_queue` (7 ngày), `reminder` (cửa sổ 14 ngày), `seen_hash` (24 giờ), `conversation_cursor` (7 ngày). Bộ đếm, phiên bản bộ luật OTP, bước Samsung đã làm lưu bằng DataStore.

## 5. API hoặc giao tiếp

Theo `12`, dưới `/api/v1`:

| Ai gọi | Đường dẫn | Phase |
|---|---|---|
| Giao diện | `/auth/login`, `/auth/refresh`, `POST /devices`, `/devices/listened-apps` | P1, P2 |
| Giao diện hoặc plugin | `GET /device/release` | P1 |
| Plugin | `GET /device/config` (danh sách app, bộ luật OTP, tên thương hiệu SMS), `POST /device/heartbeat` (trường ở mục 4, `default_sms_package`), `POST /device/events` | P2 |
| Giao diện hoặc plugin | `GET /calendar/reminders` | P3 |

Hành động trợ lý: kiểu theo `20`, vỏ phẳng (QĐ-26); lớp gốc phục vụ `open_map_*` và `open_link`.

## 6. Kiểm thử

Theo QĐ-27 mục 8, chỉ phần dễ sai:

| Phần | Ca chính |
|---|---|
| `OtpDetector` | Toàn bộ `testdata/otp-samples.yaml` cho cùng kết quả với bài kiểm Python; đủ 15 từ khóa, có dấu và không dấu; `G-123456`, `123-456`; thông báo ngân hàng không khớp mẫu giao dịch bị bỏ; SMS từ tên thương hiệu có 4 tới 8 chữ số bị bỏ; biến động số dư được giữ; tin chat có số điện thoại, số tiền không bị bỏ nhầm |
| `filterNotification` | Gói ngoài danh sách bị bỏ, không đọc trường nào; tiến trình, cuộc gọi, tóm tắt nhóm bị bỏ; ẩn nội dung được giữ với `hidden_content`; trùng trong 10 phút bị bỏ; `messages[]` chỉ lấy tin mới |
| `ReminderPlanner` | `setAlarmClock` cho loại báo thức; cửa sổ 14 ngày; nhắc đã qua bị bỏ; hoãn 10 phút; giờ Việt Nam |

**Thử tay trên Galaxy S25+** (mỗi APK có đổi lớp gốc):

1. Cài từ trang `/tai-app`; gặp cài đặt bị hạn chế, làm theo hướng dẫn, bật được quyền đọc thông báo.
2. Nút *Ứng dụng không bao giờ ngủ* mở đúng danh sách; thêm được app.
3. Giao dịch thật Vietcombank, Techcombank, MoMo ra đúng một sự kiện; OTP thật không lên máy chủ, `otpBlockedToday` tăng.
4. SMS ở app SMS mặc định vào hộp tin; đổi app SMS mặc định thì plugin theo.
5. Tin Zalo nhóm, riêng, và khi Zalo ẩn nội dung.
6. Tắt mạng, nhận 5 thông báo, bật mạng: đủ 5, không trùng.
7. Nhắc 2 phút tới, tắt mạng, khóa màn hình: kêu đúng giờ; khởi động lại máy vẫn kêu; sự kiện tạo trên Google không kêu hai lần.
8. Để máy 3 ngày không mở app: nhắc vẫn kêu, sự kiện vẫn lên.
9. Dẫn đường mở Google Maps chế độ xe hai bánh ở Việt Nam.
10. Bản APK mới: app hỏi trước, bấm *Cập nhật* thì cài được; nhắc còn sau cập nhật.

## 7. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| One UI cho app ngủ, dịch vụ nghe và báo thức dừng [N28] | Bước *Ứng dụng không bao giờ ngủ*, pin không hạn chế; cảnh báo khi quá 24 giờ không có sự kiện |
| Cài đặt bị hạn chế làm kẹt bước đọc thông báo | Hướng dẫn có thứ tự; lần đầu có thể cài bằng `adb` |
| Android 15 che nhầm thông báo biến động số dư [N12]; luật *theo nguồn* bỏ nhầm giao dịch định dạng lạ | Thử giao dịch thật; bộ mẫu chung; ghi bù bằng chat |
| Năm 2027 Android chặn cài app chưa đăng ký [N20][N21] | Đường lùi `adb` hoặc tài khoản phân phối giới hạn (mục 3.11) |
| Không có đẩy tin: nhắc của sự kiện sửa từ máy khác trễ tới 1 giờ | Sự kiện tạo trên Google do Google nhắc; đồng bộ khi mở app |
| Mất khóa ký APK | Cất theo `60` mục 3.6 |

## 8. Câu hỏi mở

Không còn. Các câu của bản 2 đã được trả lời ở QĐ-26 và QĐ-27.

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| kiến trúc (`12`) | Bỏ `/device/web-bundle` và `web_version`, chuyển `/device/release` về V1.0 (QĐ-27); `/device/config` trả bộ luật OTP và tên thương hiệu SMS, bỏ cờ đồng ý; `heartbeat` nhận `default_sms_package`, `manufacturer`, `otp_blocked_today` |
| hạ tầng (`50`) | Job `apk` bỏ bước ký gói giao diện và secret `WEB_BUNDLE_SIGNING_KEY`, bỏ job `ui` đăng gói giao diện, bỏ `troly.minNativeVersionCode`; giữ biến `ANDROID_SIGNING_CERT_SHA256`; trang `/tai-app` ghi các bước cài ở mục 3.11 |
| hạ tầng (`70`) | Bỏ máy ảo và `testhelper`; phần app chỉ còn mục 6 |
| điều phối (`02`) | Bỏ `app/android/testhelper/` và gói `secure/` chỉ còn cất mã; `00` chuyển *kiểm bản APK mới* vào Phase 1 |

## 10. Đề xuất quyết định

Không có đề xuất mới. ĐX-30-01 tới 30-14 đã xử lý ở QĐ-25, QĐ-26 (ĐX-30-12 không nhận, theo `sms_default`); phần cập nhật hai lớp của ĐX-30-03, 30-05 và khóa vân tay của 30-08 thay bằng QĐ-27.

## 11. Nguồn

Tra ngày 18/11/2026.

- [N1] Capacitor docs v8: https://capacitorjs.com/docs
- [N2] npm `@capacitor/core` (latest 8.6.2, next 9.0.0-rc.0): https://registry.npmjs.org/@capacitor/core
- [N3] Capacitor, Updating to 8.0: https://capacitorjs.com/docs/updating/8-0
- [N4] Mã nguồn Capacitor ở thẻ 8.6.2: https://github.com/ionic-team/capacitor
- [N5] `NotificationListenerService`: https://developer.android.com/reference/android/service/notification/NotificationListenerService
- [N6] Android 14, exact alarms denied by default: https://developer.android.com/about/versions/14/changes/schedule-exact-alarms
- [N7] Schedule alarms: https://developer.android.com/develop/background-work/services/alarms/schedule
- [N8] Doze and App Standby: https://developer.android.com/training/monitoring-device-state/doze-standby
- [N9] WorkManager: https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started
- [N10] Android Help, restricted settings: https://support.google.com/android/answer/12623953
- [N11] Kaspersky, Restricted Settings in Android 13 and 14 (nguồn phụ): https://www.kaspersky.com/blog/android-restricted-settings/49991/
- [N12] Android 15 behavior changes: https://developer.android.com/about/versions/15/behavior-changes-all
- [N13] Package visibility: https://developer.android.com/training/package-visibility/declaring
- [N15] Notification runtime permission: https://developer.android.com/develop/ui/views/notifications/notification-permission
- [N17] Android Keystore: https://developer.android.com/privacy-and-security/keystore
- [N18] `PackageInstaller`: https://developer.android.com/reference/android/content/pm/PackageInstaller
- [N20] Android developer verification: https://developer.android.com/developer-verification
- [N21] Developer verification FAQ (`adb` không bị chặn): https://developer.android.com/developer-verification/guides/faq
- [N23] Limited distribution accounts: https://developer.android.com/developer-verification/guides/limited-distribution
- [N24] Google Maps Intents: https://developer.android.com/guide/components/google-maps-intents
- [N25] Maps URLs: https://developers.google.com/maps/documentation/urls/get-started
- [N26] Sign your app: https://developer.android.com/studio/publish/app-signing
- [N28] Samsung Developer, Application Management: https://developer.samsung.com/mobile/app-management.html
- [N29] Samsung Support, Sleeping apps: https://www.samsung.com/us/support/answer/ANS10003442/
