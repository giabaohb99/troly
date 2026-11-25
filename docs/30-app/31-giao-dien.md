# Giao diện

Ngày lập: 18/11/2026. Người giữ: agent app Android. Trạng thái: bản 3, gọn hóa theo QĐ-26, QĐ-27 và `80-ra-soat/81-ra-cheo-lan-2.md`.

Mọi màn hình, điều hướng, luồng và trạng thái của app Trợ lý. Lớp gốc ở [30-app-android.md](30-app-android.md). Sơ đồ khung vẽ bằng ký tự; `[Gửi]` là nút, `(Mic)` là icon lucide. Nguồn chuẩn: bảng theo `11`, API theo `12` (`/api/v1`), kiểu hành động theo `20` với vỏ phẳng (QĐ-26), luật duyệt theo QĐ-27.

## 1. Mục tiêu

- **Một app xem hết** cho một người dùng: chat, tin nhắn, lịch và việc, chi tiêu, lịch trình, báo cáo, cài đặt, tìm.
- **Một tay, 1 tới 2 chạm** cho việc thường ngày; gõ một câu cho trợ lý luôn là đường tắt.
- **Cùng phong cách app gym**: nền tối, màu nhấn xanh chanh, thẻ bo tròn, icon lucide, popup trong app.

## 2. Phạm vi

| Phase | Bản | Màn và luồng |
|---|---|---|
| 1 | V1.0, V1.1 | Đăng nhập, Chat (nhãn model, *Nghĩ kỹ*, nguồn research), Tìm, Chi tiêu (qua chat và màn), Cài đặt cơ bản, báo bản APK mới |
| 2 | V1.2, V1.3 | Thiết lập máy, Hộp tin, chi tiêu tự động, Kiểm tra máy, App được nghe |
| 3 | V1.4 | Lịch và việc, kết nối Google |
| 4 | V1.6, V1.7 | Lịch trình, bản đồ, Báo cáo |
| 5 | V1.8 | Gmail trong hộp tin, xuất Sheets, Drive |

Màn chưa tới phase vẫn có ô trên thanh dưới, hiện trạng thái rỗng *Có từ Phase N*. Ngoài phạm vi V1: gym, sức khỏe, màn duyệt mã tự phát triển, máy tính bảng, nền sáng.

## 3. Thiết kế

### 3.1 Phong cách

Chép nguyên luật giao diện của app gym (ĐX-31-02):

- React 19, Vite (cổng 5190, `50`), TypeScript, Tailwind 4 cấu hình bằng CSS ở `src/index.css`, shadcn trong `src/shared/ui/`, TanStack Query, react-router, sonner, recharts.
- Màu chỉ là token (`:root` sáng và `.dark` tối), cấm hex lẻ. Giao diện **Theo máy** (mặc định), **Sáng** hoặc **Tối** chọn ở Cài đặt, lưu trên máy (QĐ-37, `src/core/theme.ts`); thanh trạng thái và thanh điều hướng Android đổi màu theo (`System.setBarStyle`). Bộ token khởi đầu là của app gym; thêm `--app-1` tới `--app-6` (nhãn app trong Hộp tin), `--income`, `--transfer`.
- Icon chỉ `lucide-react`, cấm emoji. Thông báo, xác nhận, nhập liệu bằng `sonner`, `ConfirmDialog`, `Dialog`; cấm `alert`, `confirm`, `prompt`. Nút lưu chặn bấm đúp bằng `useRef`.
- Cột giữa `max-w-lg`, lề 16 px, vùng an toàn `env(safe-area-inset-*)`, vùng chạm từ 44 px.
- Tiền `45.000 đ`, tóm tắt `45k`, `1,2 tr`; ngày `Thứ Hai, 18/11`; giờ 24 giờ, giờ Việt Nam.
- Trợ lý xưng **em**; chữ trên nút viết trung tính (*Lưu*, *Duyệt*, *Bỏ*).
- Ô chat: trên điện thoại Enter xuống dòng, gửi bằng nút gửi; trên máy tính Enter gửi, Shift+Enter xuống dòng.

### 3.2 Điều hướng

Thanh dưới 5 ô (ĐX-31-01): **Trợ lý** (`MessageCircle`), **Hộp tin** (`Inbox`, chấm số tin quan trọng chưa xem), **Lịch** (`CalendarDays`), **Chi tiêu** (`Wallet`), **Thêm** (`LayoutGrid`, tấm trượt gồm Lịch trình, Báo cáo, Cài đặt).

| Đường dẫn | Màn |
|---|---|
| `/` | Chat |
| `/tim?q=` | Tìm |
| `/hop-tin`, `/hop-tin/:conversationKey` | Hộp tin, một cuộc trò chuyện |
| `/lich?xem=ngay\|tuan\|thang&date=`, `/lich/viec` | Lịch, Việc |
| `/lich/su-kien/:id`, `/lich/viec/:id` | Hộp sửa (đích của thông báo nhắc) |
| `/chi-tieu?ky=` | Chi tiêu |
| `/lich-trinh`, `/lich-trinh/:id?ngay=` | Lịch trình |
| `/bao-cao?ky=` | Báo cáo |
| `/cai-dat`, `/cai-dat/<mục>` | Cài đặt |
| `/dang-nhap`, `/thiet-lap` | Đăng nhập, Thiết lập máy |

Đường dẫn sâu `troly://<đường dẫn>` bắt bằng `appUrlOpen`. Nút quay lại: đóng hộp thoại, rồi về màn cha, rồi về Trợ lý, ở Trợ lý thì thu nhỏ app.

### 3.3 Hành động trợ lý và thẻ duyệt

Hành động đến qua sự kiện `action` của luồng SSE và mảng `actions` của mỗi tin (`12` mục 3.9, 5.3). Vỏ phẳng: trường nằm ngay trong đối tượng, có `id` và `type`.

| `type` | Hiện thành | Khi chạm |
|---|---|---|
| `open_map_navigation` | Nút viền to, `Navigation` | `Maps.navigate` |
| `open_map_directions` | Một nút `Map` mỗi URL, nhãn theo `segment_labels` | `Maps.openUrl` |
| `open_map_place` | Nút viền, `MapPin` | Mở URL tìm địa điểm |
| `open_link` | Nút viền, icon theo `kind` (`FileText`, `Mail`, `Sheet`, `ExternalLink`) | Mở ngoài app; chỉ nhận `https` |
| `open_screen` | Nút chữ nhỏ `ChevronRight`; ngay sau công cụ ghi dữ liệu thì thành dòng xác nhận `CircleCheck` (ví dụ *Sửa khoản này*) | Chuyển màn theo `screen` |
| `memory_changed` | Dòng nhỏ `Brain` *Đã ghi nhớ: ...*, `[Hoàn tác]` | Khôi phục bản cũ |
| `confirm` | Thẻ duyệt | Mục dưới |
| `choices` | Hàng nút gợi ý nhỏ | Gửi `value` như tin của người dùng |

