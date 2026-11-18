# Giao diện

Ngày lập: 18/11/2026. Người giữ: agent app Android. Trạng thái: bản 2, đã sửa theo `80-ra-soat/80-ra-cheo-lan-1.md` và QĐ-15 tới QĐ-25.

Tài liệu này mô tả mọi màn hình, điều hướng, luồng chính và trạng thái của app Trợ lý. Lớp gốc (plugin, quyền, cập nhật) ở [30-app-android.md](30-app-android.md). Sơ đồ khung vẽ bằng ký tự, khổ điện thoại dọc; `[Gửi]` là nút, `(Mic)` là icon lucide.

Nguồn chuẩn khi lệch (QĐ-25): bảng theo `11`, đường dẫn API theo `12` (`/api/v1`, số nhiều), kiểu hành động theo `20` và tệp này, luật duyệt theo `60` mục 3.12.

## 1. Mục tiêu

- **Một app xem hết**: chat với trợ lý, tin nhắn, lịch và việc, chi tiêu, lịch trình, báo cáo, cài đặt.
- **Siêu dễ dùng, một tay**: việc thường ngày làm được trong 1 tới 2 chạm; gõ một câu cho trợ lý luôn là đường tắt.
- **Cùng phong cách app gym** (`D:\giabao\gymcanhan\web`): nền tối, màu nhấn xanh chanh, thẻ bo tròn, icon lucide, popup trong app.
- Luôn nói rõ trạng thái: đang tải, trống, lỗi, mất mạng, thiếu quyền, trợ lý đang làm gì.

## 2. Phạm vi

| Trong tài liệu này | Ở tài liệu khác |
|---|---|
| Nguyên tắc giao diện, điều hướng, đường dẫn màn | Plugin gốc, quyền hệ thống: `30` |
| Mọi màn: Chat, Hộp tin, Lịch và việc, Chi tiêu, Lịch trình, Báo cáo và thông số, Cài đặt | Dữ liệu và API chi tiết: `11`, `12` |
| Luồng: lần đầu mở app, cấp quyền, kết nối Google, duyệt hành động, mở bản đồ, cập nhật | Nội dung trợ lý trả lời, công cụ AI: `20` |
| Cách hiện hành động trợ lý trả về | Dựng link bản đồ, đánh giá lịch trình: `41` |
| Trạng thái rỗng, lỗi, mất mạng, lưu đệm | OAuth Google phía máy chủ: `40` |

Ngoài phạm vi V1: màn gym, màn sức khỏe đầy đủ (V2, chỉ có thẻ trong Báo cáo), màn duyệt mã tự phát triển (V3), máy tính bảng.

## 3. Thiết kế

### 3.1 Nguyên tắc và phong cách

Lấy nguyên luật giao diện của app gym (ĐX-31-02 đã duyệt):

| Mục | Luật |
|---|---|
| Công nghệ | React 19, Vite (cổng 5190 khi phát triển, `50`), TypeScript, Tailwind 4 cấu hình bằng CSS ở `src/index.css`, shadcn trên Radix trong `src/shared/ui/`, TanStack Query, react-router, sonner, recharts |
| Màu | Chỉ token trong `src/index.css` (`:root` và `.dark`), cấm hex lẻ. **Mặc định nền tối**. Bắt đầu bằng đúng bộ token của app gym (nền `oklch(0.155 0.008 260)`, thẻ `oklch(0.205 0.01 260)`, nhấn `oklch(0.86 0.19 130)`, cảnh báo, lỗi, thông tin) |
| Token thêm | `--app-1` tới `--app-6` cho nhãn app trong Hộp tin (5 màu `--day-*` của app gym và một màu thêm); `--income` (thu, màu nhấn); `--transfer` (chuyển nội bộ, `muted-foreground`) |
| Icon | Chỉ `lucide-react`, ăn màu chữ, cỡ bằng class. Cấm emoji, cấm icon gradient, không dùng logo thương hiệu |
| Thông báo, xác nhận, nhập liệu | `sonner`, `ConfirmDialog`, `Dialog`. Cấm `alert`, `confirm`, `prompt` |
| Nút lưu | Chặn bấm đúp bằng `useRef`; `disabled` chỉ để báo hiệu |
| Bố cục | Cột giữa `max-w-lg`, lề 16 px, vùng an toàn `env(safe-area-inset-*)`, thanh dưới cố định nền mờ |
| Chữ | Tiêu đề màn `text-2xl font-bold`; dòng phụ `text-sm text-muted-foreground`; bóng chat 15 px |
| Chạm | Vùng chạm tối thiểu 44 x 44 px; nút chính cao 44 px |
| Định dạng | Tiền `45.000 đ`, tóm tắt `45k`, `1,2 tr`; ngày `Thứ Hai, 18/11`; giờ 24 giờ; giờ Việt Nam |
| Ngôn ngữ | Tiếng Việt, câu ngắn. Trợ lý xưng **em**; chữ trên nút và tiêu đề viết trung tính (*Lưu*, *Duyệt*, *Bỏ*) |
| Thành phần chung | `src/shared/`; module không import ruột module khác |

### 3.2 Điều hướng

**Thanh dưới 5 ô** (ĐX-31-01 đã duyệt):

```
┌──────────────────────────────────────────────────────────┐
│ (MessageCircle) (Inbox) (CalendarDays) (Wallet) (LayoutGrid) │
│    Trợ lý       Hộp tin     Lịch       Chi tiêu    Thêm    │
└──────────────────────────────────────────────────────────┘
```

- **Hộp tin** có chấm số: tin quan trọng chưa xem.
- **Thêm** mở tấm trượt: Lịch trình (`Route`), Báo cáo và thông số (`ChartColumn`), Cài đặt (`Settings`). Đang ở một màn trong nhóm này thì ô **Thêm** sáng màu nhấn.

**Đường dẫn màn:**

| Đường dẫn | Màn |
|---|---|
| `/` | Chat |
| `/hop-tin`, `/hop-tin/:threadKey` | Hộp tin, một cuộc trò chuyện (theo `conversation_key`) |
| `/lich?xem=ngay\|tuan\|thang&date=YYYY-MM-DD` | Lịch |
| `/lich/viec` | Việc |
| `/lich/su-kien/:id`, `/lich/viec/:id` | Mở hộp sửa (đích của thông báo nhắc) |
| `/chi-tieu?ky=ngay\|tuan\|thang` | Chi tiêu |
| `/lich-trinh`, `/lich-trinh/:id?ngay=1` | Danh sách chuyến, chi tiết chuyến |
| `/bao-cao?ky=tuan\|thang` | Báo cáo và thông số |
| `/cai-dat`, `/cai-dat/<mục>` | Cài đặt (mục 3.6.8) |
| `/dang-nhap`, `/dong-y`, `/thiet-lap` | Đăng nhập, đồng ý xử lý dữ liệu (thành viên), thiết lập máy |

**Đường dẫn sâu** `troly://<đường dẫn>` (thông báo nhắc, trang kết nối Google `troly://cai-dat/google?ket-qua=ok|huy|thieu-quyen`) bắt bằng sự kiện `appUrlOpen` của `@capacitor/app`.

**Nút quay lại của Android:** đóng hộp thoại, tấm trượt; rồi quay lại màn cha; rồi về Trợ lý; ở Trợ lý thì thu nhỏ app (`App.minimizeApp()`).

**Đầu mỗi màn:** tiêu đề, dòng phụ, tối đa 2 nút icon bên phải.

### 3.3 Hành động trợ lý trả về

Mỗi câu trả lời gồm chữ và danh sách **hành động** (sự kiện `action` trong luồng chat SSE và mảng `actions` của mỗi tin, `12` mục 5.5). Kiểu hành động theo `20` mục 3.8 (không còn kiểu `open_map` chung); bảng dưới chốt cách hiện:

| `type` | Trường chính | Hiện thành | Khi chạm |
|---|---|---|---|
| `open_map_navigation` | `label`, `lat`, `lng`, `mode`, `avoid` | Nút viền to, icon `Navigation` | `Maps.navigate`, luồng 5 |
| `open_map_directions` | `label`, `urls[]` | Một nút icon `Map` mỗi URL; nhiều URL thì thêm *(đoạn 1/2)* | `Maps.openUrl` |
| `open_map_place` | `label`, `query`, `place_id` | Nút viền, icon `MapPin` | Mở URL tìm địa điểm |
| `open_link` | `label`, `url`, `kind` (`file`, `gmail`, `sheet`, `web`) | Nút viền, icon `FileText`, `Mail`, `Sheet`, `ExternalLink` | Mở trình duyệt hoặc app; chỉ nhận `https` |
| `open_screen` | `label`, `screen`, `params` | Nút chữ nhỏ, icon `ChevronRight`. Đi ngay sau công cụ ghi dữ liệu (ví dụ *Sửa khoản này* sau `add_expense`) thì hiện thành **dòng xác nhận** icon `CircleCheck` | Chuyển màn theo bảng `screen` |
| `memory_changed` | `version`, `text`, `undo_version` | Dòng nhỏ icon `Brain`: *Đã ghi nhớ: ...*, `[Hoàn tác]` | Khôi phục bản `undo_version` |
| `confirm` | `pending_action_id`, `title`, `summary`, `details[]`, `confirm_label`, `cancel_label`, `danger`, `require_unlock`, `expires_at` | **Thẻ xác nhận** | Luồng 4 |
| `choices` | `options[]` (`label`, `value`) | Hàng nút gợi ý nhỏ | Gửi `value` như tin của người dùng |

`type` lạ bị bỏ qua, không làm vỡ màn.

**Giá trị `screen`:**

| `screen` | `params` | Đường dẫn |
|---|---|---|
| `chat` | | `/` |
| `inbox`, `inbox_thread` | `filter`; `thread_key` | `/hop-tin`, `/hop-tin/:threadKey` |
| `calendar_day`, `event_detail` | `date`; `event_id` | `/lich?date=`, `/lich/su-kien/:id` |
| `task_list`, `task_detail` | ; `task_id` | `/lich/viec`, `/lich/viec/:id` |
| `expense_list`, `expense_detail` | `period`, `category`; `expense_id` | `/chi-tieu`, hộp sửa khoản |
| `trip_list`, `trip_detail` | ; `trip_id`, `day_no` | `/lich-trinh`, `/lich-trinh/:id?ngay=` |
| `report` | `period` | `/bao-cao` |
| `settings_google`, `settings_listened_apps`, `settings_device_check`, `settings_profile`, `settings_ai_cost` | | `/cai-dat/<mục>` |

**Thẻ xác nhận.** Chỉ dùng cho việc mà `60` mục 3.12 bắt duyệt:

| Việc | Bản | Cần vân tay (`require_unlock`) |
|---|---|---|
| Xóa bất cứ thứ gì qua trợ lý (chi tiêu, việc, lịch, ghi chú, chuyến đi, tệp) | V1 | Khi xóa từ 2 dòng trở lên |
| Lưu sự kiện có khách mời, sửa sự kiện có người khác (QĐ-23) | V1.4 | Có |
| Gửi thư Gmail (soạn nháp thì không cần) | V1.8 | Có |
| Chia sẻ tệp Drive, xuất có chia sẻ cho người khác | V1.8 | Có |
| Trả lời tin qua thông báo | V2 | Có |

Không cần thẻ: xuất Word, ghi Sheets vào Drive của chính người dùng, đổi phương án lịch trình (đổi phương án chỉ hỏi bằng `ConfirmDialog` trên app), ghi nhớ hồ sơ. Đổi danh sách app được nghe chỉ làm ở Cài đặt, không qua trợ lý.

```
┌──────────────────────────────────────────┐
│ (ShieldCheck) Gửi thư cho anh Minh       │
│ Trả lời: Lịch họp thứ Năm                │
│ ──────────────────────────────────────── │
│ Đến: minh@...                            │
│ Nội dung: Chào anh, em xác nhận 9:00 ... │
│ [Xem đủ]                                 │
│                                          │
│ [   Bỏ   ]              [   Duyệt   ]    │
│ Hết hạn sau 23 giờ                       │
└──────────────────────────────────────────┘
```

| Trạng thái | Hiện |
|---|---|
| `pending` | `cancel_label` (viền, mặc định *Bỏ*) và `confirm_label` (màu nhấn; màu lỗi nếu `danger`) |
| đang gửi lệnh (chỉ trên app) | *Duyệt* thành vòng quay *Đang làm...*, *Bỏ* ẩn |
| `done` | Thu gọn một dòng `CircleCheck`: *Đã gửi lúc 14:32* |
| `failed` | Một dòng màu lỗi với câu từ máy chủ, `[Thử lại]` |
| `rejected` | Dòng mờ *Đã bỏ* |
| `expired` | Dòng mờ *Hết hạn, nhắn lại nếu vẫn cần* |

- Thẻ hiện **đúng nội dung sẽ chạy** (người nhận, nguyên văn, số dòng bị xóa) [`60` mục 3.12].
- Duyệt chỉ bằng nút: `POST /api/v1/chat/actions/{id}/approve`, bỏ bằng `.../reject`. Câu chat như *ok*, *đồng ý* không duyệt được.
- Hạn 24 giờ; trạng thái lưu ở `tab_pending_action`, mở lại app thấy đúng.
- Nút *Duyệt* chặn bấm đúp bằng `useRef`.

### 3.4 Trạng thái chung

| Trạng thái | Cách hiện | Dùng ở |
|---|---|---|
| Đang tải lần đầu | Khung xương đúng hình nội dung | Mọi danh sách |
| Đang tải lại | `RefreshCw` quay nhỏ cạnh dòng phụ, dữ liệu cũ vẫn hiện | Mọi màn |
| Rỗng | Thẻ giữa màn: icon `size-10` màu nhấn, 1 tới 2 câu **vì sao trống và làm gì tiếp**, 1 nút chính | Câu riêng ở mục 3.6 |
| Lỗi tải | Thẻ viền màu lỗi, câu `message` của phong bì, `[Thử lại]`. 5xx: *Máy chủ đang lỗi, thử lại sau ít phút.* | Mọi màn |
| Lỗi khi lưu | Toast màu lỗi; hộp sửa giữ dữ liệu đã nhập | Mọi hộp sửa |
| Mất mạng | Dải mảnh `WifiOff`: *Mất mạng. Đang xem dữ liệu lúc 10:32.* Nút lưu, xóa, duyệt khóa kèm chữ *Cần mạng* | Mọi màn |
| Phiên hết hạn | Tự làm mới bằng mã làm mới. Thiết bị bị thu hồi: về đăng nhập, toast *Máy này đã bị đăng xuất* | Toàn app |
| Thiếu quyền | Dải cảnh báo `TriangleAlert`, một câu, `[Bật]` mở đúng bước ở Kiểm tra máy | Hộp tin, Chi tiêu, Lịch |
| Trợ lý tạm không dùng được | Lỗi `AI_UNAVAILABLE`: bóng tin có *Trợ lý đang lỗi, thử lại sau.* và `[Gửi lại]`; màn khác dùng bình thường | Chat |
| Vượt mức cảnh báo chi phí AI tháng | Dải thông tin ở Chat và thẻ Báo cáo: *Chi phí AI tháng này 212 USD, đã quá mức cảnh báo 200 USD.* **Không chặn** chat (QĐ-15) | Chat, Báo cáo |
| Có bản mới | Dải thông tin ở Chat (luồng 6) | Chat, Cài đặt > Phiên bản |

**Lưu đệm khi mất mạng.** TanStack Query lưu bền vào bộ nhớ WebView (IndexedDB), giữ tối đa 7 ngày, chỉ các truy vấn:

| Dữ liệu | Phạm vi |
|---|---|
| Chat | Phiên hôm nay |
| Hộp tin | 100 cuộc mới nhất |
| Lịch, việc | 14 ngày tới và việc chưa xong |
| Chi tiêu | Tháng này |
| Lịch trình | Chuyến `planned` và chuyến đang đi |
| Báo cáo | Bản cuối |

Ghi luôn cần mạng, trừ chat: tin chưa gửi được giữ trong ô nhập với *Chưa gửi được* và `[Gửi lại]`. Đăng xuất xóa toàn bộ lưu đệm. Đổi gói giao diện không mất lưu đệm.

### 3.5 Thành phần dùng chung

| Thành phần | Ở | Dùng cho |
|---|---|---|
| `AppShell`, `BottomNav`, `MoreSheet` | `src/app/` | Khung, thanh dưới, tấm *Thêm* |
| `PageHeader`, `EmptyState`, `ErrorState`, `SkeletonList` | `shared/components` | Mục 3.4 |
| `OfflineBanner`, `PermissionBanner`, `UpdateBanner`, `CostWarningBanner` | `shared/components` | Mục 3.4 |
| `ActionList` (`MapButton`, `LinkButton`, `ScreenLink`, `MemoryLine`, `ChoiceChips`, `ConfirmCard`) | `shared/chat` | Mục 3.3, dùng ở Chat và tấm *Tóm tắt* của Hộp tin |
| `Money`, `AppTag`, `WeekStrip` | `shared/components` | Tiền, nhãn app, dải 7 ngày (lấy từ app gym) |
| `ConfirmDialog`, `Dialog`, `Sheet` | `shared/ui` | shadcn |
| `useBackButton`, `useAppResume`, `useNetwork` | `shared/hooks` | Quay lại, quay lại tiền cảnh, mạng |

### 3.6 Màn hình

#### 3.6.1 Đăng nhập, đồng ý, khóa

```
┌──────────────────────────────────────────┐
│              (Bot) size-12               │
│                 Trợ lý                   │
│  Email                                   │
│  [______________________________]        │
│  Mật khẩu                                │
│  [______________________________] (Eye)  │
│  [            Đăng nhập            ]     │
│  Tài khoản do chủ app cấp.               │
└──────────────────────────────────────────┘
```

- Địa chỉ máy chủ gắn sẵn trong bản build. Sai mật khẩu: câu lỗi dưới ô, không xóa email. Tài khoản còn mật khẩu tạm: chuyển thẳng màn đổi mật khẩu.
- **Màn đồng ý** (`/dong-y`, chỉ cho tài khoản thành viên lần đầu; chủ không thấy, `60` mục 3.10): bản thông báo xử lý dữ liệu ngắn (dữ liệu gì, gửi tới đâu: Anthropic ở Mỹ, Google, Cloudflare; giữ bao lâu; chủ máy chủ đọc được DB), số phiên bản thông báo, hai nút `[Đồng ý]` và `[Để sau]`. *Để sau* vẫn dùng được chat, nhưng bước *Đọc thông báo* bị khóa với chữ *Cần đồng ý xử lý dữ liệu trước*. Ghi bằng `POST /api/v1/consents`.
- **Màn khóa** (khi bật khóa vân tay): icon `Fingerprint`, `[Mở khóa]`; hộp vân tay tự bật khi màn hiện.

#### 3.6.2 Chat (màn chính)

```
┌──────────────────────────────────────────┐
│ Trợ lý                     (Volume2)(…)  │
│ Haiku 5.5 · tháng này 1,84 USD           │
├──────────────────────────────────────────┤
│                    ┌───────────────────┐ │
│                    │ cơm trưa 45k      │ │
│                    └───────────────────┘ │
│ ┌──────────────────────────────┐         │
│ │ Đã ghi 45.000 đ, Ăn uống.    │         │
│ └──────────────────────────────┘         │
│ (CircleCheck) Sửa khoản này          (>) │
│                    ┌───────────────────┐ │
│                    │ chỉ đường tới chỗ │ │
│                    │ ăn trưa           │ │
│                    └───────────────────┘ │
│ ┌──────────────────────────────┐         │
│ │ Điểm kế tiếp: Bún nước lèo   │         │
│ │ Cô Ba, 12 km, khoảng 25 phút.│         │
│ └──────────────────────────────┘         │
│ [(Navigation) Dẫn đường tới Cô Ba     ]  │
├──────────────────────────────────────────┤
│ (Plus) (Mic) [Nhắn cho trợ lý    ] (Send)│
├──────────────────────────────────────────┤
│  Trợ lý  Hộp tin  Lịch  Chi tiêu  Thêm   │
└──────────────────────────────────────────┘
```

- **Phiên theo ngày tách lúc 04:00** giờ Việt Nam (QĐ-20): chat lúc 01:00 vẫn thuộc phiên hôm trước.
- **Đầu màn:** model và chi phí AI tháng này. `Volume2` bật tắt đọc câu trả lời. Ba chấm: *Phiên trước* (tóm tắt các ngày), *Xóa phiên hôm nay* (`ConfirmDialog`, gọi `DELETE /api/v1/chat/conversations/{id}`).
- **Bóng chat:** người dùng bên phải nền màu nhấn; trợ lý bên trái nền thẻ có viền; Markdown tối giản. Ghi chú hệ thống là viên nhỏ ở giữa.
- **Đang nghĩ:** vòng quay và *Em đang nghĩ...*; khi có sự kiện `tool.started` thì chữ đổi theo `label` (ví dụ *Đang ghi khoản chi*). Chữ trả lời hiện dần theo `text.delta`. Mất kết nối giữa chừng: tải lại tin hôm nay, không gửi lại câu hỏi.
- **Ô nhập:** cố định trên thanh dưới; tối đa **4.000 ký tự** (`12` mục 3.7), quá 3.800 thì hiện bộ đếm. `(Plus)`: *Ảnh*, *Tệp* (Word, PDF); tối đa 4 tệp, tải lên R2 bằng URL ký sẵn, có thanh tiến trình. `(Mic)`: chạm để nói, chạm để dừng; chữ tạm hiện trong ô; nói xong tự gửi.
- **Rỗng:** icon `Bot`, *Nhắn một câu là em ghi, tra, nhắc. Bấm micro để nói.* và nút gợi ý: *Hôm nay có tin gì quan trọng?*, *cơm trưa 45k*, *Tháng này tiêu bao nhiêu rồi?*, *Nhắc 15:00 gọi cho khách*, *Lịch tuần này*, *Chỉ đường tới điểm kế tiếp*.
- **Lỗi gửi:** *Chưa gửi được* và `[Gửi lại]`, chữ trở về ô nhập. Trợ lý từ chối: *Em không trả lời được câu này.*

#### 3.6.3 Hộp tin

```
┌──────────────────────────────────────────┐
│ Hộp tin               (Sparkles)(Filter) │
│ 12 tin mới · cập nhật 10:32              │
├──────────────────────────────────────────┤
│ [Quan trọng 3] [Tất cả] [Zalo] [Tele]    │
│ [Mess] [SMS] [Gmail]                     │
├──────────────────────────────────────────┤
│ QUAN TRỌNG                               │
│ (Star) [Zalo] Chị Lan            09:12   │
│        Chiều nay họp lúc 3h nha em  (2)  │
│ ──────────────────────────────────────── │
│ (Star) [Gmail] Ngân hàng X        08:40  │
│        Thông báo thay đổi biểu phí       │
├──────────────────────────────────────────┤
│ HÔM NAY                                  │
│        [Tele] Nhóm Dự án A        10:20  │
│        Tuấn: file mới đã up              │
│        [Zalo] Anh Hùng            07:55  │
│        Có tin mới (nội dung bị ẩn)       │
└──────────────────────────────────────────┘
```

