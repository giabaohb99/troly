# Lịch trình và bản đồ

Người giữ: agent Google. Bản 3 (18/11/2026), gọn hóa theo QĐ-26, QĐ-27. Phase 4 (V1.6).

Module `trip`: nhập lịch trình, bóc tách, định vị, đánh giá rủi ro, đưa phương án, mở Google Maps, xuất Word. Khóa Maps và giá chung ở [40-tich-hop-google.md](40-tich-hop-google.md) mục 9.

**Nguồn chuẩn:**

| Nội dung | Tài liệu |
|---|---|
| Bảng, cột | `11-co-so-du-lieu.md` mục 3.13 (QĐ-26, câu K4, K5) |
| Đường dẫn API, hình dạng `/map-links` | `12-api.md` mục 5.8 |
| Công cụ AI | `20-bo-nao-ai.md` |
| Hàm plugin | `30-app-android.md` (`Maps.navigate`, `Maps.openUrl`, `Maps.isMapsInstalled`) |

Tệp này giữ phần gốc: lược đồ bóc tách (mục 3), luật rủi ro và cấu trúc rủi ro (mục 5), link bản đồ (mục 7). Thông số Google có nguồn ở mục 11.

## 1. Mục tiêu và phạm vi

**Xong khi:**

- tệp *Lich-trinh-Phuoc-Hai-Tra-Vinh.docx* vào thì ra đủ 3 ngày, đủ điểm;
- báo được *Bảo tàng Khmer đóng thứ Hai* và *giờ phà Vũng Tàu – Cần Giờ*;
- bấm một điểm là Google Maps dẫn đường xe máy, tránh cao tốc.

| Làm | Không làm (QĐ-26) |
|---|---|
| Nhập Word, PDF, ảnh, link Maps, câu mô tả | Thời tiết, triều cường |
| Bóc tách bằng Haiku 5.5; đánh giá bằng Sonnet 5.5 (QĐ-27 mục 9) | Xuất PDF |
| Định vị bằng Places (New); thời gian chạy bằng Routes | Dẫn đường trong app |
| Luật rủi ro bằng mã; 2 tới 3 phương án | Đổi điểm giữa các ngày |
| Mở Google Maps bằng URL và lệnh Android; xuất Word | |
| Bảng giờ phà quen do người dùng nhập (QĐ-26) | |

## 2. Luồng

```
POST /api/v1/trips/import ──> 202, status=importing ──> việc trip_import
   lấy chữ + link ──> bóc tách (Haiku) ──> định vị ──> status=draft, điểm uncertain chờ xác nhận
POST /api/v1/trips/{id}/evaluate ──> 202, status=evaluating ──> việc trip_evaluate
   Routes + giờ mở cửa + luật R1..R9 ──> 2–3 phương án ──> Sonnet viết tóm tắt
POST /api/v1/trips/{id}/options/{option_id}/choose ──> status=planned
GET /api/v1/trips/{id}/map-links      POST /api/v1/trips/{id}/export-docx
```

- Hai việc nền chạy bằng job `run_queued_jobs`; app hỏi `GET /api/v1/jobs/{id}`.
- Mỗi bước là một hàm riêng trong `modules/trip/service.py`. Sửa một điểm thì chỉ chạy lại định vị và đánh giá của ngày đó.

## 3. Nhập và bóc tách

### 3.1 Lấy chữ

| Đầu vào | Cách |
|---|---|
| Word | `python-docx`: đoạn văn kèm kiểu (Title, Heading 1, Heading 2), bảng theo hàng và ô. **Link:** đọc thẻ `w:hyperlink` rồi tra `word/_rels/document.xml.rels`, đổi thành `[chữ](url)`; python-docx không có API đọc link |
| PDF, ảnh | Gửi thẳng cho Claude; PDF có lớp chữ thì trích thêm link bằng `pypdf` |
| Link Google Maps | Mục 3.3 |
| Câu mô tả | Claude hỏi lại tối đa 2 câu, chọn điểm bằng `find_place`, rồi gọi `import_trip` với `draft`. Mọi điểm chính phải có `place_id`; không tự nghĩ tên quán |

Tệp trên Drive: chọn qua hộp chọn tệp Android (40 mục 8).

### 3.2 Lược đồ bóc tách (lược đồ duy nhất)

Gọi `extract_structured(purpose="trip_extract", effort="medium", max_tokens=16000)`, model `claude-haiku-5-5`. Model Pydantic đặt ở `modules/trip/schemas.py`.

