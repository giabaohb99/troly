# App Android

Ngày lập: 18/11/2026. Người giữ: agent app Android. Trạng thái: bản 2, đã sửa theo `80-ra-soat/80-ra-cheo-lan-1.md` và QĐ-15 tới QĐ-25.

Tài liệu này mô tả lớp gốc của app (Capacitor, plugin Kotlin, quyền, nhắc, cập nhật, build). Màn hình và luồng người dùng ở [31-giao-dien.md](31-giao-dien.md). Mọi thông tin nền tảng có nguồn ở mục 11; ngày tra cứu 18/11/2026.

Nguồn chuẩn khi lệch (QĐ-25): bảng và cột theo [11-co-so-du-lieu.md](../10-backend/11-co-so-du-lieu.md); đường dẫn API theo [12-api.md](../10-backend/12-api.md) (tiền tố `/api/v1`, danh từ số nhiều); kiểu hành động trả cho app theo [20-bo-nao-ai.md](../20-ai/20-bo-nao-ai.md); cổng, compose theo [50-ha-tang-trien-khai.md](../50-ha-tang/50-ha-tang-trien-khai.md); luật OTP và luật duyệt theo [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md) mục 3.8 và 3.12.

## 1. Mục tiêu

- Một APK cài ngoài cửa hàng, chạy ổn định nhiều tháng trên **Samsung Galaxy S25+, cài đặt mặc định** (QĐ-19) mà không cần mở Android Studio.
- Lớp gốc Kotlin **mỏng**: chỉ làm việc giao diện web không làm được (nghe thông báo, nhắc đúng giờ khi mất mạng, cài bản cập nhật, mở Google Maps, giữ mã trong kho khóa, vân tay, Health Connect ở V2).
- Không thông báo nào ngoài danh sách cho phép, không mã OTP nào rời điện thoại.
- Đổi giao diện không cần cài lại APK; đổi lớp gốc thì app tải bản mới và **hỏi người dùng trước khi cài** (QĐ-18).
- Build hoàn toàn trên GitHub Actions; máy cá nhân chạy mọi thứ trong Docker (QĐ-14).

## 2. Phạm vi

| Trong tài liệu này | Ở tài liệu khác |
|---|---|
| Phiên bản nền tảng, cấu trúc dự án `app/` | Màn hình, luồng, trạng thái: `31-giao-dien.md` |
| Plugin Kotlin và hợp đồng với giao diện | Bảng và API chi tiết: `11`, `12` |
| Quyền, luồng xin quyền, bước riêng của Samsung | Bóc tách thông báo ngân hàng, gộp cặp chuyển MoMo: backend |
| Bộ lọc trên máy (lớp 1 của luật OTP), hàng đợi gửi lên | Luật OTP gốc, lớp 2 trên máy chủ, giữ dữ liệu: `60` |
| Nhắc lịch trên máy | Đồng bộ Google Calendar, Tasks, nguồn nhắc: `40-tich-hop-google.md` |
| Cập nhật hai lớp, khóa ký, build APK | Workflow, R2, bí mật CI: `50` |
| Mở Google Maps từ app | Dựng link, chia đoạn, lịch trình: `41-ban-do-lich-trinh.md` |
| Health Connect (V2) phía máy | Module health phía máy chủ (V2) |

Ngoài phạm vi: iOS, Google Play, đẩy tin qua Firebase, trả lời tin qua thông báo (V2, tài liệu riêng khi tới lượt).

## 3. Thiết kế

### 3.1 Nền tảng và phiên bản

| Thành phần | Chọn | Ghi chú, nguồn |
|---|---|---|
| Capacitor | **8.x** (bản ổn định mới nhất trên npm 8.6.2, ngày 12/11/2026) | ĐX-30-01 đã duyệt (QĐ-25). Capacitor 9 đang ở 9.0.0-rc.0, chưa dùng [N1][N2] |
| Node | 24 (ảnh `node:24-alpine` của dịch vụ `web` theo `50`) | Capacitor 8 cần từ 22 [N3] |
| JDK | 21 | Mã nguồn Capacitor 8.6.2 build bằng Java 21 [N4] |
| `minSdk` | 26 (Android 8) | Khớp Capacitor 9 và Health Connect SDK [N4][N16] |
| `compileSdk`, `targetSdk` | 36 | Mặc định của Capacitor 8 [N3]. Ảnh `infra/android-build.Dockerfile` (`50` mục 3.14) cài nền tảng `android-36`; `build-tools` để theo mặc định của Android Gradle Plugin, không ghim riêng |
| Kotlin, Gradle | Kotlin 2.2.20, Android Gradle Plugin 8.13.0, Gradle 8.14.3 | Theo hướng dẫn nâng cấp Capacitor 8 [N3] |
| WorkManager | `androidx.work:work-runtime-ktx` 2.12.0 | [N9] |
| Vân tay | `androidx.biometric` | [N14] |
| Health Connect (V2) | `androidx.health.connect:connect-client` **1.1.0** (bản ổn định mới nhất trên kho Maven của Google; 1.2.0 còn alpha) | Khớp `40`. Bản 1.1.0 trở lên cần `compileSdk` 36 [N16][N27] |
| Android Studio (chỉ khi gỡ lỗi) | Otter 2025.2.1 trở lên | [N3] |

Máy đích: Galaxy S25+ chạy One UI 7 (Android 15) trở lên, nên mọi thay đổi của Android 13, 14, 15 trong tài liệu này đều áp dụng.

Lưu ý Capacitor 8: bỏ `adjustMarginsForEdgeToEdge`, giao diện tự xử lý vùng an toàn bằng `env(safe-area-inset-*)`; thêm `density` vào `android:configChanges` của activity để WebView không tải lại khi đổi cỡ [N3].

### 3.2 Định danh app

| Mục | Giá trị |
|---|---|
| `applicationId` | `vn.io.baohuynh.troly` |
| Tên hiển thị | **Trợ lý** |
| Bản gỡ lỗi | `applicationIdSuffix ".debug"`, tên **Trợ lý (thử)**, ký bằng khóa gỡ lỗi; cài song song với bản thật |
| `versionName` | Lấy từ thẻ git `vX.Y.Z` (thẻ `v1.2.0` thành `1.2.0`) |
| `versionCode` | `X*10000 + Y*100 + Z` (1.5.2 thành 10502) |
| Đường dẫn sâu | Lược đồ riêng `troly://` (thông báo nhắc, trang kết nối Google: `troly://cai-dat/google?ket-qua=...`, ĐX-31-06 đã duyệt) |
| Sao lưu | `android:allowBackup="false"` [`60` mục 3.14] |
| Mạng | `network_security_config.xml`: `cleartextTrafficPermitted="false"` cho mọi tên miền; không ghim chứng chỉ (Cloudflare tự xoay) [`60` mục 3.14] |
| WebView | Chỉ nạp nội dung của app (`https://localhost`) và gọi tên miền API, R2; mọi link khác mở bằng trình duyệt hệ thống, không mở trong khung app |
| Thành phần xuất ra ngoài | Chỉ activity chính và dịch vụ nghe thông báo (có quyền `BIND_NOTIFICATION_LISTENER_SERVICE`); bộ nhận báo thức, bộ nhận cài đặt `exported="false"` |

### 3.3 Cấu trúc dự án

```
app/
  package.json                  scripts: dev (Vite cổng 5190), build, bundle:web
  vite.config.ts                server.port 5190, server.watch.usePolling khi chạy trong container
  capacitor.config.ts           appId, appName, webDir=dist
  src/
    core/
      api/                      gọi API /api/v1, phong bì, JWT, làm mới mã
      native/                   lớp bọc plugin gốc, mỗi plugin một tệp + bản giả cho trình duyệt
        notify.ts  alarm.ts  update.ts  maps.ts  secure.ts  system.ts  voice.ts  health.ts
      offline/                  lưu đệm TanStack Query, trạng thái mạng
    app/  shared/  modules/     (xem 31-giao-dien.md)
  android/
    app/build.gradle            applicationId, versionCode/Name từ biến môi trường CI, signingConfigs
    app/src/main/AndroidManifest.xml
    app/src/main/res/xml/network_security_config.xml
    app/src/main/java/vn/io/baohuynh/troly/
      MainActivity.kt           registerPlugin(...) cho mọi plugin cục bộ
      notify/                   TrolyNotificationListener, NotificationFilter, OtpDetector, DedupeCache
      queue/                    EventQueue (Room), UploadWorker
      alarm/                    ReminderStore (Room), ReminderScheduler, ReminderReceiver, BootReceiver
      update/                   ApkUpdater, WebBundleUpdater, WebBundleVerifier
      maps/                     MapsLauncher
      secure/                   DeviceTokenStore, RefreshTokenStore, AppLock
      system/                   PermissionStatus, mở trang cài đặt hệ thống và trang Samsung
      voice/                    SpeechRecognizer của Android
      health/                   (V2) HealthReader, HealthWorker
      plugin/                   NotifyPlugin, AlarmPlugin, UpdatePlugin, MapsPlugin,
                                SecurePlugin, SystemPlugin, VoicePlugin, HealthPlugin
    app/src/test/               JUnit trên JVM; đọc testdata/otp-samples.yaml (Gradle chép vào tài nguyên kiểm thử)
    testhelper/                 app kiểm phụ cho máy ảo: đăng thông báo giả, chỉ build ở CI
```

