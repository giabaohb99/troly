import { apiDelete, apiGet, apiPatch, apiPost, toQuery } from '@/core/api/http-client'
import type { MapLinks, PlaceCandidate, Stop, Trip, TripBrief } from '@/modules/trip/types/trip'

// Lịch trình (12 mục 5.7).
export const listTrips = () => apiGet<{ items: TripBrief[]; next_cursor: string | null }>('/trips')
export const getTrip = (id: number) => apiGet<Trip>(`/trips/${id}`)
// Đổi ngày đi: máy chủ dời giờ các điểm theo và bỏ cờ start_date_suggested.
export const updateTripStartDate = (id: number, startDate: string) => apiPatch<Trip>(`/trips/${id}`, { start_date: startDate })
export const deleteTrip = (id: number) => apiDelete<null>(`/trips/${id}`)
// mode think: AI tìm thêm giờ mở cửa trên web (QĐ-36).
export const evaluateTrip = (id: number, mode: 'normal' | 'think' = 'normal') => apiPost<{ job_id: number }>(`/trips/${id}/evaluate`, { mode })
export const chooseOption = (id: number, optionId: number) => apiPost<Trip>(`/trips/${id}/options/${optionId}/choose`)
export const getMapLinks = (id: number, dayNo: number, maxWaypoints: number) =>
  apiGet<MapLinks>(`/trips/${id}/map-links${toQuery({ day_no: dayNo, max_waypoints: maxWaypoints })}`)
export const exportDocx = (id: number) => apiPost<{ file_id: number; download_url: string }>(`/trips/${id}/export-docx`, { save_to_drive: false })
export const sendToCalendar = (id: number) => apiPost<{ event_ids: number[] }>(`/trips/${id}/to-calendar`)

// Điểm cần xác nhận: Chọn gửi place_id (kèm tọa độ nếu gợi ý có, như kết quả Tìm lại), máy chủ tự tra tọa độ;
// Bỏ qua để điểm ở trạng thái manual, không tọa độ (41 mục 5.3).
export const chooseCandidate = (tripId: number, stopId: number, place: PlaceCandidate) =>
  apiPatch<Stop>(
    `/trips/${tripId}/stops/${stopId}`,
    typeof place.lat === 'number' && typeof place.lng === 'number' ? { place_id: place.place_id, lat: place.lat, lng: place.lng } : { place_id: place.place_id },
  )
// Tìm lại gợi ý cho một điểm (Places, 41 mục 4).
export const resolveStop = (tripId: number, stopId: number, placeQuery: string) =>
  apiPost<{ candidates: PlaceCandidate[] }>(`/trips/${tripId}/stops/${stopId}/resolve`, { place_query: placeQuery })
export const skipStop = (tripId: number, stopId: number) => apiPatch<Stop>(`/trips/${tripId}/stops/${stopId}`, { resolve_status: 'manual' })
