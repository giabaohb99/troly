import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, History } from 'lucide-react'
import { apiGet } from '@/core/api/http-client'
import { MessageBubble } from '@/modules/chat/components/message-bubble'
import type { ChatMessage } from '@/modules/chat/types/chat'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'

// Xem một phiên chat cũ (màn chat có conversation_id, mở từ kết quả Tìm). Chỉ xem, không gửi.
export function PastConversation({ conversationId, onBack }: { conversationId: number; onBack: () => void }) {
  const messages = useQuery({
    queryKey: queryKeys.chat.conversation(conversationId),
    queryFn: () => apiGet<{ items: ChatMessage[] }>(`/chat/conversations/${conversationId}/messages?limit=200`),
  })

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Về hôm nay" onClick={onBack}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          <History className="size-5 text-primary" />
          Phiên trước
        </h1>
      </div>
      {messages.isPending && <SkeletonList rows={4} />}
      {messages.isError && <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />}
      {/* Máy chủ trả tin mới trước; đảo lại để đọc từ trên xuống. */}
      {[...(messages.data?.items ?? [])]
        .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
        .map((message) => (
          <MessageBubble key={message.id} role={message.role} text={message.text} model={message.model} citations={message.citations} attachments={message.attachments} />
        ))}
      <Button variant="secondary" onClick={onBack}>
        Về chat hôm nay
      </Button>
    </div>
  )
}