```
trip: title, travel_mode, origin_text, end_text, start_date|null, nights
  days[]: day_no, weekday_text, date|null, title, route_text
    stops[]: time_text, title,
             category (an_uong|nghi|tham_quan|pha|di_chuyen|khach_san|mua_sam|khac),
             places[]: {label, url, role (main|alternative|backup|generic|via)},
             cost_note, phone, note, optional
  hotels[]: {night_no, label, url, booked, backups[]}
  map_links[]: {day_no, label, url}
  notes[]
  facts[]: {kind (ferry_last|ferry_first|checkin|checkout|hotline|opening_hours|other),
            day_no, value_time, value_text, text}
```

`facts[]` ghi vào bảng `tab_trip_fact` (QĐ-26, câu K4).

**Luật bóc tách** (trong lời nhắc tĩnh):

- **Giờ:** `2h30` là 02:30; `~7h00` là 07:00 kèm `approx`; `10h30–12h30` là khoảng.
- **Vai trò:**
  - các điểm nối bằng *hoặc*: điểm đầu là `main`, sau là `alternative`;
  - điểm sau chữ *Dự phòng*: `backup`;
  - tên món kèm tên vùng mà không có tên quán: `generic`;
  - điểm chỉ đi qua: `via`.
- **Mốc cứng:** câu *chuyến cuối*, *nhận phòng*, *trả phòng*, *hotline* thành `facts`.
- **Không bịa** điểm hay giờ.

**Máy chủ kiểm lại:**

- giờ tăng dần, trừ giờ có `approx`;
- mọi link phải có trong văn bản gốc;
- số ngày khớp số tiêu đề *Ngày N*.

Sai thì gọi lại một lần; vẫn sai thì lưu nháp, đánh dấu chỗ cần sửa.

### 3.3 Link Google Maps trong tệp

Link trong tệp được dùng trước Places API.

| Dạng | Lấy ra |
|---|---|
| `/maps/search/?api=1&query=..&query_place_id=..` | Chuỗi tìm, `place_id` [M1] |
| `/maps/dir/?api=1&origin=..&destination=..&waypoints=a\|b` | Thứ tự tuyến; giá trị `lat,lng` là tọa độ do người dùng đưa (`coord_source = user`) [M1] |
| `maps.app.goo.gl/...` | Xem dưới bảng |

**Link rút gọn:**

1. Gọi Resolution API (`POST https://mapstools.googleapis.com/v1:resolveMapsUrls`): trả `place_id`, tối đa 20 link mỗi lần, tính SKU Text Search IDs Only giá 0 [M3]. Trang không ghi giai đoạn phát hành.
2. Không được thì theo chuyển hướng HTTP. Cách này không có tài liệu chính thức.
3. Vẫn không được thì hỏi người dùng.

**Ghép tọa độ:** điểm đầu hoặc cuối của link tuyến mà chữ mô tả gọi tên một điểm đã biết thì nhận tọa độ đó. Ví dụ: `origin=10.4477939,107.2876573` của link *Khách sạn → ...* là tọa độ khách sạn.

### 3.4 Chuẩn hóa

- **Ngày:** tệp chỉ ghi thứ thì gợi ý thứ Bảy gần nhất khớp thứ của ngày 1; người dùng bấm xác nhận (QĐ-26). Thứ không khớp ngày thì báo R9.
- **Giờ:** ghi `planned_start`, `planned_end`, `stay_minutes` (tên cột của 11). Giờ trống thì suy ra bằng giờ điểm trước, cộng thời gian chạy, cộng thời gian ở lại mặc định:

  | Loại | Phút |
  |---|---|
  | `an_uong` | 45 |
  | `tham_quan` | 60 |
  | `mua_sam` | 20 |
  | `nghi` | 15 |
  | `via` | 0 |

- **`fixed = true`** (mốc cứng, không sắp lại): điểm có giờ rõ không kèm `~`, loại `pha`, `khach_san`, bình minh, hoàng hôn, hoặc có `tab_trip_fact` trỏ tới.

## 4. Định vị và lưu đệm

**Thứ tự tìm** (dừng ở bước đầu có kết quả):

1. tọa độ hoặc `place_id` trong link;
2. `tab_place_cache` theo `(query_norm, bias_key)`;
3. Places API (New);
4. Geocoding, chỉ cho chuỗi là địa chỉ thuần như *144 Võ Thị Sáu Phước Hải* [M4].

Điểm `generic` không định vị: lấy 3 gợi ý gần tuyến bỏ vào `alternatives`.

**Gọi Places cho rẻ.** Giá tính theo trường xin trong `X-Goog-FieldMask` [M5][M6][M7]:

| Lời gọi | Trường | SKU | Miễn phí mỗi tháng | Giá sau mức miễn phí |
|---|---|---|---|---|
| Text Search | `places.id` | IDs Only | Không giới hạn | 0 |
| Place Details | `location`, `formattedAddress`, `types` | Essentials | 10.000 | 5 USD / 1.000 |
| Place Details | thêm `displayName` | Pro | 5.000 | 17 USD / 1.000 |
| Place Details | thêm `regularOpeningHours`, `currentOpeningHours` | Enterprise | 1.000 | 20 USD / 1.000 |

Text Search xin thêm `displayName` hay `location` là cả lời gọi thành SKU Pro.

**Quy trình định vị:**

1. **Text Search**, chỉ xin `places.id`, giá 0 [M9]:
   - `textQuery`, `languageCode=vi`, `regionCode=VN`, `pageSize=3`;
   - `locationBias` là vòng tròn 30 km quanh điểm đã định vị gần nhất trong ngày.
2. **Place Details Essentials** cho kết quả đầu [M10].
3. **Kiểm độ chắc chắn:** từ chính của chuỗi tìm có trong địa chỉ, hoặc `types` khớp loại điểm; và cách điểm trước dưới 80 km. Không đạt thì `resolve_status = uncertain`: app hiện danh sách *Điểm cần xác nhận*, lấy gợi ý qua `/trips/{id}/stops/{stop_id}/resolve`.
4. **Giờ mở cửa** (Enterprise) chỉ gọi lúc đánh giá, cho điểm `tham_quan`, `an_uong`, `mua_sam` có giờ đến.
5. Gặp `CLOSED_PERMANENTLY` thì báo rủi ro đỏ [M10].

Công cụ `find_place` xin thêm `displayName` (SKU Pro) để người dùng nhận ra quán.

**Luật lưu dữ liệu Google** [M11][M4]:

- `place_id` lưu mãi.
- Tọa độ lấy từ Google lưu tối đa 30 ngày.
- Giờ mở cửa không lưu; chỉ lưu kết luận do app viết (ví dụ *đóng thứ Hai*).

Áp vào bảng:

- **`tab_place_cache`:** `lat`, `lng`, `formatted_address` bị xóa khi `fetched_at` quá 30 ngày.
- **`tab_trip_stop`:**
  - `coord_source = user`: giữ mãi;
  - `coord_source = google`: quá 30 ngày thì `cleanup_old_data` đặt rỗng (QĐ-26, câu K19); mở chuyến thì gọi lại Place Details Essentials.
- **`tab_route_cache`:** giữ 30 ngày. Điều khoản lưu kết quả Routes phải đọc lại trước khi viết mã (QĐ-26, câu K25).

## 5. Đánh giá rủi ro

### 5.1 Thời gian chạy

Mỗi đoạn tuyến của một ngày gọi **Compute Routes** một lần [M12]:

- `travelMode=TWO_WHEELER`: Việt Nam có trong vùng hỗ trợ [M13];
- `routeModifiers.avoidHighways=true` [M14];
- `intermediates` tối đa 25 [M15];
- `departureTime` ở tương lai, `routingPreference=TRAFFIC_UNAWARE` [M16];
- field mask: `routes.legs.distanceMeters`, `routes.legs.duration`, `routes.legs.steps.navigationInstruction`, `routes.warnings`.

Từng chặng ghi vào `tab_route_cache`.

**Giá:** mọi lời gọi xe hai bánh là SKU **Enterprise**: 1.000 miễn phí mỗi tháng, sau đó 15 USD / 1.000 [M17][M7]. Mỗi ngày của chuyến tốn 1 tới 2 lời gọi.

**Beta:** TWO_WHEELER đang beta; app phải cảnh báo người dùng [M18]. Luôn hiện dòng *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch*. Lời gọi lỗi thì gọi lại bằng `DRIVE` + `avoidHighways`, ghi *ước tính theo ô tô*.

**Giờ mở cửa** [M19]:

- ngày đến trong 7 ngày tới thì dùng `currentOpeningHours` (có `specialDays`), không thì dùng `regularOpeningHours`;
- `periods[].open/close.day` từ 0 (Chủ nhật) tới 6, theo giờ địa phương; không giả định phần tử đầu là Chủ nhật.

### 5.2 Luật rủi ro (chạy bằng mã)

