# Lịch trình và bản đồ

Ngày lập: 18/11/2026. Người giữ: agent Google. Bản 2: thống nhất với bộ tài liệu theo `80-ra-cheo-lan-1.md` và QĐ-15 tới QĐ-25. Bản lộ trình: V1.6.

Tài liệu này mô tả module `trip` từ đầu tới cuối: nhập lịch trình, bóc tách, tìm tọa độ, lưu đệm địa điểm, đánh giá rủi ro, tối ưu và đưa phương án, lưu, mở Google Maps, xuất Word. OAuth và khóa Maps chung nằm ở [40-tich-hop-google.md](40-tich-hop-google.md). Thiết kế gốc ở `01-thiet-ke-tong-the.md` mục 8.7.

**Vai trò tệp này (`80-ra-cheo-lan-1.md` mục A1 dòng 16):** đây là **gốc cho module trip**. Bảng lịch trình ở `11-co-so-du-lieu.md` theo mục 12 tệp này, và lược đồ bóc tách ở mục 4.2 là lược đồ duy nhất. Những thứ sau theo nguồn chuẩn của QĐ-25:

| Nội dung | Tài liệu chuẩn |
|---|---|
| Đường dẫn API | `12-api.md` |
| Tên công cụ AI, kiểu hành động | `20-bo-nao-ai.md` |
| Tên hàm plugin Maps | `30-app-android.md` |
| Job, biến môi trường | `10-kien-truc-backend.md` |

Mọi thông số Google đã đối chiếu với tài liệu chính thức ngày 18/11/2026, nguồn ở mục 20 ([M1], [M2]...). Điểm tài liệu không nói rõ được ghi là **chưa xác minh**.

## 1. Mục tiêu

1. Đưa vào tệp Word, PDF, ảnh chụp hoặc vài câu mô tả, ra lịch trình có cấu trúc: ngày, giờ, điểm, loại điểm, phương án dự phòng.
2. Chỉ ra rủi ro trước chuyến đi: trễ giờ, nơi đóng cửa, lỡ phà, chạy xe máy quá lâu, chạy đêm.
3. Đưa 2 tới 3 phương án có số liệu (km, giờ chạy, rủi ro còn lại) để chọn.
4. Bấm một điểm là Google Maps mở dẫn đường xe máy, tránh cao tốc. Bấm một ngày là ra tuyến cả ngày, tự chia đoạn khi quá nhiều điểm.
5. Xuất lại Word đúng kiểu tệp mẫu, link bấm được.
6. Chi phí Maps Platform bằng 0 nhờ nằm trong mức miễn phí hằng tháng, có quota chặn cứng.

**Xong khi (V1.6):**

- tệp *Lich-trinh-Phuoc-Hai-Tra-Vinh.docx* vào thì ra đủ 3 ngày, đủ điểm;
- chỉ ra rủi ro *Bảo tàng Văn hóa Khmer thứ Hai* và *giờ phà Vũng Tàu – Cần Giờ*;
- bấm một điểm thì Google Maps mở chế độ xe máy.

## 2. Phạm vi

| Trong V1.6 | Ngoài V1.6 |
|---|---|
| Nhập Word (.docx), PDF, ảnh, link Google Maps, câu mô tả | Trang web du lịch bất kỳ, tệp .doc cũ |
| Bóc tách bằng Claude Haiku 5.5 (`purpose = trip_extract`), đầu ra có cấu trúc | Đặt phòng, mua vé |
| Tọa độ, giờ mở cửa bằng Places API (New); thời gian chạy bằng Routes API | Bản đồ vẽ trong app (Maps SDK) |
| Đánh giá rủi ro bằng luật cố định; AI chỉ viết tóm tắt | Thời tiết, thủy triều (xem *Câu hỏi mở*) |
| 2 tới 3 phương án, sắp lại thứ tự điểm không cố định giờ | Đổi điểm giữa các ngày |
| Mở Google Maps bằng URL và lệnh Android | Dẫn đường ngay trong app |
| Xuất Word, lưu R2, tùy chọn lưu lên Drive | Xuất PDF |
| Hỏi trong chat: *chỉ đường tới chỗ ăn trưa*, *lấy lịch trình Trà Vinh* | Theo dõi vị trí thời gian thực |

Hiện chỉ có một người dùng (QĐ-15); mọi hàm vẫn nhận và lọc theo `user_id`.

## 3. Thiết kế: luồng tổng

```
 Nhập (tệp / ảnh / mô tả)        POST /api/v1/trips/import  ──> 202 {trip_id, job_id}, status=importing
   │ 1. lấy chữ + link            (việc trip_import trong tab_job_queue)
   ▼
 Bóc tách (Claude, lược đồ 4.2) ──> tab_trip status=draft + tab_trip_stop
   │ 2. chuẩn hóa giờ, ngày, loại điểm
   ▼
 Tìm địa điểm (link trong tệp > lưu đệm > Places API) ──> điểm resolve_status=uncertain: hỏi lại
   │ 3.
   ▼
 Đánh giá                         POST /api/v1/trips/{id}/evaluate ──> 202, status=evaluating
   │ 4. Routes xe hai bánh + giờ mở cửa + luật R1..R9   (việc trip_evaluate)
   ▼
 Tối ưu, dựng 2–3 phương án (tab_trip_option)
   │ 5. người dùng chọn: POST /api/v1/trips/{id}/options/{option_id}/choose
   ▼
 Lưu (status=planned) ──> link bản đồ (GET /map-links) ──> xuất Word
```

- Bước 1–3 chạy trong việc nền `trip_import`; bước 4–5 trong `trip_evaluate`. Cả hai do job `run_queued_jobs` chạy (`10-kien-truc-backend.md`), theo ĐX-API-04: trả 202, app hỏi `GET /api/v1/jobs/{id}`.
- Mỗi bước là một hàm riêng trong `modules/trip/service.py`, chạy lại độc lập được. Ví dụ: sửa một điểm thì chỉ chạy lại bước 3 tới 5 của ngày đó.
- Tốn tiền ở hai chỗ: bước 1–2 tốn tiền AI, bước 3–4 tốn lời gọi Maps. Kết quả từng bước được lưu để không gọi lại.

## 4. Thiết kế: nhập và bóc tách

### 4.1 Lấy chữ

| Đầu vào | Cách lấy |
|---|---|
| Word (.docx) | `python-docx`: đọc đoạn văn kèm kiểu (Title, Heading 1, Heading 2), đọc bảng theo hàng và ô. **Đọc cả link**: python-docx không có API đọc link, nên đọc thẻ `w:hyperlink` và tra địa chỉ trong `word/_rels/document.xml.rels`. Mỗi đoạn link thành `[chữ](url)` trước khi đưa cho Claude |
| PDF | Gửi thẳng cho Claude dạng khối tài liệu; PDF có lớp chữ thì trích thêm link bằng `pypdf` (chú thích kiểu Link) |
| Ảnh chụp | Gửi thẳng cho Claude dạng khối ảnh; không có link nên mọi điểm tìm bằng Places API |
| Link Google Maps dán vào chat | Phân tích theo mục 4.3 |
| Câu mô tả | Claude dựng bản nháp trong lượt chat (mục 4.4) |

Tệp người dùng gửi lưu ở R2 (`tab_file`, `purpose = trip_source`). Tệp trên Google Drive chọn qua hộp chọn tệp Android (`40-tich-hop-google.md` mục 8.1).

### 4.2 Lược đồ bóc tách (lược đồ duy nhất)

`20-bo-nao-ai.md` gọi `extract_structured(purpose="trip_extract", effort="medium", max_tokens=16000)` với lược đồ này. Model Pydantic đặt ở `modules/trip/schemas.py`, thay cho lược đồ `TripExtract` và `hard_constraints` riêng của bản 1 tệp 20.

```
trip:
  title, travel_mode (motorbike|car|walk), origin_text, end_text,
  start_date (YYYY-MM-DD | null), nights
  days[]:
    day_no, weekday_text ("thứ 7", "chủ nhật"...), date (null nếu tệp không ghi),
    title, route_text (dòng "Đường đi: ...")
    stops[]:
      time_text  (nguyên văn: "2h30", "~7h00", "10h30–12h30")
      title      (một câu ngắn)
      category   (an_uong | nghi | tham_quan | pha | di_chuyen | khach_san | mua_sam | khac)
      places[]:  { label, url (nếu có), role (main | alternative | backup | generic | via) }
      cost_note, phone, note
      optional   (true nếu có "nếu còn đói", "nếu còn lúa", "có thể")
  hotels[]:     { night_no, label, url, booked (bool), backups[] }
  map_links[]:  { day_no, label, url }
  notes[]:      nguyên văn mục Lưu ý
  hard_facts[]: { kind (ferry_last|ferry_first|checkin|checkout|hotline|opening_hours|other), text, time, stop_ref }
```

**Luật bóc tách** (trong lời nhắc tĩnh, có ví dụ):

- **Giờ:** `2h30` là 02:30. `~7h00` là khoảng 07:00, đặt `approx`. `10h30–12h30` là khoảng có giờ bắt đầu và kết thúc. Không có giờ thì để trống; mục 4.5 suy ra.
- **Vai trò điểm:**
  - Hàng có nhiều điểm nối bằng *hoặc*: điểm đầu `main`, các điểm sau `alternative`.
  - Điểm sau chữ *Dự phòng*: `backup`.
  - Tên món kèm tên vùng mà không có tên quán (*bún nước lèo Trà Vinh*, *bánh giá Gò Công*): `generic`.
  - Điểm chỉ để đi qua (*cầu Rạch Miễu* trong link tuyến): `via`.
