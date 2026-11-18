# Hạ tầng và triển khai

Ngày lập: 18/11/2026. Người giữ: agent hạ tầng. Trạng thái: bản 2, đã sửa theo `80-ra-cheo-lan-1.md` và QĐ-15 tới QĐ-25.

Nguồn chuẩn (QĐ-25): tệp này là nguồn chuẩn cho mạng, cổng, compose. Bảng và cột theo `11-co-so-du-lieu.md`; đường dẫn API và giới hạn tần suất theo `12-api.md`; biến môi trường và danh sách job theo `10-kien-truc-backend.md`. Chỗ nào tệp này nêu biến hay job chưa có ở 10 thì là đề nghị gom, ghi ở mục *Cần agent khác*.

Liên quan: [01-thiet-ke-tong-the.md](../00-tong-quan/01-thiet-ke-tong-the.md) mục 4, 9, 11; [02-cau-truc-ma-nguon.md](../00-tong-quan/02-cau-truc-ma-nguon.md); [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md); [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md).

## 1. Mục tiêu

- Chạy backend troly (api, worker, db) trên VPS chung mà **không ảnh hưởng** gymcanhan: không đụng thư mục, container, cổng, mạng, `cloudflared` của app khác; tổng tài nguyên troly có trần cứng. Ngoại lệ duy nhất: tạm dừng container `core-game` của Gamebar theo QĐ-24 (mục 3.15), có người dùng xác nhận.
- Không mở cổng web nào ra Internet; mọi lưu lượng vào qua Cloudflare Tunnel sẵn có.
- Build APK và bản giao diện hoàn toàn trên GitHub Actions; máy cá nhân không cần Android SDK.
- Deploy một lệnh, quay lui một lệnh, có sao lưu ngay trước mỗi lần chạy migration.
- Mất VPS vẫn dựng lại được trong khoảng 1 giờ từ bản sao lưu trên R2. Sao lưu mỗi tuần (QĐ-16) nên có thể mất tối đa 7 ngày dữ liệu; trước việc lớn thì bấm sao lưu tay (mục 3.10).

## 2. Phạm vi

Trong tệp này: sơ đồ dịch vụ trên VPS, Docker Compose, Cloudflare Tunnel, biến môi trường, GitHub Actions, deploy và quay lui, sao lưu và diễn tập khôi phục, giám sát và nhật ký, giới hạn tài nguyên, chỗ chạy Claude CLI cho V3, môi trường phát triển, build APK trên máy, kế hoạch tạm tắt Gamebar.

Ngoài tệp này: bảo mật và quản lý bí mật chi tiết ở [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md); chiến lược kiểm thử ở [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md); cấu trúc mã backend ở `10-kien-truc-backend.md`; cách app tải bản cập nhật ở `30-app-android.md`.

Mọi thông tin về VPS trong tệp này lấy từ tài liệu và script triển khai của gymcanhan (`doc/trien-khai-vps.md`, `tools/len-vps.sh`, `docker-compose.yml`) và Gamebar (`docker-compose.yml`, `docker-compose.vps.yml`, `CLAUDE.md`), đọc ngày 18/11/2026. Chưa kiểm trực tiếp trên VPS; các điểm cần kiểm ghi ở mục *Câu hỏi mở*.

## 3. Thiết kế

### 3.1 Bối cảnh VPS chung

| Mục | Hiện trạng |
|---|---|
| Máy | Ubuntu 24.04, 2 vCPU, 4 GB RAM, ổ khoảng 22 GB dùng được |
| Truy cập | SSH bằng khóa; tường lửa chỉ mở cổng 22 |
| Gamebar | Thư mục `/opt/gamebar`, container `core-game`, nghe `127.0.0.1:8080`, SQLite trong volume `gamebar-db`, sao lưu đêm lên bucket R2 `gamebar` sau 3 giờ sáng. **Sẽ tạm dừng** ngay trước lần deploy V1.0 đầu tiên (QĐ-24, mục 3.15) |
| `cloudflared` | Nằm trong compose của Gamebar (`docker-compose.vps.yml`), `network_mode: host`. Đẩy bản Gamebar mới có thể khởi động lại tunnel vài giây |
| gymcanhan | Thư mục `/opt/gymcanhan`, container `gymcanhan`, nghe `127.0.0.1:8100`, SQLite trong volume `gym-db` |
| Bài học từ gym | Bộ đệm build Docker từng lên 12 GB (17/11/2026); script deploy của gym tự dọn lớp build cũ hơn 3 ngày |

### 3.2 Sơ đồ dịch vụ

```
                       Internet
                          |
                 Cloudflare (DNS, TLS, WAF)
                          |
     ============ VPS chung (chỉ mở cổng 22) =================================
     |                                                                         |
     |  cloudflared (của Gamebar, mạng host)                                   |
     |     game.baohuynh.io.vn  -> http://localhost:8080  core-game  (tạm dừng)|
     |     gym.baohuynh.io.vn   -> http://localhost:8100  gymcanhan             |
     |     <api-domain>         -> http://localhost:8200  troly-api   (mới)    |
     |                                                                         |
     |  Dự án compose "troly" (/opt/troly)                                     |
     |   mạng troly_edge (bridge):  troly-api  [127.0.0.1:8200 -> 8000]        |
     |   mạng troly_core (internal, không ra Internet):                        |
     |        troly-api ----+                                                  |
     |        troly-worker -+--> troly-db (PostgreSQL 16, không mở cổng)       |
     |   troly-worker cũng nối troly_edge để gọi Claude API, Google, R2        |
     |   volume: troly-pgdata                                                  |
     ===========================================================================
                 |                     |                    |
            Claude API          Google APIs          Cloudflare R2
                                                 troly-files, troly-backup,
                                                 troly-release
```

Luật cô lập với hai app kia:

| Luật | Cách làm |
|---|---|
| Thư mục riêng | Chỉ ghi vào `/opt/troly`. Không đọc, không ghi `/opt/gamebar`, `/opt/gymcanhan` |
| Tên dự án compose cố định | `name: troly` trong `docker-compose.yml`; mọi lệnh `docker compose` chạy trong `/opt/troly`. Không dùng `docker compose down` không kèm thư mục, không `docker system prune -a`, không `docker volume prune` |
| Container có tiền tố | `troly-api`, `troly-worker`, `troly-db`, `troly-migrate`. Volume `troly-pgdata`. Mạng `troly_edge`, `troly_core` |
| Cổng | Chỉ một cổng ra máy: `127.0.0.1:8200`. Cổng 8080, 8100 là của app khác. DB không mở cổng ra máy |
| `cloudflared` | Không sửa compose của Gamebar. Chỉ thêm một Public Hostname trên trang Cloudflare (người dùng tự bấm) |
| Dọn đĩa | Chỉ dọn ảnh có nhãn `com.troly.image=1` và bộ đệm build cũ hơn 3 ngày (bộ đệm build dùng chung, dọn theo tuổi như gym đang làm) |

Bảng cổng trên VPS (dự kiến, cần kiểm cổng 8200 còn trống):

| Cổng | Dịch vụ | Chủ |
|---|---|---|
| 22 | SSH | máy |
| 127.0.0.1:8080 | core-game | Gamebar (tạm dừng theo QĐ-24, cổng vẫn để dành) |
| 127.0.0.1:8100 | gymcanhan | gymcanhan |
| 127.0.0.1:8200 | troly-api | troly |

Cổng ở máy cá nhân khi phát triển (theo QĐ-14 cũng chạy trong Docker): api 8200, giao diện Vite 5190 (gym dùng 5180; `CORS_ORIGINS` phải có cổng này thay cho 5173 trong `10-kien-truc-backend.md`), DB phát triển 127.0.0.1:55432. DB kiểm thử chạy trên tmpfs, không mở cổng; khi cần soi thì mở tạm 127.0.0.1:55433.

### 3.3 Thư mục trên VPS

```
/opt/troly/
  docker-compose.yml        chép từ kho bằng git archive
  .env                      quyền 600, chủ root, không lên git
  backend/                  mã để dựng ảnh
  infra/                    cấu hình postgres, logrotate, systemd (V3)
  scripts/                  deploy, khôi phục, đăng bản
  releases.log              mỗi lần deploy một dòng: thời điểm, mã commit, thẻ ảnh, kết quả
```

Dữ liệu DB nằm trong volume Docker `troly-pgdata`, không nằm trong `/opt/troly` để `git archive` không bao giờ đè lên. Tệp người dùng nằm trên R2, VPS không giữ tệp.

### 3.4 Docker Compose

Mọi thứ chạy trên Docker, cả VPS lẫn máy cá nhân (QĐ-14). Ba tệp compose:

| Tệp | Dùng ở | Nội dung |
|---|---|---|
| `docker-compose.yml` | VPS (gốc) và máy cá nhân (làm nền) | api, worker, db, migrate như bản chạy thật; mục này |
| `docker-compose.dev.yml` | Máy cá nhân, ghép đè lên tệp gốc | Mã gắn bằng volume, api tự nạp lại, worker tự khởi động lại, DB mở cổng cho máy, dịch vụ giao diện, S3 giả; mục 3.13 |
| `infra/docker-compose.test.yml` | Máy cá nhân và GitHub Actions, đứng riêng | `db-test` trên tmpfs và `test` (cùng ảnh api, đích `dev`) chạy pytest; thêm `web-test`, `android-test`; mục 3.13 và `70-kiem-thu.md` |

Một Dockerfile backend nhiều đích (`target`), dùng chung cho api, worker, migrate và test, khác lệnh chạy:

| Đích | Nội dung | Dùng ở |
|---|---|---|
| `base` | `python:3.12-slim`, phụ thuộc chạy thật theo tệp khóa, `postgresql-client-16` (cho `pg_dump`, `pg_restore`), `age` | Nền chung |
| `dev` | `base` + phụ thuộc phát triển (pytest, ruff, pip-audit, watchfiles); không chép mã, mã gắn bằng volume | Máy cá nhân, test, CI |
| `prod` | `base` + chép mã; user không phải root | VPS |

