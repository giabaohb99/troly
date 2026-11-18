import { apiGet, toQuery } from '@/core/api/http-client'

// GET /search (12-api.md mục 5.3): tìm toàn văn, gõ không dấu vẫn ra (QĐ-27 mục 11).

export type SearchSource = 'note' | 'chat' | 'inbox' | 'trip' | 'file'

export interface SearchHit {
  source: SearchSource
  id: number
  title: string
  rank: number
  snippet: string
  date: string | null
  open: { screen: string; params: Record<string, string | number> | null } | null
}

export const searchEverything = (q: string, types: SearchSource[] | null, signal?: AbortSignal) =>
  apiGet<{ items: SearchHit[] }>(`/search${toQuery({ q, types: types?.join(','), limit: 30 })}`, { signal })