Nguyên tắc:

- Plugin là lớp **cục bộ trong app**, không tách gói npm.
- Mọi luật kiểm được (lọc, OTP, trùng lặp, đóng gói sự kiện, tính giờ nhắc, kiểm chữ ký, so phiên bản) là **hàm Kotlin thuần**, kiểm bằng JUnit trên JVM. `plugin/` chỉ chuyển đổi dữ liệu.
- Mỗi tệp trong `src/core/native/` có **bản giả cho trình duyệt**, trả dữ liệu mẫu: làm giao diện bằng dịch vụ `web` (Vite cổng 5190, `50` mục 3.13) không cần điện thoại.
- Plugin Capacitor chính thức dùng thêm: `@capacitor/app`, `@capacitor/browser` (Custom Tabs), `@capacitor/network`, `@capacitor/preferences`.

### 3.4 Giao tiếp giữa giao diện và lớp gốc

Giao diện gọi plugin bằng `Promise`; lớp gốc báo sự kiện bằng `notifyListeners`. Lỗi trả `{code, message}`, `message` tiếng Việt.

| Plugin | Phương thức | Sự kiện |
|---|---|---|
| **Notify** | `getStatus()` trả `{listenerGranted, listenerConnected, lastEventAt, queueSize, droppedToday, otpBlockedToday}`; `getAllowedApps()`; `flushQueue()` | `listenerStateChanged`, `queueChanged` |
| **Alarm** | `syncReminders({revision, items})`; `getScheduled()`; `canScheduleExact()` | `reminderAction` |
| **Update** | `checkApk()`; `downloadApk()`; `installApk()` (chỉ gọi sau khi người dùng bấm *Cập nhật*); `getVersions()`; `checkWeb()`; `notifyWebReady()`; `rollbackWeb()` | `downloadProgress`, `apkInstallState` |
| **Maps** | `navigate({lat, lng, mode, avoid})`; `openUrl({url})`; `isMapsInstalled()` | không |
| **Secure** | `storeDeviceToken({token})`; `hasDeviceToken()`; `saveRefreshToken({token})`; `loadRefreshToken()` (hiện hộp vân tay nếu bật khóa); `clearAll()`; `isLockEnabled()`; `setLock({enabled, afterMinutes})`; `unlock()` | `lockRequired`, `deviceRevoked` |
| **System** | `getPermissions()` (mục 3.10); `openSettings({target})` với `target` là `notification_listener`, `app_details`, `battery`, `samsung_never_sleeping`, `exact_alarm`, `unknown_sources`, `notifications`; `getDeviceInfo()` trả `{manufacturer, model, androidSdk, defaultSmsPackage}` | `permissionsChanged` |
| **Voice** | `isAvailable()`; `start({lang: 'vi-VN'})`; `stop()` | `partial`, `final`, `error` |
| **Health** (V2) | `getStatus()`; `requestPermissions()`; `readDaily({from, to})` | không |

Hai danh tính tách riêng theo `10-kien-truc-backend.md` mục 3.7: giao diện gọi API bằng JWT người dùng (giữ trong bộ nhớ JavaScript, làm mới bằng mã làm mới cất qua `Secure`); lớp gốc gọi nhóm `/api/v1/device/*` bằng mã thiết bị (`Authorization: Device <mã>`). Mã thiết bị **không** đổi lấy mã truy cập và không trả ngược về JavaScript. Mọi yêu cầu gửi `X-App-Version` và `X-Web-Version`.

### 3.5 Dịch vụ nghe thông báo

**Khai báo.** `TrolyNotificationListener`, `permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"`, `intent-filter` `android.service.notification.NotificationListenerService` [N5]; `meta-data` `android.service.notification.disabled_filter_types` = `ongoing` [N5]. Không chặn loại `silent` (tin nhóm Zalo tắt tiếng vẫn cần).

**Vòng đời.**

1. `onListenerConnected`: ghi thời điểm, báo `listenerStateChanged` [N5].
2. `onNotificationPosted(sbn)`: chạy bộ lọc (mục 3.6) **trên luồng nền** (từ Android 7 hàm gọi lại chạy trên luồng chính [N5]), ghi hàng đợi, xếp việc gửi.
3. `onListenerDisconnected`: gọi `requestRebind(ComponentName)` [N5]; ghi sự kiện để màn *Kiểm tra máy* báo.
4. Không dùng dịch vụ tiền cảnh. Trên Samsung, việc giữ dịch vụ sống dựa vào bước *Ứng dụng không bao giờ ngủ* (mục 3.10).

**Dữ liệu đọc** (chỉ sau khi gói qua bước 1 của bộ lọc):

| Trường | Lấy từ |
|---|---|
| `app_package`, `posted_at` | `sbn.packageName`, `sbn.postTime` (cấp sự kiện) |
| `notification_key_hash` | SHA-256 của `sbn.key` |
| `title`, `text` | `EXTRA_TITLE`; `EXTRA_BIG_TEXT` nếu có, không thì `EXTRA_TEXT` |
| `conversation_title`, `messages[]` | `MessagingStyle`: `EXTRA_CONVERSATION_TITLE`, `EXTRA_MESSAGES` (người gửi, chữ, thời điểm) |
| `is_group_conversation` | `EXTRA_IS_GROUP_CONVERSATION` |
| `category` | `notification.category` |
| `hidden_content` | đúng khi chữ trống, bị hệ thống che, hoặc trùng câu ẩn nội dung của app |

`messages[]` giúp tách từng tin khi Zalo, Messenger cập nhật **cùng một thông báo** với tin chồng lên: chỉ lấy tin mới hơn tin cuối đã gửi của cuộc đó.

**Danh sách app được nghe** (bảng `tab_listened_app` của `11`, máy chủ là gốc):

| App | Tên gói | Mục đích | Bật mặc định |
|---|---|---|---|
| Vietcombank | `com.VCB` | Chi tiêu | Có |
| Techcombank | `vn.com.techcombank.bb.app` | Chi tiêu | Có |
| MoMo | `com.mservice.momotransfer` | Chi tiêu | Có |
| Zalo | `com.zing.zalo` | Hộp tin | Có |
| Telegram | `org.telegram.messenger` | Hộp tin | Có |
| Messenger | `com.facebook.orca` | Hộp tin | Có |
| Samsung Messages | `com.samsung.android.messaging` | Hộp tin | Theo app SMS mặc định |
| Google Messages | `com.google.android.apps.messaging` | Hộp tin | Theo app SMS mặc định |

- Hai app SMS đều có dòng (QĐ-19). Ở bước thiết lập máy, giao diện đọc `System.getDeviceInfo().defaultSmsPackage` (`Telephony.Sms.getDefaultSmsPackage()`) rồi bật đúng dòng của app mặc định, tắt dòng kia, bằng `PATCH /api/v1/devices/listened-apps/{id}`. Người dùng đổi tay được ở màn *App được nghe*.
- Tên gói **kiểm lại trên máy thật**; màn *App được nghe* hiện *Đã cài* hoặc *Không thấy trên máy*.
- Khi gói Gmail đã nối Google, máy chủ bỏ `com.google.android.gm` khỏi danh sách trả về `/device/config` (`40` mục Gmail), tránh một thư vào hộp tin hai lần.
- Từ Android 11, muốn biết app có cài không và lấy tên, biểu tượng thì khai gói trong `<queries>` [N13]; khai đúng 8 gói trên và `com.google.android.apps.maps`, không dùng `QUERY_ALL_PACKAGES`.
- Plugin lấy danh sách bằng `GET /api/v1/device/config` (`If-None-Match`, 304) khi mở app và khi `heartbeat` trả `config_revision` mới. Thêm, bớt app chỉ làm trên màn Cài đặt, không qua công cụ AI (`60` mục 3.12).