- **Hàng lọc** cuộn ngang; mặc định *Quan trọng* nếu có tin quan trọng chưa xem.
- **Mỗi dòng là một cuộc trò chuyện** gom theo `conversation_key` (app và tiêu đề cuộc, cả nhóm chat), lấy từ `GET /api/v1/inbox/threads`. Nhãn app, tên, giờ tin cuối, chữ cuối, số tin mới. Tin bị ẩn nội dung: chữ nghiêng *Có tin mới (nội dung bị ẩn)*.
- **Chạm dòng:** `/hop-tin/:threadKey`, đánh dấu đã xem. Nút cuối: `[Đánh dấu đã xử lý]`, `[Người quan trọng]`, `[Hỏi trợ lý về cuộc này]`.
- **Vuốt trái:** *Đã xử lý*.
- **`(Sparkles)` Tóm tắt:** tấm trượt, tóm tắt theo bộ lọc đang chọn kèm `ActionList`; `[Hỏi thêm trong chat]`. Cách gọi (endpoint riêng hay lượt chat ẩn) theo cách `12` và `20` chốt ở A2 dòng 33.
- **`(Filter)`:** khoảng thời gian (hôm nay, 3, 7, 30 ngày, tất cả) và trạng thái.
- **Rỗng:** icon `Inbox`, *Chưa có tin nào. Tin Zalo, Telegram, Messenger, SMS hiện ở đây khi điện thoại nhận thông báo; thư Gmail có từ bản 1.8.* `[Kiểm tra máy]` nếu chưa bật nghe.
- **Thiếu quyền:** *Chưa bật đọc thông báo nên chưa nhận tin mới.* `[Bật]`.
- **Lâu không có tin:** đã bật nghe nhưng quá 24 giờ không có sự kiện: *Đã 26 giờ chưa nhận tin nào. Kiểm tra pin và chế độ ngủ của Samsung.* `[Kiểm tra]`.
- Chân danh sách: *Tin giữ 180 ngày rồi tự xóa.* (QĐ-17)

#### 3.6.4 Lịch và việc

```
┌──────────────────────────────────────────┐
│ Lịch                         (RefreshCw) │
│ Google Calendar · đồng bộ 10:30          │
├──────────────────────────────────────────┤
│ [ Lịch ] [ Việc 4 ]     [Ngày|Tuần|Tháng]│
│  T2  T3  T4  T5  T6  T7  CN              │
│  17 (18) 19  20  21  22  23              │
│      ••   •       •                      │
├──────────────────────────────────────────┤
│ Thứ Ba, 18/11                            │
│ 09:00  Họp nhóm          (Bell) 15' App  │
│        Phòng 3 · 3 khách                 │
│ 15:00  Gọi khách A       (Bell) Google   │
│ ──────────────────────────────────────── │
│ VIỆC HẠN HÔM NAY                         │
│ [ ] Gửi báo giá        (Flag) cao        │
│ [x] Nộp tiền điện                        │
│                                     (+)  │
└──────────────────────────────────────────┘
```

- **Lịch, kiểu Ngày** (mặc định): `WeekStrip`, chấm dưới ngày có sự kiện; sự kiện theo giờ, rồi việc có hạn ngày đó. **Tuần:** 7 nhóm ngày nối nhau. **Tháng:** lưới, chạm ngày về kiểu Ngày.
- **Mỗi sự kiện:** giờ, tiêu đề, địa điểm, số khách, `Bell` kèm **nguồn nhắc**: *App* (app nhắc trên máy, kèm số phút) hoặc *Google* (app Google Calendar nhắc) (`40` mục 4.6).
- **Hộp sửa sự kiện:**

```
┌──────────────────────────────────────────┐
│ Sửa sự kiện                          (X) │
│ Tiêu đề   [Họp nhóm                    ] │
│ Bắt đầu   [18/11 09:00]  Kết thúc [10:00]│
│ [ ] Cả ngày                              │
│ Địa điểm  [Phòng 3                     ] │
│ Khách mời [minh@... (x)] [lan@... (x)]   │
│           [+ Thêm email               ]  │
│ Ai nhắc   [ App nhắc ] [ Google nhắc ]   │
│ Nhắc trước [0][5][15][30][60] [Báo thức] │
│ Ghi chú   [                            ] │
│ [Xóa]                         [  Lưu  ]  │
└──────────────────────────────────────────┘
```

  - **Khách mời** (QĐ-23): nhập email, chọn gợi ý từ Google Contacts (V1.8). Lưu sự kiện có khách, hoặc sửa sự kiện đã có khách, **không lưu ngay**: tạo thẻ xác nhận *Gửi lời mời tới 2 người* hiện ngay trong hộp (dùng `ConfirmCard`), duyệt bằng vân tay rồi mới ghi và gửi. Không có khách thì lưu thẳng.
  - **Ai nhắc:** *App nhắc* thì hiện hàng *Nhắc trước*; *Google nhắc* thì ẩn hàng đó và ghi *Google Calendar trên máy sẽ nhắc*.
  - Có địa điểm thì có `[Dẫn đường]`. `[Xóa]` qua `ConfirmDialog`; sự kiện có khách thì xóa cũng qua thẻ xác nhận.
- **Việc** (`/lich/viec`): nhóm *Quá hạn* (màu lỗi), *Hôm nay*, *Sắp tới*, *Không hạn*, *Đã xong* (thu gọn). Tích hoàn thành ngay, có hoàn tác bằng toast. Hộp sửa: tiêu đề, hạn (ngày, có giờ hoặc không), ưu tiên, ghi chú. Việc có giờ thành sự kiện lịch (QĐ-09). Việc tích xong hoặc xóa trên Google Tasks ở máy khác sẽ tự hiện xong hoặc biến mất sau lần đồng bộ kế tiếp (QĐ-21); dòng đó có nhãn nhỏ *xong trên Google Tasks*.
- **`(+)` nổi:** *Thêm sự kiện* hoặc *Thêm việc*. Dòng gợi ý: *Hoặc nhắn trợ lý: nhắc 15:00 gọi khách.*
- **Rỗng:** *Ngày trống.* `[Thêm]`. Chưa kết nối Google: *Kết nối Google Calendar để thấy lịch ở đây và trên máy khác.* `[Kết nối]`.
- **Thiếu quyền:** *Nhắc sẽ không kêu vì thông báo đang tắt.* `[Bật]`.
- **Lỗi đồng bộ Google** (`GOOGLE_REAUTH_REQUIRED`): *Mất kết nối Google, lịch đang dừng đồng bộ.* `[Kết nối lại]`.

#### 3.6.5 Chi tiêu