| Mã | Luật | Đỏ | Vàng |
|---|---|---|---|
| R1 Trễ | Giờ đến (Google × `trip.speed_factor` cộng ở lại) so với `planned_start` | Trễ trên 30 phút, hoặc lỡ điểm `fixed` | Trễ 10 tới 30 phút, hoặc dư dưới 10 phút trước điểm `fixed` |
| R2 Giờ mở cửa | Mục 5.1 | Đóng cả ngày đó, hoặc đã đóng hẳn | Đến trong 30 phút trước giờ đóng; không có dữ liệu |
| R3 Phà | Giờ tới bến so với chuyến cuối: lấy `tab_trip_fact` (`ferry_last`), không có thì lấy bảng giờ phà quen (mục 5.4) | Tới sau chuyến cuối trừ 30 phút | Không biết chuyến cuối (nhắc gọi hotline); dư dưới 60 phút |
| R4 Chạy liên tục | Phút chạy giữa hai điểm dừng từ 15 phút | Trên 120 phút | Trên `trip.ride_break_minutes` (90) |
| R5 Chạy đêm | Chặng trong khung `trip.night_start` tới `trip.night_end` (18:00 tới 05:30, QĐ-26) | Khung 03:00 tới 05:00, hoặc quốc lộ nhiều xe tải (`QL1`, `QL51` trong `navigationInstruction`) | Còn lại trong khung đêm |
| R6 Tổng giờ chạy | Trong ngày | Trên 8 giờ | Trên 6 giờ |
| R7 Phòng | Tới so với `checkin`, rời so với `checkout` (mặc định 14:00 và 12:00) | Trả phòng trễ quá 60 phút | Tới trước giờ nhận phòng |
| R8 Chưa định vị | Điểm `main` không có tọa độ | | Luôn vàng |
| R9 Thứ lệch ngày | `weekday_text` khác thứ của ngày | Luôn đỏ | |

**Cấu trúc một rủi ro** (dùng cho `tab_trip.evaluation.risks` và `tab_trip_option.risks`; QĐ-26, câu K5):

```
{ "code": "R2", "level": "red|yellow", "day_no": 3, "stop_id": 41,
  "message": "Bảo tàng Văn hóa Khmer đóng cửa thứ Hai",
  "suggestion": "Bỏ điểm này hoặc thay bằng Chùa Âng",
  "checked_at": "2026-11-18T10:00:00+07:00" }
```

### 5.3 Phương án và vai trò của Sonnet

**Sắp thứ tự:**

1. Điểm `fixed` chia ngày thành khung; điểm không cố định chỉ đổi chỗ trong khung của nó.
2. Ma trận thời gian lấy bằng **Compute Route Matrix** với `DRIVE` + `avoidHighways` (SKU Essentials, 10.000 phần tử miễn phí; tối đa 625 phần tử mỗi lời gọi) [M17][M20].
3. Khung có tới 8 điểm thì thử mọi hoán vị; lớn hơn thì láng giềng gần nhất cộng 2-opt.
4. Hàm chi phí: phút chạy cộng phạt R1, R2.
5. Không dùng `optimizeWaypointOrder`: SKU Pro, không rõ có chạy với xe hai bánh không, không biết giờ mở cửa [M21].
6. Chốt thứ tự xong mới gọi Compute Routes xe hai bánh để ra số liệu cuối.

**Ba phương án:**

| Phương án | Cách dựng |
|---|---|
| **Đúng giờ, ít rủi ro** | Sửa mọi rủi ro đỏ: thêm điểm nghỉ, rời sớm, bỏ điểm `optional` trước mốc cứng, thay điểm đóng cửa bằng điểm dự phòng |
| **Nhiều điểm** | Giữ đủ điểm, chỉ sắp lại; ghi rủi ro còn lại |
| **Nhàn** | Như *Đúng giờ*, bỏ thêm điểm `optional`, ở lại lâu gấp 1,5 lần, mỗi ngày dưới 6 giờ chạy |

Mỗi phương án ghi `total_km`, `total_ride_minutes`, `night_ride_minutes`, `red_count`, `yellow_count`, `changes`, `plan`. Phương án trùng thì gộp.

**Sonnet 5.5** (`purpose = trip_evaluate`, `claude-sonnet-5-5`, QĐ-27 mục 9):

- nhận số liệu và rủi ro đã tính;
- viết `summary` 2 câu cho mỗi phương án và lời khuyên ngắn (mang gì, đổ xăng ở đâu, gọi phà);
- **không đổi số, không thêm hay bỏ rủi ro**. Máy chủ kiểm số trong chữ khớp số đã tính.

### 5.4 Bảng giờ phà quen (QĐ-26)