`type` lạ bị bỏ qua. Giá trị `screen` và đường dẫn: `chat` (`/`), `inbox`, `inbox_conversation` (`conversation_key`), `calendar_day` (`date`), `event_detail`, `task_list`, `task_detail`, `expense_list`, `expense_detail`, `trip_list`, `trip_detail` (`day_no`), `report`, `settings_google`, `settings_listened_apps`, `settings_device_check`, `settings_profile`, `settings_ai_cost`.

**Thẻ duyệt chỉ cho** (QĐ-27): gửi thư Gmail, lưu sự kiện có khách mời, chia sẻ tệp ra ngoài, trả lời tin (V2), xóa hàng loạt, xóa cả chuyến. Không có vân tay.

```
┌──────────────────────────────────────────┐
│ (ShieldCheck) Gửi thư cho anh Minh       │
│ Đến: minh@... · Trả lời: Lịch họp thứ Năm│
│ Nội dung: Chào anh, em xác nhận 9:00 ... │
│ [Xem đủ]                                 │
│ [   Bỏ   ]              [   Duyệt   ]    │
│ Hết hạn sau 23 giờ                       │
└──────────────────────────────────────────┘
```

- Thẻ hiện đúng nội dung sẽ chạy (người nhận, nguyên văn, số dòng bị xóa). Duyệt chỉ bằng nút (`POST /chat/actions/{id}/approve`, `.../reject`); gõ *ok* không duyệt. Hạn 24 giờ.
- Trạng thái: `pending` (hai nút), đang gửi (vòng quay, chỉ trên app), `done` (một dòng *Đã gửi lúc 14:32*), `failed` (câu lỗi, `[Thử lại]`), `rejected` (*Đã bỏ*), `expired` (*Hết hạn, nhắn lại nếu vẫn cần*).
- **Xóa một dòng** (qua trợ lý hay trên màn) làm ngay, hiện toast *Đã xóa* với nút *Hoàn tác* trong 8 giây.

### 3.4 Trạng thái chung

| Trạng thái | Cách hiện |
|---|---|
| Đang tải | Khung xương đúng hình nội dung; tải lại thì `RefreshCw` nhỏ cạnh dòng phụ |
| Rỗng | Thẻ giữa màn: icon màu nhấn, 1 tới 2 câu vì sao trống và làm gì tiếp, 1 nút |
| Lỗi tải | Thẻ viền màu lỗi, câu `message` của phong bì, `[Thử lại]` |
| Lỗi khi lưu | Toast màu lỗi; hộp sửa giữ dữ liệu đã nhập |
| Mất mạng | Dải `WifiOff`: *Mất mạng. Đang xem dữ liệu lúc 10:32.* Nút ghi khóa với chữ *Cần mạng* |
| Thiếu quyền | Dải `TriangleAlert`, một câu, `[Bật]` mở đúng bước ở Kiểm tra máy |
| Trợ lý lỗi | `AI_UNAVAILABLE`: bóng tin có *Trợ lý đang lỗi, thử lại sau.* và `[Gửi lại]` |
| Vượt mức cảnh báo chi phí tháng | Dải thông tin ở Chat: *Chi phí AI tháng này 212 USD, quá mức cảnh báo 200 USD.* Không chặn (QĐ-15) |
| Có bản mới | Dải ở Chat (luồng 5) |

**Lưu đệm khi mất mạng:** TanStack Query lưu bền vào IndexedDB của WebView, hạn 7 ngày, chỉ cho chat hôm nay, 100 cuộc hộp tin mới nhất, lịch 14 ngày tới và việc chưa xong, chi tiêu tháng này, chuyến đang đi và sắp đi, báo cáo cuối. Ghi luôn cần mạng, trừ chat: tin chưa gửi được giữ trong ô nhập với `[Gửi lại]`. Đăng xuất xóa hết.

### 3.5 Màn hình

#### Đăng nhập (Phase 1)

Email, mật khẩu, `[Đăng nhập]`. Địa chỉ api gắn sẵn. Sai mật khẩu: câu lỗi dưới ô. Đăng nhập một lần, mã làm mới 365 ngày (QĐ-27); không có màn khóa.

#### Chat (Phase 1, màn chính)

```
┌──────────────────────────────────────────┐
│ Trợ lý               (Search)(Volume2)(…)│
│ tháng này 1,84 USD                       │
├──────────────────────────────────────────┤
│                    ┌───────────────────┐ │
│                    │ cơm trưa 45k      │ │
│                    └───────────────────┘ │
│ ┌──────────────────────────────┐         │
│ │ Đã ghi 45.000 đ, Ăn uống.    │         │
│ └──────────────────────────────┘         │
│ Haiku 5.5                                │
│ (CircleCheck) Sửa khoản này          (>) │
│                    ┌───────────────────┐ │
│                    │ giá vàng hôm nay  │ │
│                    └───────────────────┘ │
│ ┌──────────────────────────────┐         │
│ │ SJC mua 92,1 tr, bán 94,1 tr │         │
│ │ một lượng [1].               │         │
│ └──────────────────────────────┘         │
│ Sonnet 5.5 · có tìm web                  │
│ Nguồn: [1] sjc.com.vn  [2] vnexpress.net │
├──────────────────────────────────────────┤
│ (Brain Nghĩ kỹ) (Plus) (Mic) [Nhắn...] (Send)│
├──────────────────────────────────────────┤
│  Trợ lý  Hộp tin  Lịch  Chi tiêu  Thêm   │
└──────────────────────────────────────────┘
```