- **Mốc cứng:** câu có *chuyến cuối*, *nhận phòng*, *trả phòng*, *hotline* thành `hard_facts`. Ví dụ: *chuyến cuối từ Vũng Tàu lúc 17h* thành `ferry_last`, `time = 17:00`.
- **Không bịa:** không thêm điểm hay giờ mà tệp không có. Chỗ không đọc được thì ghi `note` và để trống.

**Máy chủ kiểm lại đầu ra:**

- giờ tăng dần trong ngày, trừ hàng `approx`;
- mỗi link phải có trong văn bản gốc, để chặn link bịa;
- số ngày khớp số Heading 1 dạng *Ngày N*.

Sai thì gọi lại một lần kèm lỗi. Vẫn sai thì lưu nháp, đánh dấu chỗ cần người dùng sửa.

### 4.3 Đọc link Google Maps trong tệp

Link trong tệp là nguồn chính xác nhất, nên được dùng trước Places API.

| Dạng link | Lấy ra |
|---|---|
| `https://www.google.com/maps/search/?api=1&query=<q>&query_place_id=<id>` | `place_query = q`, `place_id` nếu có [M1] |
| `https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a\|b\|c` | Thứ tự điểm của tuyến; giá trị dạng `lat,lng` là tọa độ do người dùng đưa [M1] |
| `https://maps.app.goo.gl/...` (link rút gọn) | Xem dưới bảng |
| `geo:lat,lng?q=...` | Tọa độ [M2] |

**Link rút gọn `maps.app.goo.gl`:**

1. Gọi Resolution API: `POST https://mapstools.googleapis.com/v1:resolveMapsUrls`. API nhận link rút gọn trỏ tới một địa điểm và trả `place_id`, tối đa 20 link mỗi lần. Lời gọi tính vào SKU *Text Search Essentials (IDs Only)*, giá 0 [M3]. Trang không ghi giai đoạn phát hành hiện tại (trước đây là thử nghiệm).
2. Không dùng được thì theo chuyển hướng HTTP tới URL đầy đủ, rồi đọc tọa độ hoặc tên. Cách này **không có tài liệu chính thức**.
3. Hai cách đều hỏng thì hỏi người dùng (mục 5.3).

**Ghép tọa độ với điểm.** Ví dụ trong tệp mẫu: link *Khách sạn → Bánh khọt → ...* có `origin=10.4477939,107.2876573`, và chữ của link bắt đầu bằng *Khách sạn*. Suy ra tọa độ này là của khách sạn ngày đó. Luật: điểm đầu hoặc cuối của link tuyến mà chữ mô tả gọi tên một điểm đã biết thì gán tọa độ cho điểm đó. Tọa độ người dùng đưa là dữ liệu của người dùng, lưu lâu dài được (`coord_source = user`, mục 5.4).

### 4.4 Từ câu mô tả

Ví dụ: *đi Trà Vinh 2 ngày bằng xe máy, muốn ăn bún nước lèo, xem chùa*. Chạy trong lượt chat (`20-bo-nao-ai.md`):

1. Claude hỏi lại tối đa 2 câu nếu thiếu ngày đi, nơi xuất phát.
2. Claude dùng công cụ `find_place` (mục 5.2) để chọn điểm có thật, rồi gọi `import_trip` với `draft` theo lược đồ 4.2.
3. Từ đây đi tiếp như tệp.

Mọi điểm `main` phải có `place_id` lấy từ `find_place`. Claude không được tự nghĩ ra tên quán.

### 4.5 Chuẩn hóa

- **Ngày:**
  - Tệp mẫu chỉ ghi *thứ 7*, *chủ nhật*, *thứ 2*. Không có `start_date` thì hỏi người dùng, gợi ý thứ Bảy gần nhất khớp thứ của ngày 1 (xem *Câu hỏi mở*).
  - Ngày của từng ngày = `start_date + (day_no − 1)`.
  - Thứ trong tệp không khớp ngày thì báo (luật R9).
- **Giờ:** lưu `planned_time` (giờ bắt đầu) và `duration_minutes` (thời gian ở lại). Khoảng `10h30–12h30` thành 10:30 và 120 phút. Giờ trống thì suy ra bằng giờ điểm trước, cộng thời gian chạy (mục 6), cộng thời gian ở lại mặc định:

  | Loại | Phút |
  |---|---|
  | `an_uong` | 45 |
  | `tham_quan` | 60 |
  | `mua_sam` | 20 |
  | `nghi` | 15 |
  | `via` | 0 |

- **Điểm cố định giờ** (`is_fixed_time = true`):
  - điểm có giờ ghi rõ, không có `~`, thuộc loại `pha`, `khach_san`, hoặc là bình minh, hoàng hôn;
  - điểm gắn với `hard_facts`.

  Điểm còn lại được phép đổi thứ tự (mục 7).

## 5. Thiết kế: tìm tọa độ và lưu đệm địa điểm

### 5.1 Thứ tự tìm

Mỗi điểm có `role` là `main`, `alternative`, `backup` hoặc `via` được tìm theo thứ tự dưới đây. Dừng ở bước đầu tiên có kết quả:

1. Tọa độ hoặc `place_id` có sẵn trong link (mục 4.3).
2. `tab_place_cache`, khóa là chuỗi tìm đã chuẩn hóa cộng vùng.
3. Places API (New), theo mục 5.2.
4. Geocoding API: chỉ cho chuỗi là địa chỉ thuần (có số nhà và tên đường, ví dụ *144 Võ Thị Sáu Phước Hải*) khi bước 3 không ra [M4].

Điểm `generic` không tìm một nơi cụ thể. Text Search lấy 3 gợi ý gần tuyến của ngày đó, lưu vào `alternatives` để người dùng chọn. Link của điểm vẫn là link tìm kiếm `query=...`, như tệp mẫu.

Kết quả ghi `resolve_status`:

| Giá trị | Nghĩa |
|---|---|
| `ok` | Đã có tọa độ chắc chắn |
| `uncertain` | Cần người dùng chọn |
| `not_found` | Không tìm ra |
| `manual` | Người dùng tự chọn |

### 5.2 Gọi Places API (New) cho rẻ

Giá tính theo **trường được xin** trong `X-Goog-FieldMask` [M5][M6]:

| Lời gọi | Trường xin | SKU | Miễn phí mỗi tháng | Giá sau mức miễn phí (USD / 1.000) |
|---|---|---|---|---|
| Text Search | `places.id` | Text Search Essentials (IDs Only) | Không giới hạn | 0 |
| Place Details | `location`, `formattedAddress`, `shortFormattedAddress`, `types` | Place Details Essentials | 10.000 | 5 |
| Place Details | thêm `displayName`, `businessStatus`, `googleMapsUri`, `utcOffsetMinutes` | Place Details Pro | 5.000 | 17 |
| Place Details | thêm `regularOpeningHours`, `currentOpeningHours`, `nationalPhoneNumber`, `rating` | Place Details Enterprise | 1.000 | 20 |

Nguồn giá: [M7][M8]. Chỉ cần xin `displayName` hay `location` trong Text Search là cả lời gọi thành SKU Pro: 5.000 miễn phí, sau đó 32 USD / 1.000 [M6][M7].

**Quy trình định vị điểm của lịch trình:**

1. **Text Search, chỉ xin `places.id`:**
   - `POST https://places.googleapis.com/v1/places:searchText` [M9];
   - `textQuery` = chuỗi tìm, `languageCode = vi`, `regionCode = VN`, `pageSize = 3`;
   - `locationBias` là hình tròn 30 km quanh điểm đã định vị gần nhất trong ngày, hoặc quanh tâm tỉnh mà Claude bóc ra.

   Giá 0.
2. **Place Details Essentials** cho kết quả đầu: `GET https://places.googleapis.com/v1/places/{id}`, xin `id, location, formattedAddress, types` [M10].
3. **Kiểm độ chắc chắn:**
   - từ chính của chuỗi tìm (bỏ dấu, viết thường) có trong `formattedAddress`, hoặc `types` khớp `category`;
   - khoảng cách tới điểm trước trong ngày dưới 80 km.

   Không đạt thì gọi Place Details Essentials cho cả 3 kết quả, đặt `resolve_status = uncertain`, hỏi người dùng (mục 5.3).
4. **Giờ mở cửa** chỉ xin khi đánh giá (mục 6.2), bằng lời gọi Place Details riêng với `regularOpeningHours, currentOpeningHours, utcOffsetMinutes, businessStatus` (SKU Enterprise, 1.000 miễn phí). Chỉ gọi cho điểm `tham_quan`, `an_uong`, `mua_sam` có giờ đến dự kiến; không gọi cho phà, đường, khách sạn.

Gặp `CLOSED_PERMANENTLY` kèm `movedPlaceId` (quán đã dời) thì báo rủi ro đỏ *đã đóng cửa hẳn* và gợi ý điểm mới [M10].

**Công cụ `find_place`** (`20-bo-nao-ai.md`, thay tên `search_places` của bản 1): dùng khi dựng chuyến từ câu mô tả hoặc khi hỏi một quán. Trả tối đa 3 điểm `{name, address, place_id, lat, lng}`. Cần `name` để người dùng nhận ra quán, nên bước 2 xin thêm `displayName` (SKU Pro, 5.000 miễn phí mỗi tháng). Giờ mở cửa chỉ lấy khi câu hỏi cần (SKU Enterprise).

### 5.3 Hỏi lại khi không chắc

Màn chuyến đi có danh sách *Điểm cần xác nhận*. Mỗi dòng gồm:

- tên trong tệp;
- 1 tới 3 gợi ý (địa chỉ ngắn), mỗi gợi ý có nút *Xem* (hành động `open_map_place`);
- nút *Chọn*, nút *Bỏ qua*.

App lấy gợi ý qua `POST /api/v1/trips/{id}/stops/{stop_id}/resolve` và ghi lựa chọn qua `PATCH /api/v1/trips/{id}/stops/{stop_id}` (`12-api.md`).

Điểm bỏ qua không tham gia tính thời gian chạy; đánh giá ghi rủi ro vàng *chưa định vị* (R8).

### 5.4 Lưu đệm địa điểm và luật lưu dữ liệu Google

Điều khoản Places API cho phép [M11][M4]:

- lưu `place_id` **vô thời hạn**;
- lưu tọa độ lấy từ Google **tối đa 30 ngày liên tục**, sau đó phải xóa;
- nội dung khác (tên, địa chỉ, giờ mở cửa, đánh giá) chỉ trong phạm vi Điều khoản dịch vụ riêng. Trang đó không đọc trực tiếp được khi viết; phải đọc lại trước khi viết mã (`80-ra-cheo-lan-1.md` mục B).

Áp dụng (ĐX-T1, đã chấp nhận ở QĐ-25):

- **`tab_place_cache`**: bảng hệ thống dùng chung, không có `user_id` vì không chứa dữ liệu cá nhân.
  - `query_norm` cộng `bias_key` là khóa;
  - `place_id` giữ mãi;
  - `lat`, `lng`, `address` xóa khi `coord_expires_at` qua (30 ngày); lần dùng sau gọi lại Place Details Essentials;
  - **không** có cột giờ mở cửa.
- **Giờ mở cửa** chỉ giữ trong bộ nhớ lúc đánh giá. Kết quả đánh giá chỉ lưu kết luận do app viết (ví dụ *đóng cửa thứ Hai*) kèm thời điểm kiểm.
- **`tab_trip_stop`** lưu `place_id` lâu dài; tọa độ lưu kèm nguồn:
  - `coord_source = user`: lấy từ link của người dùng, lưu mãi;
  - `coord_source = google`: lưu kèm `coord_fetched_at`, quá 30 ngày thì làm mới khi mở chuyến.
- **`tab_route_cache`** (`11-co-so-du-lieu.md`) giữ quãng đường, thời gian từng chặng tới 30 ngày. Điều khoản lưu kết quả Routes API cũng phải đọc lại trước khi viết mã.

Việc dọn nằm trong job `cleanup_old_data` (`10-kien-truc-backend.md`): xóa tọa độ quá hạn trong `tab_place_cache` và `tab_trip_stop` (nguồn `google`), xóa dòng `tab_route_cache` quá hạn.

## 6. Thiết kế: đánh giá rủi ro

### 6.1 Thời gian chạy

Một lời gọi **Compute Routes** cho mỗi đoạn tuyến của một ngày [M12]:

- `POST https://routes.googleapis.com/directions/v2:computeRoutes`;
- `travelMode = TWO_WHEELER`: Việt Nam có trong danh sách hỗ trợ xe hai bánh [M13];
- `routeModifiers.avoidHighways = true`: áp dụng được cho TWO_WHEELER [M14];
- `intermediates` là các điểm của ngày theo thứ tự, tối đa 25 [M15];
- `departureTime` là giờ xuất phát dự kiến (phải ở tương lai);
- `routingPreference = TRAFFIC_UNAWARE`. Google chỉ khuyên đặt `departureTime` tương lai khi tính theo giao thông [M16]; xe hai bánh đã là SKU Enterprise nên mức giao thông không làm rẻ đi. Kết quả nhân hệ số an toàn (`trip.speed_factor`);
- `X-Goog-FieldMask: routes.legs.distanceMeters,routes.legs.duration,routes.legs.steps.navigationInstruction,routes.distanceMeters,routes.duration,routes.warnings`.

Mỗi lời gọi có `TWO_WHEELER` là SKU **Compute Routes Enterprise**: miễn phí 1.000 lời gọi mỗi tháng, sau đó 15 USD / 1.000 [M17][M7]. Mỗi ngày của chuyến chỉ tốn 1 tới 2 lời gọi, vì `legs` cho thời gian từng chặng. Từng chặng ghi vào `tab_route_cache` (`travel_mode = two_wheeler`).

Chế độ xe hai bánh của Routes API **đang là beta**; app phải cảnh báo người dùng khi hiển thị tuyến này [M18]. Dưới số liệu luôn có dòng: *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.*

Routes API trả lỗi với TWO_WHEELER thì gọi lại bằng `DRIVE` + `avoidHighways`, ghi chú *ước tính theo ô tô*. Tài liệu không ghi rõ API làm gì ở nước không hỗ trợ (**chưa xác minh**).

### 6.2 Giờ mở cửa

- Dùng `currentOpeningHours` nếu ngày đến nằm trong 7 ngày tới (có giờ đặc biệt, `specialDays`), ngược lại dùng `regularOpeningHours` [M19].
- `periods[].open/close` có `day` từ 0 (Chủ nhật) tới 6, `hour`, `minute`, theo giờ địa phương [M19]. Không giả định phần tử đầu là Chủ nhật. Nơi mở 24 giờ có `open` ở 0:00 và không có `close`.
- Kiểm khoảng từ *giờ đến* tới *giờ đến + `duration_minutes`* có nằm trong một `period` của đúng thứ đó không.

### 6.3 Bộ luật rủi ro

Luật chạy bằng mã, không bằng AI, để kết quả lặp lại được và có bài kiểm. Claude (`purpose = trip_evaluate`) chỉ viết câu tóm tắt.

| Mã | Luật | Đỏ | Vàng |
|---|---|---|---|
| R1 Trễ giờ | Giờ đến dự kiến (thời gian Google × `trip.speed_factor`, cộng phút ở lại) so với `planned_time` | Trễ trên 30 phút, hoặc làm lỡ điểm `is_fixed_time` sau đó | Trễ 10 tới 30 phút, hoặc dư dưới 10 phút trước điểm cố định |
| R2 Giờ mở cửa | Mục 6.2 | Đóng cả ngày đó, hoặc đã đóng cửa hẳn | Đến trong 30 phút trước giờ đóng; không có dữ liệu giờ |
| R3 Phà | Điểm `pha`: giờ tới bến so với `ferry_last` trong `hard_facts`. Google không có lịch phà, nên không có dữ liệu thì luôn nhắc gọi hotline | Tới bến sau chuyến cuối trừ 30 phút | Không biết chuyến cuối; dư dưới 60 phút |
| R4 Chạy liên tục | Tổng phút chạy giữa hai điểm dừng từ 15 phút | Trên 120 phút | Trên `trip.ride_break_minutes` (90, theo lưu ý *nghỉ khoảng mỗi 1,5 tiếng* của tệp mẫu) |
| R5 Chạy đêm | Phần chặng chạy từ `trip.night_start` tới `trip.night_end` (18:00 tới 05:30) | Chạy trong khung 03:00 tới 05:00, hoặc chạy đêm trên quốc lộ nhiều xe tải (`navigationInstruction` có `QL1`, `QL51`, `Quốc lộ 1`) | Còn lại trong khung đêm |
| R6 Tổng giờ chạy | Tổng phút chạy trong ngày | Trên 8 giờ | Trên 6 giờ |
| R7 Nhận, trả phòng | Giờ tới khách sạn so với `checkin`; giờ rời so với `checkout` (mặc định 14:00 và 12:00 nếu tệp không ghi) | Trả phòng trễ quá 60 phút | Tới trước giờ nhận phòng (gợi ý gửi đồ) |
| R8 Chưa định vị | Điểm `main` không có tọa độ | | Luôn vàng |
| R9 Thứ không khớp ngày | `weekday_text` khác thứ của ngày | Luôn đỏ | |

**Cấu trúc một rủi ro** (dùng chung cho `tab_trip.evaluation.risks` và `tab_trip_option.risks`, `12-api.md` mục 5.11 dẫn sang đây):

```
{ "code": "R2", "level": "red" | "yellow", "day_no": 3, "stop_id": 41,
  "message": "Bảo tàng Văn hóa Khmer đóng cửa thứ Hai",
  "suggestion": "Bỏ điểm này hoặc thay bằng Chùa Âng",
  "checked_at": "2026-11-18T10:00:00+07:00" }
```

`tab_trip.evaluation` = `{evaluated_at, risks: [...]}` cho danh sách điểm hiện tại của chuyến. Gợi ý sửa do luật sinh:

- R4: *thêm điểm nghỉ ở khoảng giữa chặng*;
- R3: *rời sớm hơn N phút hoặc bỏ điểm tùy chọn trước phà*.

## 7. Thiết kế: tối ưu và phương án

### 7.1 Sắp lại thứ tự

Trong một ngày, các điểm `is_fixed_time` chia ngày thành các **khung**. Điểm không cố định được đổi thứ tự trong khung của nó, không nhảy sang khung khác hay ngày khác.

1. **Ma trận thời gian** giữa các điểm của khung, bằng **Compute Route Matrix**:
   - `travelMode = DRIVE`, `avoidHighways = true`, `TRAFFIC_UNAWARE`;
   - SKU Essentials, 10.000 phần tử miễn phí mỗi tháng [M17][M7];
   - tối đa 625 phần tử mỗi lời gọi, tối đa 50 điểm gốc và đích dạng `place_id` hoặc địa chỉ [M20].

   Không dùng TWO_WHEELER cho ma trận: đó là SKU Enterprise (1.000 phần tử miễn phí), dễ hết. Ma trận chỉ cần đúng thứ tự tương đối.