**Đồng ý của thành viên.** Tài khoản thành viên (không phải chủ) chỉ bật được nghe thông báo sau khi đồng ý bản thông báo xử lý dữ liệu (`tab_consent`, `kind = data_processing`, `60` mục 3.10). Plugin không bắt đầu gửi khi `/device/config` báo chưa có đồng ý. Hiện chỉ có một người dùng là chủ (QĐ-15), nên bước này chưa hiện; vẫn làm sẵn trong V1.2.

### 3.6 Bộ lọc trên máy (lớp 1)

Hàm thuần `filterNotification(input, rules, now): Decision` trả `Drop(reason)` hoặc `Keep(event)`. Chạy theo thứ tự, gặp điều kiện bỏ là dừng:

| Bước | Điều kiện bỏ | Ghi chú |
|---|---|---|
| 1 | Gói không có trong danh sách đang bật | Không đọc trường nào, không lưu, không ghi nhật ký tên gói. Tăng `droppedToday` |
| 2 | Thông báo của chính app Trợ lý | |
| 3 | Thông báo tiến trình: cờ `FLAG_ONGOING_EVENT`, `FLAG_FOREGROUND_SERVICE`; `category` là `progress`, `call`, `transport`, `service`, `navigation`; `EXTRA_PROGRESS_MAX > 0` | Lớp dự phòng cho `disabled_filter_types` |
| 4 | Tóm tắt nhóm (`FLAG_GROUP_SUMMARY`) | |
| 5 | **OTP** theo bảng dưới | Bỏ cả thông báo. Tăng `otpBlockedToday` (bộ đếm riêng, không lưu nội dung) |
| 6 | Trùng: cùng băm `(gói, tiêu đề, chữ)` trong 10 phút, hoặc tin trong `messages[]` đã gửi | Bộ đệm băm 24 giờ, tối đa 2.000 mục |
| 7 | Rỗng với app ngân hàng, ví | App tin nhắn rỗng thì **giữ** với `hidden_content = true` |

Sau bộ lọc: cắt `text` tối đa 2.000 ký tự, bỏ ký tự điều khiển, gắn `client_event_id` (UUID), ghi hàng đợi.

**Luật OTP** (`OtpDetector`), đúng bộ luật `60` mục 3.8; bộ luật có số phiên bản, máy chủ chạy cùng bộ luật ở lớp 2:

| Luật | Nội dung |
|---|---|
| Từ khóa (không phân biệt hoa thường, so cả bản bỏ dấu) | `OTP`, `mã xác thực`, `mã xác nhận`, `mã xác minh`, `mã kích hoạt`, `mật khẩu một lần`, `Smart OTP`, `không cung cấp mã`, `không chia sẻ mã`, `verification code`, `passcode`, `one-time`, `security code`, `login code`, `2FA` |
| Mẫu số đi kèm | Chuỗi 4 tới 8 chữ số đứng riêng **trong cùng câu** với một từ khóa trên; hoặc dạng `G-123456`, `123-456` ở bất cứ đâu |
| Theo nguồn | Thông báo của app ngân hàng, ví (mục đích *Chi tiêu*) mà **không khớp mẫu giao dịch** thì bỏ hết (thông báo đăng nhập, mã xác nhận chuyển tiền...). Mẫu giao dịch: có số tiền dạng `[+-]?[0-9.,]+ ?(VND|đ|d)` và một trong các dấu hiệu biến động (`+`/`-` trước số tiền, *GD*, *giao dịch*, *số dư*, *nhận*, *chuyển*) |
| Theo người gửi SMS | Với app SMS: tiêu đề (người gửi) là tên thương hiệu ngân hàng, ví, sàn thương mại điện tử, dịch vụ đăng nhập (Google, Zalo, Facebook...) **và** nội dung có chuỗi 4 tới 8 chữ số thì bỏ. Danh sách tên thương hiệu nằm trong bộ luật, sửa được qua bản giao diện mới không cần APK (gửi xuống qua `/device/config` khi `12` thêm trường) |

- Từ Android 15, hệ thống tự **che nội dung** thông báo mà nó đoán có OTP với app nghe thông báo không được tin cậy [N12]. Máy đích chạy Android 15 trở lên nên lớp này luôn có; thông báo bị che coi như rỗng (bước 7). Đây là lớp thêm, không thay bộ lọc của app.
- Bộ mẫu dùng chung `testdata/otp-samples.yaml` (`70` mục 3.5): JUnit Kotlin và bài kiểm Python đọc cùng tệp, phải cho cùng kết quả.

### 3.7 Hàng đợi gửi lên

- **Lưu trên máy:** bảng Room `device_event_queue` (mục 4.2), bộ nhớ riêng của app, tối đa 7 ngày hoặc 5.000 dòng.
- **Gửi:** WorkManager, việc duy nhất `upload-events`, `ExistingWorkPolicy.KEEP`, `NetworkType.CONNECTED`, lùi kiểu lũy thừa từ 30 giây [N9]. Mỗi lô tối đa 50 sự kiện và 256 KB (giới hạn chung ở `12` mục 3.7), tới `POST /api/v1/device/events` bằng mã thiết bị.
- **Không trùng:** máy chủ trả `accepted`, `duplicates`, `rejected[]`, cộng lại bằng số đã gửi; máy xóa cả lô (`12` mục 5.15). `rejected` mã `OTP_DETECTED` nghĩa là lớp 1 để lọt: ghi nhật ký mã sự kiện (không ghi nội dung), tăng bộ đếm ở *Kiểm tra máy* để sửa luật.
- **Lỗi:** mạng lỗi, 5xx: `Result.retry()`; 429: chờ theo `Retry-After`; 401 `DEVICE_REVOKED`: dừng việc nền, `Secure.clearAll()`, báo `deviceRevoked`; 426: dừng gửi, giữ hàng đợi, chờ cập nhật.
- **Khi máy ngủ (Doze):** WorkManager và mạng bị hoãn tới cửa sổ bảo trì [N8]; khi người dùng mở app thì `Notify.flushQueue()` gửi ngay.
- Từ Android 15, gọi mạng ngoài vòng đời tiến trình sẽ lỗi [N12]; dịch vụ nghe chỉ ghi hàng đợi và xếp WorkManager, không gọi mạng trực tiếp.

### 3.8 Nhắc lịch trên máy

**Nguồn nhắc.** Mỗi sự kiện có một nguồn nhắc `tab_event.remind_source` (`40` mục 4.6, ĐX-G6):

| Sự kiện tạo ở | `remind_source` mặc định | App |
|---|---|---|
| App (chat, chạm) | `app` | Đặt báo thức trên máy; Google không nhắc |
| Google Calendar | `google` | Không đặt báo thức; app Google Calendar trên máy tự nhắc |

Người dùng đổi được từng sự kiện ở màn sửa sự kiện (`31`). Việc có hạn luôn do app nhắc.

**Đồng bộ xuống.** `GET /api/v1/calendar/reminders?days=14` với `If-None-Match: <revision>` (304 khi không đổi), chỉ trả nhắc có `remind_source = app` và việc có hạn; mỗi nhắc có `key` ổn định. Giao diện gọi bằng JWT rồi chuyển cho `Alarm.syncReminders`; worker nền gọi bằng mã thiết bị, nên API này phải cho **U/D** (A2 dòng 28, đã duyệt). Gọi khi:

- mở app và khi quay lại tiền cảnh;
- ngay sau khi người dùng thêm, sửa, xóa lịch hoặc việc trong app;
- việc định kỳ WorkManager mỗi 1 giờ, cần mạng.

**Đặt báo thức.**

- Quyền: `USE_EXACT_ALARM` (cấp khi cài, không thu hồi được, dành cho app lịch và báo thức) và `SCHEDULE_EXACT_ALARM` với `maxSdkVersion="32"` [N6][N7].
- Luôn kiểm `canScheduleExactAlarms()` trước khi đặt [N6].
- Nhắc thường: `setExactAndAllowWhileIdle(RTC_WAKEUP, ...)` (trong Doze tối đa một lần mỗi 9 phút mỗi app [N8]). Nhắc loại **báo thức** (giờ phà, giờ trả phòng): `setAlarmClock()`, hệ thống không dời giờ và thoát Doze để kêu [N7][N8].
- Thiếu quyền báo thức chính xác (hiếm): `setWindow()` 10 phút, cảnh báo ở *Kiểm tra máy* [N6].
- Samsung: app trong danh sách *Ứng dụng đang ngủ* bị hạn chế báo thức [N28]; vì vậy bước *Ứng dụng không bao giờ ngủ* (mục 3.10) là bắt buộc để nhắc chắc chắn kêu.