- **Phiên** tách lúc 04:00 (QĐ-20); tin mới cách tin cuối dưới 3 giờ thì vẫn nối mạch phiên trước (QĐ-27 mục 12), giao diện hiện liền một dòng thời gian.
- **Đầu màn:** chi phí AI tháng này. `(Search)` mở màn Tìm. `Volume2` đọc to câu trả lời (mặc định tắt). Ba chấm: *Phiên trước*, *Xóa phiên hôm nay* (`ConfirmDialog`, `DELETE /chat/conversations/{id}`).
- **Nhãn model** dưới mỗi câu trả lời của trợ lý (QĐ-27 mục 9): *Haiku 5.5*, *Sonnet 5.5*, *Opus 5.5*, thêm *· có tìm web* khi lượt đó dùng tìm web; chữ nhỏ màu mờ.
- **Nút *Nghĩ kỹ*** (`Brain`) cạnh ô nhập: bật thì tin kế tiếp gửi `think_harder = true` (máy chủ dùng Sonnet 5.5), tự tắt sau khi gửi. Nói rõ *dùng Opus* trong câu thì máy chủ dùng Opus 5.5.
- **Nguồn research:** câu trả lời có tìm web hiện số `[1]`, `[2]` trong chữ và hàng *Nguồn* dưới bóng; mỗi nguồn là nút ghi tên miền, chạm mở trang bằng trình duyệt ngoài. Chạm số trong chữ cuộn tới nguồn đó.
- **Đang nghĩ:** *Em đang nghĩ...*; khi có `tool.started` thì đổi theo `label` (ví dụ *Đang tìm trên web*). Chữ hiện dần theo `text.delta`; khi nhận `message.completed` thì thay bóng bằng chữ cuối. Mất kết nối giữa chừng: tải lại tin hôm nay, không gửi lại.
- **Ô nhập:** tối đa 4.000 ký tự; `(Plus)` gửi ảnh hoặc tệp (PDF, Word, tối đa 4 tệp, tải lên R2 có thanh tiến trình; chữ trích từ tệp được tìm ở màn Tìm); `(Mic)` chạm để nói, chạm để dừng, nói xong tự gửi.
- **Rỗng:** *Nhắn một câu là em ghi, tra, nhắc. Bấm micro để nói.* và gợi ý: *cơm trưa 45k*, *Tháng này tiêu bao nhiêu rồi?*, *Tìm ghi chú về hợp đồng nhà*, *Giá vàng hôm nay*, *Hôm nay có tin gì quan trọng?* (từ Phase 2), *Lịch tuần này* (từ Phase 3).
- Lời chào lần đầu là câu cố định (QĐ-26).

**Nói với trợ lý (1.0.6):** ô nhập trống thì nút gửi thành nút micro lớn (56 px); đang nghe thì nút đỏ có vòng nháy, chữ tạm hiện trong ô nhập; im lặng thì tự dừng và tự gửi. Lượt hỏi bằng giọng thì đọc to câu trả lời (bỏ Markdown, link, khối mã; tối đa khoảng 600 ký tự rồi nói *Chi tiết em để trên màn hình*); chạm màn hình hoặc bấm micro thì dừng đọc. Công tắc *Đọc trả lời khi hỏi bằng giọng* (mặc định bật, lưu trên máy) ở Cài đặt → Thông báo, mục *Giọng nói*, kèm dòng máy có giọng đọc tiếng Việt chưa và nút *Cài đặt giọng đọc*. Máy chưa có giọng tiếng Việt thì báo kèm nút mở cài đặt giọng đọc.