2. **Tìm thứ tự:**
   - khung có tới 8 điểm không cố định thì thử mọi hoán vị (8! = 40.320, dưới 1 giây);
   - lớn hơn thì dùng láng giềng gần nhất rồi cải thiện bằng 2-opt.
3. **Hàm chi phí:** tổng phút chạy, cộng phạt vi phạm R2 và R1.
4. **Không dùng `optimizeWaypointOrder`** của Routes API:
   - tính theo SKU Pro [M21];
   - tài liệu không nói nó chạy được với TWO_WHEELER;
   - nó không biết giờ mở cửa.
5. Chọn xong thứ tự thì gọi lại Compute Routes TWO_WHEELER (mục 6.1) để ra số liệu cuối.

### 7.2 Dựng phương án

Mặc định 3 phương án. Mỗi phương án là danh sách điểm theo ngày cộng giờ, tính lại đủ R1 tới R9:

| Phương án | Cách dựng |
|---|---|
| **Đúng giờ, ít rủi ro** | Sửa mọi rủi ro đỏ bằng gợi ý của luật: thêm điểm nghỉ, rời sớm, bỏ điểm `optional` trước mốc cứng, thay điểm đóng cửa bằng điểm dự phòng trong tệp |
| **Nhiều điểm** | Giữ đủ điểm của tệp, chỉ sắp lại thứ tự; ghi rõ rủi ro còn lại |
| **Nhàn** | Như *Đúng giờ*, bỏ thêm điểm `optional`, thời gian ở lại tăng 1,5 lần, mỗi ngày dưới 6 giờ chạy |

- Mỗi phương án ghi `total_km`, `total_minutes` (tổng phút chạy xe), `night_ride_minutes`, `red_count`, `yellow_count`, `changes` (thay đổi so với tệp gốc).
- Phương án trùng nhau thì gộp, chỉ hiện những phương án khác nhau.
- Claude viết `summary` 2 câu cho mỗi phương án từ số liệu, không tự đổi số.

### 7.3 Tiền Maps cho một lần đánh giá

| Lời gọi | Một chuyến 3 ngày, khoảng 40 điểm | SKU |
|---|---|---|
| Text Search IDs Only | khoảng 45 | Miễn phí |
| Place Details Essentials | khoảng 40 tới 60 | 10.000 miễn phí |
| Place Details Enterprise (giờ mở cửa) | khoảng 15 | 1.000 miễn phí |
| Compute Route Matrix DRIVE | khoảng 150 phần tử | 10.000 miễn phí |
| Compute Routes TWO_WHEELER | 4 tới 6 mỗi phương án, tối đa 18 | 1.000 miễn phí |

Một người dùng, vài chuyến mỗi tháng: dưới mức miễn phí nhiều lần. Quota chặn cứng theo ngày (`40-tich-hop-google.md` mục 11 bước 6) đặt theo bảng này:

| API | Quota mỗi ngày |
|---|---|
| Compute Routes | 30 lời gọi (khoảng 1.000 mỗi tháng) |
| Places | 300 lời gọi |
| Route Matrix | 300 phần tử |

Chạm quota thì đánh giá báo *đã hết lượt tra cứu bản đồ hôm nay*, dùng số liệu có sẵn trong `tab_route_cache`.

## 8. Thiết kế: lưu

- **Bóc tách xong:** `tab_trip` từ `importing` sang `draft`, có `tab_trip_stop`. Lỗi thì `failed`, kèm câu lỗi trong `tab_job_queue.error`.
- **Đánh giá:**
  - `status = evaluating` trong lúc chạy;
  - xong thì tạo các `tab_trip_option` (`stops` là bản chụp thứ tự và giờ theo ngày, cùng `risks`), ghi `tab_trip.evaluation`, `evaluated_at`;
  - trạng thái về lại `draft`, hoặc `planned` nếu trước đó đã chọn phương án.
- **Chọn phương án** (`POST /api/v1/trips/{id}/options/{option_id}/choose`):
  - `chosen = true`, `tab_trip.chosen_option_id`;
  - ghi đè `tab_trip_stop` bằng `stops` của phương án (`day_no`, `seq`, `planned_time`, `duration_minutes`);
  - `status = planned`.

  Phương án khác giữ lại để so.
- **Sửa tay một điểm sau đó** (`PATCH`, `/stops/reorder`): đặt việc `trip_evaluate` cho riêng ngày đó, cập nhật `tab_trip.evaluation`.
- **Đưa vào lịch** (`POST /api/v1/trips/{id}/to-calendar`, đề nghị thêm vào 12):
  - mỗi ngày một sự kiện cả ngày;
  - thêm sự kiện có giờ cho mốc cứng (phà, nhận phòng);
  - đi qua module `calendar` (`40-tich-hop-google.md` mục 4), `remind_source = app`.
- **Xóa chuyến:** trên màn chuyến đi (`DELETE /api/v1/trips/{id}`), hoặc qua chat bằng công cụ `delete_trip` (`20-bo-nao-ai.md`, `kind = delete_trip`, phải duyệt).
- **Hỏi trong chat** *lấy lịch trình Trà Vinh*: `get_trip` tìm theo tên và ngày, trả tóm tắt theo ngày kèm `open_screen` tới `trip_detail`.

## 9. Thiết kế: mở bản đồ

**Máy chủ dựng mọi link Google Maps, app chỉ mở** (ĐX-API-06). Hàm dựng link nằm một chỗ trong `modules/trip/service.py` và phục vụ hai nơi:

- `GET /api/v1/trips/{id}/map-links` cho màn chuyến đi;
- công cụ `open_route` (qua `ai/actions.py`) cho chat.

Link không cần khóa API, không tính tiền [M1][M2]. App chỉ tự ghép lệnh `google.navigation` từ tọa độ máy chủ trả (`30-app-android.md`).

### 9.1 Ba loại nút

| Nút | Hành động (`20-bo-nao-ai.md`) | Link | Ghi chú |
|---|---|---|---|
| **Dẫn đường** tới một điểm | `open_map_navigation` `{lat, lng, query, mode: "l", avoid: "h", fallback_url}` | App gọi `Maps.navigate({lat, lng, mode, avoid})`, mở `google.navigation:q=<lat>,<lng>&mode=l&avoid=h` | `mode=l` là xe hai bánh, `avoid=h` là tránh cao tốc. Luôn đi từ vị trí hiện tại, không có điểm dừng [M2]. Điểm chưa có tọa độ thì không hiện nút này, chỉ hiện *Xem một điểm* |
| **Xem đường cả ngày** | `open_map_directions` `{urls, segment_labels}` | `https://www.google.com/maps/dir/?api=1&origin=<lat,lng>&destination=<lat,lng>&waypoints=<lat,lng>\|...&travelmode=two-wheeler&avoid=highways` | Một URL mỗi đoạn, chia theo 9.2 [M1] |
| **Xem một điểm** | `open_map_place` `{query, place_id}` | `https://www.google.com/maps/search/?api=1&query=<tên>&query_place_id=<place_id>` | Có `query_place_id` thì Maps dùng nó trước, `query` chỉ dự phòng [M1] |

`fallback_url` của nút dẫn đường là link `dir` có `destination=<lat,lng>&travelmode=two-wheeler&avoid=highways&dir_action=navigate`. App mở link này khi `Maps.isMapsInstalled()` trả `false` [M1]. Link https trên Android mở app Google Maps nếu có, không thì mở trình duyệt [M1].

**Chế độ xe máy ở Việt Nam:**

- Routes API liệt kê Việt Nam trong vùng hỗ trợ xe hai bánh [M13].
- Trang trợ giúp Google Maps chỉ nói chế độ xe hai bánh có ở *một số nơi*, không có danh sách nước [M22].
- Maps URLs ghi `two-wheeler` chỉ chạy khi người dùng *đang ở* nước hỗ trợ [M1].

Vì vậy app Google Maps ở Việt Nam có nhận `travelmode=two-wheeler` và `mode=l` không thì **chưa xác minh**. Đây là bài thử trên máy thật đầu tiên của V1.6 (mục 14). Dù chế độ xe máy không chạy, link vẫn có `avoid=highways`, nên Maps không chỉ đường lên cao tốc. Đó đúng là việc mà lưu ý trong tệp mẫu (*bấm chọn chế độ xe máy để không bị chỉ đường lên cao tốc*) đang bắt người dùng làm tay.

### 9.2 Chia đoạn khi quá nhiều điểm

Giới hạn của Maps URLs [M1]:

- `waypoints` tối đa **9** điểm; trình duyệt trên điện thoại chỉ **3** điểm;
- cả link tối đa **2.048 ký tự**.

App gửi `max_waypoints` trong `GET /api/v1/trips/{id}/map-links?day_no=N&max_waypoints=9|3`: là 3 khi `Maps.isMapsInstalled()` trả `false` (ĐX-API-06 nhận thêm tham số này).

Thuật toán với danh sách điểm đã sắp `P0 ... Pn` của một ngày, gồm khách sạn đầu và cuối ngày, không gồm điểm phụ:

1. Ưu tiên **cắt ở điểm nghỉ dài**: khách sạn, ngủ trưa, điểm có `duration_minutes` từ 90. Mỗi phần là một nhóm theo nghĩa (sáng, chiều, tối), giống tệp mẫu.
2. Nhóm còn quá `1 + max_waypoints + 1` điểm thì cắt tiếp. Điểm cuối đoạn trước là điểm đầu đoạn sau, để không đứt tuyến.
3. Dùng tọa độ `lat,lng` (khoảng 22 ký tự) thay tên tiếng Việt đã mã hóa (thường trên 100 ký tự). Không gửi kèm `waypoint_place_ids`, cho link ngắn.
4. Dựng xong thì đo độ dài. Quá 2.048 ký tự thì bớt một điểm ở đoạn đó rồi dựng lại.
5. Tên mỗi đoạn (`segment_labels`): *<tên điểm đầu> → <tên điểm cuối> (N điểm)*.

Điểm `alternative`, `backup`, `generic` không vào link tuyến; chúng hiện dưới điểm chính kèm nút *Xem một điểm*.

### 9.3 Trong chat

Hỏi *chỉ đường tới chỗ ăn trưa*:

1. Công cụ `open_route` (`trip_id = null`, `scope = stop`) tìm chuyến có ngày hôm nay.
2. Tìm điểm `an_uong` kế tiếp có `planned_time` từ 10:30 tới 14:00, sau giờ hiện tại.
3. Trả hành động `open_map_navigation`, nhãn *Dẫn đường tới Cơm niêu Làng Chài*.

App hiện nút, không tự mở; chạm mới mở. Claude chỉ nhận một dòng *Đã tạo nút Dẫn đường tới ...*, không thấy URL.

## 10. Thiết kế: xuất Word theo kiểu tệp mẫu

Dùng `python-docx`. Thông số đo từ tệp mẫu:

| Phần | Kiểu |
|---|---|
| Trang | A4 dọc (11906 × 16838 twip); lề trên, dưới 1200 twip; lề trái, phải 1440 twip |
| Chữ mặc định | Arial 11 |
| Title | Arial 18, đậm, màu `1F3864`, cách dưới 10 pt |
| Heading 1 | Arial 14, đậm, màu `1F3864`, cách trên 16 pt, dưới 6 pt |
| Heading 2 | Arial 12, đậm, cách trên 10 pt, dưới 4 pt |
| Bảng giờ | 2 cột rộng 1500 và 7526 twip, bố cục cố định. Hàng đầu *Giờ* / *Làm gì* chữ đậm, nền `DCE6F1`. Viền ô `BFBFBF` 0,5 pt; lề ô trên, dưới 60 twip, trái, phải 100 twip |
| Link | Màu `0563C1`, gạch chân, Arial |

**Bố cục:**

1. Title: tên chuyến.
2. Một dòng: *N ngày M đêm, đi xe máy, xuất phát và kết thúc tại X.*
3. Một dòng lưu ý cố định: *Link chỉ đường đã đặt sẵn chế độ xe máy và tránh cao tốc. Các chữ màu xanh đều bấm được.* (thay câu *bấm chọn chế độ xe máy* của tệp mẫu).
4. Mỗi ngày:
   - Heading 1: *Ngày N (thứ X, dd/mm): A → B*;
   - dòng *Đường đi: ...* kèm tổng km, giờ chạy;
   - bảng giờ, mỗi điểm một hàng: tên điểm là link *Xem một điểm*; điểm dự phòng nối bằng *hoặc*, *Dự phòng:*; giá, số điện thoại ở cuối;
   - Heading 2 *Bản đồ ngày N*, mỗi đoạn tuyến một dòng link (mục 9.2, `max_waypoints = 9`).
5. Heading 1 *Khách sạn*: mỗi đêm một dòng, *đã đặt* hoặc *chưa đặt*, có dự phòng.
6. Heading 1 *Lưu ý*:
   - rủi ro đỏ và vàng còn lại của phương án đã chọn;
   - lưu ý nguyên văn của tệp gốc;
   - dòng cuối *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.*

**Link trong python-docx:** thư viện không có hàm thêm link. Phải tạo quan hệ `RT.HYPERLINK` (`part.relate_to(url, RT.HYPERLINK, is_external=True)`) rồi chèn `w:hyperlink` chứa `w:r` có kiểu chữ link. Hàm đặt ở `modules/trip/docx_export.py`.

**Lưu:**

- `POST /api/v1/trips/{id}/export-docx` (`12-api.md`) lưu tệp vào R2 (`tab_file`, `purpose = trip_export`), ghi `tab_trip.export_file_id`, trả link tải.
- Nếu đã bật dịch vụ `drive` thì có tham số `save_to_drive` (đề nghị thêm vào 12) để tải lên thư mục *Trợ lý* (`40-tich-hop-google.md` mục 8.1). Ghi vào Drive của chính người dùng thì không cần duyệt (`60-bao-mat-rieng-tu.md` mục 3.12).

**Kiểm vòng tròn:** xuất ra Word rồi nhập lại phải ra cùng số ngày, số điểm, cùng `place_id`, cùng giờ.

## 11. Ví dụ chạy thử trên tệp mẫu Phước Hải – Trà Vinh

Tệp *Lich-trinh-Phuoc-Hai-Tra-Vinh.docx* có:

- 1 tiêu đề;
- 3 bảng giờ, gồm 12, 11 và 8 hàng;
- 6 link tuyến ở các mục *Bản đồ ngày N*;
- mục *Khách sạn*, mục *Lưu ý* (5 dòng);
- 43 link địa điểm: 41 link tìm kiếm `query=` và 2 link rút gọn `maps.app.goo.gl`, cả hai trỏ tới Hotel Quốc Hương.

Dưới đây là kết quả **mong đợi** của từng bước, dùng làm bài kiểm chấp nhận V1.6. Số km và giờ thật do Routes API trả khi chạy; ở đây chỉ ghi số tệp đã nêu.

### 11.1 Bóc tách

| Ngày | Thứ | Điểm chính | Điểm phụ | Mốc cứng |
|---|---|---|---|---|
| 1 | thứ 7 | Cần Thơ (xuất phát 02:30) → phà Cát Lái (~07:00) → chợ Phước Hải (~09:30) → Cafe Phượng (10:30, 120 phút) → Bánh canh cô Phờ (12:40, `optional`) → Hotel Quốc Hương (13:00) → Bánh khọt cây bàng (15:45) → Đèo Nước Ngọt, Đỉnh Kỳ Vân (16:20) → Long Hải Channel (17:00, 60 phút) → Hàu chị Oanh (18:30) → bờ kè Trần Hưng Đạo, Ốc Thanh Vân, bánh tráng cô Loan (20:00) | Bánh khọt 5/12 Võ Thị Sáu; Hàu dì Sáu Xu My; Bò sốt hàu Bami; Hải sản Phúc Khang; cầu Mỹ Thuận (`via`) | `checkin` 13:00 |
| 2 | chủ nhật | Làng chài, hẻm Lý Tự Trọng (05:20) → Hủ tiếu mực Vui (06:50) → Hồ Sở Bông, Núi Minh Đạm (07:50) → khách sạn (09:45) → trả phòng (10:45) → Cơm niêu Làng Chài (11:00) → Đồng lúa An Nhứt (12:15, `optional`) → bến phà Vũng Tàu (~13:30) → bến Tắc Suất, Lâm Viên Cần Giờ (14:30, 90 phút) → phà Bình Khánh (16:15) → 68 Hotel Gò Công (~17:45) | Bánh căn cô Hai; Cơm Nhà Tui (`backup`); bánh giá, hủ tiếu, mắm tôm chà Gò Công (`generic`) | `checkout` 10:45; `ferry_last` 17:00 từ Vũng Tàu; `hotline` 0254 6525 656 |
| 3 | thứ 2 | Ăn sáng, trả phòng Gò Công (06:30) → cầu Rạch Miễu (`via`) → Ao Bà Om, Chùa Âng (~10:30) → bún nước lèo (12:00, `generic`) → nghỉ cafe (13:00, 90 phút) → Chùa Hang (14:45) → bánh tét Trà Cuôn (15:15) → Cần Thơ (15:30 đi, ~18:30 tới) | Bảo tàng Văn hóa Khmer (tệp ghi *có thể đóng cửa thứ 2*); bánh canh Bến Có (`generic`) | |

- **Khách sạn:**
  - đêm 1: Hotel Quốc Hương, đã đặt;
  - đêm 2: Khách sạn 68 Gò Công, chưa đặt; dự phòng Khách sạn Sapphire.
- **Ngày đi:** tệp không ghi `start_date`, app hỏi và gợi ý thứ Bảy gần nhất. Chọn 21/11/2026 (thứ Bảy) thì ngày 3 là thứ Hai 23/11/2026, khớp tệp.

### 11.2 Tìm địa điểm

- **Hotel Quốc Hương:** hai đường, cùng kết quả:
  - link rút gọn, qua Resolution API ra `place_id`;
  - link tuyến *Khách sạn → ...* có `origin=10.4477939,107.2876573`, nên khách sạn có `coord_source = user`.
- **Điểm có link `query=`:** chuỗi tìm lấy nguyên từ link, ví dụ *Hủ tiếu mực bánh canh Vui 144 Võ Thị Sáu Phước Hải*.
- **Điểm không có link:**
  - *phà Cát Lái*, *cầu Mỹ Thuận* lấy từ `waypoints` của link tuyến ngày 1;
  - *cầu Rạch Miễu* lấy từ link tuyến ngày 3, `role = via`, `duration_minutes = 0`.
- **Điểm `generic`** (bánh giá, hủ tiếu Gò Công, mắm tôm chà, bún nước lèo, bánh canh Bến Có, bánh tét Trà Cuôn): mỗi điểm 3 gợi ý gần tuyến.
- **Có thể phải hỏi lại** (`uncertain`) vì tên chung: *Làng chài Phước Hải*, *Bờ kè Phước Hải Trần Hưng Đạo*.