```
┌──────────────────────────────────────────┐
│ Chi tiêu                        (Filter) │
│ Tháng 11                                 │
├──────────────────────────────────────────┤
│ ┌────────────┐┌────────────┐┌──────────┐ │
│ │ Hôm nay    ││ Tuần này   ││ Tháng    │ │
│ │ 165k       ││ 1,2 tr     ││ 6,8 tr   │ │
│ └────────────┘└────────────┘└──────────┘ │
│ [Tất cả] [Ăn uống] [Đi lại] [Mua sắm] ...│
├──────────────────────────────────────────┤
│ CẦN XEM LẠI (1)                          │
│ (CircleHelp) 250.000 đ  Chưa rõ khoản    │
│              TCB ...4821 · 11:05  [Sửa]  │
├──────────────────────────────────────────┤
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

- **Ba thẻ tổng** (chi), chạm đổi kỳ; thu là dòng nhỏ màu `--income`.
- **Lọc:** danh mục; `(Filter)` thêm nguồn (chat, ngân hàng, MoMo, tay), khoảng ngày, thu hay chi.
- **Cần xem lại:** dòng có `needs_review` (`11`) đứng đầu, nền cảnh báo nhạt.
- **Dòng:** icon danh mục, khoản, số tiền, danh mục, nguồn, giờ. Nguồn ngân hàng hiện mã ngân hàng và **4 số cuối** tài khoản; **không có số dư** (QĐ-22). Khoản `kind = transfer` (chuyển nội bộ) chữ mờ, nhãn *chuyển nội bộ*, không tính vào tổng.
- **Chạm dòng:** hộp sửa: số tiền (gõ `45k` được), khoản, danh mục (viên chọn, một chạm là lưu), nơi, thời điểm, ghi chú, chi hay thu. `[Xóa]` qua `ConfirmDialog`. Dòng từ ngân hàng có phần thu gọn *Thông báo gốc* để đối chiếu (đã bỏ số dư).
- **`(+)` nổi:** ghi tay. Gợi ý: *Hoặc nhắn trợ lý: cơm trưa 45k.*
- **Có dòng mới từ ngân hàng** khi đang mở app: toast *Đã ghi 120.000 đ, Grab (Vietcombank)* với *Sửa*.
- **Rỗng:** icon `Wallet`, *Chưa có khoản nào trong kỳ này. Nhắn trợ lý như "cơm trưa 45k", hoặc bật đọc thông báo để tự ghi từ Vietcombank, Techcombank, MoMo.* `[Ghi tay]`.
- **Thiếu quyền:** *Chưa bật đọc thông báo nên chưa tự ghi từ ngân hàng.* `[Bật]`.

#### 3.6.6 Lịch trình

**Danh sách chuyến** (`/lich-trinh`):

```
┌──────────────────────────────────────────┐
│ Lịch trình                               │
├──────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │
│ │ Phước Hải – Trà Vinh       [Đã lên]  │ │
│ │ 21/11 – 23/11 · 3 ngày · xe máy      │ │
│ │ 412 km · 2 rủi ro                    │ │
│ └──────────────────────────────────────┘ │
│ ┌──────────────────────────────────────┐ │
│ │ Đà Lạt cuối tuần   [Đang đọc tệp...] │ │
│ └──────────────────────────────────────┘ │
│ [ (Upload) Nhập lịch trình            ]  │
└──────────────────────────────────────────┘
```

- Chuyến đang đi đứng đầu, viền màu nhấn, mở thẳng ngày hôm nay.
- **Nhập lịch trình:** *Gửi tệp (Word, PDF, ảnh)*, *Dán link*, *Mô tả bằng lời*; cả ba sang Chat với tệp hoặc câu soạn sẵn. Nhập và đánh giá chạy nền (`202` kèm `job_id`): thẻ chuyến hiện *Đang đọc tệp...*, *Đang đánh giá...*; xong thì có thẻ hành động *Xem chuyến ...* trong Chat.
- **Rỗng:** icon `Route`, *Chưa có chuyến nào. Gửi tệp lịch trình hoặc kể chuyến đi, em lên lịch, chỉ ra rủi ro và mở Google Maps chế độ xe máy.* `[Nhập lịch trình]`.

**Chi tiết chuyến** (`/lich-trinh/:id`):

```
┌──────────────────────────────────────────┐
│ (ChevronLeft) Phước Hải – Trà Vinh  (…)  │
│ Phương án: Đúng giờ, ít rủi ro           │
├──────────────────────────────────────────┤
│ (MapPinOff) 2 điểm cần xác nhận   [Xem]  │
│ (TriangleAlert) 2 rủi ro          [Xem]  │
├──────────────────────────────────────────┤
│ [Ngày 1 · T6] [Ngày 2 · T7] [Ngày 3 · CN]│
├──────────────────────────────────────────┤
│ 06:00 (Bike) Xuất phát Phước Hải         │
│ 08:30 (Utensils) Bún nước lèo Cô Ba      │
│       85 km · khoảng 2 giờ 10            │
│       [(Navigation) Dẫn đường] [Xem]     │
│ 10:00 (Ship) Phà Cổ Chiên                │
│       Chuyến cuối 18:30  (Clock) mốc cứng│
│       [(Navigation) Dẫn đường] [Xem]     │
│ 14:00 (Landmark) Bảo tàng Khmer          │
│       (TriangleAlert) Đóng cửa thứ Hai   │
│       [(Navigation) Dẫn đường] [Xem]     │
│ ──────────────────────────────────────── │
│ [ (Map) Xem đường cả ngày (1/2) ]        │
│ [ (Map) Xem đường cả ngày (2/2) ]        │
│ Thời gian xe máy do Google ước tính      │
│ (bản thử nghiệm), có thể lệch.           │
└──────────────────────────────────────────┘
```

- **Điểm cần xác nhận** (`41` mục 5.3): tấm trượt, mỗi dòng có tên trong tệp, 1 tới 3 gợi ý (địa chỉ ngắn, nút *Xem* mở Maps tìm kiếm kèm `query_place_id`), nút *Chọn*, nút *Bỏ qua* (giữ link tìm kiếm, không có tọa độ). Điểm bỏ qua có nhãn vàng *chưa định vị*, nút *Dẫn đường* thay bằng *Xem* tìm kiếm.
- **Thẻ ngày** cuộn ngang. Mỗi điểm: giờ dự kiến, icon theo loại (`Utensils`, `BedDouble`, `Landmark`, `Ship`, `Bike`, `ShoppingBag`, `Hotel`), tên, km và giờ chạy từ điểm trước, cảnh báo nếu có, `[Dẫn đường]` (`open_map_navigation`) và `[Xem]`. Điểm có dự phòng: *2 lựa chọn khác*.
- **Cuối mỗi ngày:** một nút mỗi đoạn *Xem đường cả ngày* từ `GET /api/v1/trips/{id}/map-links?day_no=&max_waypoints=` (app gửi 9 nếu có Google Maps, 3 nếu không, `30` mục 3.12). Dưới số liệu luôn có dòng cố định *Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.* (`41`)
- **Rủi ro:** tấm trượt liệt kê theo mức đỏ, vàng.
- **Menu ba chấm:** *So sánh phương án* (2 tới 3 phương án: km, giờ chạy, giờ chạy đêm, số rủi ro; *Chọn*; đổi phương án đang dùng thì `ConfirmDialog` trên app, không cần thẻ duyệt), *Đưa vào lịch* (mỗi ngày một sự kiện cả ngày và sự kiện có giờ cho mốc cứng, nhắc do app; xong thì toast *Đã đưa 5 mục vào lịch*), *Xuất Word* (tạo tệp, mở hoặc chia sẻ; có *Lưu lên Drive* khi đã nối Drive), *Hỏi trợ lý về chuyến này*, *Xóa chuyến* (`ConfirmDialog`).
- **Mất mạng:** chuyến đã lưu đệm xem được đủ; *Dẫn đường* vẫn dùng được vì chỉ cần tọa độ.

#### 3.6.7 Báo cáo và thông số

```
┌──────────────────────────────────────────┐
│ Báo cáo                    [Tuần|Tháng]  │
│ Tháng 11 · cập nhật 10:32                │
├──────────────────────────────────────────┤
│ ┌ Chi tiêu ───────────────────────────┐  │
│ │ 6,8 tr  (TrendingUp) +12% tháng trước│ │
│ │ ███████ Ăn uống 2,1 tr              │  │
│ │ █████   Đi lại 1,4 tr               │  │
│ └─────────────────────────────────────┘  │
│ ┌ Lịch tuần ──────┐ ┌ Hộp tin ───────┐   │
│ │ 9 sự kiện       │ │ 3 quan trọng   │   │
│ │ 2 việc quá hạn  │ │ 12 chưa xử lý  │   │
│ └─────────────────┘ └────────────────┘   │
│ ┌ Chi phí AI ─────┐ ┌ Thiết bị ──────┐   │
│ │ 1,84 USD tháng  │ │ Đang nghe      │   │
│ │ mức báo 200 USD │ │ tin cuối 10:31 │   │
│ │ ▁▂▁▃▂▁▂ (ngày)  │ │ chặn 3 OTP     │   │
│ └─────────────────┘ └────────────────┘   │
│ ┌ Sức khỏe (V2) ──────────────────────┐  │
│ └─────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- **Chi tiêu:** tổng kỳ, so kỳ trước, thanh 5 danh mục lớn nhất (recharts).
- **Lịch tuần**, **Hộp tin:** số liệu, chạm sang màn tương ứng.
- **Chi phí AI** (QĐ-15): chi tháng này so với **mức cảnh báo 200 USD** (`AI_MONTHLY_USD`), cột theo ngày. Không có trần ngày. Vượt mức thì thẻ viền cảnh báo, chat vẫn dùng bình thường.
- **Thiết bị:** dịch vụ nghe, tin cuối, hàng đợi, số tin OTP đã chặn hôm nay. Chạm sang Kiểm tra máy.
- **Sức khỏe:** V2; chưa bật thì *Có ở bản V2*.
- Không có nút *Gửi báo cáo* (QĐ-11). Lỗi một thẻ chỉ thẻ đó hiện *Không tải được* `[Thử lại]`.