- Người dùng tự nhập ba tuyến: Vũng Tàu – Cần Giờ, Cát Lái, Bình Khánh. Mỗi tuyến có `place_id` hoặc chuỗi tìm của bến, giờ chuyến đầu, giờ chuyến cuối, hotline, ghi chú, ngày cập nhật.
- R3 dùng bảng này khi tệp lịch trình không ghi giờ phà.
- Thông tin quá 180 ngày thì R3 vẫn nhắc gọi hotline. Google không có dữ liệu giờ phà.
- Chỗ lưu: khóa cài đặt `trip.ferries` (jsonb), đề nghị 11 thêm.

### 5.5 Chi phí một chuyến 3 ngày, khoảng 40 điểm

**Maps** (đều trong mức miễn phí, quota chặn cứng theo ngày ở 40 mục 11):

| Lời gọi | Số lần |
|---|---|
| Text Search IDs Only | khoảng 45 |
| Place Details Essentials | 40 tới 60 |
| Place Details Enterprise | khoảng 15 |
| Route Matrix | khoảng 150 phần tử |
| Compute Routes Enterprise | 12 tới 18 |

**AI** (giá ở `20-bo-nao-ai.md`):

| Bước | Model | Token ước tính | Chi phí |
|---|---|---|---|
| Bóc tách | Haiku 5.5 (0,10 / 0,50 USD mỗi triệu token vào / ra) | Khoảng 12.000 vào, 10.000 ra (kể cả suy nghĩ) | Khoảng 0,006 USD |
| Đánh giá | Sonnet 5.5 (2 / 10 USD mỗi triệu token) | Khoảng 10.000 vào, 2.000 ra | Khoảng 0,04 USD |

Tổng dưới 0,05 USD mỗi chuyến; mỗi lần đánh giá lại tốn thêm khoảng 0,04 USD.

## 6. Lưu

- **Trạng thái chuyến:** `importing` → `draft` (hoặc `failed`) → `evaluating` → `draft` hoặc `planned`.
- **Đánh giá xong:** ghi các `tab_trip_option` và `tab_trip.evaluation` (`{evaluated_at, risks}`), `evaluated_at`.
- **Chọn phương án:**
  - `chosen = true`, `chosen_option_id`;
  - ghi đè `tab_trip_stop` theo `plan`;
  - `status = planned`.
- **Sửa tay một điểm:** đánh giá lại riêng ngày đó.
- **Đưa vào lịch** (`/trips/{id}/to-calendar`): mỗi ngày một sự kiện cả ngày, cộng sự kiện có giờ cho mốc cứng. `remind_source = app`; phà và trả phòng đặt `is_alarm`.
- **Xóa chuyến qua trợ lý:** thẻ duyệt (`tool_name = delete_trip`, QĐ-27). Xóa trên màn chuyến đi theo `12-api.md`.
- **Hỏi *lấy lịch trình Trà Vinh*:** `get_trip` trả tóm tắt theo ngày, kèm nút mở màn chuyến.

## 7. Mở bản đồ

Máy chủ dựng mọi link ở một chỗ (`modules/trip/service.py`), dùng chung cho `GET /trips/{id}/map-links` và công cụ `open_route`. Hành động trả cho app có dạng phẳng theo `12-api.md` mục 5.8 (QĐ-26). Link không cần khóa, không tính tiền [M1][M2].

| Nút | Hành động | Link |
|---|---|---|
| Dẫn đường tới một điểm | `open_map_navigation` `{lat, lng, mode: "l", avoid: "h"}` → `Maps.navigate` | `google.navigation:q=<lat>,<lng>&mode=l&avoid=h`: xe hai bánh, tránh cao tốc, luôn đi từ vị trí hiện tại, không có điểm dừng [M2]. Điểm chưa có tọa độ không có nút này |
| Xem đường cả ngày | `open_map_directions` `{urls, segment_labels}` | `https://www.google.com/maps/dir/?api=1&origin=<lat,lng>&destination=<lat,lng>&waypoints=<lat,lng>\|...&travelmode=two-wheeler&avoid=highways` [M1] |
| Xem một điểm | `open_map_place` `{query, place_id}` | `https://www.google.com/maps/search/?api=1&query=<tên>&query_place_id=<id>`; Maps dùng `place_id` trước [M1] |

**Chế độ xe máy ở Việt Nam:**

- Routes API có Việt Nam trong vùng hỗ trợ [M13].
- Trợ giúp Google Maps chỉ ghi *một số nơi*, không có danh sách nước [M22].
- Maps URLs chỉ chạy `two-wheeler` khi người dùng đang ở nước hỗ trợ [M1].