### 11.3 Rủi ro mong đợi

| Ngày | Mã | Mức | Nội dung mong đợi |
|---|---|---|---|
| 1 | R5 | Đỏ | Chạy từ 02:30, có đoạn trong khung 03:00–05:00 trên QL1A; tệp đã ghi *buồn ngủ thì dừng ngay* |
| 1 | R4 | Đỏ hoặc vàng | Cần Thơ → Cát Lái khoảng 4 tiếng rưỡi. Tệp ghi nghỉ mỗi 1,5 tiếng nhưng không có điểm nghỉ cụ thể; gợi ý thêm 2 điểm nghỉ (quanh cầu Mỹ Thuận và Tân An) |
| 1 | R3 | Vàng | Phà Cát Lái: tệp không có giờ chuyến, nhắc kiểm giờ chạy |
| 1 | R6 | Vàng | Khoảng 250 km, 7 tiếng tính cả nghỉ (theo tệp) |
| 2 | R3 | Vàng hoặc đỏ | Phà Vũng Tàu – Cần Giờ: chuyến cuối 17:00 theo thông tin cũ, tới bến ~13:30 là dư. Nhưng chặng Phước Hải → An Nhứt → bến phà sau bữa trưa 11:00 có thể sát giờ. Gợi ý của luật: bỏ An Nhứt (đúng lưu ý cuối của tệp), gọi hotline trước 1 ngày |
| 2 | R2 | Vàng | Lâm Viên Cần Giờ: kiểm giờ mở cửa chủ nhật, giờ đóng so với 16:00 |
| 2 | R5 | Vàng | Phà Bình Khánh 16:15 → Gò Công ~17:45: cuối chặng lúc chạng vạng, sau 18:00 nếu trễ |
| 3 | R2 | Đỏ hoặc vàng | **Bảo tàng Văn hóa dân tộc Khmer Trà Vinh vào thứ Hai**: `regularOpeningHours` không có thứ Hai thì đỏ *đóng cửa thứ Hai*; không có dữ liệu giờ thì vàng *chưa rõ giờ, tệp ghi có thể đóng* |
| 3 | R4 | Vàng | Gò Công → Trà Vinh khoảng 3 tiếng liền; gợi ý nghỉ ở Bến Tre |
| 3 | R5 | Vàng | Về Cần Thơ 15:30 → 18:30: khoảng cuối chạy sau 18:00 |

### 11.4 Phương án mong đợi

- **Đúng giờ, ít rủi ro:**
  - ngày 1 thêm 2 điểm nghỉ trước phà Cát Lái;
  - ngày 2 bỏ Đồng lúa An Nhứt, rời Phước Hải sớm để tới bến phà trước 13:00;
  - ngày 3 bỏ Bảo tàng Khmer (nếu đóng), thêm nghỉ ở Bến Tre, rời Trà Vinh 15:00.
- **Nhiều điểm:** giữ nguyên tệp, chỉ sắp lại các điểm ăn tối, dạo đêm ngày 1 cho đỡ vòng; ghi rủi ro còn lại.
- **Nhàn:** như *Đúng giờ*, bỏ thêm Bánh canh cô Phờ và Núi Minh Đạm, thời gian ở lại dài hơn.

### 11.5 Link bản đồ mong đợi (`max_waypoints = 9`)

- **Ngày 1:** cắt ở khách sạn (13:00), thành hai nhóm, khớp cách tệp mẫu chia 2 link cho ngày 1:
  - nhóm sáng: Cần Thơ → cầu Mỹ Thuận → phà Cát Lái → chợ Phước Hải → Cafe Phượng → Bánh canh cô Phờ → khách sạn;
  - nhóm chiều tối: khách sạn → bánh khọt → Đèo Nước Ngọt → Đỉnh Kỳ Vân → Channel → Hàu chị Oanh → bờ kè → Ốc Thanh Vân → bánh tráng cô Loan. Nhóm này có 9 điểm (7 điểm dừng), gọn trong một link.
- **Ngày 2:** cắt ở khách sạn (09:45 về, 10:45 trả phòng) và ở bến phà, thành 3 link như tệp mẫu.
- **Ngày 3:** 1 link: 68 Hotel → cầu Rạch Miễu → Ao Bà Om → Chùa Âng → Chùa Hang → Trà Cuôn → Cần Thơ.
- **Mọi link** có `travelmode=two-wheeler&avoid=highways`, dùng tọa độ, dài khoảng 300 tới 400 ký tự, dưới 2.048.
- Với `max_waypoints = 3`, nhóm chiều tối ngày 1 thành 2 đoạn.

### 11.6 Tiền Maps của lần chạy thử

| Lời gọi | Số lần |
|---|---|
| Text Search IDs Only | khoảng 45 (41 link tìm kiếm cộng vài điểm không có link) |
| Place Details Essentials | khoảng 50 |
| Place Details Enterprise | khoảng 15 |
| Compute Route Matrix | khoảng 150 phần tử |
| Compute Routes Enterprise | khoảng 12 |

Tất cả trong mức miễn phí; tiền 0 USD.

## 12. Dữ liệu cần

Tệp này là gốc cho bảng lịch trình. `11-co-so-du-lieu.md` mục 3.13 gom theo đây. Quy ước theo 11: `bigint`, **cột chung** (`id`, `user_id`, `created_at`, `updated_at`), `CK` cho giá trị liệt kê. Tên cột dùng lại tên đã có ở 11 khi cùng nghĩa.

**`tab_trip`** (bảng của 11, thêm hoặc sửa):

| Cột | Thay đổi | Ghi chú |
|---|---|---|
| status | CK `importing`, `draft`, `evaluating`, `planned`, `done`, `failed` | Gộp theo `80-ra-cheo-lan-1.md` mục C (CSDL-05) |
| end_text | thêm, text | Điểm kết thúc |
| nights | thêm, smallint | |
| source_kind | thêm, text CK `docx`, `pdf`, `image`, `text`, `link` | |
| extract_json | thêm, jsonb | Đầu ra bóc tách gốc (lược đồ 4.2), để chạy lại bước 2–5 không tốn AI |
| hard_facts | thêm, jsonb NN default `[]` | Mốc cứng theo lược đồ 4.2. Gộp vào cột JSON, không tạo bảng `tab_trip_fact` riêng (trả lời `80` mục A1 dòng 15) |
| evaluation | giữ | `{evaluated_at, risks}`, cấu trúc rủi ro ở mục 6.3 |
| Còn lại | giữ như 11 | `title`, `start_date`, `end_date`, `travel_mode`, `origin_text`, `source_file_id`, `source_text`, `notes`, `evaluated_at`, `chosen_option_id`, `export_file_id` |

**`tab_trip_stop`** (bảng của 11, thêm hoặc sửa):

| Cột | Thay đổi | Ghi chú |
|---|---|---|
| category | CK `an_uong`, `nghi`, `tham_quan`, `pha`, `di_chuyen`, `khach_san`, `mua_sam`, `khac` | Thêm `khach_san`, `mua_sam` |
| planned_time, duration_minutes, is_fixed_time | giữ tên của 11 | Mục 4.5 |
| time_text | thêm, text | Nguyên văn trong tệp |
| approx | thêm, boolean NN default false | Giờ có dấu `~` |
| optional | thêm, boolean NN default false | |
| role | thêm, text NN CK `main`, `alternative`, `backup`, `generic`, `via`, default `main` | |
| parent_stop_id | thêm, bigint FK `tab_trip_stop` CASCADE | Điểm phụ trỏ về điểm chính |
| source_url | thêm, text | Link gốc trong tệp |
| address | giữ | Địa chỉ từ Google: xóa cùng tọa độ khi quá 30 ngày (nguồn `google`) |
| lat, lng, place_id | giữ | |
| coord_source | thêm, text CK `user`, `google` | Mục 5.4 |
| coord_fetched_at | thêm, timestamptz | |
| resolve_status | giữ | `ok`, `uncertain`, `not_found`, `manual` |
| alternatives | giữ, jsonb | Gợi ý cho điểm `generic`: `place_id` và nhãn, không lưu tọa độ |
| phone, cost_note, note, title, place_query, day_no, seq | giữ | |

**`tab_trip_option`** (bảng của 11, thêm):

| Cột | Thay đổi | Ghi chú |
|---|---|---|
| stops | giữ tên của 11 | JSON theo ngày: `stop_id`, `seq`, `planned_time`, `duration_minutes`, `leg_minutes`, `leg_km` |
| total_minutes | giữ, nghĩa là tổng phút chạy xe | |
| night_ride_minutes | thêm, int | |
| red_count, yellow_count | thêm, smallint | |
| changes | thêm, jsonb | Thay đổi so với tệp gốc |
| evaluated_at | thêm, timestamptz | |
| risks | giữ | Cấu trúc mục 6.3 |

**`tab_place_cache`** (sửa theo ĐX-T1):

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | bigint PK | |
| query_norm | text NN | Chữ thường, bỏ dấu, gộp khoảng trắng |
| bias_key | text NN | Vùng tìm, ví dụ `tinh:tra-vinh` hoặc ô lưới 0,25 độ |
| place_id | text | Giữ mãi |
| lat, lng | numeric(9,6) | Xóa khi quá `coord_expires_at` |
| address | text | Xóa cùng tọa độ |
| fetched_at, coord_expires_at | timestamptz | `coord_expires_at = fetched_at + 30 ngày` |