**Đặt lại báo thức** (mọi báo thức mất khi tắt máy [N7]):

| Tình huống | Bắt bằng |
|---|---|
| Khởi động lại máy | `BOOT_COMPLETED` (quyền `RECEIVE_BOOT_COMPLETED`) [N7] |
| Cập nhật app | `MY_PACKAGE_REPLACED` |
| Đổi giờ, múi giờ | `TIME_SET`, `TIMEZONE_CHANGED` |
| Cấp lại quyền báo thức | `ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED` [N6] |
| Buộc dừng app (Android 15 hủy mọi `PendingIntent`) | Hệ thống gửi `BOOT_COMPLETED` khi app được mở lại [N12]; mở app cũng tự đặt lại |

**Thông báo nhắc.** Kênh `nhac-lich` (quan trọng cao), `bao-thuc`, `cap-nhat`, `he-thong`. Cần `POST_NOTIFICATIONS` (Android 13 trở lên, mặc định tắt) [N15]. Nút **Xong** (việc) hoặc **Đã biết** (lịch), **Hoãn 10 phút** (đặt lại cục bộ). Bấm nút ghi sự kiện `reminder_action` vào hàng đợi. Chạm mở `troly://lich/su-kien/<id>` hoặc `troly://lich/viec/<id>`.

### 3.9 Đăng nhập, mã thiết bị, khóa vân tay

Theo `10-kien-truc-backend.md` mục 3.7 (hai danh tính, không lẫn nhau).

**Đăng nhập.** `POST /api/v1/auth/login` trả **mã truy cập** (JWT, hạn theo `10`) và **mã làm mới** (xoay vòng mỗi lần làm mới). JWT chỉ nằm trong bộ nhớ JavaScript. Mật khẩu không lưu trên máy.

**Đăng ký thiết bị.** Sau lần đăng nhập đầu, giao diện gọi `POST /api/v1/devices`; máy chủ trả **mã thiết bị** một lần. Giao diện chuyển ngay cho `Secure.storeDeviceToken` rồi bỏ khỏi bộ nhớ JavaScript. Mã thiết bị chỉ gọi được nhóm `/device/*` và `/calendar/reminders`.

**Cất mã thiết bị.** Khóa AES-256-GCM sinh trong `AndroidKeyStore`, vật liệu khóa không ra khỏi kho [N17]; bản mã trong bộ nhớ riêng của app. Khóa **không** gắn xác thực người dùng, vì worker nền chạy cả khi màn hình khóa.

**Cất mã làm mới.** Cặp khóa RSA 2048 trong kho khóa, mã hóa RSA-OAEP. Khi bật khóa vân tay, khóa riêng gắn `setUserAuthenticationParameters(0, AUTH_BIOMETRIC_STRONG or AUTH_DEVICE_CREDENTIAL)`: **giải mã** phải qua vân tay hoặc mã màn khóa, còn **mã hóa** bằng khóa công khai thì không [N14][N17]. Mã làm mới mới sau mỗi lần xoay vòng cất lại ngay không hỏi vân tay; mở app sau khi khóa thì phải qua vân tay. Tắt khóa vân tay thì sinh lại cặp khóa không gắn xác thực. (`setUserAuthenticationParameters` có từ Android 11; máy đích đủ bản.)

**Thu hồi.** 401 `DEVICE_REVOKED`, hoặc mã làm mới hết hạn, bị thu hồi: `Secure.clearAll()`, về màn đăng nhập.

**Khóa vân tay.** `BiometricPrompt` với `BIOMETRIC_STRONG or DEVICE_CREDENTIAL` [N14], hiện khi mở app và khi app ở nền quá số phút cài đặt (đề xuất 5, Câu hỏi mở 1). Vượt qua thì giải mã mã làm mới, lấy JWT mới. Chặn người cầm máy đang mở khóa; không chống được máy đã root.

**Duyệt hành động.** Thẻ xác nhận có `require_unlock` gọi `Secure.unlock()` trước khi gửi lệnh duyệt (luật duyệt theo `60` mục 3.12; cách hiện ở `31` mục 3.3).

### 3.10 Quyền và bước riêng của Samsung

| Quyền | Loại | Dùng cho | Xin lúc | Nếu không có |
|---|---|---|---|---|
| `INTERNET` | thường | gọi API | tự có | |
| `POST_NOTIFICATIONS` | lúc chạy, Android 13+ [N15] | nhắc lịch, báo bản mới | bước 1 thiết lập | không nhắc được |
| Truy cập thông báo | truy cập đặc biệt | hộp tin, chi tiêu tự động | bước 2 | hộp tin, chi tiêu tự động ngừng |
| Cho phép cài đặt bị hạn chế | thao tác của người dùng, Android 13+ | mở khóa quyền truy cập thông báo cho app cài ngoài [N10][N11] | trong bước 2 nếu bị chặn | không cấp được bước 2 |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | thường, mở hộp hỏi của hệ thống | pin *Không hạn chế* | bước 3 | dịch vụ có thể bị tắt |
| *Ứng dụng không bao giờ ngủ* (Samsung) | cài đặt One UI | One UI không đưa app vào ngủ, ngủ sâu | bước 4 | sau vài ngày không mở app, One UI hạn chế báo thức, việc nền; ngủ sâu thì app không chạy nền, không gửi thông báo [N28] |
| `USE_EXACT_ALARM` (API 33+), `SCHEDULE_EXACT_ALARM` (API 31-32) | thường / truy cập đặc biệt [N6][N7] | nhắc đúng giờ | tự có | nhắc lệch tối đa 10 phút |
| `RECEIVE_BOOT_COMPLETED` | thường | đặt lại nhắc | tự có | |
| `REQUEST_INSTALL_PACKAGES` | truy cập đặc biệt *Cài ứng dụng không rõ nguồn gốc* | cài APK mới | lần đầu có bản mới | tải APK và cài tay |
| `UPDATE_PACKAGES_WITHOUT_USER_ACTION` | thường | sau khi người dùng đã bấm *Cập nhật* trong app, không phải bấm lần hai ở hộp hệ thống (mục 3.11) | tự có | hệ thống hiện thêm hộp xác nhận |
| `USE_BIOMETRIC` | thường | khóa vân tay | tự có | |
| `RECORD_AUDIO` | lúc chạy | nói với trợ lý | lần đầu bấm micro | chỉ gõ chữ |
| `health.READ_STEPS`, `READ_SLEEP`, `READ_HEART_RATE` (V2) | quyền Health Connect | thông số sức khỏe | khi bật mục Sức khỏe | ẩn thẻ |

Không xin: vị trí, danh bạ trên máy, SMS, `QUERY_ALL_PACKAGES`, dịch vụ tiền cảnh, trợ năng.

**Kiểm tra quyền** (`System.getPermissions()`, gọi lại mỗi khi app quay lại tiền cảnh): truy cập thông báo bằng `isNotificationListenerAccessGranted(ComponentName)`; báo thức `canScheduleExactAlarms()` [N6]; pin `isIgnoringBatteryOptimizations()` [N8]; cài gói `canRequestPackageInstalls()`; thông báo `areNotificationsEnabled()` [N15]; vân tay `BiometricManager.canAuthenticate()` [N14]. Danh sách *Không bao giờ ngủ* của Samsung **không đọc được** từ app: dựa vào người dùng tự tích *Đã làm*, cộng tín hiệu gián tiếp (lâu không có sự kiện, `listener_connected` sai).

**Luồng xin quyền** (màn *Thiết lập máy*, `31` luồng 2), mỗi bước một nút mở đúng trang:

1. **Thông báo:** hộp hỏi `POST_NOTIFICATIONS`.
2. **Đọc thông báo:** mở `Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS`. App cài từ trình duyệt hoặc trình quản lý tệp trên Android 13 trở lên bị **cài đặt bị hạn chế**: công tắc khóa xám [N10][N11]. Hướng dẫn trong app: thử bật một lần, bị chặn thì vào *Cài đặt > Ứng dụng > Trợ lý > menu ba chấm > Cho phép cài đặt bị hạn chế*, xác nhận, quay lại bật [N10]. Nút *Mở thông tin ứng dụng* gọi `ACTION_APPLICATION_DETAILS_SETTINGS`.
3. **Pin không hạn chế:** `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` hiện hộp hỏi của hệ thống [N8]. Google Play cấm cách này trừ khi chức năng cốt lõi bị ảnh hưởng [N8]; app cài ngoài và nghe thông báo là cốt lõi.
4. **Không bao giờ ngủ (Samsung, chỉ hiện khi `manufacturer` là Samsung):** nút mở thẳng danh sách bằng intent mà Samsung công bố: action `com.samsung.android.sm.ACTION_OPEN_CHECKABLE_LISTACTIVITY`, package `com.samsung.android.lool`, extra `activity_type = 2` [N28]. Mở không được thì hướng dẫn tay: *Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > chọn Trợ lý > Thêm* [N29]. Samsung ghi app trong danh sách này có thể tốn pin hơn khi chạy nền [N29]. Người dùng bấm *Đã làm* để tích bước này.
5. **Báo thức chính xác:** chỉ hiện khi `canScheduleExactAlarms()` sai, mở `ACTION_REQUEST_SCHEDULE_EXACT_ALARM` [N6].
6. **Cài app không rõ nguồn gốc:** không hỏi lúc thiết lập; hỏi lần đầu có bản APK mới, mở `ACTION_MANAGE_UNKNOWN_APP_SOURCES`.

Thiết lập máy cũng chọn app SMS mặc định (mục 3.5). Không bước nào bắt buộc để dùng Chat; thiếu bước nào thì banner ở màn liên quan.

### 3.11 Cập nhật hai lớp

#### Lớp giao diện

**Gói giao diện** là zip của `dist/`, kèm thông tin (khớp `WebBundleInfo` ở `12` mục 5.15):

| Trường | Ý nghĩa |
|---|---|
| `version` | chuỗi phiên bản giao diện, ví dụ `1.5.2+20261118.1` |
| `min_app_version_code` | `versionCode` APK thấp nhất chạy được gói này |
| `sha256` | băm tệp zip |
| `signature` | ECDSA P-256 (SHA256withECDSA), base64, trên chuỗi `version|min_app_version_code|sha256` |

Khóa riêng là secret `WEB_BUNDLE_SIGNING_KEY`; khóa công khai là hằng số trong `build.gradle`, nhúng vào APK. ECDSA P-256 có sẵn trong `java.security.Signature` trên mọi bản từ `minSdk` 26.

**Luồng:**

1. Khi mở app và mỗi 6 giờ ở tiền cảnh: `GET /api/v1/device/web-bundle?current_version=&app_version_code=`.
2. Có bản mới: tải zip, kiểm `sha256`, kiểm chữ ký bằng khóa công khai nhúng sẵn; sai thì xóa, báo lỗi, không áp dụng.
3. Giải nén vào `files/web/<version>/`, kiểm có `index.html`, chặn đường dẫn thoát thư mục.
4. **Áp dụng ở lần mở app kế tiếp**: lưu đường dẫn bằng cơ chế sẵn có của Capacitor (`bridge.setServerBasePath`, lưu bền vào `CapWebViewSettings`, cùng cơ chế plugin `WebView` lõi của Capacitor 8.6.2 [N4]). Giao diện hiện dòng *Có giao diện mới* kèm nút *Mở lại ngay*.
5. **Tự quay lui:** giao diện mới phải gọi `Update.notifyWebReady()` trong 10 giây; không thì lần mở sau về gói trước. Giữ tối đa 2 gói tải về cộng gói gốc trong APK.
6. Nguồn gốc WebView không đổi (`https://localhost`) nên lưu đệm của giao diện còn nguyên.

Không dùng dịch vụ bên thứ ba (Capgo, Appflow) [N22]; ĐX-30-05 đã duyệt.

#### Lớp gốc (APK)

**App luôn hỏi trước khi cài (QĐ-18).** Không có cài đặt tự cài.

1. Khi mở app và mỗi ngày một lần: `GET /api/v1/device/release?current_version_code=` trả `{update_available, required, latest: {version_code, version_name, download_url, sha256, size_bytes, notes, min_supported_version_code}}`. `download_url` là URL ký sẵn ngắn hạn trỏ bucket `troly-release`.
2. Có bản mới: thẻ *Có bản x.y.z* trong app (và thông báo kênh `cap-nhat` nếu app đang ở nền). Không tải, không cài gì cho tới khi người dùng bấm **Cập nhật**.
3. Người dùng bấm: tải bằng WorkManager, kiểm `sha256`; đọc chứng chỉ ký của APK tải về (`getPackageArchiveInfo` với `GET_SIGNING_CERTIFICATES`), khác chứng chỉ app đang chạy thì không cài.
4. `canRequestPackageInstalls()` sai thì đưa tới `ACTION_MANAGE_UNKNOWN_APP_SOURCES`.
5. Cài bằng `PackageInstaller` session, `commit` với `IntentSender` [N18]. Vì người dùng đã đồng ý ở bước 3, session đặt `setRequireUserAction(USER_ACTION_NOT_REQUIRED)` và app khai `UPDATE_PACKAGES_WITHOUT_USER_ACTION` để không phải bấm thêm lần nữa ở hộp hệ thống; hệ thống chỉ bỏ hộp này khi app tự cập nhật chính nó và `targetSdk` đủ cao (Android 16 cần từ 34, Android 17 từ 35) [N19]. Vẫn luôn xử lý `STATUS_PENDING_USER_ACTION`: mở `Intent` trong `EXTRA_INTENT` [N18][N19].
6. `required = true`: chặn dùng app, chỉ còn nút *Cập nhật* (vẫn là người dùng bấm).
7. Cài xong, hệ thống tắt app; `MY_PACKAGE_REPLACED` đặt lại báo thức, thông báo *Đã cập nhật lên x.y.z*.

#### Xác minh nhà phát triển Android (mốc 2027)

Từ 30/09/2026 Android chặn cài app chưa đăng ký ở Brazil, Indonesia, Singapore, Thái Lan; **năm 2027 mở rộng toàn cầu**, áp cho mọi app trên máy Android được chứng nhận từ Android 8, kể cả APK cài từ trình duyệt [N20][N21]. App chưa đăng ký chỉ cài và **cập nhật** được qua `adb` hoặc *luồng nâng cao* (bật chế độ nhà phát triển, khởi động lại, chờ 24 giờ một lần) [N21].

Hướng xử lý (ĐX-30-04 đã duyệt): mở **tài khoản phân phối giới hạn** trên Android Developer Console (miễn phí, không cần giấy tờ; cần tài khoản Google bật xác minh hai bước và hồ sơ thanh toán Google), đăng ký tên gói `vn.io.baohuynh.troly` và chứng chỉ khóa ký trong V1.5 [N23]. Giới hạn số máy: trang hướng dẫn ghi 50, trang hỏi đáp ghi 20 [N21][N23]; đủ cho một người dùng. Mất khóa ký thì không đăng ký được tên gói [N21].

### 3.12 Mở Google Maps

| Hành động (`20` mục 3.8) | Cách mở |
|---|---|
| `open_map_navigation` | `Intent(ACTION_VIEW, "google.navigation:q=<lat>,<lng>&mode=<mode>&avoid=<avoid>")`, `setPackage("com.google.android.apps.maps")`. Mặc định `mode=l` (xe hai bánh), `avoid=h` (tránh cao tốc) [N24] |
| `open_map_directions` | Mỗi URL trong `urls[]` một nút; `Intent(ACTION_VIEW, url)`. URL do máy chủ dựng (`/trips/{id}/map-links`, `41`) dạng `https://www.google.com/maps/dir/?api=1&...&travelmode=two-wheeler` [N25] |
| `open_map_place` | URL `https://www.google.com/maps/search/?api=1&query=...&query_place_id=...` [N25] |

- Khai `<queries>` gói Maps [N13]; luôn `resolveActivity` trước `startActivity`. Không có Maps thì mở `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>&travelmode=two-wheeler&dir_action=navigate` bằng trình duyệt [N24][N25].
- Khi xin link cả ngày, app gửi `max_waypoints = 9` nếu `Maps.isMapsInstalled()`, không thì `3`, vì URL chỉ đường cho tối đa 3 điểm dừng trên trình duyệt di động và 9 ở nơi khác, URL tối đa 2.048 ký tự [N25].
- Google khuyên dùng URL Maps đa nền tảng, chỉ dùng lệnh Android riêng cho tính năng chỉ có trên điện thoại như dẫn đường từng chặng [N24]: đúng hướng trên.
- Chế độ `two-wheeler` chỉ có ở quốc gia được hỗ trợ [N25]; thử trên máy thật (mục 6.3). Thời gian xe máy do Routes API ước tính đang ở bản thử nghiệm; giao diện ghi dòng cảnh báo (`41`, `31`).

