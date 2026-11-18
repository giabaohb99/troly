# Cấu trúc mã nguồn

Ngày lập: 18/11/2026. Đây là cấu trúc đích của kho `troly`. Thư mục mã sẽ được tạo dần theo lộ trình ở [00-ke-hoach.md](00-ke-hoach.md).

## 1. Toàn kho

```
troly/
  README.md                     giới thiệu ngắn, chỉ tới docs/
  CLAUDE.md                     luật làm việc cho người và cho agent
  .gitignore
  .env.example                  mẫu biến môi trường, không chứa bí mật
  docker-compose.yml            api, worker, db (chạy chung VPS với Gamebar, gymcanhan)
  .github/
    workflows/
      backend-test.yml          chạy bài kiểm backend mỗi lần đẩy
      app-build.yml             build giao diện + APK, đẩy APK lên R2
  docs/                         MỌI tài liệu nằm ở đây (xem mục 4)
  backend/                      máy chủ Python
  app/                          app Android (Capacitor: giao diện React + plugin Kotlin)
  infra/                        tệp cấu hình triển khai
  scripts/                      lệnh tiện ích (sao lưu, khôi phục, đăng bản APK)
```

## 2. Backend

```
backend/
  pyproject.toml
  alembic.ini
  alembic/versions/
  app/
    main.py                     dựng FastAPI, gắn router của mọi module
    core/
      config.py                 đọc .env
      db.py                     engine, session
      auth.py                   đăng nhập, JWT, mã thiết bị
      security.py               băm, mã hóa token Google
      errors.py                 phong bì lỗi tiếng Việt
      logging.py
      scheduler.py              tiện ích lịch chạy cho worker
    ai/
      client.py                 gọi Claude, đo token, tính tiền
      prompt.py                 lời nhắc hệ thống tĩnh + ghép hồ sơ lõi
      loop.py                   vòng gọi công cụ
      compaction.py             tóm tắt phiên dài
      registry.py               gom công cụ của mọi module
      actions.py                hành động trả cho app (mở bản đồ, mở link, xác nhận)
    integrations/
      google/
        oauth.py                kết nối tài khoản Google, làm mới token
        calendar.py             Google Calendar
        tasks.py                Google Tasks
        gmail.py                Gmail
        people.py               Google Contacts (People API)
        drive.py                Google Drive
        sheets.py               Google Sheets
        maps.py                 Geocoding, Places, Routes
      r2.py                     Cloudflare R2
    modules/
      memory/                   hồ sơ lõi, ghi chú
      chat/                     hội thoại, tin nhắn
      expense/                  chi tiêu, bóc tách thông báo ngân hàng và MoMo
      inbox/                    tin nhắn nghe từ thông báo + Gmail, tổng hợp
      task/                     việc cần làm
      calendar/                 lịch, nhắc
      trip/                     lịch trình, điểm dừng, bản đồ, xuất Word
      report/                   bảng điều khiển, thống kê, báo cáo khi được hỏi
      setting/                  cài đặt người dùng
      device/                   thiết bị, sự kiện điện thoại, phiên bản app
      file/                     tệp trên R2
      health/                   (V2) số liệu Health Connect, buổi tập
      <tên module>/
        models.py               bảng
        schemas.py              dữ liệu vào ra
        repo.py                 đọc ghi DB, mọi hàm nhận (session, user_id, ...)
        service.py              luật nghiệp vụ
        router.py               REST API
        tools.py                công cụ cho AI
        tests/
  worker/
    main.py                     vòng chạy nền
    jobs/                       đồng bộ Google, xử lý sự kiện, sao lưu, dọn dữ liệu cũ
  tests/                        bài kiểm dùng chung, bài kiểm chéo người dùng
```

Luật module: module không import ruột module khác. Cần dùng chung thì đưa lên `core/` hoặc `integrations/`. Module gọi nhau qua `service.py` công khai.

## 3. App Android

```
app/
  package.json
  capacitor.config.ts
  vite.config.ts
  index.html
  src/
    main.tsx
    core/                       gọi API, đăng nhập, cầu nối plugin gốc
    shared/
      ui/                       thành phần shadcn
      constants/query-keys.ts
      utils/
    modules/
      chat/                     màn chat (màn chính)
      inbox/                    hộp tin
      calendar/                 lịch + việc
      expense/                  chi tiêu
      trip/                     lịch trình + bản đồ
      report/                   bảng điều khiển, thống kê
      setting/                  cài đặt, kết nối Google, app được nghe, thiết bị
      <tên module>/{api,components,hooks,pages,types,utils}
  android/                      dự án Android do Capacitor sinh
    app/src/main/java/vn/io/baohuynh/troly/
      notify/                   NotificationListenerService, bộ lọc, hàng đợi
      alarm/                    nhắc lịch bằng AlarmManager
      update/                   kiểm và tải bản cập nhật
      maps/                     mở Google Maps
      health/                   (V2) đọc Health Connect
      plugin/                   plugin Capacitor nối các phần trên với giao diện
```

## 4. Tài liệu

```
docs/
  README.md                     mục lục, ai giữ tệp nào
  00-ke-hoach.md                kế hoạch tổng, lộ trình, phân công agent
  01-thiet-ke-tong-the.md       thiết kế tổng thể (bức tranh chung)
  02-cau-truc-ma-nguon.md       tệp này
  10-kien-truc-backend.md       tầng lớp, luật module, lỗi, đăng nhập, worker
  11-co-so-du-lieu.md           toàn bộ bảng, cột, chỉ mục, migration
  12-api.md                     danh sách API, phong bì, phân trang
  20-bo-nao-ai.md               lời nhắc, cache, trí nhớ, công cụ, chi phí
  30-app-android.md             Capacitor, plugin Kotlin, quyền, cập nhật
  31-giao-dien.md               màn hình, luồng, thành phần
  40-tich-hop-google.md         OAuth và từng dịch vụ Google
  41-ban-do-lich-trinh.md       lịch trình, Google Maps, xuất Word
  50-ha-tang-trien-khai.md      VPS, Docker, Cloudflare, GitHub Actions, sao lưu
  60-bao-mat-rieng-tu.md        mã, token, OTP, dữ liệu người khác
  70-kiem-thu.md                chiến lược kiểm thử, bộ mẫu
  90-quyet-dinh.md              sổ quyết định
  nhat-ky-viec.md               nhật ký việc đã làm
```