- **Bỏ** các cột `name`, `opening_hours`, `utc_offset_minutes`, `expires_at` (cả dòng) của bản 11.
- UQ `(query_norm, bias_key)`.
- Bảng hệ thống, không có `user_id`.

**`tab_route_cache`:** giữ như 11.

**Khóa cài đặt** (`tab_setting`, quy ước dấu chấm của 11):

| Khóa | Mặc định |
|---|---|
| `trip.night_start` | `18:00` |
| `trip.night_end` | `05:30` |
| `trip.ride_break_minutes` | `90` |
| `trip.speed_factor` | `1.2` |

Giữ `trip.default_travel_mode` của 11.

**Việc nền** (`tab_job_queue.kind`): `trip_import`, `trip_evaluate` (đã có ở 11).

## 13. API hoặc giao tiếp

**REST** theo `12-api.md` mục 5.11 (tiền tố `/api/v1`). Tệp này chỉ thêm ý nghĩa:

| Phương thức, đường dẫn | Dùng ở mục |
|---|---|
| `POST /api/v1/trips/import` (`file_id` hoặc `text`; thêm `start_date`) → 202 `{trip_id, job_id}` | 3, 4 |
| `GET /api/v1/trips`, `GET /api/v1/trips/{id}` | 8 |
| `PATCH /api/v1/trips/{id}` | 4.5 (`start_date`) |
| `POST /api/v1/trips/{id}/stops`, `PATCH .../stops/{stop_id}`, `DELETE .../stops/{stop_id}`, `POST .../stops/reorder` | 5.3, 8 |
| `POST /api/v1/trips/{id}/stops/{stop_id}/resolve` | 5.3 |
| `POST /api/v1/trips/{id}/evaluate` → 202 `{job_id}` | 6, 7 |
| `POST /api/v1/trips/{id}/options/{option_id}/choose` | 8 |
| `GET /api/v1/trips/{id}/map-links?day_no=N&max_waypoints=9` | 9 |
| `POST /api/v1/trips/{id}/export-docx` | 10 |
| `DELETE /api/v1/trips/{id}` | 8 |

**Đề nghị thêm vào `12-api.md`:**

| Đề nghị | Dùng ở mục |
|---|---|
| Tham số `max_waypoints` cho `/map-links`. `stops[]` trong phản hồi trả `lat`, `lng`, `fallback_url`, `view_url` thay cho `navigate_uri`, vì app tự ghép lệnh `google.navigation` | 9 |
| `start_date` cho `/trips/import` | 4.5 |
| `POST /api/v1/trips/{id}/to-calendar` | 8 |
| Tham số `save_to_drive` cho `/export-docx` | 10 |
| Cấu trúc `risks` và `evaluation` dẫn sang mục 6.3 | 6.3 |
| Thêm `evaluating` vào trạng thái chuyến | 8 |

**Công cụ AI** (tên theo `20-bo-nao-ai.md`):

| Công cụ | Ghi chú |
|---|---|
| `import_trip` | |
| `evaluate_trip` | |
| `save_trip` | |
| `list_trips`, `get_trip` | |
| `find_place` | Mục 5.2 |
| `open_route` | Mục 9.3 |
| `export_trip_docx` | |
| `delete_trip` | Duyệt |

**Hành động trả cho app** (`20-bo-nao-ai.md` mục 3.8): `open_map_navigation`, `open_map_directions`, `open_map_place`, `open_link` (`kind = file` cho tệp Word), `open_screen` (`trip_detail`), `confirm` (`kind = delete_trip`). Không còn kiểu `open_map` có `kind`, `uri` của bản 1.

**Plugin Kotlin `Maps`** (`30-app-android.md`):

- `navigate({lat, lng, mode, avoid})`: mở `google.navigation` với `setPackage("com.google.android.apps.maps")`, kiểm `resolveActivity()` trước;
- `openUrl({url})`;
- `isMapsInstalled()`: app dùng kết quả để gửi `max_waypoints` và chọn `fallback_url`.

Khai `<queries>` cho gói Maps trên Android 11 trở lên.

## 14. Kiểm thử

Bài kiểm luật viết trước. Phản hồi Google giả lập bằng máy chủ giả của `70-kiem-thu.md` mục 3.6, mẫu dựng theo ví dụ trong tài liệu Google.

1. **Đọc Word:** tệp mẫu ra đúng:
   - 3 bảng, 31 hàng giờ;
   - 6 link tuyến;
   - 2 link rút gọn (cùng một địa điểm);
   - mọi link tìm kiếm giải mã ra đúng chuỗi tiếng Việt.

   Đoạn chứa nhiều link giữ đúng thứ tự.
2. **Chuẩn hóa giờ:**
   - `2h30` ra 02:30;
   - `~7h00` ra 07:00 với `approx`;
   - `10h30–12h30` ra 10:30 và 120 phút;
   - `13h00–15h30` qua bữa trưa.
3. **Bóc tách** (gọi Claude thật, chạy tay hoặc `pytest -m ai_eval`, không trong CI thường): tệp mẫu ra đúng bảng 11.1; không có link nào ngoài tệp.
4. **Đọc link:** `query`, `query_place_id`, `origin` dạng tọa độ, `waypoints` có `%7C`; gán `10.4477939,107.2876573` cho khách sạn.
5. **Places:**
   - Text Search chỉ xin `places.id` (kiểm header `X-Goog-FieldMask`);
   - Place Details của luồng lịch trình không có trường Pro hay Enterprise;
   - `find_place` có `displayName`;
   - giờ mở cửa chỉ xin cho đúng loại điểm;
   - `CLOSED_PERMANENTLY` ra rủi ro đỏ.
6. **Lưu đệm:**
   - quá 30 ngày thì xóa tọa độ, giữ `place_id`;
   - không có cột giờ mở cửa;
   - tọa độ `coord_source = user` không bị xóa.
7. **Luật rủi ro:** mỗi luật R1 tới R9 có ca đỏ, ca vàng, ca không báo. Có ca *thứ Hai bảo tàng đóng* với `periods` không có `day = 1`, và ca phà tới sau 16:30 khi `ferry_last = 17:00`.
8. **Tối ưu:**
   - hoán vị không đưa điểm qua khung cố định;
   - phương án trùng được gộp;
   - số trong `summary` khớp số đã tính.
9. **Link bản đồ:**
   - chia đoạn ở khách sạn;
   - không đoạn nào quá 9 điểm dừng (3 khi `max_waypoints = 3`);
   - đoạn sau bắt đầu ở điểm cuối đoạn trước;
   - mọi link dưới 2.048 ký tự;
   - link tuyến có `travelmode=two-wheeler&avoid=highways`;
   - `fallback_url` có `dir_action=navigate`;
   - `open_route` và `/map-links` ra cùng URL.
10. **Xuất Word:** kiểu chữ, màu, độ rộng cột đúng mục 10; link bấm được; kiểm vòng tròn.
11. **Chéo người dùng:** người A không đọc, sửa, xuất, xóa được chuyến của người B; `tab_place_cache` không chứa dữ liệu nhận diện người dùng.
12. **Thử trên máy thật** (Samsung Galaxy S25+, QĐ-19; ghi vào `70-kiem-thu.md`):
    - `google.navigation:...&mode=l&avoid=h` có mở đúng chế độ xe máy không;
    - link `travelmode=two-wheeler` mở chế độ nào;
    - link 9 điểm dừng mở đủ điểm trong app Maps không;
    - link rút gọn của tệp mẫu đọc được qua Resolution API không.

## 15. Rủi ro

| Rủi ro | Mức | Giảm nhẹ |
|---|---|---|
| App Google Maps ở Việt Nam bỏ qua `two-wheeler` hoặc `mode=l` | Trung bình | Luôn kèm `avoid=highways` / `avoid=h`; thử trên máy thật đầu V1.6 |
| Thời gian xe hai bánh của Routes API lệch (beta) | Trung bình | `trip.speed_factor` chỉnh được; cảnh báo cố định trong app và Word |
| Places tìm nhầm quán cùng tên | Trung bình | `locationBias` theo ngày; kiểm khoảng cách; hỏi lại; ưu tiên link trong tệp |
| Hết mức miễn phí SKU Enterprise (giờ mở cửa, xe hai bánh) | Thấp | Gọi Enterprise chỉ khi cần; quota chặn cứng theo ngày |
| Hiểu sai điều khoản lưu dữ liệu Google (giờ mở cửa, kết quả tuyến) | Trung bình | Thiết kế theo cách chặt; đọc lại Điều khoản dịch vụ riêng trước khi viết mã |
| Lịch phà không có nguồn dữ liệu | Cao | R3 luôn nhắc gọi hotline; lấy giờ từ tệp; không tự khẳng định giờ phà |
| Resolution API cho link rút gọn thay đổi hoặc ngừng | Thấp | Theo chuyển hướng HTTP, rồi hỏi người dùng |
| Claude bóc sai giờ hoặc bịa điểm | Trung bình | Kiểm link có trong văn bản gốc; kiểm giờ tăng dần; người dùng xem bản nháp trước khi đánh giá |

## 16. Câu hỏi mở

Đã chốt từ bản 1 (`80-ra-cheo-lan-1.md` mục B, *Kỹ thuật tự chốt được*):

- hệ số xe máy 1,2 chỉnh sau khi dùng thật;
- đọc lại điều khoản lưu dữ liệu tuyến đường trước khi viết mã;
- tọa độ lưu lâu dài bằng `coord_source`.

Còn mở (gom ở `80` mục B câu 26):