### 3.13 Nói với trợ lý

Nhận dạng giọng nói của Web Speech API trong WebView chưa được xác nhận; dùng plugin `Voice` với `SpeechRecognizer` của Android, `vi-VN`, trả `partial` và `final`. Quyền `RECORD_AUDIO`. Không gửi âm thanh lên máy chủ trong V1.

### 3.14 Health Connect (V2)

- Android 14 trở lên có sẵn trong hệ thống [N16]; máy đích đủ bản.
- Thư viện `connect-client` 1.1.0 (mục 3.1). Khai quyền `android.permission.health.READ_STEPS`, `READ_SLEEP`, `READ_HEART_RATE`; `<queries>` gói `com.google.android.apps.healthdata`; kiểm `getSdkStatus()` [N16].
- **Bắt buộc** activity chính sách riêng tư nhận `androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE`, và `activity-alias` cho `VIEW_PERMISSION_USAGE`, danh mục `HEALTH_PERMISSIONS` trên Android 14 trở lên [N16]. Dùng trang tĩnh trong gói giao diện.
- Chỉ đọc được 30 ngày trước thời điểm cấp quyền nếu không xin quyền đọc lịch sử; bước chân đọc bằng `aggregate()` [N16].
- Worker hằng ngày gửi tổng ngày hôm trước tới `POST /api/v1/device/health`.

### 3.15 Khóa ký APK

- Sinh **một lần** bằng `keytool` trong container JDK trên máy cá nhân (không sinh trên GitHub Actions): RSA 4096 bit, `-validity 10950` (**30 năm**, khớp `60` mục 3.6; Android khuyên tối thiểu 25 năm [N26]).
- Mất khóa thì không phát hành được bản cập nhật [N26] và không đăng ký được tên gói với chương trình xác minh [N21]. Số bản cất và cách xử lý khi lộ theo `60` mục 3.6 (GitHub Secrets và bản cất ngoại tuyến).
- `keystore.properties`, `*.jks`, `*.keystore` trong `.gitignore`.
- Dấu vân tay SHA-256 của chứng chỉ (không bí mật) ghi theo `60` mục 3.6 và đặt thành biến không bí mật của workflow để job `apk` so sau khi ký.
- Bản gỡ lỗi ký bằng khóa gỡ lỗi, tên gói `.debug`.

### 3.16 Build bằng GitHub Actions

Workflow `app-build.yml` do agent hạ tầng giữ (`50`: job `ui`, `android-unit`, `android-emulator`, `apk`). Phần app cần:

| Thẻ hoặc sự kiện | Job, kết quả |
|---|---|
| Thẻ `vX.Y.Z` | `apk`: build APK release đã ký + gói giao diện đi kèm; `android-emulator` chạy trước khi đăng |
| Đẩy `main` có đổi `app/src/` | `ui`: build gói giao diện, đặt `min_app_version_code` = `versionCode` thấp nhất có đủ plugin gói cần (khai trong `app/package.json`) |
| Đổi `app/android/**`, `testdata/**` | `android-unit`: JUnit JVM, đối chiếu kết quả OTP với Python |
| Đổi `notify/`, `alarm/`, `update/` | `android-emulator`: máy ảo, app kiểm phụ `testhelper` đăng thông báo giả, danh sách cho phép trỏ vào gói của nó (`70` mục 3.9) |

**Các bước job `apk`:** checkout; Node 24, `npm ci`, `npm run build` (kiểm `tsc -b`, `oxlint`, `vitest`); `npx cap sync android`; JDK 21; giải mã kho khóa ra tệp tạm; `./gradlew testReleaseUnitTest assembleRelease` với version và mật khẩu qua biến môi trường; `apksigner verify --print-certs`, so dấu vân tay; tính `sha256`, đẩy `releases/troly-<versionName>.apk` lên bucket `troly-release`, gọi `POST /api/v1/admin/releases` (`kind = apk`); đóng gói và ký gói giao diện, đăng `kind = web`; xóa kho khóa tạm kể cả khi lỗi.

**Bí mật** (tên theo `50`): `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `WEB_BUNDLE_SIGNING_KEY`, `R2_RELEASE_ACCESS_KEY_ID`, `R2_RELEASE_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `RELEASE_PUBLISH_TOKEN`.

**Cài lần đầu:** tải APK từ trang tải do máy chủ cấp (`50`), mở bằng trình duyệt Samsung hoặc Chrome, cho phép trình duyệt cài app không rõ nguồn gốc, cài, rồi làm luồng thiết lập máy.

### 3.17 Phát triển và gỡ lỗi

**Thường ngày (không cần Android Studio):** `docker compose` với tệp dev của `50` chạy dịch vụ `web` (Vite cổng 5190, `server.watch.usePolling = true` vì thư mục gắn từ Windows), proxy `/api` sang api cổng 8200; plugin dùng bản giả. JUnit Kotlin chạy trong dịch vụ `android-test` hoặc để CI.

**Khi cần Android Studio** (plugin chạy sai trên máy thật, dịch vụ nghe bị ngắt, báo thức không kêu, cài cập nhật lỗi):

1. Cài Android Studio Otter 2025.2.1 trở lên [N3].
2. Trên Galaxy S25+: *Cài đặt > Thông tin điện thoại > Thông tin phần mềm*, chạm *Số hiệu bản tạo* 7 lần để bật *Tùy chọn nhà phát triển*; bật *Gỡ lỗi USB*; cắm cáp.
3. `npx cap sync android`, `npx cap open android`, chạy biến thể `debug` (app `.debug` riêng).
4. Nhật ký lớp gốc: `adb logcat -s Troly` (không bao giờ ghi nội dung thông báo, chỉ lý do bỏ và mã sự kiện).
5. Nhật ký giao diện: `chrome://inspect` (chỉ bản gỡ lỗi bật gỡ lỗi WebView).
6. Tải lại nóng trên máy: `npx cap run android --live-reload --host <ip-máy-tính> --port 5190`.
7. Thử Doze: `adb shell dumpsys deviceidle force-idle`, thoát bằng `adb shell dumpsys deviceidle unforce` [N8].
8. Giả thông báo: `adb shell cmd notification post -t "<tiêu đề>" <tag> "<nội dung>"` (gói `com.android.shell`; bản gỡ lỗi có công tắc thêm gói này vào danh sách nghe), hoặc cài app `testhelper`.
9. Thử mất quyền báo thức: *Cài đặt > Ứng dụng > Quyền truy cập đặc biệt > Báo thức và lời nhắc* [N6].

Từ 2027, `adb install` vẫn cài được app chưa đăng ký [N21].

## 4. Dữ liệu cần

### 4.1 Trên máy chủ (agent kiến trúc gom vào `11`)

| Bảng | Thêm hoặc chốt | Lý do |
|---|---|---|
| `tab_device` | Thêm `listener_connected`, `notifications_enabled`, `exact_alarm_allowed` (bool), `queue_size` (int), `manufacturer` (text), `default_sms_package` (text), `otp_blocked_today` (int) | Màn *Kiểm tra máy*; máy chủ biết máy nào mất quyền, dịch vụ nghe chết, bộ lọc chạy |
| `tab_device_event` | `kind` thêm `reminder_action` (V1.4); V2 thêm `health_daily`. `payload` theo mục 5.1. Giữ 180 ngày (QĐ-17) | |
| `tab_app_release` | Với `kind = web`: `version_name` là `version`; `signature` như mục 3.11; `min_supported_version_code` đóng vai `min_app_version_code` | |
| `tab_listened_app` | Dòng mặc định theo bảng mục 3.5 (8 dòng, hai app SMS bật theo máy) | QĐ-19 |
| `tab_setting` | Khóa `app.lock_enabled` (bool, true), `app.lock_after_minutes` (int, 5). Bỏ `app.auto_install_update` (QĐ-18) | |
| `tab_consent` | Theo `60`; plugin cần biết đã có `data_processing` chưa (qua `/device/config`) | Thành viên |

### 4.2 Trên máy (Room, bộ nhớ riêng của app)