**Phiên chat (QĐ-51 bước 1, bản 1.1.0):** nút góc trái tiêu đề mở ngăn kéo *Các phiên*: *Phiên mới*, ô tìm (máy chủ tìm cả nội dung qua `q`, app lọc tại chỗ không dấu), phiên ghim ở trên rồi theo lần nhắn cuối; mỗi dòng tên, đoạn tin cuối, giờ; giữ lâu hoặc nút ba chấm mở *Đổi tên*, *Ghim*/*Bỏ ghim*, *Xóa phiên* (hỏi lại). Tiêu đề màn chat là tên phiên (chưa đặt thì *Phiên dd/MM HH:mm*), bấm để đổi tên; nút ba chấm bên phải thay nút thùng rác cũ. Mở app vào phiên hoạt động gần nhất (`/chat/today`); chọn phiên thì đường dẫn `/?phien=<id>` (thông báo trợ lý trả lời mở đúng phiên), phiên cũ chat tiếp được (`POST /chat/messages` có `conversation_id`). Giọng nói, đính kèm, thẻ duyệt giữ nguyên. API của agent kiến trúc (25/11): mở một phiên ghép trang tin mới nhất, việc chờ duyệt và thông tin phiên (`GET /chat/conversations/{id}`, `last_preview` đã đề nghị thêm; chưa có thì tìm trong danh sách, dòng hai dùng `summary`). Phản hồi 1.1.1: máy chủ không trả phiên chưa có tin (trừ phiên vừa tạo trong 10 phút) và `/chat/today` không tạo phiên; chưa có phiên thì tiêu đề *Trợ lý*, tin đầu gửi không kèm `conversation_id` để máy chủ tạo phiên. Mở `?phien=` của phiên không còn (404) thì toast *Phiên này không còn.* và về phiên gần nhất.

**Chia sẻ vào Trợ lý (QĐ-51 bước 2):** từ app khác bấm Chia sẻ, chọn Trợ lý thì mở màn `/chia-se`: xem trước ảnh, tệp, ô *Nhắn kèm* điền sẵn chữ hoặc link được chia sẻ, chọn phiên (mặc định phiên hoạt động gần nhất, hoặc *Phiên mới*), *Gửi* thì tải tệp lên, mở phiên đó và gửi ngay. Tệp không nhận được ghi *Bỏ qua N tệp*.

#### Tìm (Phase 1)

```
┌──────────────────────────────────────────┐
│ (ChevronLeft) [hop dong nha          (X)]│
│ [Tất cả] [Ghi chú] [Chat] [Hộp tin]      │
│ [Lịch trình] [Tệp]                       │
├──────────────────────────────────────────┤
│ GHI CHÚ                                  │
│ (StickyNote) Hợp đồng thuê nhà 2026      │
│   ...gia hạn **hợp đồng nhà** tới 12/2027│
│ TỆP                                      │
│ (FileText) hop-dong-thue.pdf · 12/03     │
│   ...bên A cho thuê **nhà** số 15...     │
│ CHAT                                     │
│ (MessageCircle) 02/11 · ...nhắc em gia   │
│   hạn **hợp đồng nhà**...                │
├──────────────────────────────────────────┤
│ [ (Bot) Hỏi trợ lý về "hop dong nha" ]   │
└──────────────────────────────────────────┘
```

- Một ô tìm chung trên ghi chú, chat, hộp tin, lịch trình và chữ trích từ tệp tải lên (PDF, Word, ảnh); tìm toàn văn PostgreSQL, gõ không dấu vẫn ra (QĐ-27 mục 11).
- Kết quả nhóm theo loại, mỗi dòng có đoạn trích với chữ khớp in đậm; chạm mở đúng chỗ (ghi chú, phiên chat cuộn tới tin, cuộc hộp tin, chuyến, tệp).
- Gõ xong 300 ms thì tìm; lọc theo loại bằng viên chọn. Nút cuối *Hỏi trợ lý* gửi câu sang Chat.
- Rỗng: *Không thấy kết quả. Thử từ khác hoặc hỏi trợ lý.*

#### Chi tiêu (Phase 1; tự động từ Phase 2)

```
┌──────────────────────────────────────────┐
│ Chi tiêu                        (Filter) │
│ ┌──────────┐┌──────────┐┌──────────┐     │
│ │ Hôm nay  ││ Tuần này ││ Tháng    │     │
│ │ 165k     ││ 1,2 tr   ││ 6,8 tr   │     │
│ └──────────┘└──────────┘└──────────┘     │
│ [Tất cả] [Ăn uống] [Đi lại] [Mua sắm] ...│
│ CẦN XEM LẠI (1)                          │
│ (CircleHelp) 250.000 đ  Chưa rõ khoản    │
│              TCB ...4821 · 11:05  [Sửa]  │
│ HÔM NAY · 165.000 đ                      │
│ (Utensils) Cơm trưa        45.000 đ      │
│            Ăn uống · chat · 12:10        │
│ (Landmark) Grab           120.000 đ      │
│            Đi lại · VCB ...1234 · 08:30  │
│ (ArrowLeftRight) VCB sang MoMo           │
│            500.000 đ · chuyển nội bộ     │
│                                     (+)  │
└──────────────────────────────────────────┘
```

- Ba thẻ tổng chi, chạm đổi kỳ; thu là dòng nhỏ màu `--income`. Lọc danh mục; `(Filter)` thêm nguồn, khoảng ngày, chi hay thu.
- *Cần xem lại*: dòng có `needs_review` đứng đầu.
- Nguồn ngân hàng hiện mã ngân hàng và 4 số cuối, **không số dư** (QĐ-22). Khoản `transfer` chữ mờ, nhãn *chuyển nội bộ*, không tính vào tổng.
- Chạm dòng: hộp sửa (số tiền gõ `45k` được, khoản, danh mục một chạm là lưu, nơi, thời điểm, ghi chú, chi hay thu, phần thu gọn *Thông báo gốc*). `[Xóa]` xóa ngay, toast *Hoàn tác*.
- `(+)`: ghi tay. Có dòng mới từ ngân hàng khi đang mở app: toast *Đã ghi 120.000 đ, Grab (Vietcombank)* với *Sửa*.
- Rỗng: *Chưa có khoản nào. Nhắn trợ lý như "cơm trưa 45k".* `[Ghi tay]`. Thiếu quyền (từ Phase 2): *Chưa bật đọc thông báo nên chưa tự ghi từ ngân hàng.* `[Bật]`.

#### Hộp tin (Phase 2)

```
┌──────────────────────────────────────────┐
│ Hộp tin               (Sparkles)(Filter) │
│ [Quan trọng 3] [Tất cả] [Zalo] [Tele]    │
│ [Mess] [SMS] [Gmail]                     │
│ QUAN TRỌNG                               │
│ (Star) [Zalo] Chị Lan            09:12   │
│        Chiều nay họp lúc 3h nha em  (2)  │
│ HÔM NAY                                  │
│        [Tele] Nhóm Dự án A        10:20  │
│        Tuấn: file mới đã up              │
│        [Zalo] Anh Hùng            07:55  │
│        Có tin mới (nội dung bị ẩn)       │
└──────────────────────────────────────────┘
```

- Mỗi dòng là một cuộc trò chuyện theo `conversation_key`, lấy từ `GET /inbox/conversations`; chạm mở `/hop-tin/:conversationKey` (`/inbox/conversations/{conversation_key}/messages`), đánh dấu đã xem. Nút cuối: *Đã xử lý*, *Người quan trọng*, *Hỏi trợ lý về cuộc này*. Vuốt trái: *Đã xử lý*.
- `(Sparkles)` **Tóm tắt**: chuyển sang Chat và gửi câu dựng sẵn theo bộ lọc đang chọn (ví dụ *Tóm tắt tin quan trọng hôm nay trong Zalo*); không có endpoint riêng (`12` mục 5.5).
- `(Filter)`: thời gian (hôm nay, 3, 7, 30 ngày, tất cả), trạng thái.
- Rỗng: *Chưa có tin nào. Tin Zalo, Telegram, Messenger, SMS hiện ở đây khi điện thoại nhận thông báo; thư Gmail có từ Phase 5.*
- Thiếu quyền: *Chưa bật đọc thông báo.* `[Bật]`. Đã bật mà quá 24 giờ không có tin: *Đã 26 giờ chưa nhận tin nào. Kiểm tra pin và chế độ ngủ của Samsung.* `[Kiểm tra]`.
- Chân danh sách: *Tin giữ 180 ngày rồi tự xóa.* (QĐ-17)
- Chữ tin và thư (phản hồi 1.0.8): link bấm mở trình duyệt ngoài, link dài hơn 40 ký tự hiện gọn thành chip tên miền (giữ link thật), số điện thoại và tổng đài 1800, 1900 bấm gọi, email bấm mở màn soạn thư; thư dạng chữ gộp dòng bị ngắt giữa câu, giữ đoạn, lời chào, chữ ký, gạch đầu dòng (`reflowPlainText`). Thư HTML vẫn tạm dừng (QĐ-48).
- Thứ tự (phản hồi 1.0.7): mọi tab xếp theo tin mới nhất giảm dần; tin quan trọng chỉ có ngôi sao, không đẩy lên đầu (tab *Quan trọng* lọc riêng). Tab *Email* có hàng chip tài khoản dưới hàng tab (*Tất cả*, rồi từng tài khoản rút gọn phần trước @), nhớ lựa chọn cuối trên máy, gửi `account_email=` cho `GET /inbox/conversations` (máy chủ trả thêm `accounts` cho chip) và lọc cả ở app; mỗi dòng thư có huy hiệu màu theo tài khoản nhận.
- Tệp `.md` ở mọi chỗ mở `/xem-tep/:fileId` (trình hiện Markdown trong app, không dùng HTML). Tải lên suy mime theo đuôi khi Android trả rỗng (`shared/utils/mime.ts`).

#### Zalo đầy đủ qua zalo-bridge (QĐ-52, cờ `zalo_bridge`)

- Cài đặt → *Zalo* (`/cai-dat/zalo`): trạng thái tài khoản; *Đăng nhập bằng mã QR* hiện ảnh QR (`qr_png_base64`) và đếm lùi, hỏi `GET /zalo/status` mỗi 2 giây tới *Đã đăng nhập X*; *Tạo mã mới* khi hết hạn; báo *bị đăng xuất vì mở Zalo Web nơi khác, tự thử lại sau 10 phút* khi `kicked`; *Đăng xuất* (hỏi lại).
- Hộp tin, tab Zalo: hội thoại khóa đầy đủ (`zalo:u:`, `zalo:g:`) mở khung chat `/zalo/:key`; khóa cũ đọc từ thông báo vẫn mở màn cũ. Nút nổi *Tin Zalo mới* mở danh bạ (`/zalo/moi`, `GET /zalo/contacts`).
- Khung chat: bong bóng kiểu Zalo (người khác bên trái, nhóm có tên người gửi; tin mình bên phải), gộp theo ngày, đứng ở tin cuối, *Xem tin cũ hơn*; ảnh xem nhỏ bấm mở lớn, video và tệp mở bằng trình xem máy, ghi âm nghe ngay, tệp đang lấy thì *Đang lấy...*; trích dẫn chỉ hiển thị; tin thu hồi in nghiêng *(Tin đã thu hồi)*; link, số, email bấm được. Gửi chữ và tối đa 5 tệp (`POST /zalo/messages`, tải tệp trước); tin hiện tạm *Đang gửi*, *Đã gửi, chờ Zalo báo lại* tới khi bridge báo lại; lỗi thì *Gửi lại* (429 *Gửi chậm lại, thử lại sau N giây*; chưa đăng nhập thì dải dẫn tới quét mã). Menu: *Lấy tin cũ* (nhóm lấy 50 tin, một-một Zalo không giữ lịch sử), *Đánh dấu đã xử lý*. Bot gửi thay luôn qua thẻ duyệt `send_zalo_message` ở chat.

#### Thiết lập máy (Phase 2)

```
┌──────────────────────────────────────────┐
│ Thiết lập máy                    [Để sau]│
│ (CircleCheck) 1. Cho phép thông báo      │
│ (Circle)      2. Đọc thông báo   [Bật]   │
│               Bị khóa xám? [Xem cách mở] │
│ (Circle)      3. Pin không hạn chế [Bật] │
│ (Circle)      4. Không cho ngủ (Samsung) │
│               [Mở danh sách]  [Đã làm]   │
│ App SMS mặc định: Samsung Messages       │
│ [              Xong               ]      │
└──────────────────────────────────────────┘
```

- Mỗi bước: icon trạng thái, một câu lý do, nút mở đúng trang (`30` mục 3.10). Quay lại app thì kiểm lại ngay, bước xong tự tích.
- **Bị khóa xám** (cài đặt bị hạn chế): tấm hướng dẫn 4 bước: bấm *Bật* một lần; bấm *Mở thông tin ứng dụng*; menu ba chấm, *Cho phép cài đặt bị hạn chế*, xác nhận; quay lại bấm *Bật*.
- **Bước 4, chỉ trên Samsung:** `[Mở danh sách]` mở thẳng *Ứng dụng không bao giờ ngủ*; mở không được thì hiện đường tay *Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > Trợ lý > Thêm*. Người dùng bấm `[Đã làm]`. Dòng phụ: *Samsung tự cho app ngủ sau vài ngày không mở; khi đó nhắc lịch và tin mới có thể không tới.*
- **App SMS:** chỉ hiện tên app SMS mặc định app đọc được (`sms_default`, `30` mục 3.6); đổi app SMS mặc định trong cài đặt Android thì app tự theo.
- Bước báo thức chính xác chỉ hiện khi thiếu (Phase 3). `[Để sau]` và `[Xong]` đều vào Chat; bước thiếu hiện banner ở màn liên quan.

#### Lịch và việc (Phase 3)

```
┌──────────────────────────────────────────┐
│ Lịch                         (RefreshCw) │
│ Google Calendar · đồng bộ 10:30          │
│ [ Lịch ] [ Việc 4 ]     [Ngày|Tuần|Tháng]│
│  T2  T3  T4  T5  T6  T7  CN              │
│  17 (18) 19  20  21  22  23              │
│ Thứ Ba, 18/11                            │
│ 09:00  Họp nhóm          (Bell) 15' App  │
│        Phòng 3 · 3 khách                 │
│ 15:00  Gọi khách A       (Bell) Google   │
│ VIỆC HẠN HÔM NAY                         │
│ [ ] Gửi báo giá        (Flag) cao        │
│                                     (+)  │
└──────────────────────────────────────────┘
```

- **Lịch:** kiểu Ngày (dải tuần, sự kiện theo giờ rồi việc có hạn), Tuần, Tháng. Dữ liệu `GET /calendar/events`. Mỗi sự kiện ghi nguồn nhắc: *App* (kèm số phút) hoặc *Google*.
- **Hộp sửa sự kiện:** tiêu đề, bắt đầu, kết thúc, cả ngày, địa điểm, **khách mời** (email; QĐ-23), **Ai nhắc** (*App nhắc* thì có hàng *Nhắc trước* 0, 5, 15, 30, 60 phút, *Báo thức*; *Google nhắc* thì ẩn hàng đó), ghi chú. Lưu sự kiện có khách hoặc sửa sự kiện đã có khách: hiện thẻ duyệt *Gửi lời mời tới 2 người* ngay trong hộp, duyệt rồi mới ghi. Không có khách thì lưu thẳng. **Sự kiện người khác mời:** chỉ đổi được *Ai nhắc*, các ô khác khóa với dòng *Sự kiện của người khác*.
- **Việc:** nhóm *Quá hạn*, *Hôm nay*, *Sắp tới*, *Không hạn*, *Đã xong*. Tích xong ngay, toast *Hoàn tác*. Việc tích xong trên Google Tasks ở máy khác tự hiện xong sau lần đồng bộ (QĐ-21). Việc **bị xóa trên Google Tasks** (`remote_deleted`): dòng nhãn vàng *Đã xóa trên Google Tasks* với `[Xóa luôn]` và `[Giữ lại]` (`POST /tasks/{id}/resolve-remote-delete`).
- `(+)`: thêm sự kiện hoặc việc; gợi ý *Hoặc nhắn trợ lý: nhắc 15:00 gọi khách.*
- Rỗng: *Ngày trống.* Chưa kết nối Google: *Kết nối Google Calendar để thấy lịch ở đây.* `[Kết nối]`.
- Thiếu quyền: *Nhắc sẽ không kêu vì thông báo đang tắt.* `[Bật]`. Mất kết nối Google: *Cần kết nối lại Google.* `[Kết nối lại]`.

#### Lịch trình (Phase 4)

**Danh sách chuyến:** thẻ chuyến (tên, ngày, số ngày, phương tiện, km, số rủi ro, trạng thái *Đang đọc tệp...*, *Đang đánh giá...* khi việc nền chạy). Chuyến đang đi đứng đầu. `[Nhập lịch trình]`: *Gửi tệp*, *Dán link*, *Mô tả bằng lời*, cả ba sang Chat. Rỗng: *Chưa có chuyến nào. Gửi tệp lịch trình hoặc kể chuyến đi.*

**Chi tiết chuyến:**

```
┌──────────────────────────────────────────┐
│ (ChevronLeft) Phước Hải – Trà Vinh  (…)  │
│ Phương án: Đúng giờ, ít rủi ro           │
│ (MapPinOff) 2 điểm cần xác nhận   [Xem]  │
│ (TriangleAlert) 2 rủi ro          [Xem]  │
│ [Ngày 1 · T6] [Ngày 2 · T7] [Ngày 3 · CN]│
│ 08:30 (Utensils) Bún nước lèo Cô Ba      │
│       85 km · khoảng 2 giờ 10            │
│       [(Navigation) Dẫn đường] [Xem]     │
│ 10:00 (Ship) Phà Cổ Chiên                │
│       Chuyến cuối 18:30  (Clock) mốc cứng│
│ [ (Map) Xem đường cả ngày (1/2) ]        │
│ [ (Map) Xem đường cả ngày (2/2) ]        │
│ Thời gian xe máy do Google ước tính      │
│ (bản thử nghiệm), có thể lệch.           │
└──────────────────────────────────────────┘
```

- **Điểm cần xác nhận** (`41` mục 5.3): mỗi dòng có tên trong tệp, 1 tới 3 gợi ý (nút *Xem*), *Chọn*, *Bỏ qua*. Điểm bỏ qua có nhãn *chưa định vị*, không có *Dẫn đường*.
- Mỗi điểm: giờ, icon theo loại, tên, km và giờ chạy từ điểm trước, cảnh báo, `[Dẫn đường]`, `[Xem]`. Cuối ngày một nút mỗi đoạn từ `GET /trips/{id}/map-links?day_no=&max_waypoints=` (9 nếu có Google Maps, 3 nếu không). Dòng cố định *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.*
- Ba chấm: *So sánh phương án* (chọn phương án khác hỏi bằng `ConfirmDialog`), *Đưa vào lịch* (`POST /trips/{id}/to-calendar`, toast *Đã đưa 5 mục vào lịch*), *Xuất Word*, *Hỏi trợ lý*, *Xóa chuyến* (thẻ duyệt).

Khách sạn gắn từ thư xác nhận (QĐ-49, `stop.booking`): khối nhỏ dưới điểm ghi nơi đặt và mã đặt chỗ (chạm biểu tượng để chép), giờ nhận, trả phòng, số khách, giá, chính sách hủy; *Đã hủy* thì gạch chữ, *Đã đổi* ghi nhãn. Nút *Gọi* (số của khách sạn) và *Dẫn đường* dùng như điểm khác.

#### Báo cáo (Phase 4)

Bốn thẻ, mỗi thẻ lỗi riêng được: **Chi tiêu** (tổng kỳ, so kỳ trước, 5 danh mục lớn nhất); **Lịch tuần** (số sự kiện, việc quá hạn); **Hộp tin** (quan trọng chưa xem, chưa xử lý); **Chi phí AI** (chi tháng so với mức cảnh báo 200 USD, cột theo ngày; không có trần ngày, QĐ-15); **Thiết bị** (đang nghe, tin cuối, số OTP đã chặn hôm nay). Không có nút gửi báo cáo (QĐ-11).

Thẻ **Tập luyện** (QĐ-54) cuối màn Báo cáo, tải riêng `GET /reports/gym?period=week|month` (dạng thẻ như dashboard, theo đề xuất gửi agent kiến trúc): chip *Tuần này* / *Tháng này*; số buổi đã tập trên số buổi theo lịch (thiếu buổi thì màu cảnh báo), tối đa 3 bài tăng tạ nổi bật, cân nặng đầu và cuối khoảng, đạm trung bình so mục tiêu (dưới 90% màu cảnh báo), buổi hôm nay và ngày mai; nút *Mở app gym* (https://gym.baohuynh.io.vn, mở trình duyệt). `disabled` thì *Chưa nối app gym*.

**Kết nối (QĐ-56, thay màn DEGO của QĐ-55):** Cài đặt → *Kết nối* (`/cai-dat/ket-noi`, đường dẫn sâu `troly://settings/connectors?ok=1&id=`, màn `settings_connectors`): danh sách kết nối (tên, *Chưa nối* / *Đã nối tài khoản X* / *Cần nối lại*). *Thêm kết nối*: tên, địa chỉ MCP, chip gợi ý ERP DEGO (`GET /connectors/presets` trả `{items}`); máy chủ có OAuth thì mở trang đăng nhập của hệ thống trong trình duyệt của app (người dùng nhập mật khẩu, đồng ý trên trang đó, về app báo đã nối; lỗi về theo mã `loi` gồm `huy`, `state`, `iss`, `token`, `loi`, app tự hiện câu); không có OAuth thì ô dán khóa (che, không tự điền). Màn một kết nối (`/cai-dat/ket-noi/:id`): trạng thái, *Kết nối*/*Nối lại* hoặc *Nhập khóa*/*Đổi khóa*, danh sách công cụ (tên hiển thị, mô tả; công cụ đọc nhãn *đọc*), mỗi công cụ ghi một công tắc (mặc định tắt, bật có cảnh báo, ghi vẫn qua thẻ duyệt; gửi `PATCH /connectors/{id}` với cả danh sách `write_tools_enabled`), *Gỡ kết nối* (hỏi lại). Chat: nút *Kết nối* cạnh Tìm web khi đã nối ít nhất một hệ thống, giữ tới khi tắt, gửi `use_connectors: true`; hành động `connect` của trợ lý chạy đúng luồng trên (có `connector_id` thì đăng nhập, không thì mở form thêm điền sẵn). API đã chốt với agent Google, cờ `use_connectors` (`true` hoặc danh sách id) và hành động `connect` đã chốt với agent AI (25/11); ẩn khi cờ `connectors` tắt.

#### Cài đặt

| Mục | Phase | Nội dung |
|---|---|---|
| **Hồ sơ lõi** | 1 | Sửa Markdown, đếm ký tự trên 8.000, danh sách bản cũ và *Khôi phục* |
| **Chi phí AI** (`settings_ai_cost`) | 1 | Chi tháng so với mức cảnh báo 200 USD, cột 30 ngày, chia theo việc và theo model (Haiku, Sonnet, Opus), tỉ lệ đọc cache |
| **Phiên bản** | 1 | Bản app; `[Kiểm tra cập nhật]`; ghi chú bản mới; `[Cập nhật]` (luôn hỏi trước, QĐ-18) |
| **App được nghe** | 2 | 7 dòng (`30` mục 3.6): tên, mục đích, *Đã cài* hoặc *Không thấy trên máy*, tin cuối, công tắc. Dòng SMS ghi tên app SMS mặc định thật. Đã nối Gmail thì ghi *Thư lấy qua Gmail*. Công tắc *Cho trợ lý đọc hộp tin* (`inbox.ai_enabled`). Chân: *Thông báo của app ngoài danh sách bị bỏ ngay trên điện thoại. Tin có mã OTP luôn bị bỏ.* |
| **Người quan trọng** | 2 | Người theo tên trên thông báo; từ khóa gấp |
| **Kiểm tra máy** | 2 | Các bước Thiết lập máy với trạng thái; dịch vụ nghe, tin cuối; *Đã chặn N tin OTP hôm nay*; hàng đợi và `[Gửi ngay]`; số nhắc đã đặt; Google Maps đã cài chưa |
| **Kết nối Google** | 3 | Email, trạng thái (`GET /google/status`), từng dịch vụ có công tắc và lần đồng bộ cuối; *Lỗi đồng bộ*: danh sách mục hỏng từ `GET /google/outbox` với `[Thử lại]` và, khi xung đột, `[Áp lại]` (`POST /google/outbox/{id}/retry`); `[Ngắt kết nối]` hỏi có giữ dữ liệu không (`keep_data`) Khối *Tài khoản Gmail* (QĐ-50, `GET /google/accounts`): tài khoản chính (Lịch, Việc, Gmail) và tài khoản thêm (chỉ Gmail), nút *Thêm tài khoản Gmail* (`POST /google/connect {role: mail}`, về `?ket-qua=ok&tai-khoan=mail`; chọn trùng tài khoản chính thì `ket-qua=da-co`), *Gỡ* cho tài khoản thêm (hỏi gỡ có bỏ thư khỏi Hộp tin không, `DELETE /google/accounts/{id}?delete_messages=`); chọn *Thư vào Hộp tin* (`gmail.categories`: `primary`, `primary_updates` mặc định, `all` là tất cả trừ Quảng cáo, Mạng xã hội; thư quan trọng luôn vào). Tab Email của Hộp tin và đầu luồng thư ghi tài khoản nhận; soạn và trả lời có ô *Gửi từ* khi có từ hai tài khoản (mặc định tài khoản của luồng thư, không thì tài khoản chính), thẻ duyệt gửi ghi *Gửi từ*. Đã chốt với agent Google (20/11). |
| **Thiết bị** | 1 | Máy đã đăng nhập; đăng xuất máy khác; đổi tên |
| **Đăng xuất** | 1 | `ConfirmDialog` |

### 3.6 Luồng chính

**Luồng 1. Lần đầu mở app (Phase 1).** Mở app, chưa có mã làm mới thì Đăng nhập, đăng ký thiết bị (`POST /devices`), vào Chat với lời chào cố định. Từ Phase 2, sau đăng nhập đi qua Thiết lập máy.

**Luồng 2. Cấp quyền (Phase 2).** Như màn Thiết lập máy; bước thiếu hiện banner ở Hộp tin, Chi tiêu, Lịch và ở Kiểm tra máy.

**Luồng 3. Kết nối Google (Phase 3).**

```
Cài đặt > Kết nối Google ──[Kết nối]──> POST /google/connect ──> auth_url
   ──> Custom Tabs (trình duyệt ngoài): chọn tài khoản, bấm qua cảnh báo "chưa xác minh", đồng ý
   ──> trang máy chủ ──> troly://cai-dat/google?ket-qua=ok|huy|thieu-quyen|loi
   ──> app đóng Custom Tabs, tải lại GET /google/status ──> Lịch
```

Không mở trong WebView (Google chặn OAuth trong trình duyệt nhúng). `huy`: toast *Chưa kết nối.* `thieu-quyen`: hiện dịch vụ thiếu quyền, *Kết nối lại*. `loi`: *Kết nối lỗi, thử lại sau.* Đóng trình duyệt giữa chừng: quay lại thì tải lại trạng thái. Câu tiến trình đồng bộ lần đầu lấy từ `GoogleStatus`.

**Luồng 4. Duyệt hành động.** Trợ lý trả thẻ duyệt (mục 3.3); *Bỏ* gọi `reject`; *Duyệt* hiện *Đang làm...* rồi gọi `approve`; xong thì *Đã gửi* và tải lại màn liên quan; lỗi thì câu lỗi và *Thử lại*.

**Luồng 5. Cập nhật app (Phase 1).** Mở app thì kiểm bản mới; có bản mới thì dải *Có bản 1.6.0: lịch trình và bản đồ.* `[Cập nhật]` `[Để sau]`. Chỉ khi bấm *Cập nhật* mới tải và cài; lần đầu chưa cho cài nguồn ngoài thì hướng dẫn một bước. Bản bắt buộc chặn app, chỉ còn nút *Cập nhật*.

**Luồng 6. Mở bản đồ (Phase 4).** Chạm *Dẫn đường*: có Google Maps thì mở thẳng dẫn đường xe hai bánh tránh cao tốc; không có thì mở trang Google Maps trên trình duyệt, toast *Máy chưa có Google Maps*. Trợ lý không tự mở bản đồ.

## 4. Dữ liệu cần

Không có bảng riêng. Cần từ `11`: `tab_pending_action` (thẻ duyệt), `tab_expense.needs_review`, `tab_inbox_message.conversation_key`, `tab_event.remind_source` và khách mời, `tab_task.sync_status = remote_deleted`, khóa `tab_setting` `ui.voice_reply` (mặc định tắt), `inbox.ai_enabled`. Cần thêm: model đã dùng và danh sách nguồn research của mỗi tin trả lời (mục 9).

## 5. API hoặc giao tiếp

Đường dẫn dưới `/api/v1`, theo `12`:

| Màn | Gọi |
|---|---|
| Đăng nhập | `/auth/login`, `/auth/refresh`, `POST /devices` |
| Chat | `/chat/today`, `/chat/conversations`, `POST /chat/messages` (SSE, `think_harder`), `/chat/actions/{id}/approve`, `/reject`, `DELETE /chat/conversations/{id}`, `/chat/status`, `/files/*`, `/memory/profile/revisions/{v}/restore` |
| Tìm | `GET /search?q=&types=` (cần thêm, mục 9) |
| Chi tiêu | `/expenses`, `/expenses/summary`, `/expenses/categories`, `/expenses/{id}/source` |
| Hộp tin | `/inbox/conversations`, `/inbox/conversations/{conversation_key}/messages`, `/mark`, `/inbox/rules` |
| Lịch và việc | `/calendar/events`, `/tasks`, `/tasks/{id}/complete`, `/tasks/{id}/resolve-remote-delete`, `/calendar/reminders` |
| Lịch trình | `/trips`, `/trips/{id}`, `/stops/{stop_id}/resolve`, `/options/{option_id}/choose`, `/map-links`, `/export-docx`, `/to-calendar`, `/jobs/{id}` |
| Báo cáo | `/reports/dashboard`, `/reports/ai-cost` |
| Cài đặt | `/memory/profile`, `/devices`, `/devices/listened-apps`, `/settings`, `/google/status`, `/google/connect`, `/google/disconnect`, `/google/outbox`, `/device/release` |

Query key đặt hết ở `src/shared/constants/query-keys.ts`.

## 6. Kiểm thử

Theo QĐ-27 mục 8, giao diện không có bộ bài kiểm riêng; phần dễ sai (OTP, bộ lọc, giờ nhắc) ở `30` mục 6. Thử tay trên Galaxy S25+ mỗi bản:

1. Đăng nhập một lần, đóng mở app nhiều ngày vẫn không phải đăng nhập lại.
2. Chat: *cơm trưa 45k* ra dòng xác nhận; câu hỏi giá vàng có nhãn *Sonnet 5.5 · có tìm web* và nguồn bấm mở được; *Nghĩ kỹ* tự tắt sau một tin; tin quá 4.000 ký tự không gửi; mất mạng giữa chừng không mất tin.
3. Tìm *hop dong nha* (không dấu) ra ghi chú, tệp PDF, tin chat có chữ *hợp đồng nhà*.
4. Xóa một khoản chi: xóa ngay, *Hoàn tác* khôi phục. Xóa nhiều khoản qua trợ lý: ra thẻ duyệt.
5. Bàn phím không che ô nhập; vùng an toàn đúng với thanh điều hướng cử chỉ của One UI.
6. Từ Phase 2: Thiết lập máy đủ 4 bước, gồm bước Samsung; hộp tin gom đúng cuộc; *Tóm tắt* sang Chat.
7. Từ Phase 3: sự kiện có khách ra thẻ duyệt; sự kiện người khác mời chỉ đổi được *Ai nhắc*; việc xóa trên Google Tasks hiện nhãn và hai nút.
8. Từ Phase 4: điểm cần xác nhận chọn được; *Dẫn đường* mở Google Maps xe hai bánh; *Đưa vào lịch* tạo đúng mục.

## 7. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Nhiều mảng trong một app làm rối | Thanh dưới chỉ 4 mảng hằng ngày; màn chưa tới phase hiện rỗng; ô tìm chung và trợ lý làm đường tắt |
| Hộp tin giữ 180 ngày, danh sách dài làm WebView giật | Gom theo cuộc, phân trang con trỏ, tải dần |
| Bàn phím ảo che ô nhập trong Capacitor 8 | Thử trên S25+ ngay Phase 1; `env(safe-area-inset-bottom)`, `dvh` |
| Người dùng quên bước Samsung | Bước riêng ở Thiết lập máy; dải *Lâu không có tin*; thẻ Thiết bị |

## 8. Câu hỏi mở

Không còn. Nền tối, đọc to mặc định tắt, không thông báo khi ghi giao dịch lúc app đóng, Google nhắc sự kiện tạo trên Google: đã chốt ở QĐ-26.

## 9. Cần agent khác

| Agent | Việc |
|---|---|
| kiến trúc (`12`) | Thêm `GET /search?q=&types=` (ghi chú, chat, hộp tin, lịch trình, tệp; trả đoạn trích và chỗ mở); `Message` thêm `model` và `citations[]` (`title`, `url`), sự kiện `message.completed` mang hai trường này; đổi tên màn `settings_ai_budget` thành `settings_ai_cost`; bỏ `/consents`, `/me/export`, `DELETE /me` và màn liên quan theo QĐ-27 |
| AI (`20`) | Ghi model thật đã dùng vào tin trả lời; trả nguồn research thành `citations[]`; `think_harder` chọn Sonnet 5.5 (QĐ-27 mục 9); `label` của `tool.started` cho tìm web là *Đang tìm trên web*; bỏ `require_unlock` |
| kiến trúc (`11`) | Bỏ `require_unlock` khỏi `tab_pending_action` (không còn vân tay) |

## 10. Đề xuất quyết định

Không có đề xuất mới. ĐX-31-01 tới 31-11 đã xử lý ở QĐ-25, QĐ-26; phần vân tay (ĐX-31-07, 31-11), *Dữ liệu của tôi* và *Máy chủ* (ĐX-31-10) thay bằng QĐ-27.

## 11. Nguồn

- App gym: `D:\giabao\gymcanhan\CLAUDE.md` (mục Giao diện), `web/src/index.css`, `web/src/app/app-layout.tsx`, `web/src/modules/coach/pages/coach-page.tsx`.
- Nền tảng (quyền, Samsung, Google Maps, cài APK): mục Nguồn của [30-app-android.md](30-app-android.md).
- Google chặn OAuth trong trình duyệt nhúng (`disallowed_useragent`): https://developers.google.com/identity/protocols/oauth2/native-app