Ảnh `prod` dựng bằng `docker build --target prod`.

Phiên bản ảnh nền chốt cho mọi nơi (VPS, máy cá nhân, kiểm thử, CI): `postgres:16-alpine`, `python:3.12-slim`, `node:24-alpine` (máy cá nhân đang có Node 24; Capacitor 8 cần Node 22 trở lên). Nhỏ hơn bản đầy đủ, hợp ổ 22 GB của VPS. Tìm toàn văn tiếng Việt dùng cấu hình `simple` kèm `unaccent`, chạy giống nhau trên bản alpine.

Phác thảo `docker-compose.yml` (mô tả cấu hình, không phải mã ứng dụng; agent kiến trúc và giai đoạn mã giữ quyền chỉnh):

```yaml
name: troly

x-backend: &backend
  image: troly-backend:${TROLY_IMAGE_TAG:-latest}
  env_file: .env
  restart: unless-stopped
  logging:
    driver: json-file
    options: { max-size: "10m", max-file: "3" }
  labels: { com.troly.image: "1" }
  stop_grace_period: 30s

services:
  db:
    image: postgres:16-alpine
    container_name: troly-db
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: UTC
    command: >
      postgres -c shared_buffers=128MB -c effective_cache_size=256MB
               -c work_mem=4MB -c maintenance_work_mem=64MB
               -c max_connections=30 -c log_min_duration_statement=1000
    volumes: [troly-pgdata:/var/lib/postgresql/data]
    networks: [troly_core]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      retries: 5
    deploy:
      resources: { limits: { cpus: "0.75", memory: 512M } }
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }

  migrate:
    <<: *backend
    container_name: troly-migrate
    command: ["alembic", "upgrade", "head"]
    restart: "no"
    networks: [troly_core]
    depends_on: { db: { condition: service_healthy } }
    profiles: ["migrate"]

  api:
    <<: *backend
    container_name: troly-api
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
              "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
    ports: ["${API_BIND:-127.0.0.1}:${API_PORT:-8200}:8000"]
    networks: [troly_core, troly_edge]
    depends_on: { db: { condition: service_healthy } }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources: { limits: { cpus: "0.75", memory: 448M } }

  worker:
    <<: *backend
    container_name: troly-worker
    command: ["python", "-m", "worker.main"]
    networks: [troly_core, troly_edge]
    depends_on: { db: { condition: service_healthy } }
    deploy:
      resources: { limits: { cpus: "0.5", memory: 384M } }

volumes:
  troly-pgdata:

networks:
  troly_core: { internal: true }
  troly_edge: {}
```

Ghi chú:

- `troly_core` là mạng `internal`: DB không có đường ra Internet và container của app khác không cùng mạng nên không thấy DB.
- `--forwarded-allow-ips "*"` an toàn vì cổng chỉ nghe `127.0.0.1`, chỉ `cloudflared` trên cùng máy gọi tới. IP thật của người gọi lấy từ đầu `CF-Connecting-IP` (dùng cho giới hạn tần suất, xem [60-bao-mat-rieng-tu.md](../60-bao-mat/60-bao-mat-rieng-tu.md) mục 3.7).
- Một tiến trình uvicorn là đủ (hiện một người dùng, QĐ-15; khung tối đa 4); giữ một tiến trình để bộ đếm giới hạn tần suất trong bộ nhớ đúng (`12-api.md` mục 3.7). Cần nhiều tiến trình thì chuyển bộ đếm sang Postgres trước.
- Giao diện React không phục vụ từ VPS: bản build giao diện và APK nằm trên R2 (bucket `troly-release`), api chỉ trả bản kê (manifest) kèm URL ký sẵn. Lý do ở mục *Đề xuất quyết định*.
- Migration chạy bằng dịch vụ một lần `migrate` (profile riêng), không chạy tự động khi api khởi động, để deploy kiểm soát được thứ tự: sao lưu, migrate, rồi mới đổi api.

### 3.5 Giới hạn tài nguyên

Ước tính RAM trên VPS 4 GB (số của Gamebar và gym là ước, cần đo bằng `docker stats` trước khi chốt). Cột cuối là lúc Gamebar đã tạm dừng theo QĐ-24 (mục 3.15); `cloudflared` vẫn chạy.

| Thành phần | RAM ước | Trần đặt | Khi Gamebar tạm dừng |
|---|---|---|---|
| Hệ điều hành, Docker | khoảng 500 MB | không đặt | khoảng 500 MB |
| `cloudflared` | khoảng 50 tới 100 MB | không đặt | vẫn chạy, khoảng 50 tới 100 MB |
| core-game (Node, Socket.IO, SQLite) | 300 tới 600 MB | của Gamebar | 0 |
| gymcanhan (Node, SQLite) | khoảng 150 MB | của gym | khoảng 150 MB |
| troly-db | 150 tới 300 MB | 512 MB | như cũ |
| troly-api | 150 tới 250 MB | 448 MB | như cũ |
| troly-worker | 120 tới 200 MB, lên cao khi `pg_dump` | 384 MB | như cũ |
| **Tổng ước lúc chạy** | **1,4 tới 2,1 GB** | | **0,9 tới 1,5 GB** |
| Dự trữ cho build Docker, bộ đệm trang | 1,9 tới 2,6 GB | | 2,5 tới 3,1 GB |

Tổng trần troly là 1,34 GB RAM và 2 vCPU chia theo hạn mức (0,75 + 0,75 + 0,5). Hạn mức CPU là trần, không giữ chỗ, nên lúc rảnh không lấy gì của app khác. Khi Gamebar tạm dừng, **giữ nguyên các trần trên**: chỗ trống thêm dùng làm dự trữ cho lúc build ảnh trên VPS và cho V3 (Claude CLI), và để mở lại Gamebar sau này không phải đổi cấu hình troly.

Luật thêm để không làm nghẽn app khác:

- Build ảnh troly chạy với `nice -n 10` trong script deploy; dọn bộ đệm build cũ hơn 3 ngày sau mỗi lần build.
- Sao lưu chạy chủ nhật 02:00 giờ Việt Nam (job `backup_database` của `10-kien-truc-backend.md` mục 3.9, lịch theo QĐ-16); `pg_dump` chạy với `nice` và `ionice -c3` trong container worker.
- Worker xử lý sự kiện thiết bị theo lô 50 mỗi vòng, nghỉ `WORKER_POLL_SECONDS` (30 giây) giữa các vòng (theo `10-kien-truc-backend.md` mục 3.9); đồng bộ Google mỗi người mỗi dịch vụ tối đa một lần mỗi `GOOGLE_SYNC_MIN_SECONDS` (300 giây).
- Nhật ký Docker giới hạn 3 tệp x 10 MB mỗi container.
- Ngưỡng ổ đĩa: job `disk_check` đo dung lượng trống của phân vùng chứa volume; dưới 15 phần trăm thì ghi cảnh báo vào trạng thái hệ thống (mục 3.12), dưới 8 phần trăm thì tạm dừng các việc ghi nhiều (đồng bộ Gmail, nhập tệp) và chỉ giữ chat, chi tiêu.

### 3.6 Cloudflare Tunnel