| Bảng | Cột | Giữ |
|---|---|---|
| `device_event_queue` | `client_event_id`, `kind`, `app_package`, `posted_at`, `payload` (JSON), `created_at`, `attempts` | 7 ngày hoặc 5.000 dòng |
| `reminder` | `reminder_key`, `source` (`event`, `task`), `source_id`, `fire_at_utc`, `title`, `body`, `kind` (`normal`, `alarm`), `deep_link`, `snoozed_until` | Cửa sổ 14 ngày |
| `seen_hash` | `hash`, `seen_at` | 24 giờ, tối đa 2.000 dòng |
| `conversation_cursor` | `notification_key_hash`, `last_message_at` | 7 ngày |

Cài đặt nhỏ (danh sách app, phiên bản bộ luật OTP, bộ đếm theo ngày, bước Samsung đã làm) lưu bằng DataStore.

## 5. API hoặc giao tiếp

### 5.1 API app dùng

Theo `12` (mọi đường dẫn dưới `/api/v1`). Bảng chỉ ghi phần lớp gốc liên quan.

| Ai gọi | Đường dẫn | Ghi chú |
|---|---|---|
| Giao diện, JWT | `POST /auth/login`, `POST /auth/refresh` | Mã làm mới cất qua `Secure` |
| Giao diện, JWT | `POST`, `GET /devices`; `PATCH`, `DELETE /devices/{id}` | Mã thiết bị trả một lần |
| Giao diện, JWT | `GET`, `POST /devices/listened-apps`; `PATCH`, `DELETE /devices/listened-apps/{id}` | Màn *App được nghe*, chọn app SMS |
| Plugin, mã thiết bị | `GET /device/config` (304) | Danh sách app, phiên bản bộ luật OTP, cờ đồng ý |
| Plugin, mã thiết bị | `POST /device/heartbeat` | Khi mở app, khi quyền đổi, 6 giờ một lần; thêm các trường mục 4.1 |
| Plugin, mã thiết bị | `POST /device/events` | Mục 3.7 |
| Giao diện hoặc plugin | `GET /device/release`, `GET /device/web-bundle` | Mục 3.11 |
| Giao diện hoặc plugin | `GET /calendar/reminders` (304) | U/D, chỉ `remind_source = app` |
| Plugin (V2) | `POST /device/health` | `days[]`: ngày, bước, phút ngủ, nhịp tim nghỉ |

**`payload` của sự kiện `notification`** (A1 dòng 7 đã duyệt theo tệp này): `title`, `text`, `conversation_title`, `messages[]` (`sender`, `text`, `at`), `is_group_conversation`, `category`, `notification_key_hash`, `hidden_content`. `app_package`, `posted_at` ở cấp sự kiện. Không gửi `notification_key` gốc, `sub_text`, `is_group_summary`. Không trường nào khác rời máy.

**`payload` của sự kiện `reminder_action`:** `reminder_key`, `source`, `source_id`, `action` (`done`, `ack`, `snooze`), `at`.

### 5.2 Hợp đồng plugin với giao diện

Như mục 3.4. Kiểu TypeScript ở `app/src/core/native/*.ts`, kèm bản giả. Mã lỗi cố định: `PERMISSION_MISSING`, `NOT_AVAILABLE`, `VERIFY_FAILED`, `NETWORK`, `CANCELLED`.

### 5.3 Hành động trợ lý trả cho app

Kiểu theo `20` mục 3.8, cách hiện theo `31` mục 3.3. Lớp gốc chỉ phục vụ `open_map_navigation` (`Maps.navigate`), `open_map_directions`, `open_map_place`, `open_link` (`Maps.openUrl` hoặc trình duyệt), và `Secure.unlock` cho thẻ `confirm` có `require_unlock`. Không còn kiểu `open_map` chung.

## 6. Kiểm thử

### 6.1 JUnit trên JVM (dịch vụ `android-test`, job `android-unit`)

| Hàm | Ca chính |
|---|---|
| `filterNotification` | gói ngoài danh sách bị bỏ và không đọc trường nào; tiến trình, cuộc gọi, tải tệp bị bỏ; tóm tắt nhóm bị bỏ; app tin nhắn ẩn nội dung được giữ với `hidden_content`; app ngân hàng rỗng bị bỏ |
| `OtpDetector` | toàn bộ `testdata/otp-samples.yaml` cho cùng kết quả với bài kiểm Python; đủ 15 từ khóa, có dấu và không dấu; `G-123456`, `123-456`; thông báo ngân hàng không khớp mẫu giao dịch bị bỏ; SMS từ tên thương hiệu có 4 tới 8 chữ số bị bỏ; biến động số dư được giữ; tin chat có số điện thoại, số tiền không bị bỏ nhầm |
| `DedupeCache` | trong 10 phút bị bỏ, sau 10 phút được giữ; `messages[]` chỉ lấy tin mới |
| `buildEventPayload` | chỉ đúng các trường mục 5.1; khóa thông báo đã băm |
| `ReminderPlanner` | `setAlarmClock` cho loại báo thức; cửa sổ 14 ngày; nhắc đã qua bị bỏ; hoãn 10 phút |
| `WebBundleVerifier` | đúng chữ ký thì nhận; sai một byte, sai chữ ký, `min_app_version_code` lớn hơn bản đang chạy thì từ chối; zip có `../` bị từ chối |
| `compareVersion`, `versionCodeFromTag` | `v1.5.2` ra 10502 |

### 6.2 Máy ảo (job `android-emulator`)

Theo `70` mục 3.9: bật quyền nghe bằng `cmd notification allow_listener`; app `testhelper` đăng thông báo giả; kiểm sự kiện vào hàng đợi, OTP không vào; tắt mạng rồi bật, WorkManager gửi đúng một lần tới máy chủ giả; báo thức kêu sau khởi động lại máy ảo.

### 6.3 Máy thật Galaxy S25+ (mỗi bản APK có đổi lớp gốc)

1. Cài mới từ trình duyệt: gặp cài đặt bị hạn chế, làm theo hướng dẫn, bật được quyền đọc thông báo.
2. Thêm vào *Ứng dụng không bao giờ ngủ* bằng nút trong app (intent của Samsung mở đúng danh sách).
3. Giao dịch thật Vietcombank, Techcombank, MoMo ra đúng một sự kiện; OTP thật không lên máy chủ; `otpBlockedToday` tăng.
4. Tin SMS ở app SMS mặc định (Samsung Messages hoặc Google Messages) vào hộp tin; app SMS còn lại không gửi gì.
5. Tin Zalo nhóm, riêng, và khi Zalo bật ẩn nội dung.
6. Tắt mạng, nhận 5 thông báo, bật mạng: đủ 5, không trùng.
7. Đặt nhắc 2 phút, tắt mạng, khóa màn hình: kêu đúng giờ. Khởi động lại máy: nhắc sau đó vẫn kêu. Sự kiện tạo trên Google Calendar không kêu hai lần.
8. Để máy yên 3 ngày không mở app: nhắc vẫn kêu, sự kiện vẫn lên (kiểm bước Samsung).
9. Dẫn đường: Google Maps mở thẳng chế độ xe hai bánh ở Việt Nam.
10. Gói giao diện mới áp dụng ở lần mở sau; gói hỏng tự quay lui.
11. APK mới: app hỏi trước; bấm *Cập nhật* thì cài không cần bấm thêm (hoặc hiện hộp hệ thống nếu không đủ điều kiện); nhắc còn sau cập nhật.
12. Thu hồi thiết bị: app về màn đăng nhập ở lần gọi kế tiếp.

## 7. Rủi ro

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Năm 2027 chặn cài và cập nhật app chưa đăng ký [N20][N21] | Cao | Tài khoản phân phối giới hạn, đăng ký trong V1.5; đường lùi `adb`, luồng nâng cao |
| One UI đưa app vào ngủ hoặc ngủ sâu: hạn chế báo thức, việc nền; ngủ sâu thì không chạy nền [N28] | Cao | Bước *Ứng dụng không bao giờ ngủ* có nút mở thẳng; pin không hạn chế; `heartbeat`, `last_event_at` để máy chủ và màn *Kiểm tra máy* phát hiện im lặng quá 24 giờ |
| Cài đặt bị hạn chế làm kẹt bước bật quyền | Trung bình | Hướng dẫn có thứ tự; lần đầu có thể cài bằng `adb` |
| Android 15 che nhầm thông báo biến động số dư vì đoán là OTP [N12] | Trung bình | Thử giao dịch thật trên S25+; theo dõi số thông báo ngân hàng rỗng; ghi bù bằng chat |
| Luật *theo nguồn* bỏ nhầm thông báo giao dịch có định dạng lạ | Trung bình | Mẫu giao dịch trong bộ mẫu chung; bộ luật có phiên bản, sửa nhanh |
| Tên gói ngân hàng, SMS khác dự kiến | Thấp | Màn *App được nghe* báo *Không thấy trên máy*; sửa ở máy chủ |
| Không có đẩy tin: nhắc của sự kiện `remind_source = app` sửa từ máy khác có thể trễ tới 1 giờ | Thấp | Sự kiện tạo trên Google do Google nhắc; đồng bộ mỗi giờ và khi mở app |
| Gói giao diện gọi plugin APK cũ chưa có | Trung bình | `min_app_version_code`; tự quay lui |
| Mất khóa ký APK | Cao, hiếm | Theo `60` mục 3.6 |
| Ngưỡng `targetSdk` của cài không cần bấm lần hai tăng theo Android [N19] | Thấp | Luôn xử lý `STATUS_PENDING_USER_ACTION` |
| Intent mở danh sách Samsung đổi ở One UI mới | Thấp | Đường lùi hướng dẫn tay [N29] |
| Capacitor 9 đổi yêu cầu (`compileSdk` 37) [N4] | Thấp | `minSdk` đã 26; nâng khi có bản ổn định |

