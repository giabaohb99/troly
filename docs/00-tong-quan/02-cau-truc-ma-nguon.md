# Cấu trúc mã nguồn

Ngày lập: 18/11/2026. Bản 2: bổ sung theo rà chéo lần 1 (mục A4 dòng 56 của `80-ra-cheo-lan-1.md`). Đây là cấu trúc đích của kho `troly`; thư mục mã tạo dần theo lộ trình ở [00-ke-hoach.md](00-ke-hoach.md). Chi tiết nội dung từng tệp nằm ở tài liệu mảng tương ứng.

## 1. Toàn kho

```
troly/
  README.md                     giới thiệu ngắn, chỉ tới docs/
  CLAUDE.md                     luật làm việc cho người và cho agent
  .gitignore
  .env.example                  mẫu biến môi trường, không chứa bí mật
  docker-compose.yml            api, worker, db, migrate (bản chạy thật, nền cho máy cá nhân)
  docker-compose.dev.yml        ghép đè khi phát triển: gắn mã, tự nạp lại, mở cổng DB, giao diện, S3 giả
  .github/
    workflows/
      backend-test.yml          bài kiểm backend trong Docker mỗi lần đẩy
      app-build.yml             build gói giao diện + APK, ký, đẩy lên R2, đăng bản
      ai-eval.yml               chạy bộ câu mẫu AI khi được gọi tay
  docs/                         MỌI tài liệu (mục 4)
  backend/                      máy chủ Python (mục 2)
  app/                          app Android (mục 3)
  infra/
    docker-compose.test.yml     db-test trên tmpfs, test, web-test, android-test
    android-builder/            ảnh Docker có Android SDK để build APK trên máy
  scripts/                      deploy, khôi phục sao lưu, đăng bản
  testdata/                     bộ mẫu dùng chung: thông báo ngân hàng đã che số, mẫu OTP, phản hồi Google đã che, hợp đồng API
```

## 2. Backend

```
backend/
  Dockerfile                    ba đích: base, dev, prod
  pyproject.toml
  alembic.ini
  alembic/versions/
  app/
    main.py                     gốc ghép: gắn router, đăng ký công cụ AI, lớp giữa
    cli.py                      lệnh quản trị: create-owner, revoke-device, reencrypt-tokens, unlock-user
    core/
      config.py                 đọc biến môi trường (pydantic-settings)
      db.py                     engine, session
      models.py                 lớp nền, cột chung
      clock.py                  giờ hiện tại (đóng băng được trong bài kiểm)
      auth.py                   đăng nhập, JWT, mã thiết bị, mã CI
      security.py               băm, mã hóa token Google (Fernet)
      errors.py                 phong bì lỗi tiếng Việt
      logging.py                log JSON, che dữ liệu nhạy cảm
      scheduler.py              hằng số khóa job, tiện ích lịch
    ai/
      client.py                 gọi Claude, đo token
      pricing.py                bảng giá, tính tiền mỗi lượt
      prompt.py                 lời nhắc hệ thống tĩnh + ghép hồ sơ lõi
      loop.py                   vòng gọi công cụ (run_turn)
      compaction.py             tóm tắt phiên dài
      extract.py                bóc tách có cấu trúc (thông báo, câu chi tiêu, lịch trình)
      schemas.py                lược đồ dùng chung của tầng AI
      registry.py               danh sách công cụ; main.py gọi register_tools
      actions.py                hành động trả cho app
    integrations/
      google/
        models.py               bảng tài khoản Google, trạng thái đồng bộ, outbox
        oauth.py  calendar.py  tasks.py  gmail.py  people.py  drive.py  sheets.py  maps.py
      r2.py                     Cloudflare R2
    modules/
      __init__.py               ENABLED_MODULES
      setting/  file/  memory/  chat/  expense/  inbox/  task/  calendar/  trip/  report/  device/
      health/                   (V2)
      <tên module>/
        models.py               bảng
        schemas.py              dữ liệu vào ra
        repo.py                 đọc ghi DB, mọi hàm nhận (session, user_id, ...)
        service.py              luật nghiệp vụ; module khác chỉ gọi tệp này và schemas.py
        router.py               REST API
        tools.py                công cụ cho AI
        jobs.py                 (tùy module) việc nền riêng của module
        tests/
  worker/
    main.py                     vòng chạy nền
    jobs/                       việc điều phối nhiều module (xử lý sự kiện thiết bị) và sao lưu, dọn dữ liệu
  tests/                        bài kiểm dùng chung, bài kiểm chéo người dùng
    ai_eval/                    bộ câu mẫu AI (pytest -m ai_eval)
```

Luật module chi tiết ở `10-kien-truc-backend.md` mục 3.4.

## 3. App Android

```
app/
  package.json
  capacitor.config.ts
  vite.config.ts
  index.html
  src/
    main.tsx
    app/                        khung: AppShell, thanh dưới 5 ô, tấm Thêm, router
    core/
      api/                      gọi API, đăng nhập, làm mới mã
      native/                   cầu nối tới plugin Kotlin
      offline/                  lưu đệm TanStack Query khi mất mạng
    shared/
      ui/                       thành phần shadcn
      components/  hooks/  chat/  utils/
      constants/query-keys.ts
    modules/
      chat/  inbox/  calendar/  expense/  trip/  report/  setting/
      <tên module>/{api,components,hooks,pages,types,utils}
  android/                      dự án Android do Capacitor sinh
    app/src/main/java/vn/io/baohuynh/troly/
      notify/                   NotificationListenerService, bộ lọc app, OTP, trùng lặp
      queue/                    hàng đợi gửi lên (WorkManager)
      alarm/                    nhắc lịch bằng AlarmManager
      update/                   kiểm, tải, hỏi cài bản mới
      maps/                     mở Google Maps
      secure/                   kho khóa Android (cất mã thiết bị, mã làm mới)
      system/                   kiểm quyền, tối ưu pin, chế độ ngủ của One UI
      voice/                    nhận dạng giọng nói
      health/                   (V2) Health Connect
      plugin/                   plugin Capacitor nối các phần trên với giao diện
```

Chi tiết ở `30-app-android.md` và `31-giao-dien.md`.

## 4. Tài liệu

```
docs/
  README.md                     mục lục, người giữ, quy ước
  00-tong-quan/                 00 kế hoạch, 01 thiết kế tổng thể, 02 cấu trúc mã nguồn
  10-backend/                   10 kiến trúc backend, 11 cơ sở dữ liệu, 12 API
  20-ai/                        20 bộ não AI
  30-app/                       30 app Android, 31 giao diện
  40-google/                    40 tích hợp Google, 41 bản đồ và lịch trình
  50-ha-tang/                   50 hạ tầng, triển khai
  60-bao-mat/                   60 bảo mật, riêng tư
  70-kiem-thu/                  70 kiểm thử
  80-ra-soat/                   báo cáo rà chéo từng lần
  90-quan-ly/                   90 sổ quyết định, nhật ký việc
```

Chi tiết từng tệp và quy ước đặt tên ở [docs/README.md](../README.md).