#### 3.6.8 Cài đặt

```
┌──────────────────────────────────────────┐
│ Cài đặt                                  │
├──────────────────────────────────────────┤
│ Gia Bảo · giabao@...                     │
│ (FileText)    Hồ sơ lõi              (>) │
│ (Link)        Kết nối Google   3/6   (>) │
│ (BellRing)    App được nghe    7     (>) │
│ (Star)        Người quan trọng 5     (>) │
│ (Coins)       Chi phí AI 1,84 USD    (>) │
│ (ShieldCheck) Kiểm tra máy (TriangleAlert)│
│ (Smartphone)  Thiết bị         1     (>) │
│ (Lock)        Khóa và bảo mật        (>) │
│ (Database)    Dữ liệu của tôi        (>) │
│ (Server)      Máy chủ (chủ)          (>) │
│ (Download)    Phiên bản 1.5.2        (>) │
│ [            Đăng xuất            ]      │
└──────────────────────────────────────────┘
```

| Mục (đường dẫn) | Nội dung |
|---|---|
| **Hồ sơ lõi** (`/cai-dat/ho-so`) | Ô sửa Markdown, đếm ký tự trên 8.000, phiên bản, ai sửa lần cuối; danh sách bản cũ, *Khôi phục* một bản. *Trợ lý đọc phần này ở mọi câu trả lời.* |
| **Kết nối Google** (`/cai-dat/google`) | Email Google, *Đã kết nối* hoặc *Cần kết nối lại*. Dịch vụ: Calendar, Tasks (V1.4), Gmail, Contacts, Drive, Sheets (V1.8), mỗi dịch vụ công tắc, lần đồng bộ cuối, lỗi. Chưa tới bản thì *Có ở bản 1.8*. `[Kết nối]` hoặc `[Ngắt kết nối]` (`ConfirmDialog`). Luồng 3 |
| **App được nghe** (`/cai-dat/app-nghe`) | 8 app mặc định (`30` mục 3.5): tên, mục đích, *Đã cài* hoặc *Không thấy trên máy*, tin cuối, công tắc. App SMS ghi *(app SMS mặc định)* cạnh dòng đang bật. Đã nối Gmail thì dòng Gmail ghi *Thư lấy qua Gmail, không nghe thông báo*. `[Thêm app]` nhập tên gói tay. Công tắc **Cho trợ lý đọc hộp tin** (`inbox.ai_enabled`, `60`): tắt thì trợ lý không tóm tắt hay tra tin của người khác. Chân: *Thông báo của app ngoài danh sách bị bỏ ngay trên điện thoại. Tin có mã OTP luôn bị bỏ.* |
| **Người quan trọng** (`/cai-dat/nguoi-quan-trong`) | Người (theo tên trên thông báo, theo app hoặc mọi app), gợi ý từ người gửi gần đây. Phần **Từ khóa gấp** (mặc định *gấp*, *hôm nay*, *họp*). |
| **Chi phí AI** (`/cai-dat/chi-phi-ai`) | Chi tháng này so với mức cảnh báo 200 USD (chỉ xem, đặt ở máy chủ); cột 30 ngày; chia theo việc (chat, tóm tắt hộp tin, bóc tách thông báo, lịch trình); model; tỉ lệ đọc cache. Không có trần ngày (QĐ-15) |
| **Kiểm tra máy** (`/cai-dat/kiem-tra-may`) | Các bước của Thiết lập máy (luồng 2, gồm bước Samsung) với trạng thái; dịch vụ nghe kết nối không, tin cuối; *Đã chặn N tin OTP hôm nay* (bộ đếm riêng); số thông báo bỏ vì ngoài danh sách; hàng đợi và `[Gửi ngay]`; số nhắc đã đặt trong 14 ngày; Google Maps đã cài chưa; hãng máy, bản Android |
| **Thiết bị** (`/cai-dat/thiet-bi`) | Máy đã đăng nhập, *Máy này*; `[Đăng xuất máy này]` cho máy khác (`ConfirmDialog`); đổi tên máy |
| **Khóa và bảo mật** (`/cai-dat/bao-mat`) | *Khóa bằng vân tay*, *Khóa sau* (ngay, 1, 5, 15 phút); *Đổi mật khẩu*; giải thích dữ liệu nào rời điện thoại (thông báo của app được nghe, đã bỏ OTP) và giữ bao lâu (tin của người khác **180 ngày**, QĐ-17) |
| **Dữ liệu của tôi** (`/cai-dat/du-lieu`) | *Xuất toàn bộ dữ liệu* (`POST /api/v1/me/export`, nhận link tải khi xong); đồng ý đã cho và *Rút đồng ý* (rút `data_processing` thì tắt nghe thông báo, xóa hộp tin; `ConfirmDialog`); *Xóa tài khoản* (`DELETE /api/v1/me`, `ConfirmDialog` gõ lại email) |
| **Máy chủ** (`/cai-dat/may-chu`, chỉ chủ) | Lần sao lưu gần nhất và số bản đang giữ (QĐ-16), dung lượng ổ đĩa còn trống, trạng thái các job, `otp_blocked_server` (phải bằng 0), từ `GET /api/v1/admin/worker` (`50`) |
| **Phiên bản** (`/cai-dat/phien-ban`) | Bản app và bản giao diện; `[Kiểm tra cập nhật]`; ghi chú bản mới; `[Cập nhật]` khi có bản APK (luôn hỏi, QĐ-18); `[Mở lại để dùng giao diện mới]` khi có gói chờ |

### 3.7 Luồng chính

#### Luồng 1. Lần đầu mở app

```
Mở app ──> Có mã làm mới? ──không──> Đăng nhập ──> Mật khẩu tạm? ──có──> Đổi mật khẩu
              │                          │                                    │
              có                         v                                    │
              │                   Thành viên? ──có──> Màn đồng ý ─────────────┤
              v                          │                                    │
        Khóa bật? ──có──> Màn khóa       không                                │
              │              │           v                                    v
              không       vân tay   Đặt tên máy, đăng ký thiết bị ──> Thiết lập máy (luồng 2)
              v              │                                                │
            Chat <───────────┴──────────────── Bật khóa vân tay? [Bật] [Để sau] <┘
                 (lần đầu: lời chào + gợi ý)
```

- Màn chờ chỉ có biểu tượng app trên nền tối, tối đa 1 giây.
- Lời chào lần đầu kèm thẻ *Kết nối Google Calendar* nếu chưa kết nối.

#### Luồng 2. Cấp quyền (Thiết lập máy)

```
┌──────────────────────────────────────────┐
│ Thiết lập máy                    [Để sau]│
│ 4 bước để trợ lý nghe tin và nhắc lịch   │
├──────────────────────────────────────────┤
│ (CircleCheck) 1. Cho phép thông báo      │
│               Để nhắc lịch, báo bản mới  │
│ (Circle)      2. Đọc thông báo   [Bật]   │
│               Gom tin Zalo, Telegram,    │
│               tự ghi chi tiêu ngân hàng. │
│               Bị khóa xám? [Xem cách mở] │
│ (Circle)      3. Pin không hạn chế [Bật] │
│ (Circle)      4. Không cho ngủ (Samsung) │
│               [Mở danh sách]  [Đã làm]   │
│ ──────────────────────────────────────── │
│ App SMS: Samsung Messages (mặc định) [Đổi]│
├──────────────────────────────────────────┤
│ [              Xong               ]      │
└──────────────────────────────────────────┘
```