Vì vậy app Maps ở Việt Nam có nhận `two-wheeler` và `mode=l` không thì **chưa xác minh**; đây là bài thử đầu tiên trên Galaxy S25+. Dù không nhận, `avoid=highways` vẫn chặn cao tốc. Đó đúng là việc mà tệp mẫu đang dặn người dùng bấm tay.

**Chia đoạn** [M1]: Maps URLs nhận tối đa **9** điểm dừng (trình duyệt điện thoại chỉ **3**) và link dài tối đa **2.048** ký tự.

1. Cắt trước ở điểm nghỉ dài (khách sạn, ngủ trưa, `stay_minutes` từ 90).
2. Nhóm còn quá `max_waypoints + 2` điểm thì cắt tiếp. Điểm cuối đoạn trước là điểm đầu đoạn sau.
3. Dùng `lat,lng` (khoảng 22 ký tự) thay tên đã mã hóa (thường trên 100 ký tự). Quá 2.048 ký tự thì bớt một điểm.
4. `max_waypoints` do app gửi: 9, hoặc 3 khi `Maps.isMapsInstalled()` trả `false`.
5. Điểm `alternative`, `backup`, `generic` không vào tuyến; chúng có nút *Xem một điểm*.

**Trong chat:** *chỉ đường tới chỗ ăn trưa*:

1. `open_route` tìm chuyến hôm nay, điểm `an_uong` kế tiếp có `planned_start` từ 10:30 tới 14:00.
2. Trả nút `open_map_navigation`. Claude chỉ thấy dòng *Đã tạo nút ...*, không thấy URL.

## 8. Xuất Word theo kiểu tệp mẫu

**Thông số đo từ tệp mẫu:**

| Phần | Kiểu |
|---|---|
| Trang | A4 dọc; lề trên, dưới 1200 twip; lề trái, phải 1440 twip |
| Chữ | Arial 11 |
| Title | Arial 18 đậm, màu `1F3864` |
| Heading 1 | Arial 14 đậm, màu `1F3864` |
| Heading 2 | Arial 12 đậm |
| Bảng giờ | 2 cột 1500 / 7526 twip. Hàng đầu đậm, nền `DCE6F1`; viền `BFBFBF`; lề ô 60 / 100 twip |
| Link | Màu `0563C1`, gạch chân |

**Bố cục:**

1. Tiêu đề, một dòng tóm tắt.
2. Một dòng *Link chỉ đường đã đặt sẵn chế độ xe máy và tránh cao tốc*, thay câu *bấm chọn chế độ xe máy* của tệp mẫu.
3. Mỗi ngày gồm:
   - Heading 1 *Ngày N (thứ X, dd/mm): A → B*;
   - dòng *Đường đi* kèm km và giờ chạy;
   - bảng giờ: tên điểm là link *Xem một điểm*; dự phòng nối bằng *hoặc* hoặc *Dự phòng:*;
   - Heading 2 *Bản đồ ngày N*, mỗi đoạn tuyến một link.
4. *Khách sạn*.
5. *Lưu ý*: rủi ro còn lại, lưu ý gốc, dòng cảnh báo thời gian xe máy.

**Cách làm:** python-docx không có hàm thêm link. Phải tạo quan hệ `RT.HYPERLINK` rồi chèn `w:hyperlink` (`modules/trip/docx_export.py`). Tệp lưu R2 (`purpose = trip_export`). Lưu lên Drive qua `POST /files/{id}/drive` (40 mục 8).

**Kiểm vòng tròn:** xuất ra rồi nhập lại phải ra cùng ngày, điểm, `place_id`, giờ.

## 9. Chạy thử trên tệp mẫu Phước Hải – Trà Vinh

**Tệp có:**

- 3 bảng giờ (12, 11 và 8 hàng, tổng 31 hàng);
- 6 link tuyến;
- 43 link địa điểm: 41 link `query=` và 2 link rút gọn cùng trỏ Hotel Quốc Hương.

**Kết quả mong đợi** (bài kiểm chấp nhận Phase 4):

