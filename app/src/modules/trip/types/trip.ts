// Kiểu chuyến đi theo 12 mục 5.7, 11 (tab_trip, tab_trip_stop, tab_trip_option, tab_trip_fact), 41 mục 5, 6.
// Dạng JSON chi tiết đã đề xuất cho agent Google ở mục 5 bảng việc.

export type TripStatus = 'importing' | 'draft' | 'evaluating' | 'planned' | 'done' | 'failed'
export type TravelMode = 'motorbike' | 'car' | 'walk'
export type StopCategory = 'an_uong' | 'nghi' | 'tham_quan' | 'pha' | 'di_chuyen' | 'khach_san' | 'mua_sam' | 'khac'
export type StopRole = 'main' | 'alternative' | 'backup' | 'generic' | 'via'

export interface TripBrief {
  id: number
  title: string
  start_date: string | null
  end_date: string | null
  nights: number | null
  travel_mode: TravelMode
  status: TripStatus
  total_km: number | null
  red_count: number
  yellow_count: number
  needs_confirmation_count: number
  // QĐ-42: đã đi xong, lưu trữ (null khi chưa); is_past: đã lưu trữ hoặc ngày cuối đã qua.
  archived_at?: string | null
  is_past?: boolean
}

export interface Stop {
  id: number
  day_no: number
  seq: number
  title: string
  category: StopCategory
  role: StopRole
  // Điểm phụ (hoặc, dự phòng) trỏ về điểm chính; app gom dưới điểm chính.
  parent_stop_id: number | null
  source_url: string | null
  time_text: string | null
  planned_start: string | null
  planned_end: string | null
  approx: boolean
  fixed: boolean
  optional: boolean
  stay_minutes: number | null
  place_query: string | null
  // Xã/phường, tỉnh của điểm và chuỗi tìm đầy đủ *tên, xã/phường, tỉnh* (máy chủ dựng). Tìm theo tên trần thì Google
  // ra chỗ trùng tên gần người dùng (lỗi Phước Hải ra Cần Thơ).
  area?: string | null
  search_query?: string | null
  place_id: string | null
  lat: number | null
  lng: number | null
  resolve_status: 'ok' | 'uncertain' | 'not_found' | 'manual'
  phone: string | null
  cost_note: string | null
  note: string | null
  leg_km: number | null
  leg_minutes: number | null
  // Đặt chỗ bóc từ thư xác nhận (QĐ-49), chỉ có ở khách sạn tự gắn từ email. Gọi dùng `phone`, dẫn đường dùng tọa độ.
  booking?: StopBooking | null
}

export interface StopBooking {
  booking_id: number
  provider: string | null
  booking_ref: string | null
  check_in: string | null
  check_out: string | null
  guests: number | null
  // Máy chủ gửi chuỗi số thập phân ("1250000.00").
  price: string | number | null
  currency: string | null
  cancellation: string | null
  status: 'confirmed' | 'changed' | 'cancelled'
  source: 'email'
}

export interface TripDay {
  day_no: number
  date: string | null
  weekday_text: string | null
  title: string | null
  total_km: number | null
  ride_minutes: number | null
  stops: Stop[]
}

// Gợi ý trong Trip.needs_confirmation không có tọa độ (11 cấm lưu tọa độ Google); Tìm lại thì có.
export interface PlaceCandidate {
  name: string
  address: string | null
  place_id: string
  lat?: number | null
  lng?: number | null
}

export interface NeedsConfirmation {
  stop_id: number
  day_no: number
  title: string
  place_query: string | null
  candidates: PlaceCandidate[]
}

export interface TripFact {
  id: number
  kind: 'ferry_last' | 'ferry_first' | 'checkin' | 'checkout' | 'hotline' | 'opening_hours' | 'other'
  day_no: number | null
  stop_id: number | null
  value_time: string | null
  value_text: string | null
  text: string
}

export interface Risk {
  code: string
  level: 'red' | 'yellow'
  day_no: number | null
  stop_id: number | null
  message: string
  suggestion: string | null
  checked_at: string | null
}

export interface TripOption {
  id: number
  name: string
  summary: string | null
  total_km: number | null
  total_ride_minutes: number | null
  night_ride_minutes: number | null
  red_count: number
  yellow_count: number
  changes: string[]
  chosen: boolean
}

export interface Trip {
  id: number
  title: string
  start_date: string | null
  end_date: string | null
  travel_mode: TravelMode
  origin_text: string | null
  status: TripStatus
  error: string | null
  chosen_option_id: number | null
  archived_at?: string | null
  is_past?: boolean
  // true khi ngày đi là gợi ý thứ Bảy gần nhất; app hỏi xác nhận, PATCH start_date thì thành false.
  start_date_suggested: boolean
  // Lời khuyên ngắn của Sonnet; null khi chưa đánh giá.
  advice: string[] | null
  notes: string[]
  days: TripDay[]
  needs_confirmation: NeedsConfirmation[]
  facts: TripFact[]
  options: TripOption[]
  // estimated: km và giờ chạy do AI ước tính (QĐ-36, chưa có Maps Platform).
  evaluation: { evaluated_at: string; risks: Risk[]; estimated?: boolean } | null
}

// GET /trips/{id}/map-links: hành động phẳng như của chat (12 mục 3.9).
export interface MapDirections {
  id: string
  type: 'open_map_directions'
  label: string
  urls: string[]
  segment_labels: string[]
}

export interface MapNavigation {
  id: string
  type: 'open_map_navigation'
  label: string
  lat: number | null
  lng: number | null
  query: string | null
  mode: string
  avoid: string | null
  uri?: string | null
  fallback_url: string
}

export interface MapLinks {
  day_no: number
  segments: MapDirections[]
  stops: { stop_id: number; lat: number; lng: number; navigation: MapNavigation; place: { query: string; place_id: string | null } }[]
}
