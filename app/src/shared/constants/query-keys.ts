// Mọi query key của TanStack Query đặt ở đây (luật như app gym).
export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  chat: {
    today: ['chat', 'today'] as const,
    status: ['chat', 'status'] as const,
    conversations: ['chat', 'conversations'] as const,
    conversation: (id: number) => ['chat', 'conversation', id] as const,
  },
  expense: {
    all: ['expense'] as const,
    list: (filters: Record<string, unknown>) => ['expense', 'list', filters] as const,
    summary: (period: string) => ['expense', 'summary', period] as const,
    categories: ['expense', 'categories'] as const,
  },
  search: {
    results: (q: string, types: string) => ['search', q, types] as const,
  },
  memory: {
    profile: ['memory', 'profile'] as const,
  },
  device: {
    release: ['device', 'release'] as const,
    list: ['device', 'list'] as const,
    permissions: ['device', 'permissions'] as const,
    notifyStatus: ['device', 'notify-status'] as const,
    listenedApps: ['device', 'listened-apps'] as const,
    alarms: ['device', 'alarms'] as const,
  },
  calendar: {
    all: ['calendar'] as const,
    events: (range: { from: string; to: string }) => ['calendar', 'events', range] as const,
    event: (id: number, occurrence: string | null) => ['calendar', 'event', id, occurrence] as const,
    tasks: (status: string) => ['calendar', 'tasks', status] as const,
    task: (id: number) => ['calendar', 'task', id] as const,
  },
  google: {
    status: ['google', 'status'] as const,
    outbox: ['google', 'outbox'] as const,
  },
  inbox: {
    all: ['inbox'] as const,
    conversations: (filters: Record<string, unknown>) => ['inbox', 'conversations', filters] as const,
    messages: (key: string) => ['inbox', 'messages', key] as const,
  },
}