## 8. Câu hỏi mở

1. Khóa vân tay sau bao lâu ở nền? Đề xuất 5 phút.
2. Tài khoản Google dùng cho Android Developer Console đã bật xác minh hai bước và có hồ sơ thanh toán Google chưa? Cần trước V1.5.
3. Nhận giọng nói bằng dịch vụ của Google trên máy có chấp nhận không? Đề xuất: có.
4. App SMS mặc định trên chiếc S25+ đang là Samsung Messages hay Google Messages? Không bắt buộc trả lời (app tự đọc), chỉ để chuẩn bị bộ mẫu SMS.
5. One UI trên máy đang là bản mấy? Để thử đúng intent và đường cài đặt Samsung.

Đã đóng nhờ QĐ: máy đích (QĐ-19), tự cài APK (QĐ-18), người dùng thứ hai (QĐ-15).

## 9. Cần agent khác

| Agent | Tệp | Việc |
|---|---|---|
| kiến trúc | `11` | Mục 4.1: cột `tab_device`; `reminder_action`; `payload`; định dạng `signature`; 8 dòng mặc định `tab_listened_app`; bỏ khóa `app.auto_install_update` |
| kiến trúc | `12` | `/calendar/reminders` cho U/D và chỉ trả `remind_source = app`; `heartbeat` nhận trường mục 4.1; `/device/config` trả thêm phiên bản bộ luật OTP, danh sách tên thương hiệu SMS, cờ đồng ý, và bỏ `com.google.android.gm` khi Gmail đã nối; thêm `POST /device/health` (V2); giới hạn lô 50 sự kiện, 256 KB một chỗ |
| kiến trúc | `10` | Thêm `/calendar/reminders` vào danh sách mã thiết bị được gọi; job xử lý `reminder_action`; cảnh báo thiết bị im lặng quá 24 giờ |
| hạ tầng | `50` | Biến không bí mật chứa dấu vân tay chứng chỉ ký; job `ui` đọc `min_app_version_code` từ `app/package.json`; module `testhelper` trong job `android-emulator`; trang tải APK lần đầu |
| hạ tầng | `70` | Danh sách thử tay mục 6.3 thay cho danh sách tối thiểu |
| điều phối | `01`, `02` | Như báo cáo rà chéo mục D1 (Capacitor 8, câu cài APK theo QĐ-18, gói Android, `testhelper/`) |

## 10. Đề xuất quyết định

ĐX-30-01 tới ĐX-30-10 đã duyệt theo QĐ-25; riêng ĐX-30-03 nay đọc theo QĐ-18 (luôn hỏi, `UPDATE_PACKAGES_WITHOUT_USER_ACTION` chỉ bỏ bấm lần hai sau khi người dùng đã bấm *Cập nhật*). Đề xuất mới:

| Số | Đề xuất | Lý do |
|---|---|---|
| ĐX-30-11 | Thiết lập máy có bước *Ứng dụng không bao giờ ngủ* chỉ hiện trên Samsung, mở bằng intent Samsung công bố, có đường lùi hướng dẫn tay, người dùng tự tích *Đã làm* | QĐ-19; One UI hạn chế báo thức và việc nền của app đang ngủ; app không đọc được trạng thái danh sách |
| ĐX-30-12 | Cả hai app SMS có dòng trong `tab_listened_app`; app tự bật dòng của app SMS mặc định khi thiết lập | QĐ-19; mỗi máy một app mặc định, đổi được về sau |
| ĐX-30-13 | Health Connect dùng `connect-client` 1.1.0 ổn định | Khớp `40`; 1.2.0 còn alpha |
| ĐX-30-14 | Mẫu giao dịch cho luật OTP *theo nguồn* đặt trong bộ luật có phiên bản, dùng chung cho Kotlin và Python qua `testdata/otp-samples.yaml` | Luật *theo nguồn* cần biết thế nào là thông báo giao dịch; hai lớp phải cho cùng kết quả |

## 11. Nguồn

Tra ngày 18/11/2026.

- [N1] Capacitor docs, v8: https://capacitorjs.com/docs
- [N2] npm registry `@capacitor/core` (latest 8.6.2, next 9.0.0-rc.0): https://registry.npmjs.org/@capacitor/core
- [N3] Capacitor, Updating to 8.0: https://capacitorjs.com/docs/updating/8-0 ; Support policy: https://capacitorjs.com/docs/main/reference/support-policy
- [N4] Mã nguồn Capacitor, `android/capacitor/build.gradle` và `plugin/WebView.java` ở thẻ 8.6.2 và nhánh `main`: https://github.com/ionic-team/capacitor
- [N5] `NotificationListenerService`: https://developer.android.com/reference/android/service/notification/NotificationListenerService
- [N6] Android 14, Schedule exact alarms are denied by default: https://developer.android.com/about/versions/14/changes/schedule-exact-alarms
- [N7] Schedule alarms: https://developer.android.com/develop/background-work/services/alarms/schedule
- [N8] Optimize for Doze and App Standby: https://developer.android.com/training/monitoring-device-state/doze-standby
- [N9] WorkManager, Getting started: https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started
- [N10] Android Help, Learn about restricted settings: https://support.google.com/android/answer/12623953
- [N11] Kaspersky, Restricted Settings in Android 13 and 14 (nguồn phụ): https://www.kaspersky.com/blog/android-restricted-settings/49991/
- [N12] Android 15 behavior changes, all apps: https://developer.android.com/about/versions/15/behavior-changes-all
- [N13] Package visibility, `<queries>`: https://developer.android.com/training/package-visibility/declaring
- [N14] Biometric authentication: https://developer.android.com/identity/sign-in/biometric-auth
- [N15] Notification runtime permission: https://developer.android.com/develop/ui/views/notifications/notification-permission
- [N16] Health Connect, Get started: https://developer.android.com/health-and-fitness/guides/health-connect/develop/get-started
- [N17] Android Keystore system: https://developer.android.com/privacy-and-security/keystore
- [N18] `PackageInstaller`: https://developer.android.com/reference/android/content/pm/PackageInstaller
- [N19] `PackageInstaller.SessionParams#setRequireUserAction`: https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams#setRequireUserAction(int)
- [N20] Android developer verification: https://developer.android.com/developer-verification
- [N21] Android developer verification FAQ: https://developer.android.com/developer-verification/guides/faq
- [N22] Capgo, Self-hosted getting started: https://capgo.app/docs/plugins/updater/self-hosted/getting-started/
- [N23] Limited distribution accounts: https://developer.android.com/developer-verification/guides/limited-distribution
- [N24] Google Maps Intents for Android: https://developer.android.com/guide/components/google-maps-intents
- [N25] Maps URLs: https://developers.google.com/maps/documentation/urls/get-started
- [N26] Sign your app: https://developer.android.com/studio/publish/app-signing
- [N27] Kho Maven của Google, `androidx.health.connect:connect-client` (bản ổn định mới nhất 1.1.0): https://dl.google.com/android/maven2/androidx/health/connect/connect-client/maven-metadata.xml
- [N28] Samsung Developer, Application Management (ngủ sau khoảng 3 ngày, hạn chế Job, Alarm, dịch vụ tiền cảnh; ngủ sâu sau 16 ngày; intent mở danh sách, `activity_type = 2`): https://developer.samsung.com/mobile/app-management.html
- [N29] Samsung Support, Sleeping apps on your Galaxy device (đường cài đặt, cảnh báo tốn pin): https://www.samsung.com/us/support/answer/ANS10003442/