1. Mỗi bước: icon trạng thái, tên, một câu lý do, nút. Quay lại app thì kiểm lại ngay, bước xong tự tích, toast *Đã bật ...*.
2. **Bị khóa xám** (cài đặt bị hạn chế): tấm hướng dẫn 4 bước, nút cuối `[Mở thông tin ứng dụng]`:
   1. Bấm *Bật* ở bước 2 một lần, thấy công tắc bị khóa thì quay lại đây.
   2. Bấm *Mở thông tin ứng dụng*.
   3. Bấm menu ba chấm góc trên, chọn *Cho phép cài đặt bị hạn chế*, xác nhận.
   4. Quay lại, bấm *Bật* ở bước 2 lần nữa.
3. **Bước 4, chỉ trên máy Samsung:** `[Mở danh sách]` mở thẳng *Ứng dụng không bao giờ ngủ*; mở không được thì hiện đường tay *Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > Trợ lý > Thêm*. App không đọc được danh sách này nên người dùng bấm `[Đã làm]` để tích. Dòng phụ: *Samsung tự cho app ngủ sau vài ngày không mở; khi đó nhắc lịch và tin mới có thể không tới.*
4. **App SMS:** tự chọn theo app SMS mặc định của máy (Samsung Messages hoặc Google Messages, QĐ-19); `[Đổi]` chọn app còn lại.
5. Thành viên chưa đồng ý xử lý dữ liệu: bước 2 khóa với *Cần đồng ý xử lý dữ liệu trước* `[Xem]`.
6. Báo thức chính xác và cài app không rõ nguồn chỉ hiện khi cần (`30` mục 3.10).
7. `[Để sau]` và `[Xong]` đều vào Chat; bước thiếu hiện banner ở màn liên quan và ở Kiểm tra máy.

#### Luồng 3. Kết nối Google

```
Cài đặt > Kết nối Google ──> Màn giải thích ──[Kết nối]──> POST /google/connect ──> auth_url
                              • quyền sẽ xin                         │
                              • Google báo "chưa xác minh":          v
                                bấm Nâng cao > Đi tới...   Custom Tabs (trình duyệt ngoài)
                                                                     │ chọn tài khoản, đồng ý
                                                                     v
                              Trang máy chủ: Đã kết nối ──> troly://cai-dat/google?ket-qua=ok
                                                                     │
                                                                     v
                      App: đóng Custom Tabs, tải lại GET /google/account, chọn dịch vụ bật
                                                                     │
                                                                     v
                      Đồng bộ lần đầu: "Đang lấy lịch (30 ngày trước tới 1 năm sau)..." ──> Lịch
```

- Không mở trong WebView của app (Google chặn OAuth trong trình duyệt nhúng).
- `ket-qua=huy`: toast *Chưa kết nối, có thể thử lại bất cứ lúc nào.* `ket-qua=thieu-quyen`: hiện dịch vụ thiếu quyền và *Kết nối lại*.
- Người dùng đóng trình duyệt giữa chừng: khi app quay lại tiền cảnh thì tải lại trạng thái, không báo lỗi.
- Khoảng đồng bộ lần đầu theo cách `11` và `40` chốt (A2 dòng 11, 81); chữ trên màn lấy từ trạng thái máy chủ trả về.

#### Luồng 4. Duyệt hành động

```
Người dùng: "xóa mấy khoản trùng hôm qua"
        │
        v
Trợ lý trả lời + thẻ xác nhận (pending): "Xóa 2 khoản chi hôm qua" + từng dòng
        │
        ├──[Bỏ]──> POST .../reject ──> "Đã bỏ"
        │
        └──[Duyệt]──> require_unlock? ──có──> hộp vân tay ──hủy──> giữ pending
                          │                       │
                          không                   đúng
                          v                       v
                    "Đang làm..." POST .../approve
                          │
                ┌─────────┴─────────┐
                v                   v
          done "Đã xóa 2 khoản"   failed: câu lỗi + [Thử lại]
          (toast + tải lại Chi tiêu)
```

- Hạn 24 giờ; dùng một lần; mở trên máy khác thấy trạng thái đã đổi.
- Gõ *ok* trong chat không duyệt; trợ lý nhắc bấm nút trên thẻ.
- Không hành động nào trong bảng mục 3.3 chạy mà không qua thẻ này.

#### Luồng 5. Mở bản đồ

```
Chạm [Dẫn đường] (Chat hoặc Lịch trình)
        │
        v
Maps.navigate(lat, lng, mode=l, avoid=h)
        ├── có Google Maps ──> mở thẳng dẫn đường xe hai bánh, tránh cao tốc
        └── chưa có ──> mở URL Google Maps trên trình duyệt + toast "Máy chưa có Google Maps"

Chạm [Xem đường cả ngày (1/2)] ──> Maps.openUrl(url máy chủ dựng) ──> Google Maps, travelmode=two-wheeler
```

- Điểm chưa định vị: không có *Dẫn đường*, chỉ *Xem* tìm kiếm hoặc *Xác nhận địa điểm*.
- Trợ lý không tự mở bản đồ; người dùng luôn là người chạm.
- Quay lại app: màn và vị trí cuộn giữ nguyên.

#### Luồng 6. Cập nhật app

```
Mở app ──> checkWeb / checkApk
   ├── có gói giao diện mới ──> tải ngầm, kiểm chữ ký ──> dải nhỏ "Có giao diện mới. [Mở lại ngay]"
   └── có APK mới ──> dải ở Chat: "Có bản 1.6.0: lịch trình và bản đồ. [Cập nhật] [Để sau]"
           │
           [Cập nhật] (người dùng bấm, QĐ-18)
           │
           ├── chưa cho cài app không rõ nguồn ──> hướng dẫn 1 bước, mở cài đặt
           v
       Tải (thanh tiến trình) ──> cài (không cần bấm lần hai, hoặc hộp xác nhận của Android)
           v
       App tự mở lại ──> toast "Đã cập nhật lên 1.6.0"
```

Không bao giờ tự tải hay cài khi người dùng chưa bấm. Bản bắt buộc: màn chắn toàn app với ghi chú bản mới và một nút `[Cập nhật]`.

## 4. Dữ liệu cần

Giao diện không có bảng riêng. Cần ở máy chủ (agent kiến trúc gom vào `11`):

| Dữ liệu | Đề xuất | Dùng ở |
|---|---|---|
| Hành động chờ duyệt | `tab_pending_action` (A1 dòng 1), có `require_unlock` | Thẻ xác nhận |
| Cần xem lại | `tab_expense.needs_review` (đã có ở `11`) | Chi tiêu |
| Cuộc trò chuyện | `tab_inbox_message.conversation_key` (A1 dòng 13) | Hộp tin |
| Khách mời | Cột hoặc bảng khách mời của sự kiện theo `11` và `40` (QĐ-23) | Hộp sửa sự kiện |
| Nguồn nhắc | `tab_event.remind_source` (`app`, `google`) | Lịch |
| Cài đặt | `tab_setting`: `app.lock_enabled`, `app.lock_after_minutes`, `ui.voice_reply`, `inbox.ai_enabled` | Cài đặt |
| Đồng ý | `tab_consent` (`60`) | Màn đồng ý, Dữ liệu của tôi |

Lưu đệm phía máy theo mục 3.4.

## 5. API hoặc giao tiếp

Giao diện gọi API qua `src/core/api` (phong bì, câu lỗi tiếng Việt, rẽ nhánh theo `data.code`) và plugin qua `src/core/native` (`30` mục 3.4). Đường dẫn dưới `/api/v1`:

| Màn | Gọi |
|---|---|
| Đăng nhập, đồng ý | `/auth/login`, `/auth/refresh`, `/auth/change-password`, `POST /devices`, `GET`, `POST /consents` |
| Chat | `GET /chat/today`, `GET /chat/conversations`, `POST /chat/messages` (SSE), `POST /chat/actions/{id}/approve`, `/reject`, `DELETE /chat/conversations/{id}`, tải tệp `/files/*`, `/memory/profile/revisions/{v}/restore` cho *Hoàn tác* ghi nhớ |
| Hộp tin | `GET /inbox/threads`, tin của một cuộc, đánh dấu đã xem, đã xử lý, người quan trọng, tóm tắt (theo A2 dòng 33) |
| Lịch và việc | `/events`, `/tasks`, `/calendar/reminders` (để chuyển cho plugin), `/google/account` |
| Chi tiêu | `/expenses` có lọc và con trỏ, tổng theo kỳ, danh mục |
| Lịch trình | `/trips`, `/trips/{id}`, `/trips/{id}/stops/{stop_id}/resolve`, `/trips/{id}/options/{option_id}/choose`, `/trips/{id}/map-links`, `/trips/{id}/export-docx`, `/trips/{id}/to-calendar` (A2 dòng 26), `/jobs/{id}` |
| Báo cáo | `GET /reports/dashboard`, `GET /reports/ai-cost` |
| Cài đặt | `/memory/profile`, `/google/*`, `/devices/listened-apps`, `/inbox/rules`, `/settings`, `/devices`, `/me/export`, `DELETE /me`, `/consents`, `/admin/worker` (chủ), `/device/release`, `/device/web-bundle` |

Query key đặt hết ở `src/shared/constants/query-keys.ts`.

## 6. Kiểm thử

**Vitest** (cạnh tệp, chạy trong dịch vụ `web-test`):

| Phần | Ca chính |
|---|---|
| `ConfirmCard` | đủ 5 trạng thái máy chủ và trạng thái đang gửi; bấm *Duyệt* hai lần chỉ gửi một lệnh; `require_unlock` gọi `Secure.unlock` trước; vân tay hủy giữ `pending` |
| `ActionList` | mỗi `type` của mục 3.3 hiện đúng; `type` lạ bị bỏ; `open_link` không phải `https` bị bỏ; `screen` ánh xạ đúng đường dẫn |
| Hộp sửa sự kiện | có khách mời thì không lưu thẳng mà ra thẻ xác nhận; *Google nhắc* ẩn hàng *Nhắc trước* |
| `Money`, ngày giờ | `45000` thành `45.000 đ`, `45k`; `1200000` thành `1,2 tr`; giờ Việt Nam; phiên chat tách 04:00 |
| Nút quay lại | đúng thứ tự mục 3.2 |
| `OfflineBanner` | mất mạng khóa nút lưu; có mạng lại thì tải lại |
| Chat | gửi lỗi giữ chữ, *Gửi lại*; quá 4.000 ký tự không gửi; vượt mức cảnh báo chỉ hiện dải, không khóa |
| Lưu đệm | đăng xuất xóa hết; chỉ truy vấn trong bảng mục 3.4 được lưu |

**Kiểm bằng mắt** ở khổ 360 x 780 trên trình duyệt (bản giả plugin) và trên Galaxy S25+: mọi màn ở các trạng thái tải, rỗng, lỗi, mất mạng, thiếu quyền; bàn phím không che ô nhập chat; vùng an toàn với thanh điều hướng cử chỉ của One UI.

**Luồng đầu cuối trên máy thật:** 6 luồng ở mục 3.7, cùng danh sách `30` mục 6.3.

## 7. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Nhiều mảng trong một app làm rối | Thanh dưới chỉ 4 mảng hằng ngày; mọi thứ hỏi trợ lý được; xem lại sau 2 tuần dùng thật |
| Hộp tin giữ 180 ngày (QĐ-17), danh sách dài làm WebView giật | Gom theo cuộc, phân trang con trỏ, tải dần; chỉ dựng dòng trong khung nhìn khi quá 200 dòng |
| Bàn phím ảo che ô nhập trong Capacitor 8 | Thử trên S25+ ở V1.0; `env(safe-area-inset-bottom)`, `dvh` như app gym |
| Lưu đệm trong WebView chứa tin nhắn và chi tiêu | Phạm vi nhỏ, hạn 7 ngày, xóa khi đăng xuất; khóa vân tay |
| Người dùng quên bước Samsung, app bị cho ngủ | Bước riêng trong Thiết lập máy; dải *Lâu không có tin* ở Hộp tin; thẻ Thiết bị ở Báo cáo |
| Thẻ hành động sai định dạng | Bỏ qua `type` lạ, kiểm dữ liệu ở biên |

## 8. Câu hỏi mở

1. Có cần chế độ nền sáng không, hay chỉ nền tối như app gym?
2. Trợ lý đọc to câu trả lời: mặc định bật hay tắt? Đề xuất: tắt.
3. Khi có giao dịch ngân hàng mới lúc app đang đóng, có cần thông báo hệ thống không? Đề xuất: không (QĐ-11).

Đã đóng: bố cục thanh dưới (ĐX-31-01 đã duyệt), tự chỉnh trần ngày (QĐ-15 bỏ trần ngày), người dùng thứ hai (QĐ-15).

## 9. Cần agent khác

| Agent | Tệp | Việc |
|---|---|---|
| AI | `20` | Thêm `choices`; cờ `require_unlock` trong `confirm` theo bảng mục 3.3; bảng `screen`; `inbox_thread` dùng `thread_key`; tạo hoặc sửa sự kiện có khách mời trả `confirm` |
| kiến trúc | `11` | `tab_pending_action.require_unlock`; `conversation_key`; `remind_source`; khóa `ui.voice_reply`, `inbox.ai_enabled` |
| kiến trúc | `12` | `DELETE /chat/conversations/{id}`; `/inbox/threads` theo `conversation_key`; `/reports/ai-cost` trả `monthly_warning_usd` thay `daily_limit_usd` (QĐ-15); `/trips/{id}/map-links` nhận `max_waypoints`; `/me/export`, `DELETE /me`, `/consents`; `/admin/worker` có trạng thái sao lưu, ổ đĩa; giới hạn 4.000 ký tự giữ nguyên |
| Google | `40`, `41` | Trạng thái đồng bộ lần đầu trả câu hiện được; khách mời và nguồn nhắc trong API sự kiện; `to-calendar` dùng `remind_source = app` |
| hạ tầng | `60` | Đối chiếu bảng *Cần vân tay* ở mục 3.3 |

## 10. Đề xuất quyết định

ĐX-31-01 tới ĐX-31-07 đã duyệt theo QĐ-25 (ĐX-31-03 nay theo bộ kiểu của `20`, thêm `choices` và `require_unlock`). Đề xuất mới:

| Số | Đề xuất | Lý do |
|---|---|---|
| ĐX-31-08 | Thẻ chi phí AI chỉ hiện chi tháng so với mức cảnh báo 200 USD; vượt mức chỉ hiện dải, không khóa chat | QĐ-15 |
| ĐX-31-09 | Lưu sự kiện có khách mời đi qua thẻ xác nhận ngay trong hộp sửa, có vân tay | QĐ-23; `60` mục 3.12 |
| ĐX-31-10 | Thêm mục *Dữ liệu của tôi* (xuất, rút đồng ý, xóa tài khoản) và *Máy chủ* (chỉ chủ) trong Cài đặt | Quyền của chủ thể ở `60`; trạng thái sao lưu, ổ đĩa ở `50` |
| ĐX-31-11 | Cột *cần vân tay* theo bảng mục 3.3 (xóa nhiều dòng, gửi ra ngoài, khách mời) | Chặn người khác cầm máy bấm duyệt |

## 11. Nguồn

- App gym: `D:\giabao\gymcanhan\CLAUDE.md` (mục Giao diện), `web/src/index.css`, `web/src/app/app-layout.tsx`, `web/src/modules/coach/pages/coach-page.tsx`.
- Thông tin nền tảng (Custom Tabs, quyền, Samsung, Google Maps, cập nhật): mục Nguồn của [30-app-android.md](30-app-android.md).
- Google chặn OAuth trong trình duyệt nhúng (lỗi `disallowed_useragent`): https://developers.google.com/identity/protocols/oauth2/native-app