| Ngày | Điểm chính | Mốc cứng | Rủi ro mong đợi |
|---|---|---|---|
| 1 (thứ 7) | Cần Thơ 02:30 → cầu Mỹ Thuận (`via`) → phà Cát Lái ~07:00 → chợ Phước Hải → Cafe Phượng → Bánh canh cô Phờ (`optional`) → Hotel Quốc Hương 13:00 → bánh khọt → Đèo Nước Ngọt, Kỳ Vân → Channel 17:00 → Hàu chị Oanh → bờ kè, Ốc Thanh Vân, bánh tráng cô Loan | `checkin` 13:00 | R5 đỏ (QL1A khung 03:00–05:00); R4 (Cần Thơ → Cát Lái khoảng 4 tiếng rưỡi, gợi ý 2 điểm nghỉ); R3 vàng (phà Cát Lái chưa có giờ nếu bảng phà chưa nhập); R6 vàng |
| 2 (chủ nhật) | Làng chài 05:20 → Hủ tiếu Vui → Hồ Sở Bông, Minh Đạm → trả phòng 10:45 → Cơm niêu Làng Chài 11:00 → An Nhứt (`optional`) → bến phà Vũng Tàu ~13:30 → Tắc Suất, Lâm Viên Cần Giờ → phà Bình Khánh 16:15 → 68 Hotel Gò Công ~17:45 | `checkout` 10:45; `ferry_last` 17:00; `hotline` 0254 6525 656 | R3 vàng hoặc đỏ (chặng sau bữa trưa sát giờ; gợi ý bỏ An Nhứt như tệp đã dặn); R2 vàng (Lâm Viên chủ nhật); R5 vàng (về Gò Công lúc chạng vạng) |
| 3 (thứ 2) | Gò Công 06:30 → cầu Rạch Miễu (`via`) → Ao Bà Om, Chùa Âng ~10:30 → bún nước lèo (`generic`) → cafe 13:00 → Chùa Hang 14:45 → bánh tét Trà Cuôn → Cần Thơ ~18:30 | | **R2 Bảo tàng Văn hóa Khmer thứ Hai** (đỏ nếu giờ mở cửa không có thứ Hai; vàng nếu thiếu dữ liệu); R4 vàng (3 tiếng liền, gợi ý nghỉ ở Bến Tre); R5 vàng |

**Định vị:**

- Khách sạn ngày 1 có tọa độ người dùng (`origin` của link tuyến) và `place_id` từ link rút gọn.
- Các điểm *bánh giá*, *hủ tiếu Gò Công*, *mắm tôm chà*, *bún nước lèo*, *bánh canh Bến Có*, *bánh tét Trà Cuôn* là `generic`.
- *Làng chài Phước Hải*, *Bờ kè Trần Hưng Đạo* dễ thành `uncertain`.

**Ngày đi:** chọn 21/11/2026 (thứ Bảy) thì ngày 3 là thứ Hai 23/11, khớp tệp.

**Link mong đợi** (`max_waypoints = 9`):

- ngày 1 cắt ở khách sạn thành 2 link, như tệp mẫu;
- ngày 2 cắt ở khách sạn và bến phà thành 3 link;
- ngày 3 một link.

Mọi link có `travelmode=two-wheeler&avoid=highways`, dài khoảng 300 tới 400 ký tự.

## 10. Dữ liệu, API, kiểm thử, rủi ro

**Dữ liệu:** dùng đúng `11-co-so-du-lieu.md` mục 3.13 (`tab_trip`, `tab_trip_stop`, `tab_trip_option`, `tab_trip_fact`, `tab_place_cache`, `tab_route_cache`). Đề nghị 11:

- thêm `tab_trip.evaluation jsonb` (QĐ-26, câu K5);
- thêm `opening_hours`, `other` vào `tab_trip_fact.kind` (câu K4);
- cấu trúc rủi ro ở 11 dùng `message`, `suggestion`, `checked_at` như mục 5.2 (đang ghi `text`, `hint`);
- thêm khóa cài đặt `trip.night_start`, `trip.night_end`, `trip.ride_break_minutes`, `trip.speed_factor`, `trip.ferries`.

**API:** dùng đúng `12-api.md` mục 5.1 và 5.8, không xin thêm đường. Công cụ AI theo `20-bo-nao-ai.md`: `import_trip`, `evaluate_trip`, `save_trip`, `list_trips`, `get_trip`, `find_place`, `open_route`, `export_trip_docx`, `delete_trip`.

**Kiểm thử** (QĐ-27: phần dễ sai):

- **Đọc Word:** tệp mẫu ra 31 hàng, 6 link tuyến, 2 link rút gọn, chuỗi tiếng Việt giải mã đúng.
- **Chuẩn hóa giờ:** `2h30`, `~7h00`, `10h30–12h30`.
- **Field mask:** Text Search chỉ xin `places.id`; luồng định vị không xin trường Pro, Enterprise.
- **Luật R1 tới R9:** mỗi luật có ca đỏ, ca vàng, ca không báo; có ca bảo tàng thứ Hai, ca phà tới sau 16:30 khi chuyến cuối 17:00.
- **Chia đoạn link:** không quá 9 (hoặc 3) điểm dừng; đoạn sau nối đoạn trước; dưới 2.048 ký tự; có `travelmode=two-wheeler&avoid=highways`.
- **Số trong tóm tắt của Sonnet** khớp số đã tính.
- **Xuất Word:** kiểm vòng tròn.
- **Bóc tách thật tệp mẫu:** chạy tay.
- **Thử trên Galaxy S25+:**
  - `mode=l` và `two-wheeler` mở chế độ nào;
  - link 9 điểm dừng mở đủ điểm không;
  - Resolution API đọc được link rút gọn không.