1. **Ngày đi mặc định:** tệp chỉ ghi thứ thì gợi ý thứ Bảy gần nhất, hay luôn bắt chọn ngày?
2. **Khung chạy đêm** 18:00 tới 05:30 có hợp lý không? Khung 03:00 tới 05:00 tính đỏ?
3. **Thời tiết, mưa, triều cường:** có cần ở V1.6 không? Google Maps Platform có Weather API nhưng chưa được đối chiếu trong tài liệu này.
4. **Lịch phà:** có muốn tự nhập bảng giờ phà quen (Vũng Tàu – Cần Giờ, Cát Lái, Bình Khánh) làm dữ liệu tĩnh không? Google không có dữ liệu này.
5. **Xuất PDF** cùng Word có cần không?

## 17. Cần agent khác

- **Agent kiến trúc:**
  - `11-co-so-du-lieu.md`:
    - gom mục 12 (bảng trip theo tệp này, `tab_place_cache` theo ĐX-T1, `hard_facts` trong `tab_trip`, khóa `trip.*`);
    - `cleanup_old_data` xóa tọa độ quá hạn ở `tab_place_cache` và ở `tab_trip_stop` nguồn `google`.
  - `12-api.md`: các đề nghị ở mục 13; sửa câu *Cấu trúc link theo `01-thiet-ke-tong-the.md` mục 8.7* thành *theo `41-ban-do-lich-trinh.md` mục 9*.
- **Agent AI** (`20-bo-nao-ai.md`):
  - đã khớp: `find_place`, `delete_trip`, ba kiểu hành động bản đồ, lược đồ 4.2;
  - còn: bảng 3.8 ghi plugin `maps` (`openNavigation`), nhưng tên theo `30-app-android.md` là `Maps.navigate`; `find_place` lấy `displayName` (SKU Pro), giờ mở cửa chỉ khi câu hỏi cần.
- **Agent app Android:**
  - `30-app-android.md`: plugin `Maps` như mục 13; dòng 455 còn ghi `open_map`, cần đổi theo ba kiểu hành động bản đồ.
  - `31-giao-dien.md`:
    - danh sách *Điểm cần xác nhận*;
    - so sánh phương án;
    - dòng cảnh báo thời gian xe máy là ước tính bản thử nghiệm;
    - nút *Dẫn đường*, *Xem đường cả ngày* (mỗi đoạn một nút), *Xuất Word*, *Đưa vào lịch*.
- **Agent hạ tầng:** quota Maps theo mục 7.3 trong `50-ha-tang-trien-khai.md`; luật lưu dữ liệu Google 30 ngày trong `60-bao-mat-rieng-tu.md`; bài thử trên máy thật ở mục 14 bước 12 vào `70-kiem-thu.md`.
- **Điều phối:** `01-thiet-ke-tong-the.md` mục 8.7 theo ĐX-T6; bảng `tab_place_cache` ở mục 6 theo ĐX-T1.

## 18. Đề xuất quyết định

**Trạng thái các đề xuất bản 1:**

| Số | Nội dung | Trạng thái |
|---|---|---|
| ĐX-T1 | `tab_place_cache` bỏ giờ mở cửa, tọa độ Google 30 ngày | Đã chấp nhận (QĐ-25) |
| ĐX-T2 | Text Search IDs Only rồi Place Details Essentials | Đã chấp nhận |
| ĐX-T3 | Routes TWO_WHEELER mỗi đoạn một lời gọi; tự sắp thứ tự | Đã chấp nhận |
| ĐX-T4 | Link luôn kèm tránh cao tốc, tối đa 9 điểm, cắt ở điểm nghỉ | Đã chấp nhận |
| ĐX-T5 | Luật rủi ro bằng mã | Đã chấp nhận |
| ĐX-T6 | Sửa 01 mục 8.7 | Đã chấp nhận, điều phối sửa |

**Đề xuất mới:**

| Số tạm | Đề xuất | Lý do |
|---|---|---|
| ĐX-T7 | Mốc cứng lưu trong `tab_trip.hard_facts` (jsonb), không tạo bảng `tab_trip_fact` | Ít bảng; mốc cứng chỉ đọc cùng chuyến |
| ĐX-T8 | `/map-links` trả tọa độ và `fallback_url` cho từng điểm thay cho `navigate_uri`; app tự ghép lệnh `google.navigation` | Khớp hành động `open_map_navigation` của 20 và plugin `Maps.navigate` của 30 |
| ĐX-T9 | Cấu trúc một rủi ro theo mục 6.3, dùng chung cho `tab_trip.evaluation` và `tab_trip_option.risks` | `12-api.md` và `11-co-so-du-lieu.md` đang chờ tệp này chốt |
| ĐX-T10 | `find_place` lấy thêm `displayName` (SKU Pro, 5.000 miễn phí); luồng định vị của lịch trình vẫn chỉ dùng Essentials | Người dùng cần thấy tên quán khi chọn; một người dùng thì dư mức miễn phí |

## 19. Phụ lục: giới hạn Maps đã đối chiếu

| Thông số | Giá trị | Nguồn |
|---|---|---|
| Maps URLs cần khóa API | Không | M1 |
| Số `waypoints` tối đa trong Maps URLs | 9; trình duyệt trên điện thoại: 3 | M1 |
| Độ dài link Maps URLs | 2.048 ký tự | M1 |
| Giá trị `travelmode` | `driving`, `walking`, `bicycling`, `two-wheeler`, `transit` | M1 |
| Giá trị `avoid` trong Maps URLs | `tolls`, `highways`, `ferries` | M1 |
| `google.navigation` `mode` | `d` ô tô, `b` xe đạp, `l` xe hai bánh, `w` đi bộ | M2 |
| `google.navigation` `avoid` | `t` phí, `h` cao tốc, `f` phà; ghép được | M2 |
| Routes TWO_WHEELER có Việt Nam | Có (beta) | M13, M18 |
| `intermediates` tối đa | 25 | M15 |
| Route Matrix | Tối đa 625 phần tử; 50 điểm gốc và đích dạng `place_id` hoặc địa chỉ | M20 |
| Mức miễn phí mỗi SKU mỗi tháng | Essentials 10.000; Pro 5.000; Enterprise 1.000 | M8 |
| Lưu `place_id` | Vô thời hạn | M11 |
| Lưu tọa độ | Tối đa 30 ngày | M11, M4 |

## 20. Nguồn

Tất cả truy cập ngày 18/11/2026.

| Mã | Nội dung | Địa chỉ |
|---|---|---|
| M1 | Maps URLs: tìm kiếm, chỉ đường, `waypoints`, `travelmode`, `avoid`, `dir_action`, 2.048 ký tự | https://developers.google.com/maps/documentation/urls/get-started |
| M2 | Lệnh Android cho Google Maps: `google.navigation`, `geo:`, `mode`, `avoid` | https://developer.android.com/guide/components/google-maps-intents |
| M3 | Resolution API cho link Maps | https://developers.google.com/maps/ai/maps-experience-agent-tools/resolution-api |
| M4 | Geocoding: tham số, luật lưu | https://developers.google.com/maps/documentation/geocoding/requests-geocoding ; https://developers.google.com/maps/documentation/geocoding/policies |
| M5 | Trường dữ liệu Places và SKU | https://developers.google.com/maps/documentation/places/web-service/data-fields |
| M6 | Chi tiết SKU | https://developers.google.com/maps/billing-and-pricing/sku-details |
| M7 | Bảng giá | https://developers.google.com/maps/billing-and-pricing/pricing |
| M8 | Mức miễn phí theo SKU, thay đổi 03/2025 | https://developers.google.com/maps/billing-and-pricing/faq ; https://developers.google.com/maps/billing-and-pricing/march-2025 |
| M9 | Text Search (New) | https://developers.google.com/maps/documentation/places/web-service/text-search |
| M10 | Place Details (New) | https://developers.google.com/maps/documentation/places/web-service/place-details |
| M11 | Chính sách Places API: lưu `place_id`, tọa độ 30 ngày | https://developers.google.com/maps/documentation/places/web-service/policies |
| M12 | Routes API `computeRoutes` | https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes |
| M13 | Vùng hỗ trợ xe hai bánh | https://developers.google.com/maps/documentation/routes/coverage-two-wheeled |
| M14 | `RouteModifiers` | https://developers.google.com/maps/documentation/routes/reference/rest/v2/RouteModifiers |
| M15 | Tối ưu điểm dừng, giới hạn 25 | https://developers.google.com/maps/documentation/routes/opt-way |
| M16 | Đánh đổi giao thông, `departureTime` | https://developers.google.com/maps/documentation/routes/config_trade_offs |
| M17 | SKU Routes | https://developers.google.com/maps/billing-and-pricing/sku-details/routes |
| M18 | `RouteTravelMode`: TWO_WHEELER beta, phải cảnh báo người dùng | https://developers.google.com/maps/documentation/routes/reference/rest/v2/RouteTravelMode |
| M19 | Tài nguyên Place: `OpeningHours` | https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places |
| M20 | `computeRouteMatrix`, giới hạn phần tử | https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix ; https://developers.google.com/maps/documentation/routes/usage-and-billing |
| M21 | `optimizeWaypointOrder` tính SKU Pro | https://developers.google.com/maps/documentation/routes/opt-way |
| M22 | Trợ giúp Google Maps: chế độ xe hai bánh | https://support.google.com/maps/answer/11473680 |
| M23 | Độ phủ dữ liệu Maps theo nước | https://developers.google.com/maps/coverage |
| M24 | Quản lý chi phí, quota | https://developers.google.com/maps/billing-and-pricing/manage-costs |