1. Người dùng chọn tên miền con cho api (tạm gọi `<api-domain>`, ví dụ dạng `troly.baohuynh.io.vn`).
2. Trên Cloudflare: Zero Trust > Networks > Tunnels > tunnel đang dùng của Gamebar > Public Hostname > thêm `<api-domain>` trỏ `http://localhost:8200`. Không tạo tunnel mới, không sửa compose Gamebar.
3. SSL/TLS ở chế độ Full; bật *Always Use HTTPS*.
4. Quy tắc WAF giới hạn tần suất (gói miễn phí có một quy tắc): đường dẫn `/api/v1/auth/*` tối đa 20 yêu cầu mỗi phút mỗi IP, khớp bảng giới hạn chung ở `12-api.md` mục 3.7. Đây là lớp ngoài; lớp trong ở api theo đúng bảng đó.
5. Không bật Cloudflare Access cho api vì app gọi trực tiếp bằng JWT và mã thiết bị; Access chỉ cân nhắc cho trang quản trị nếu sau này có.
6. Chat trả luồng SSE (`12-api.md` mục 5.5): không bật quy tắc nén hay bộ đệm nào cho `<api-domain>` (Cache Rules để *Bypass* cho `/api/*`); api gửi `X-Accel-Buffering: no` và ping mỗi 15 giây để không chạm giới hạn 100 giây không có dữ liệu của Cloudflare.
7. Đường công khai không cần đăng nhập: `/api/health`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/google/oauth/callback`, `/api/v1/webhooks/google/*`, và hai trang tĩnh `/chinh-sach-rieng-tu`, `/tai-app` (mục 3.16). Webhook Google kiểm `X-Goog-Channel-Token`, chỉ đặt cờ cần đồng bộ.
9. Webhook Google và trang OAuth không được bị chặn bởi bước kiểm trình duyệt của Cloudflare: tắt *Bot Fight Mode* cho tên miền con này hoặc thêm luật bỏ qua (Skip) cho `/api/v1/webhooks/google/*` và `/api/v1/google/oauth/callback`; Google không chạy được JavaScript thử thách.
10. Không cần tệp `/.well-known/assetlinks.json`: app quay về sau khi nối Google bằng lược đồ `troly://cai-dat/google?ket-qua=` (ĐX-31-06), không dùng App Link.
8. Giới hạn thân yêu cầu: máy chủ từ chối thân trên 1 MB (gói Cloudflare miễn phí cho tới 100 MB nên lớp chặn thật nằm ở api). Tệp lớn tải thẳng lên R2 bằng URL ký sẵn, không qua api.

Rủi ro đã biết: `cloudflared` sống trong compose Gamebar, mỗi lần Gamebar deploy thì troly mất kết nối vài giây. App chịu được nhờ hàng đợi WorkManager gửi lại và TanStack Query thử lại. Phương án tách ở mục *Đề xuất quyết định*.

### 3.7 Biến môi trường

Tệp `.env.example` ở gốc kho liệt kê đủ biến, không có giá trị thật. Trên VPS, `.env` ở `/opt/troly/.env`, quyền 600. Đổi `.env` thì chạy `docker compose up -d` (lệnh `docker restart` không nạp lại `.env`).

Nội dung đích của `.env.example`:

```dotenv
# Mẫu biến môi trường của troly. Chép thành .env (không lên git), quyền 600.
# Đổi .env xong chạy: docker compose up -d   (docker restart không nạp lại .env)

# ---------- Chung ----------
# dev | test | prod
ENV=dev
# Giờ của container và DB là UTC; giờ hiển thị theo APP_TIMEZONE và múi giờ từng người
TZ=UTC
APP_TIMEZONE=Asia/Ho_Chi_Minh
# Trần số tài khoản đang hoạt động
MAX_USERS=4
# Gốc được gọi API: WebView Capacitor và máy dev
CORS_ORIGINS=https://localhost,http://localhost:5190
LOG_LEVEL=INFO
# Địa chỉ công khai của api, dùng dựng link và redirect OAuth. Ví dụ https://<api-domain>
PUBLIC_BASE_URL=
# Giữ 127.0.0.1 trên VPS để chỉ Cloudflare Tunnel vào được
API_BIND=127.0.0.1
API_PORT=8200
# Thẻ ảnh đang chạy; script deploy tự ghi, quay lui bằng cách đặt lại thẻ cũ
TROLY_IMAGE_TAG=latest

# ---------- Cơ sở dữ liệu ----------
POSTGRES_DB=troly
POSTGRES_USER=troly
# Chuỗi ngẫu nhiên dài, không dùng lại ở nơi khác
POSTGRES_PASSWORD=
# Dựng từ ba biến trên; host là tên dịch vụ trong compose
DATABASE_URL=postgresql+psycopg://troly:<mật khẩu>@db:5432/troly
DB_POOL_SIZE=5

# ---------- Đăng nhập và phiên ----------
# 64 byte ngẫu nhiên, base64. Đổi khóa này là mọi phiên phải đăng nhập lại
JWT_SECRET=
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=60
BCRYPT_ROUNDS=12
LOGIN_MAX_FAILS=5
LOGIN_LOCK_MINUTES=15

# ---------- Mã hóa token Google khi lưu ----------
# Vòng khóa Fernet: phiên_bản:khóa, cách nhau dấu phẩy; khóa đầu tiên dùng để mã hóa bản ghi mới
TOKEN_ENCRYPTION_KEYS=v1:

# ---------- Bộ não AI (Claude API) ----------
ANTHROPIC_API_KEY=
AI_MODEL_CHAT=claude-haiku-5-5
AI_MODEL_EXTRACT=claude-haiku-5-5
# low cho chat thường, medium khi người dùng nói nghĩ kỹ
AI_EFFORT_CHAT=low
# Tóm tắt phiên khi lời nhắc vượt mức này (token)
AI_COMPACT_TOKENS=30000
AI_MAX_TOOL_ROUNDS=8
# Chặn bấm liên tục, không phải trần chi phí
AI_USER_HOURLY_TURNS=60
# QĐ-15: không có trần ngày. Mức tháng chỉ để cảnh báo trong app, không chặn
AI_MONTHLY_USD=200
# Số tin hộp tin tối đa gửi cho Claude trong một lần tổng hợp
AI_INBOX_MAX_ITEMS=200

# ---------- Cloudflare R2 ----------
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_FILES=troly-files
R2_BUCKET_BACKUP=troly-backup
R2_BUCKET_RELEASE=troly-release
# Hạn URL ký sẵn (giây), theo 12-api.md: tải lên 10 phút, tải về 15 phút
R2_PRESIGN_UPLOAD_SECONDS=600
R2_PRESIGN_DOWNLOAD_SECONDS=900

# ---------- Sao lưu (QĐ-16) ----------
# Khóa công khai age; khóa bí mật để giải mã KHÔNG nằm trên VPS
BACKUP_AGE_RECIPIENT=
# Mỗi tuần một lần: chủ nhật 02:00 giờ Việt Nam
BACKUP_WEEKDAY=sun
BACKUP_HOUR=2
# Tổng số bản giữ, tính cả bản trước migration
BACKUP_KEEP=5

# ---------- Google ----------
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
# Ví dụ https://<api-domain>/api/v1/google/oauth/callback
GOOGLE_OAUTH_REDIRECT_URI=
# Khóa Google Maps Platform, giới hạn theo IP của VPS và theo API
GOOGLE_MAPS_API_KEY=
GOOGLE_SYNC_MIN_SECONDS=300

# ---------- Đăng bản app ----------
# Băm SHA-256 của mã CI dùng gọi POST /api/v1/admin/releases (mã gốc nằm trong GitHub Secrets)
RELEASE_PUBLISH_TOKEN_HASH=

# ---------- Worker ----------
WORKER_POLL_SECONDS=30
# Lô sự kiện thiết bị mỗi vòng (10-kien-truc-backend.md mục 3.9)
WORKER_BATCH_SIZE=50
# QĐ-17: tin của người khác (hộp tin, sự kiện thiết bị, khối chat chứa tin người khác)
THIRD_PARTY_RETENTION_DAYS=180
AUDIT_LOG_RETENTION_DAYS=365
DISK_WARN_PERCENT=15
DISK_STOP_PERCENT=8

# Giới hạn tần suất là hằng số theo bảng ở 12-api.md mục 3.7, không đặt trong .env

# ---------- Tự phát triển (V3) ----------
# Bật cổng API cho máy chạy Claude CLI; để false tới V3
DEV_JOBS_ENABLED=false
# Băm SHA-256 của mã máy chạy (mã gốc chỉ nằm ở máy chạy Claude CLI)
DEV_RUNNER_TOKEN_HASH=
DEV_JOB_DAILY_USD=5
```

Nguồn chuẩn tên biến là `10-kien-truc-backend.md` mục 3.6 (QĐ-25). Biến AI theo `20-bo-nao-ai.md` và QĐ-15 (bỏ `AI_USER_DAILY_USD`, `AI_DAILY_USD`). Biến do tệp này đề nghị 10 gom vào bảng: `API_BIND`, `API_PORT`, `TROLY_IMAGE_TAG`, `POSTGRES_*`, `R2_BUCKET_FILES`, `R2_BUCKET_BACKUP`, `R2_BUCKET_RELEASE`, `R2_PRESIGN_UPLOAD_SECONDS`, `R2_PRESIGN_DOWNLOAD_SECONDS`, `BACKUP_*`, `GOOGLE_OAUTH_REDIRECT_URI`, `GOOGLE_SYNC_MIN_SECONDS`, `RELEASE_PUBLISH_TOKEN_HASH`, `WORKER_BATCH_SIZE`, `THIRD_PARTY_RETENTION_DAYS`, `AUDIT_LOG_RETENTION_DAYS`, `DISK_*`, `DEV_*`.

**Hạn mức Google Maps Platform** (đặt trong Google Cloud Console > Quotas, theo bảng ở `41-ban-do-lich-trinh.md` mục 7.3): Compute Routes 30 lời gọi mỗi ngày, Places 300 mỗi ngày, Route Matrix 300 phần tử mỗi ngày. Ngân sách trong Billing chỉ gửi cảnh báo, không chặn chi; chặn thật là quota theo ngày. Khóa `GOOGLE_MAPS_API_KEY` giới hạn theo IP của VPS và chỉ bật Geocoding, Places, Routes.

Biến **không** nằm trong `.env` của app:

| Biến | Nằm ở đâu | Vì sao |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Chỉ trong môi trường của máy chạy Claude CLI (mục 3.11) | User của Claude CLI không được đọc `.env` app; app không cần token này |
| Khóa bí mật `age` để giải mã sao lưu | Trình quản lý mật khẩu của người dùng và máy cá nhân | Lộ VPS không lộ được bản sao lưu cũ |
| Khóa ký APK, khóa ký gói giao diện | GitHub Secrets và bản cất ngoại tuyến | Xem `60-bao-mat-rieng-tu.md` mục 3.6 |
| `TUNNEL_TOKEN` | `.env` của Gamebar | Thuộc Gamebar |

### 3.8 GitHub Actions

Hai tệp theo `02-cau-truc-ma-nguon.md`, cộng một tệp đánh giá AI chạy tay.

**`backend-test.yml`**: chạy khi đẩy hoặc mở PR có thay đổi ở `backend/**`, `testdata/**`, `docker-compose*.yml`, `infra/docker-compose.test.yml`, `.github/workflows/backend-test.yml`. Chạy **đúng các lệnh compose như ở máy cá nhân** (mục 3.13), không cài Python lên runner, để kết quả ở máy và trên CI giống nhau. Viết tắt `T` = `docker compose -f infra/docker-compose.test.yml`.

| Bước | Nội dung |
|---|---|
| Dựng ảnh | `T build test` (đích `dev`), bộ đệm lớp Docker của GitHub Actions |
| Kiểm tĩnh | `T run --rm test ruff check` và `ruff format --check` |
| Migration | `T run --rm test alembic upgrade head` trên `db-test` trống, rồi `downgrade -1` và `upgrade head` lại cho migration mới nhất |
| Bài kiểm | `T run --rm test pytest -m "not ai_eval"` (xem [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md)) |
| Phụ thuộc | `T run --rm test pip-audit` trên tệp khóa; lỗ hổng mức cao làm đỏ |
| Ảnh chạy thật | `docker build --target prod` (không đẩy đi đâu) để chắc ảnh VPS còn dựng được |
| Dọn | `T down -v` |

**`app-build.yml`**: ba job.

| Job | Khi chạy | Nội dung |
|---|---|---|
| `ui` | Đẩy hoặc PR có thay đổi ở `app/src/**`, `app/package*.json` | `npm ci`, `tsc -b`, lint, `vitest run`, `vite build`. Trên nhánh `main`: nén bản build thành zip, tính `sha256`, ký ECDSA P-256 (`WEB_BUNDLE_SIGNING_KEY`, theo `30-app-android.md`), đẩy lên bucket `troly-release`, gọi `POST /api/v1/admin/releases` với `kind = web` |
| `android-unit` | Thay đổi ở `app/android/**` | JDK 21, `gradle testDebugUnitTest` cho bộ lọc thông báo (chạy trên JVM, không cần máy ảo) |
| `android-emulator` | Thay đổi ở `app/android/**/notify/**` hoặc khi đăng bản | Máy ảo Android trên runner Linux có KVM; kiểm `NotificationListenerService` thật (xem `70-kiem-thu.md`) |
| `apk` | Đẩy thẻ `v*` hoặc chạy tay | Dựng giao diện, `npx cap sync android`, giải mã keystore từ secret ra tệp tạm, `gradle assembleRelease`, `apksigner verify`, tính `sha256`, đẩy `releases/troly-<versionName>.apk` vào bucket `troly-release`, gọi `POST /api/v1/admin/releases` với `kind = apk` để ghi `tab_app_release`, xóa tệp keystore tạm |

Đánh số phiên bản theo `30-app-android.md`: `versionName` lấy từ thẻ (`v1.2.0` thành `1.2.0`); `versionCode` = `X*10000 + Y*100 + Z`.

Thêm cho job `ui` và `apk` theo `30-app-android.md`:

- Job `apk` so dấu vân tay chứng chỉ ký: `apksigner verify --print-certs` phải ra đúng giá trị biến GitHub (không bí mật) `ANDROID_SIGNING_CERT_SHA256`; lệch thì dừng, không đẩy lên R2.
- Job `ui` đọc số `versionCode` APK tối thiểu mà gói giao diện cần (khai trong `app/package.json`, trường `troly.minNativeVersionCode`) và gửi thành `min_supported_version_code` của bản `web` (API trả ra dưới tên `min_app_version_code`).
- Đăng bản không làm máy tự cài: app luôn hỏi trước khi cài APK mới (QĐ-18).

Ghi `tab_app_release`: job `apk` không có quyền vào DB. Nó gọi api qua Cloudflare bằng mã CI (`RELEASE_PUBLISH_TOKEN`), api kiểm băm mã, kiểm tệp có trên R2 và `sha256` khớp rồi mới ghi dòng. Mã CI chỉ dùng được cho đường dẫn đăng bản này.

**`ai-eval.yml`**: chỉ chạy tay (`workflow_dispatch`), chạy bộ câu mẫu với Claude thật, trần 0,5 USD mỗi lần (xem `70-kiem-thu.md` mục 3.7).

GitHub Secrets cần có:

| Secret | Dùng ở | Ghi chú |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | `apk` | Keystore mã base64 |
| `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` | `apk` | |
| `WEB_BUNDLE_SIGNING_KEY` | `ui`, `apk` | Khóa bí mật ECDSA P-256; khóa công khai nhúng trong APK |
| `R2_RELEASE_ACCESS_KEY_ID`, `R2_RELEASE_SECRET_ACCESS_KEY`, `R2_ENDPOINT` | `ui`, `apk` | Mã R2 chỉ có quyền trên bucket `troly-release` |
| `RELEASE_PUBLISH_TOKEN` | `ui`, `apk` | Mã gọi API đăng bản |
| `PUBLIC_BASE_URL` | `ui`, `apk` | Địa chỉ api |
| `ANTHROPIC_API_KEY_EVAL` | `ai-eval` | Khóa riêng cho đánh giá, đặt trần chi trên trang Anthropic |

Biến GitHub không bí mật: `ANDROID_SIGNING_CERT_SHA256` (dấu vân tay chứng chỉ ký APK, cũng ghi ở `60-bao-mat-rieng-tu.md` mục 3.6).

Các secret dùng để đăng bản đặt trong GitHub Environment `release`, chỉ nhánh `main` và thẻ `v*` được dùng. Thời gian chạy ước: `backend-test` khoảng 3 phút, `ui` 2 phút, `apk` 8 tới 12 phút, `android-emulator` 10 tới 15 phút. Kho riêng tư có hạn mức phút miễn phí mỗi tháng, nên job máy ảo không chạy mỗi lần đẩy.

### 3.9 Deploy và quay lui

GitHub Actions **không** SSH vào VPS; khóa SSH không nằm trên GitHub. Deploy chạy từ máy cá nhân bằng `bash scripts/deploy.sh`, giống cách gym và Gamebar đang làm. Trong V3, việc deploy sau khi bấm Duyệt chạy bằng chính script này trên VPS (mục 3.11).

**Lần đầu**

0. Tạm dừng Gamebar theo mục 3.15, sau khi người dùng xác nhận (QĐ-24).
1. Chạy `bash scripts/deploy.sh` một lần; script báo thiếu `/opt/troly/.env` rồi dừng.
2. Trên VPS tạo `/opt/troly/.env` từ `.env.example`, quyền 600; điền mật khẩu DB, `JWT_SECRET`, `TOKEN_ENCRYPTION_KEYS`, khóa Anthropic, R2, Google, `BACKUP_AGE_RECIPIENT`.
3. Chạy lại `bash scripts/deploy.sh`.
4. Tạo tài khoản chủ: `docker compose run --rm api python -m app.cli create-owner` (tên lệnh theo `10-kien-truc-backend.md` mục 3.1); mật khẩu tạm hiện một lần trên màn hình, đổi ngay khi đăng nhập app.
5. Thêm Public Hostname trên Cloudflare (mục 3.6).
6. Kiểm `https://<api-domain>/api/health` trả `status: ok`, `db: true`.
7. Diễn tập khôi phục lần đầu (mục 3.10) sau bản sao lưu đầu tiên.

**Các bước trong `scripts/deploy.sh`**

| Bước | Việc | Hỏng thì |
|---|---|---|
| 1 | Kiểm ở máy: nhánh `main`, cây sạch, bài kiểm của CI trên commit này đã xanh (`gh run list`) | Dừng |
| 2 | `git archive` các tệp cần (`docker-compose.yml`, `.env.example`, `backend`, `infra`, `scripts`) đẩy qua SSH vào `/opt/troly` | Dừng |
| 3 | Trên VPS: `nice -n 10 docker build -t troly-backend:<sha ngắn>` | Dừng, bản cũ vẫn chạy |
| 4 | Nếu ảnh mới có migration chưa chạy (`alembic current` khác `head` của ảnh mới): sao lưu trước migration ra `troly-backup/premigrate/<thời điểm>-<sha>.dump.age` (tính trong 5 bản, QĐ-16). Không có migration thì bỏ bước này | Dừng, không migrate khi chưa có bản sao lưu |
| 5 | `TROLY_IMAGE_TAG=<sha> docker compose --profile migrate run --rm migrate` | Dừng, bản cũ vẫn chạy (migration theo luật tương thích ngược, xem dưới) |
| 6 | Ghi `TROLY_IMAGE_TAG=<sha>` vào `.env`, `docker compose up -d api worker` | Sang quay lui |
| 7 | Chờ healthcheck api xanh tối đa 60 giây, gọi `/api/health` qua 127.0.0.1 | Sang quay lui |
| 8 | Ghi một dòng vào `releases.log`; xóa ảnh `troly-backend` cũ, giữ 3 thẻ gần nhất; `docker builder prune -f --filter until=72h`; in `df -h /` | Chỉ cảnh báo |

**Luật migration để quay lui được**

- Mỗi migration phải **tương thích ngược** với mã của bản ngay trước: thêm cột cho phép null hoặc có mặc định, thêm bảng, thêm chỉ mục `CONCURRENTLY` nếu bảng lớn. Đổi tên hay xóa cột làm hai lần deploy: bản trước thôi dùng, bản sau mới xóa.
- Nhờ vậy quay lui chỉ cần đổi lại ảnh, không cần hạ DB.
- Mỗi migration có hàm `downgrade` và được CI chạy thử (mục 3.8), nhưng trên VPS chỉ hạ DB khi thật cần.

**Quay lui**: `bash scripts/deploy.sh --rollback` đặt `TROLY_IMAGE_TAG` về thẻ trước trong `releases.log` và `docker compose up -d api worker`. Thời gian dưới 1 phút. Nếu migration làm hỏng dữ liệu: dừng api và worker, khôi phục bản `premigrate` mới nhất bằng `scripts/restore-db.sh` (mục 3.10), rồi chạy ảnh cũ.

Giao diện và APK quay lui riêng: đặt `is_published = false` cho bản lỗi trong `tab_app_release` (`PATCH /api/v1/releases/{id}`), app lấy bản liền trước. APK không hạ được trên máy nếu `versionCode` nhỏ hơn, nên sửa APK lỗi bằng cách đăng bản mới có `versionCode` lớn hơn.

### 3.10 Sao lưu và diễn tập khôi phục

Theo QĐ-16: sao lưu **mỗi tuần một lần**, giữ tối đa **5 bản**, bản trước migration tính trong 5 bản đó. Không còn bản ngày, bản tháng.

**Sao lưu tuần** là job theo lịch `backup_database` của worker (`10-kien-truc-backend.md` mục 3.9, đổi lịch thành chủ nhật 02:00):

1. Chủ nhật 02:00 giờ Việt Nam; nếu worker không chạy lúc đó thì chạy bù khi khởi động.
2. `pg_dump --format=custom` (đã nén) từ `troly-db` qua mạng `troly_core`, chạy với `nice` và `ionice -c3`.
3. Mã hóa bằng `age` với khóa công khai `BACKUP_AGE_RECIPIENT`. Bản rõ không ghi xuống đĩa: dữ liệu chảy qua ống từ `pg_dump` sang `age` sang tải lên R2 nhiều phần.
4. Đẩy lên `troly-backup/weekly/YYYY-MM-DD.dump.age`. Bản trước migration (mục 3.9) nằm ở `troly-backup/premigrate/`.
5. Sau khi bản mới tải lên thành công, liệt kê cả hai thư mục và xóa bản cũ nhất cho tới khi còn `BACKUP_KEEP` (5) bản. Luôn giữ ít nhất 1 bản `weekly` mới nhất: khi phải xóa thì xóa bản `premigrate` cũ trước, để một tuần nhiều migration không đẩy hết bản tuần ra ngoài.
6. Ghi kết quả (thời điểm, khóa R2, kích thước, `sha256` của tệp mã hóa, số dòng các bảng chính, thời gian chạy, lỗi) vào `tab_job_run.detail`.
7. Quá 8 ngày không có bản thành công thì trạng thái hệ thống chuyển đỏ (mục 3.12).

**Sao lưu tay**: chủ bấm *Sao lưu ngay* ở màn Cài đặt, gọi `POST /api/v1/admin/worker/jobs/backup_database/run` (`12-api.md` mục 5.17). Dùng trước việc lớn (nhập nhiều dữ liệu, đổi máy) để không phải chịu mất tới 7 ngày dữ liệu. Bản tay tính như bản tuần trong 5 bản.

Tin của người khác giữ 180 ngày trong DB (QĐ-17); 5 bản tuần làm dữ liệu đã xóa còn nằm trong bản sao lưu thêm tối đa khoảng 5 tuần. Ghi rõ điều này ở `60-bao-mat-rieng-tu.md` mục 3.9.

Bản sao lưu không chứa khóa: `TOKEN_ENCRYPTION_KEYS`, `JWT_SECRET` nằm ở `.env`, không trong DB. Người dùng cất một bản `.env` đã mã hóa (hoặc từng khóa) trong trình quản lý mật khẩu; mất `TOKEN_ENCRYPTION_KEYS` thì chỉ phải kết nối lại Google, không mất dữ liệu khác.

Tệp người dùng trên R2 (`troly-files`) không sao lưu thêm; R2 tự giữ nhiều bản sao. Xóa tệp trong app là xóa thật trên R2.

**Khôi phục**: `scripts/restore-db.sh <khóa R2> [--target drill|production]`.

- `drill` (mặc định): dựng container tạm `troly-db-drill` (`postgres:16-alpine`, trần 384 MB, mạng riêng, không cổng), giải mã và `pg_restore` vào đó, chạy bộ kiểm (bảng dưới), rồi xóa container.
- `production`: yêu cầu gõ lại tên bản sao lưu để xác nhận; dừng api và worker, sao lưu DB hiện tại thành một bản `premigrate` trước, khôi phục, chạy `alembic current` để thấy đúng phiên bản, bật lại api và worker.

**Diễn tập khôi phục** chạy trên **máy cá nhân** (có Docker và có khóa bí mật `age`), không chạy trên VPS. Lần đầu ngay sau bản sao lưu đầu tiên của V1.0; sau đó mỗi tháng một lần, dùng bản `weekly` mới nhất:

| Bước | Đạt khi |
|---|---|
| Tải bản `weekly` mới nhất, giải mã | Giải mã được, `sha256` khớp `tab_job_run.detail` |
| `pg_restore` vào `postgres:16-alpine` tạm | Không lỗi |
| `alembic current` | Bằng `head` của commit đang chạy trên VPS lúc sao lưu |
| Đếm dòng các bảng chính | Khớp số ghi trong `tab_job_run.detail` |
| Chạy api bằng DB vừa khôi phục (bộ compose dev), đăng nhập tài khoản chủ ở máy | Đăng nhập, xem chi tiêu tháng của bản sao lưu được |
| Ghi kết quả | Một mục trong `docs/90-quan-ly/nhat-ky-viec.md`: ngày, bản dùng, thời gian khôi phục |

Mục tiêu: mất tối đa 7 ngày dữ liệu (RPO, theo QĐ-16; thấp hơn nếu có sao lưu tay), dựng lại dưới 1 giờ (RTO) kể cả dựng lại VPS mới.

### 3.11 Chỗ chạy Claude CLI cho V3

Ràng buộc từ `01-thiet-ke-tong-the.md` mục 9: Claude CLI chạy bằng user riêng, không vào DB đang chạy, không đọc `.env` app, có trần chi phí.

Phương án đề xuất: **máy chạy riêng dạng container trên VPS, nói chuyện với api qua HTTP, không có quyền Docker**.

```
 troly-worker  --tạo tab_dev_job-->  troly-db
      ^
      | HTTP (mã máy chạy)
 troly-dev (container, user 10001, không có docker.sock, không vào troly_core)
   - Claude CLI, git, Python 3.12, Node
   - /work/troly: bản clone riêng, mỗi việc một worktree ở nhánh dev/<id>
   - postgres tạm (tmpfs) trong cùng container để chạy pytest
   - trần: 1 vCPU, 1 GB RAM, 30 phút mỗi việc, 1 việc một lúc
      |
      | git push nhánh dev/<id> (khóa deploy chỉ của kho troly)
      v
   GitHub: CI chạy backend-test, app-build trên nhánh
      |
 Người dùng bấm Duyệt trong app
      |
 troly-deployer (systemd timer của root trên máy, mỗi phút):
   hỏi api có việc đã duyệt -> gộp nhánh vào main -> bash scripts/deploy.sh (chạy tại chỗ)
```

| Điểm | Cách làm |
|---|---|
| Đăng nhập Claude CLI | `CLAUDE_CODE_OAUTH_TOKEN` chỉ nằm trong biến môi trường của container `troly-dev` (tệp `/opt/troly-dev/.env`, quyền 600), không trong `/opt/troly/.env` |
| Lấy việc | `GET /api/v1/dev/jobs/next`, `POST /api/v1/dev/jobs/{id}/result` bằng mã máy chạy; api chỉ mở các đường dẫn này khi `DEV_JOBS_ENABLED=true` |
| Không vào DB thật | Container không nối mạng `troly_core`; bài kiểm chạy trên Postgres tạm trong container |
| Đẩy mã | Khóa deploy SSH có quyền ghi chỉ trên kho `giabaohb99/troly`; nhánh `main` bật bảo vệ, chỉ nhận gộp từ deployer |
| Trần chi phí | Claude CLI dùng gói đăng ký (QĐ-12), không tính vào `AI_MONTHLY_USD`; giới hạn bằng thời gian mỗi việc và `DEV_JOB_DAILY_USD` (chỉ cho phần gọi khóa API nếu có) |
| Giờ chạy | Chỉ nhận việc từ 22:00 tới 07:00 hoặc khi người dùng bấm *Chạy ngay*, để không tranh CPU với app khác (nhất là khi Gamebar mở lại) |
| Deploy | Chỉ deployer (root) chạy `scripts/deploy.sh`; sao lưu trước migration là bước bắt buộc như mục 3.9 |

Phương án thay thế: chạy Claude CLI trên máy cá nhân (không tốn RAM VPS, nhưng máy phải bật). Chọn ở mục *Câu hỏi mở*.

### 3.12 Giám sát và nhật ký

| Lớp | Cách làm |
|---|---|
| Sức khỏe api | `GET /api/health` (`12-api.md` mục 5): không cần đăng nhập, trả `status`, `db`, `worker_lag_seconds`, `version`, `git_sha`. Không trả thông tin khác |
| Trạng thái hệ thống | `GET /api/v1/admin/worker` (chỉ chủ, đã có ở `12-api.md` mục 5.17), thêm các trường: sao lưu thành công gần nhất, số bản đang giữ, dung lượng trống, chi phí AI tháng này so với `AI_MONTHLY_USD`, số sự kiện đang chờ, số OTP bị chặn ở máy chủ (phải bằng 0) |
| Báo động | Không gửi tin tự động (QĐ-11). App của chủ hiện dải đỏ ở màn Cài đặt và một thông báo trên máy khi mở app nếu: quá 8 ngày không có bản sao lưu thành công, ổ dưới ngưỡng, worker không chạy quá 10 phút, chi phí AI tháng vượt `AI_MONTHLY_USD` (chỉ báo, không chặn, QĐ-15) |
| Kiểm từ ngoài | App không gọi được api quá 3 lần liền thì hiện *Không kết nối được máy chủ*. Kiểm định kỳ từ ngoài là câu hỏi mở |
| Nhật ký ứng dụng | JSON một dòng mỗi sự kiện ra stdout: thời điểm, mức, `request_id`, `user_id`, đường dẫn, mã trả về, thời gian. **Không ghi** nội dung tin nhắn, thông báo ngân hàng, token, mật khẩu, câu chat (xem `60-bao-mat-rieng-tu.md` mục 3.13) |
| Lưu nhật ký | Docker `json-file`, 3 tệp x 10 MB mỗi container; xem bằng `docker compose logs --since 1h api` |
| Nhật ký kiểm toán | Bảng riêng trong DB cho sự kiện bảo mật (đăng nhập, thêm hoặc thu hồi thiết bị, duyệt hành động, xuất dữ liệu), giữ 365 ngày |
| Chi phí AI | `tab_ai_run`, hiện ở bảng điều khiển |
| DB | `log_min_duration_statement=1000`: câu truy vấn chậm hơn 1 giây vào nhật ký Postgres |

### 3.13 Môi trường phát triển trên máy cá nhân

Máy cá nhân: Windows 11, Docker 29.8.1, Docker Compose v5.5.1, Node 24.18.0. Không cài Python, Postgres hay Android SDK cho dự án; mọi thứ chạy trong container (QĐ-14). Node trên máy chỉ là đường tắt, không bắt buộc.

**Dịch vụ của `docker-compose.dev.yml`** (ghép đè lên `docker-compose.yml`):

| Dịch vụ | Khác bản chạy thật |
|---|---|
| `db` | Volume riêng `troly-dev-pgdata`; mở `127.0.0.1:55432` để xem bằng công cụ DB; bỏ trần tài nguyên |
| `api` | `build.target: dev`, ảnh `troly-backend:dev`; gắn `./backend` vào `/app`; lệnh `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`; cổng `127.0.0.1:8200`; `ENV=dev` |
| `worker` | Cùng ảnh `dev`, cùng volume mã; lệnh `watchfiles "python -m worker.main" app worker` để tự khởi động lại khi sửa mã |
| `migrate` | Cùng ảnh `dev`, chạy tay (profile `migrate`) |
| `web` | `node:24-alpine`; gắn `./app`; `node_modules` nằm trong volume riêng `troly-dev-node-modules` (không lẫn với Windows); lệnh `npm ci` lần đầu rồi `npm run dev -- --host 0.0.0.0 --port 5190`; cổng `127.0.0.1:5190`; proxy `/api` sang `http://api:8000` |
| `s3` | S3 giả (ví dụ ảnh `motoserver/moto`), dữ liệu trong bộ nhớ, để chạy tính năng tệp mà không đụng R2 thật. Đây là mặc định ở máy cá nhân (chốt ở `80-ra-cheo-lan-1.md` mục B). Tắt máy là mất tệp thử, chấp nhận được |

**Tự nạp lại trên Windows:** mã nằm ở ổ `D:` của Windows, gắn vào container Linux qua Docker Desktop; sự kiện đổi tệp có thể không tới container. Vì vậy bản dev bật chế độ dò định kỳ: `WATCHFILES_FORCE_POLLING=true` cho api và worker, `server.watch.usePolling` của Vite cho `web` (hoặc `CHOKIDAR_USEPOLLING=true`). Tốn thêm chút CPU, đổi lại chạy chắc. Phương án nhanh hơn nếu sau này thấy chậm: để kho trong ổ Linux của WSL2.

**Biến môi trường ở máy cá nhân:** `.env` ở gốc kho (không lên git), chép từ `.env.example`, đặt `ENV=dev`, `PUBLIC_BASE_URL=http://localhost:8200`, `CORS_ORIGINS` có `http://localhost:5190`. Để khỏi gõ hai `-f` mỗi lần, thêm vào `.env` của máy cá nhân dòng `COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml` (Windows ngăn bằng dấu chấm phẩy). `.env` trên VPS **không** có dòng này. Khóa Anthropic ở máy dùng khóa riêng, trần chi thấp; Google dùng OAuth client riêng cho phát triển với địa chỉ chuyển hướng `http://localhost:8200/...`.

**Lệnh thường dùng** (khi đã đặt `COMPOSE_FILE`; chưa đặt thì thêm `-f docker-compose.yml -f docker-compose.dev.yml`):

| Việc | Lệnh |
|---|---|
| Dựng và chạy cả bộ | `docker compose up -d --build` |
| Xem nhật ký api | `docker compose logs -f api` |
| Chạy migration | `docker compose run --rm migrate` (hoặc `docker compose run --rm api alembic upgrade head`) |
| Tạo migration mới | `docker compose run --rm api alembic revision --autogenerate -m "<mô tả>"`; tệp sinh ra hiện ngay trong `backend/alembic/versions/` nhờ volume |
| Tạo tài khoản chủ ở máy | `docker compose run --rm api python -m app.cli create-owner`; mật khẩu thử ghi vào tệp tài khoản thử ở máy (không lên git), giống gymcanhan |
| Vào shell Python | `docker compose exec api python` |
| Xem DB | `docker compose exec db psql -U troly troly` |
| Chạy bài kiểm một module | `docker compose -f infra/docker-compose.test.yml run --rm test pytest backend/app/modules/<x>` |
| Chạy bài kiểm giao diện | `docker compose -f infra/docker-compose.test.yml run --rm web-test npx vitest run src/<thư mục>` |
| Dừng | `docker compose down` (giữ dữ liệu); `docker compose down -v` xóa cả DB dev |

**Bài kiểm chạy riêng khỏi bộ dev:** `infra/docker-compose.test.yml` đứng riêng, không đọc `.env` của máy, dựng `db-test` trên tmpfs mỗi lần, nên chạy bài kiểm không làm bẩn DB dev và chạy y hệt trên GitHub Actions (mục 3.8). Chi tiết ở `70-kiem-thu.md` mục 3.2.

**Thử app trên điện thoại thật với máy chủ ở máy cá nhân:** mặc định api chỉ nghe `127.0.0.1`. Khi cần, đặt `API_BIND=0.0.0.0` tạm thời, mở cổng 8200 trên tường lửa Windows cho mạng riêng, và cho bản APK dev trỏ tới IP LAN của máy. Xong thì trả lại `127.0.0.1`. Cách đơn giản hơn: APK dev trỏ vào api trên VPS.

**Dung lượng:** ảnh backend dev khoảng 0,5 tới 1 GB, `node_modules` khoảng 0,5 GB, DB dev nhỏ. Dọn định kỳ bằng `docker image prune` trên máy cá nhân (không phải VPS).

### 3.14 Build APK trên máy bằng Docker

Bản chính thức (bản ký phát hành, đẩy lên R2, ghi `tab_app_release`) **chỉ** build trên GitHub Actions (QĐ-08). Phương án thêm: một ảnh Docker có Android SDK chạy trên máy cá nhân để build bản thử khi làm phần Kotlin.

**Cách làm đề xuất**

- Tệp `infra/android-build.Dockerfile` tự viết, ghim phiên bản: nền `eclipse-temurin:21-jdk`, cài Android command-line tools, `platform-tools`, `build-tools` và `platforms;android-<API>` đúng bản `30-app-android.md` chọn, cùng Node 24 để dựng giao diện và `npx cap sync`. Không dùng ảnh Android dựng sẵn của người lạ (rủi ro chuỗi cung ứng).
- Dịch vụ `android-test` trong `infra/docker-compose.test.yml` dùng ảnh này: chạy JUnit (`./gradlew testDebugUnitTest`) và build bản thử (`./gradlew assembleDebug`). Bộ đệm Gradle và SDK trong volume riêng để lần sau nhanh.
- Bản thử ký bằng khóa debug, `applicationIdSuffix ".debug"`, tên app *Trợ lý (thử)*: cài song song với bản chính trên cùng điện thoại, không đè, không đụng dữ liệu bản chính. Khóa ký phát hành **không** đưa vào máy cá nhân cho việc này.
- Cài lên máy: chép tệp APK ra điện thoại rồi cài, hoặc dùng `adb` trên Windows (gói `platform-tools` nhỏ, chỉ cần khi gỡ lỗi qua cáp). Container trên Windows không thấy cổng USB nếu không cài thêm công cụ chuyển USB vào WSL, nên `adb` để ở ngoài container.

**Ưu nhược**

| | GitHub Actions (chính) | Docker có Android SDK trên máy (thêm) |
|---|---|---|
| Cài đặt | Không cần gì trên máy | Ảnh khoảng 4 tới 8 GB trên ổ máy cá nhân; lần dựng đầu 20 tới 40 phút |
| Tốc độ một vòng sửa Kotlin | Đẩy mã, chờ 8 tới 12 phút | Lần đầu chậm, lần sau 1 tới 3 phút nhờ bộ đệm Gradle |
| Tốn phút CI | Có (kho riêng tư có hạn mức) | Không |
| Ký phát hành | Có, khóa trong GitHub Secrets | Không; chỉ khóa debug |
| Giống nhau giữa các lần build | Runner do GitHub cập nhật | Ghim phiên bản trong Dockerfile, chủ động hơn |
| Máy ảo Android để kiểm | Có (runner Linux có KVM) | Không chạy được máy ảo trong container trên Windows; muốn máy ảo phải cài Android Studio ngoài Docker |
| Gỡ lỗi trực tiếp trên điện thoại | Không | Cần `adb` ngoài container; muốn gỡ lỗi từng dòng Kotlin vẫn cần Android Studio |
| Bảo trì | Workflow có sẵn mẫu | Tự giữ Dockerfile, cập nhật SDK khi Capacitor đòi bản mới |

**Đề xuất:** chưa dựng ở V1.0, V1.1 (chưa có Kotlin đáng kể). Dựng ảnh này khi bắt đầu V1.2 (plugin nghe thông báo), vì lúc đó vòng sửa và thử Kotlin dày. Bản phát hành vẫn chỉ từ GitHub Actions.

### 3.15 Tạm tắt Gamebar (QĐ-24)

Mục đích: nhường RAM và CPU của VPS cho troly; mở lại sau. **Chỉ dừng container `core-game`. Giữ nguyên `cloudflared`**, vì tunnel nằm trong compose của Gamebar và gymcanhan dùng chung tunnel đó: dừng `cloudflared` là gym và troly cùng mất kết nối.

**Thời điểm:** ngay trước lần deploy V1.0 đầu tiên (bước 0 ở mục 3.9), **khi người dùng đã xác nhận** trong chat. Agent không SSH, không chạy lệnh nào lên VPS; người dùng (hoặc điều phối khi được người dùng giao rõ) chạy các lệnh dưới đây.

**Trước khi dừng**

| Bước | Lệnh hoặc việc | Để làm gì |
|---|---|---|
| 1 | Mở sảnh Gamebar trên tên miền của game, kiểm không có phòng *Đang chơi* | Không cắt ngang người đang chơi (luật của Gamebar) |
| 2 | Tùy chọn: sao lưu Gamebar ngay bằng công cụ của Gamebar (`tools/khoi-phuc-r2.js`, chạy theo hướng dẫn trong kho Gamebar) | Có bản mới nhất trước khi tắt; sao lưu đêm của Gamebar nằm trong `core-game` nên sẽ ngừng khi tắt |
| 3 | `docker stats --no-stream` | Ghi lại RAM trước khi tắt, để so |

**Dừng**

```
docker stop core-game
```

Chỉ lệnh này. **Không** chạy `docker compose down` hay `docker compose stop` trong `/opt/gamebar` (sẽ dừng hoặc xóa cả `cloudflared`), không xóa container, không xóa volume `gamebar-db`. Container có `restart: unless-stopped` nên đã dừng tay thì khởi động lại máy cũng không tự chạy lại.

**Kiểm sau khi dừng**

| Kiểm | Đạt khi |
|---|---|
| `docker ps --format "{{.Names}} {{.Status}}"` | Có `cloudflared` và `gymcanhan` đang chạy; `core-game` không còn trong danh sách đang chạy |
| `curl -s http://127.0.0.1:8100/api/health` | Gym trả lời bình thường |
| Mở tên miền gym trên điện thoại | Vào được (tunnel vẫn sống) |
| `docker stats --no-stream`, `free -m` | RAM trống tăng tương ứng (bảng mục 3.5) |

Trong lúc tắt, tên miền của game trả lỗi 502 của Cloudflare. Chấp nhận được; nếu muốn có trang báo *tạm nghỉ* thì để sau.

**Mở lại**

1. Kiểm RAM còn đủ: `docker stats --no-stream`; tổng đang dùng cộng 600 MB cho game phải dưới khoảng 3,2 GB.
2. `docker start core-game`.
3. Kiểm `curl -s http://127.0.0.1:8080` trả lời, mở tên miền game.
4. Sao lưu đêm của Gamebar tự chạy lại (chạy bù khi khởi động).

Lưu ý: chạy script deploy của Gamebar (`tools/len-vps.sh`, tức `docker compose up -d` trong `/opt/gamebar`) cũng làm `core-game` chạy lại. Nếu Gamebar cần đẩy bản mới trong thời gian tạm tắt thì dừng lại `core-game` ngay sau đó.

### 3.16 Trang tĩnh trên tên miền api

Hai trang HTML ngắn, api phục vụ trực tiếp (không qua R2), không cần đăng nhập, không có JavaScript:

| Đường dẫn | Nội dung | Ai cần |
|---|---|---|
| `/chinh-sach-rieng-tu` | Dữ liệu app thu, gửi tới đâu (Anthropic, Google, Cloudflare), giữ bao lâu, cách xóa; tóm tắt `60-bao-mat-rieng-tu.md` mục 3.9, 3.10 | Màn đồng ý OAuth của Google (`40-tich-hop-google.md`); thành viên mới |
| `/tai-app` | Tên bản APK mới nhất, `sha256`, dấu vân tay chứng chỉ ký, nút tải (chuyển hướng sang URL ký sẵn 15 phút), các bước cài (*Cài ứng dụng không rõ nguồn gốc*, *Cho phép cài đặt bị hạn chế*, tắt chế độ ngủ của One UI theo QĐ-19) | Cài lần đầu trên máy mới (`30-app-android.md`) |

APK không chứa bí mật nên trang tải để công khai; muốn kín hơn thì đặt Cloudflare Access cho riêng `/tai-app` (câu hỏi mở).

## 4. Dữ liệu cần

Bảng theo `11-co-so-du-lieu.md` (QĐ-25). Đề nghị agent kiến trúc gom:

| Bảng | Cột hoặc việc | Dùng cho |
|---|---|---|
| `tab_job_run` | thêm cột `detail` (jsonb): với `backup_database` ghi khóa R2, kích thước, `sha256` của tệp mã hóa, số dòng các bảng chính | Đối chiếu khi diễn tập khôi phục, trạng thái sao lưu cho chủ |
| `tab_job_schedule` | `backup_database` đổi lịch thành chủ nhật 02:00 (QĐ-16); thêm job `disk_check` (mỗi 15 phút) | Mục 3.5, 3.10 |
| `tab_app_release` (`kind` là `apk` hoặc `web`) | thêm `published_by` (`ci`, `manual`); thu hồi bản lỗi bằng `is_published = false`; sửa câu *dòng được thêm bằng `scripts/`* thành ghi qua `POST /api/v1/admin/releases` | Mục 3.8 |
| `tab_dev_job` | thêm `commit_sha`, `approved_by`, `approved_at`, `deployed_at`, `deploy_result` | V3 |

## 5. API hoặc giao tiếp

Gốc API theo `12-api.md`: `https://<api-domain>/api/v1`, riêng `/api/health` không phiên bản.

| Đường dẫn | Ai gọi | Xác thực | Ghi chú |
|---|---|---|---|
| `GET /api/health` | Docker healthcheck, script deploy, app | Không | Đã có ở `12-api.md`; không lộ gì ngoài tình trạng và phiên bản |
| `GET /api/v1/admin/worker` | App của chủ | JWT, owner | Đã có; xin thêm trường ở mục 3.12 |
| `POST /api/v1/admin/worker/jobs/backup_database/run` | Nút *Sao lưu ngay* | JWT, owner | Đã có (chạy job bất kỳ); dùng cho sao lưu tay |
| `GET /chinh-sach-rieng-tu`, `GET /tai-app` | Trình duyệt, Google | Không | **Mới**, trang HTML tĩnh ngoài `/api` (mục 3.16) |
| `POST /api/v1/admin/releases` | Job `ui`, `apk` | Mã CI | **Mới.** Thân: `kind`, `version_code`, `version_name`, `r2_key`, `sha256`, `size_bytes`, `signature`, `min_supported_version_code`, `notes`. Máy chủ kiểm tệp có trên R2 và `sha256` khớp rồi mới ghi |
| `GET /api/v1/device/release`, `GET /api/v1/device/web-bundle` | App, plugin | JWT hoặc mã thiết bị | Đã có; URL ký sẵn trỏ bucket `troly-release`, hạn 15 phút |
| `GET /api/v1/dev/jobs/next`, `POST /api/v1/dev/jobs/{id}/result` | Container `troly-dev` (V3) | Mã máy chạy | Tắt khi `DEV_JOBS_ENABLED=false` |
| `GET /api/v1/dev/jobs/approved` | `troly-deployer` (V3) | Mã máy chạy riêng | |

Giao tiếp ngoài: Claude API, Google APIs, R2 (S3 API) đi từ api và worker qua mạng `troly_edge`.

## 6. Kiểm thử

- CI kiểm `docker compose config` hợp lệ và ảnh backend dựng được (mục 3.8).
- Script deploy có cờ `--dry-run`: in các lệnh sẽ chạy, không chạy.
- Bài kiểm việc sao lưu dùng R2 giả (S3 giả trong bộ nhớ) và khóa `age` tạo riêng cho bài kiểm: sao lưu, liệt kê, xóa bản quá hạn đúng số bản giữ, khôi phục ra DB tạm.
- Bài kiểm luật giữ 5 bản: một tuần có 6 lần migration vẫn còn ít nhất 1 bản `weekly`.
- Diễn tập khôi phục (lần đầu sau bản sao lưu đầu tiên, sau đó hằng tháng, mục 3.10) là bài kiểm thật của cả chuỗi.
- Tạm tắt Gamebar: chạy bảng *Kiểm sau khi dừng* ở mục 3.15; gym vẫn chạy, tunnel vẫn sống.
- Lần deploy đầu: đo `docker stats` trước và sau khi bật troly, ghi số vào nhật ký việc; gym không đổi thời gian phản hồi.
- Chi tiết ở [70-kiem-thu.md](../70-kiem-thu/70-kiem-thu.md).

## 7. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Hết RAM 4 GB khi build ảnh trên VPS | Trung bình (thấp hơn khi Gamebar tạm dừng) | Trần bộ nhớ từng container; build với `nice`; Gamebar tạm dừng theo QĐ-24; khi Gamebar mở lại thì deploy ngoài giờ cao điểm của game (script hỏi xác nhận nếu đang 19:00 tới 23:00 và `core-game` đang chạy) |
| Ổ 22 GB đầy vì ảnh Docker và bộ đệm build | Cao | Giữ 3 thẻ ảnh; dọn bộ đệm 3 ngày; `disk_check` cảnh báo ở 15 phần trăm; DB troly nhỏ (ước dưới 1 GB năm đầu); chỉ 5 bản sao lưu và nằm trên R2 |
| Dừng nhầm `cloudflared` khi tắt Gamebar (dùng `docker compose down` hay `stop` trong `/opt/gamebar`) | Cao | Mục 3.15 chỉ cho phép `docker stop core-game`; bảng kiểm sau khi dừng có kiểm gym |
| Gamebar tự chạy lại khi ai đó deploy Gamebar | Thấp | Ghi chú ở mục 3.15; báo agent Gamebar (mục 9) |
| `cloudflared` của Gamebar khởi động lại khi sửa Gamebar | Trung bình | App có hàng đợi gửi lại; báo agent Gamebar rằng troly dùng chung tunnel; phương án tách tunnel |
| Mất tới 7 ngày dữ liệu khi hỏng DB (sao lưu tuần, QĐ-16) | Trung bình | Sao lưu tay trước việc lớn; sao lưu trước mỗi migration; volume Postgres nằm trên ổ VPS, hỏng VPS mới phải dùng bản sao lưu |
| Lệnh dọn Docker toàn máy xóa nhầm volume của app khác | Cao | Cấm `docker system prune -a`, `docker volume prune` trong mọi script; chỉ dọn theo nhãn và theo tuổi |
| Lộ VPS kéo theo lộ `.env` troly | Cao | Xem `60-bao-mat-rieng-tu.md`; khóa giải mã sao lưu không trên VPS; xoay khóa theo danh sách |
| Migration làm hỏng dữ liệu | Trung bình | Sao lưu `premigrate` bắt buộc; luật tương thích ngược; khôi phục bằng script |
| Mất khóa ký APK | Cao | Hai bản cất ngoại tuyến (xem `60-bao-mat-rieng-tu.md`) |
| Hết phút miễn phí GitHub Actions | Thấp | Job máy ảo không chạy mỗi lần đẩy; bộ đệm Gradle và npm |
| Claude CLI V3 tranh tài nguyên | Trung bình | Trần 1 vCPU, 1 GB; chỉ chạy ban đêm; một việc một lúc |

## 8. Câu hỏi mở

Đã chốt, bỏ khỏi danh sách: ba bucket R2 (QĐ-25 nhận đề xuất của 50); S3 giả ở máy cá nhân (mục B của rà chéo); sao lưu (QĐ-16); trần AI (QĐ-15); tạm tắt Gamebar (QĐ-24).

1. Tên miền con cho api là gì (`<api-domain>`)?
2. Cần kiểm trên VPS (người dùng chạy, agent không SSH): cổng 8200 còn trống (`ss -ltn`); RAM thực của `core-game`, `gymcanhan`, `cloudflared` (`docker stats --no-stream`); dung lượng ổ còn trống (`df -h /`).
3. Trước khi tạm dừng `core-game`: có chạy sao lưu Gamebar ngay không (mục 3.15 bước 2)? Mở lại Gamebar theo điều kiện nào (ngày cụ thể, hay khi RAM đo thật còn đủ)?
4. Có muốn kiểm sức khỏe từ ngoài không? Phương án không cần bên thứ ba: workflow GitHub Actions chạy theo lịch mỗi 2 giờ gọi `/api/health`, hỏng thì GitHub gửi thư (khoảng 360 phút CI mỗi tháng).
5. V3: chạy Claude CLI trên VPS (mục 3.11) hay trên máy cá nhân?
6. Có bật khóa giữ (bucket lock) cho `troly-backup` để server bị chiếm cũng không xóa được bản sao lưu không? Lưu ý: khóa giữ làm bản cũ không xóa được trước hạn, nên số bản có thể vượt 5 trong thời gian khóa.
7. Dựng ảnh Docker có Android SDK trên máy cá nhân từ V1.2 (mục 3.14) không? Ổ máy cá nhân còn đủ 10 GB không?
8. Trang `/tai-app` để công khai hay đặt Cloudflare Access?
9. Gym chưa có sao lưu; có muốn dùng chung cách sao lưu của troly cho gym về sau không (ngoài phạm vi troly)?

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| agent kiến trúc | `10-kien-truc-backend.md`: ảnh `postgres:16-alpine` thay `postgres:16` (mục 3.4); `backend/Dockerfile` ba đích `base`, `dev`, `prod`; api chạy được với `--reload` và `WATCHFILES_FORCE_POLLING`, worker chạy được dưới `watchfiles` (mục 3.13); bảng biến: bỏ `AI_USER_DAILY_USD`, `AI_DAILY_USD` (QĐ-15), thay `R2_BUCKET` bằng ba biến bucket, thêm các biến ở cuối mục 3.7 (gồm `GOOGLE_OAUTH_REDIRECT_URI` là tên chốt cho redirect OAuth, `R2_PRESIGN_UPLOAD_SECONDS`, `R2_PRESIGN_DOWNLOAD_SECONDS`, `THIRD_PARTY_RETENTION_DAYS`, `BACKUP_*`), `CORS_ORIGINS` mặc định có `http://localhost:5190`; job `backup_database` chạy chủ nhật 02:00, giữ 5 bản gồm bản trước migration, mã hóa `age` (QĐ-16); job `disk_check`; api chạy một tiến trình, đọc IP từ `CF-Connecting-IP`; luật migration tương thích ngược (mục 3.9); phục vụ hai trang tĩnh mục 3.16. `11-co-so-du-lieu.md`: các mục ở mục 4. `12-api.md`: thêm `POST /api/v1/admin/releases` (xác thực mã CI), trường thêm cho `/admin/worker`, hai trang tĩnh |
| agent app Android | Node 24 (`node:24-alpine`) thay Node 22 ở `30-app-android.md`; trường `troly.minNativeVersionCode` trong `app/package.json`; tên biến `ANDROID_SIGNING_CERT_SHA256`; bản thử `applicationIdSuffix ".debug"`; chốt `compileSdk`, `build-tools` cho `infra/android-build.Dockerfile`; Vite cổng 5190, `server.watch.usePolling` khi chạy trong container; nút *Sao lưu ngay* và trạng thái sao lưu, ổ đĩa, cảnh báo chi phí tháng cho chủ ở Cài đặt; nội dung trang `/tai-app` (bước cài trên Galaxy S25+) |
| agent AI | Tên biến `AI_*` theo mục 3.7 (QĐ-15: không trần ngày, `AI_MONTHLY_USD` chỉ cảnh báo); bộ câu mẫu chạy bằng `pytest -m ai_eval` |
| agent Google | Tên biến `GOOGLE_OAUTH_REDIRECT_URI`, đường callback `/api/v1/google/oauth/callback` (12); bỏ `GOOGLE_TOKEN_KEY` (token mã hóa theo `60-bao-mat-rieng-tu.md` mục 3.5); bỏ yêu cầu `assetlinks.json` (quay về bằng `troly://`); đường webhook theo 12 (`/api/v1/webhooks/google/*`), đã có luật bỏ qua kiểm trình duyệt ở mục 3.6; đặt quota Maps theo mục 3.7 khi dựng dự án Google Cloud |
| điều phối | Cập nhật `02-cau-truc-ma-nguon.md`: `docker-compose.dev.yml`, `infra/docker-compose.test.yml`, `infra/android-build.Dockerfile`, `backend/Dockerfile` (ba đích), `.github/workflows/ai-eval.yml`, `scripts/deploy.sh`, `scripts/restore-db.sh`. Báo agent Gamebar: troly dùng chung tunnel `cloudflared`; `core-game` sẽ tạm dừng theo QĐ-24, deploy Gamebar sẽ làm nó chạy lại. Lấy xác nhận của người dùng trước bước tạm dừng (mục 3.15) |

## 10. Đề xuất quyết định

| Đề xuất | Lý do |
|---|---|
| api nghe `127.0.0.1:8200`; DB không mở cổng; mạng `troly_core` là mạng internal | Cô lập với Gamebar và gym; giống cách hai app đó đang chạy |
| Dùng chung tunnel `cloudflared` của Gamebar, chỉ thêm Public Hostname; tắt kiểm trình duyệt cho đường webhook Google | Không phải sửa Gamebar; tách tunnel riêng (thêm container `troly-cloudflared` với tunnel mới) chỉ làm khi việc Gamebar khởi động lại tunnel gây phiền thật |
| Trần tài nguyên troly: db 512 MB, api 448 MB, worker 384 MB; CPU 0,75 / 0,75 / 0,5 | VPS 4 GB dùng chung; troly không được làm chậm game |
| Bản giao diện React và APK đều nằm trên R2 (`troly-release`), api chỉ trả bản kê | Đổi giao diện không phải deploy backend; VPS không phục vụ tệp tĩnh lớn; khớp với cách APK đã nằm trên R2 |
| GitHub Actions không SSH vào VPS; deploy chạy từ máy cá nhân bằng `scripts/deploy.sh` (V3 thì deployer trên VPS) | Khóa SSH không rời máy người dùng; giống gym và Gamebar |
| CI ghi `tab_app_release` qua API bằng mã CI riêng, không vào DB | CI không cần đường vào DB |
| Ba bucket R2 riêng (tệp, sao lưu, bản phát hành), mã R2 của CI chỉ có quyền trên bucket phát hành | R2 phân quyền theo bucket, không theo tiền tố |
| Sao lưu mã hóa bằng `age` với khóa công khai trên VPS, khóa bí mật chỉ ở người dùng; diễn tập khôi phục trên máy cá nhân, lần đầu ngay sau bản sao lưu đầu tiên rồi hằng tháng | Lộ VPS không lộ bản sao lưu; diễn tập không tốn RAM VPS |
| Áp QĐ-16: chủ nhật 02:00, giữ 5 bản gồm bản trước migration, luôn còn ít nhất 1 bản tuần; thêm nút sao lưu tay | Một người dùng; nút tay bù cho RPO 7 ngày |
| Áp QĐ-24: chỉ `docker stop core-game`, giữ `cloudflared`; giữ nguyên trần tài nguyên troly khi Gamebar tắt | Gym dùng chung tunnel; mở lại Gamebar không phải đổi cấu hình troly |
| Ảnh nền chốt: `postgres:16-alpine`, `python:3.12-slim`, `node:24-alpine` cho mọi nơi | Nhỏ, hợp ổ 22 GB; giống nhau giữa máy cá nhân, CI và VPS |
| Hạn URL ký sẵn theo 12: tải lên 10 phút, tải về 15 phút | Một bộ số cho cả bộ tài liệu |
| Hai trang tĩnh `/chinh-sach-rieng-tu`, `/tai-app` do api phục vụ | Google cần trang chính sách; cài app lần đầu cần chỗ tải |
| Migration bắt buộc tương thích ngược với bản trước | Quay lui chỉ cần đổi ảnh |
| Claude CLI V3 chạy trong container riêng không có quyền Docker, nói chuyện với api qua HTTP; deploy do một tiến trình root riêng làm sau khi duyệt | Đúng ràng buộc mục 9 thiết kế tổng thể: không vào DB, không đọc `.env` app |
| Ba tệp compose: `docker-compose.yml` (VPS), `docker-compose.dev.yml` (ghép đè ở máy cá nhân), `infra/docker-compose.test.yml` (kiểm thử, đứng riêng); một Dockerfile backend ba đích `base`, `dev`, `prod` | QĐ-14; tệp gốc giống hệt VPS nên lỗi cấu hình lộ ra ở máy trước |
| Ở máy cá nhân api tự nạp lại bằng `uvicorn --reload`, worker bằng `watchfiles`, bật dò định kỳ vì mã nằm trên ổ Windows | Sự kiện đổi tệp từ ổ Windows không chắc tới container |
| GitHub Actions chạy bài kiểm backend bằng đúng lệnh `docker compose -f infra/docker-compose.test.yml run --rm test ...` như ở máy | Đỏ ở CI thì tái hiện được y hệt ở máy |
| Bản APK phát hành chỉ build trên GitHub Actions; ảnh Docker có Android SDK trên máy chỉ build bản thử ký debug, `applicationIdSuffix .debug`, dựng từ V1.2 | Khóa ký phát hành không rời GitHub Secrets; vòng sửa Kotlin nhanh hơn mà không tốn phút CI |