**Rủi ro:**

| Rủi ro | Giảm nhẹ |
|---|---|
| Maps ở Việt Nam bỏ qua chế độ xe máy | Luôn kèm tránh cao tốc; thử trên máy đầu Phase 4 |
| Thời gian xe hai bánh lệch (beta) | `trip.speed_factor` chỉnh được sau vài chuyến; dòng cảnh báo cố định |
| Places tìm nhầm quán cùng tên | `locationBias` theo ngày; kiểm khoảng cách; hỏi lại; ưu tiên link trong tệp |
| Hết SKU Enterprise | Chỉ gọi khi cần; quota chặn cứng |
| Hiểu sai điều khoản lưu dữ liệu | Thiết kế theo cách chặt; đọc lại điều khoản trước khi viết mã |
| Không có nguồn giờ phà | Bảng phà quen do người dùng nhập; R3 luôn nhắc hotline |
| Claude bóc sai hoặc bịa | Kiểm link có trong tệp, kiểm giờ; người dùng xem nháp trước khi đánh giá |

**Kiểm trước khi viết mã:** điều khoản lưu dữ liệu Maps và Routes (QĐ-26, câu K25).

**Đề xuất quyết định:** bảng giờ phà quen lưu ở khóa `trip.ferries` (mục 5.4), vì câu 28 của QĐ-26 chưa chỉ chỗ lưu. Đã ghi ở `bang-viec.md` mục 4.

## 11. Nguồn

Truy cập ngày 18/11/2026.

| Mã | Nội dung | Địa chỉ |
|---|---|---|
| M1 | Maps URLs: tìm kiếm, chỉ đường, 9 điểm dừng (3 trên trình duyệt điện thoại), 2.048 ký tự, `travelmode`, `avoid` | https://developers.google.com/maps/documentation/urls/get-started |
| M2 | Lệnh Android: `google.navigation`, `mode`, `avoid` | https://developer.android.com/guide/components/google-maps-intents |
| M3 | Resolution API | https://developers.google.com/maps/ai/maps-experience-agent-tools/resolution-api |
| M4 | Geocoding, luật lưu | https://developers.google.com/maps/documentation/geocoding/policies |
| M5 | Trường Places và SKU | https://developers.google.com/maps/documentation/places/web-service/data-fields |
| M6 | Chi tiết SKU | https://developers.google.com/maps/billing-and-pricing/sku-details |
| M7 | Bảng giá | https://developers.google.com/maps/billing-and-pricing/pricing |
| M9 | Text Search (New) | https://developers.google.com/maps/documentation/places/web-service/text-search |
| M10 | Place Details (New) | https://developers.google.com/maps/documentation/places/web-service/place-details |
| M11 | Chính sách Places: `place_id` lưu mãi, tọa độ 30 ngày | https://developers.google.com/maps/documentation/places/web-service/policies |
| M12 | `computeRoutes` | https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes |
| M13 | Vùng hỗ trợ xe hai bánh | https://developers.google.com/maps/documentation/routes/coverage-two-wheeled |
| M14 | `RouteModifiers` | https://developers.google.com/maps/documentation/routes/reference/rest/v2/RouteModifiers |
| M15 | Tối ưu điểm dừng, 25 điểm | https://developers.google.com/maps/documentation/routes/opt-way |
| M16 | `departureTime`, giao thông | https://developers.google.com/maps/documentation/routes/config_trade_offs |
| M17 | SKU Routes | https://developers.google.com/maps/billing-and-pricing/sku-details/routes |
| M18 | TWO_WHEELER beta, phải cảnh báo | https://developers.google.com/maps/documentation/routes/reference/rest/v2/RouteTravelMode |
| M19 | `OpeningHours` | https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places |
| M20 | `computeRouteMatrix`, 625 phần tử | https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix |
| M21 | `optimizeWaypointOrder` tính SKU Pro | https://developers.google.com/maps/documentation/routes/opt-way |
| M22 | Trợ giúp Google Maps: xe hai bánh | https://support.google.com/maps/answer/11473680 |
