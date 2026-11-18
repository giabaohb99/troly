import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { listConversationMessages } from '@/modules/chat/api/chat-api'
import type { ChatMessage } from '@/modules/chat/types/chat'
import { hasGap } from '@/modules/chat/utils/older-messages'

interface OlderState {
  conversationId: number | null
  // Con trỏ của trang mới nhất lúc bắt đầu tải tin cũ.
  startCursor: string | null
  items: ChatMessage[]
  cursor: string | null
}

const EMPTY: OlderState = { conversationId: null, startCursor: null, items: [], cursor: null }

// Tin cũ đã tải giữ trong bộ nhớ theo phiên: chuyển tab rồi quay lại màn chat không phải tải lại.
let saved: OlderState = EMPTY

// Màn chat chỉ tải 50 tin mới nhất (/chat/today); kéo lên gần đầu thì tải trang cũ hơn bằng
// GET /chat/conversations/{id}/messages?cursor= (mỗi trang cũ trước, next_cursor là id tin cũ nhất).
export function useOlderMessages(conversationId: number | null, latestCursor: string | null) {
  const [state, setState] = useState<OlderState>(() => (saved.conversationId !== null && saved.conversationId === conversationId ? saved : EMPTY))
  useEffect(() => {
    saved = state
  }, [state])
  const [loading, setLoading] = useState(false)
  const loadingRef = useRef(false)

  // Đổi phiên (qua ngày, xóa phiên) hoặc có khoảng hở: coi như chưa tải tin cũ; lần tải sau bắt đầu lại.
  const stale = state.items.length > 0 && (state.conversationId !== conversationId || hasGap(state.startCursor, latestCursor))

  const items = stale ? [] : state.items
  const cursor = items.length > 0 ? state.cursor : latestCursor
  const hasMore = !!cursor && !!conversationId

  const loadOlder = useCallback(async (): Promise<ChatMessage[]> => {
    if (loadingRef.current || !cursor || !conversationId) return []
    loadingRef.current = true
    setLoading(true)
    try {
      const page = await listConversationMessages(conversationId, cursor, 50)
      setState((prev) => {
        const base = prev.conversationId === conversationId && !hasGap(prev.startCursor, latestCursor) ? prev : EMPTY
        return {
          conversationId,
          startCursor: base.startCursor ?? latestCursor,
          items: [...page.items, ...base.items],
          cursor: page.next_cursor,
        }
      })
      return page.items
    } catch (error) {
      toast.error(getErrorMessage(error))
      return []
    } finally {
      loadingRef.current = false
      setLoading(false)
    }
  }, [conversationId, cursor, latestCursor])

  return { older: items, hasMore, loading, loadOlder }
}
