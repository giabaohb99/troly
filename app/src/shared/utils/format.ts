// Định dạng hiển thị theo giờ Việt Nam (31-giao-dien.md mục 3.1).

const TZ = 'Asia/Ho_Chi_Minh'
const WEEKDAYS = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy']

// 45000 thành "45.000 đ".
export function formatMoney(amount: number): string {
  return `${Math.round(amount).toLocaleString('vi-VN')} đ`
}

// Tóm tắt: 45000 thành "45k", 1200000 thành "1,2 tr", 2000000000 thành "2 tỷ".
export function formatMoneyShort(amount: number): string {
  const abs = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''
  const trim = (value: number) => value.toLocaleString('vi-VN', { maximumFractionDigits: 1 })
  if (abs >= 1_000_000_000) return `${sign}${trim(abs / 1_000_000_000)} tỷ`
  if (abs >= 1_000_000) return `${sign}${trim(abs / 1_000_000)} tr`
  if (abs >= 1_000) return `${sign}${trim(abs / 1_000)}k`
  return `${sign}${abs}`
}

// Đọc số tiền người dùng gõ: "45k", "45.000", "1,2tr", "1tr2", "2 triệu". Không đọc được thì null.
export function parseMoney(input: string): number | null {
  const text = input.trim().toLowerCase().replace(/\s+/g, '').replace(/đ|vnd|d$/g, '')
  if (!text) return null
  const millionMix = text.match(/^(\d+)(tr|triệu|m)(\d{1,3})$/)
  if (millionMix) return Number(millionMix[1]) * 1_000_000 + Number(millionMix[3].padEnd(3, '0')) * 1_000
  const match = text.match(/^(\d+(?:[.,]\d+)*)(k|ng|nghìn|ngàn|tr|triệu|m|tỷ|ty)?$/)
  if (!match) return null
  const unit = match[2]
  let numberText = match[1]
  if (unit) numberText = numberText.replace(',', '.')
  else numberText = numberText.replace(/[.,]/g, '')
  const value = Number(numberText)
  if (!Number.isFinite(value)) return null
  const multiplier = !unit ? 1 : ['k', 'ng', 'nghìn', 'ngàn'].includes(unit) ? 1_000 : ['tr', 'triệu', 'm'].includes(unit) ? 1_000_000 : 1_000_000_000
  const result = Math.round(value * multiplier)
  return result > 0 ? result : null
}

function partsInVietnam(date: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short', hour12: false }).formatToParts(date)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return { year: get('year'), month: get('month'), day: get('day'), hour: get('hour') === '24' ? '00' : get('hour'), minute: get('minute') }
}

// "14:30"
export function formatTime(iso: string): string {
  const p = partsInVietnam(new Date(iso))
  return `${p.hour}:${p.minute}`
}

// "YYYY-MM-DD" theo giờ Việt Nam, dùng để gom theo ngày.
export function toDateKey(iso: string | Date): string {
  const p = partsInVietnam(typeof iso === 'string' ? new Date(iso) : iso)
  return `${p.year}-${p.month}-${p.day}`
}

// "Thứ Hai, 18/11"
export function formatDayTitle(dateKey: string): string {
  const [y, m, d] = dateKey.split('-').map(Number)
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
  return `${weekday}, ${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`
}

// Nhãn model trên câu trả lời: "claude-sonnet-5-5" thành "Sonnet 5.5".
export function formatModelLabel(model: string | null | undefined): string | null {
  if (!model) return null
  const match = model.match(/^claude-([a-z]+)-(\d+)-(\d+)/)
  if (!match) return model
  return `${match[1].charAt(0).toUpperCase()}${match[1].slice(1)} ${match[2]}.${match[3]}`
}

export function formatUsd(value: number): string {
  return `${value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`
}

// Giờ nếu là hôm nay, không thì ngày "dd/mm" (danh sách hộp tin).
export function formatWhen(iso: string, todayKey: string = toDateKey(new Date())): string {
  const key = toDateKey(iso)
  if (key === todayKey) return formatTime(iso)
  const [, m, d] = key.split('-')
  return `${d}/${m}`
}
