// Giá trị `screen` của hành động open_screen ra đường dẫn trong app (12-api.md mục 3.9, 31 mục 3.2).
export function screenToRoute(screen: string, params: Record<string, string | number> | null): string {
  const p = params ?? {}
  switch (screen) {
    case 'chat':
      return p.conversation_id ? `/?phien=${p.conversation_id}` : '/'
    case 'search':
      return p.q ? `/tim?q=${encodeURIComponent(String(p.q))}` : '/tim'
    // Hai màn agent kiến trúc thêm vào 12 mục 3.9: ghi chú và tệp mở từ màn Tìm.
    case 'note_detail':
      return p.note_id ? `/tim?ghi-chu=${p.note_id}` : '/tim'
    case 'file_detail':
      return p.file_id ? `/tim?tep=${p.file_id}` : '/tim'
    case 'expense_list':
      return '/chi-tieu'
    case 'expense_detail':
      return p.expense_id ? `/chi-tieu?sua=${p.expense_id}` : '/chi-tieu'
    case 'inbox':
    case 'inbox_conversation':
      return '/hop-tin'
    case 'calendar_day':
      return p.date ? `/lich?ngay=${p.date}` : '/lich'
    case 'event_detail':
      if (!p.event_id) return '/lich'
      return p.occurrence_start ? `/lich/su-kien/${p.event_id}?lan=${encodeURIComponent(String(p.occurrence_start))}` : `/lich/su-kien/${p.event_id}`
    case 'task_list':
      return '/lich?tab=viec'
    case 'task_detail':
      return p.task_id ? `/lich/viec/${p.task_id}` : '/lich?tab=viec'
    case 'settings_google':
      return '/cai-dat/google'
    case 'settings_listened_apps':
    case 'settings_device_check':
      return '/thiet-lap'
    case 'trip_list':
    case 'trip_detail':
      return '/lich-trinh'
    case 'report':
      return '/bao-cao'
    default:
      return screen.startsWith('settings_') ? '/cai-dat' : '/'
  }
}
