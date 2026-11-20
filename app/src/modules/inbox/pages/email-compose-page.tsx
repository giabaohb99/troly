import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ChevronLeft, Loader2, Send } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getErrorMessage } from '@/core/api/api-error'
import { confirmOfPending } from '@/modules/inbox/utils/compose'
import { createDraft, parseEmails, sendDraft } from '@/modules/inbox/api/gmail-api'
import { GmailConnectHint, isGmailNotConnected } from '@/modules/inbox/components/gmail-connect-hint'
import { defaultSenderId, useGoogleAccounts } from '@/shared/api/google-accounts-api'
import { ConfirmCard } from '@/shared/components/confirm-card'
import type { ConfirmInfo } from '@/shared/types/pending-action'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'

interface ComposeState {
  to?: string[]
  cc?: string[]
  subject?: string
  threadRef?: string | null
  // Tài khoản nhận luồng thư đang trả lời (QĐ-50).
  accountEmail?: string | null
}

// Soạn thư mới hoặc trả lời (QĐ-43): soạn xong tạo nháp rồi xin gửi; máy chủ trả thẻ duyệt, thư chỉ đi khi bấm Duyệt.
export function EmailComposePage() {
  const navigate = useNavigate()
  const initial = (useLocation().state ?? {}) as ComposeState
  const [to, setTo] = useState((initial.to ?? []).join(', '))
  const [cc, setCc] = useState((initial.cc ?? []).join(', '))
  const [subject, setSubject] = useState(initial.subject ?? '')
  const [body, setBody] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [saving, setSaving] = useState(false)
  const [pending, setPending] = useState<ConfirmInfo | null>(null)
  const savingRef = useRef(false)
  const isReply = !!initial.threadRef
  // Gửi từ (QĐ-50): chỉ hiện khi có từ hai tài khoản Gmail; mặc định tài khoản của luồng thư, không thì tài khoản chính.
  const accounts = useGoogleAccounts()
  const senders = (accounts.data ?? []).filter((a) => a.status !== 'revoked')
  const [senderId, setSenderId] = useState<number | null>(null)
  useEffect(() => {
    if (senderId === null && accounts.data) setSenderId(defaultSenderId(accounts.data, initial.accountEmail))
  }, [accounts.data, senderId, initial.accountEmail])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (savingRef.current) return
    const toList = parseEmails(to)
    const ccList = parseEmails(cc)
    const bad = [...toList.invalid, ...ccList.invalid]
    if (toList.valid.length === 0 || bad.length > 0) {
      setError(new Error(bad.length ? `Email chưa đúng: ${bad.join(', ')}` : 'Cần ít nhất một người nhận.'))
      return
    }
    if (!body.trim()) {
      setError(new Error('Thư chưa có nội dung.'))
      return
    }
    savingRef.current = true
    setSaving(true)
    setError(null)
    try {
      const draft = await createDraft({ to: toList.valid, cc: ccList.valid, subject: subject.trim(), body: body.trim(), thread_ref: initial.threadRef ?? null, account_id: senderId })
      const result = await sendDraft(draft.id)
      setPending(confirmOfPending(result.pending_action, toList.valid.length))
    } catch (err) {
      setError(err)
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate(-1)}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="text-lg font-bold">{isReply ? 'Trả lời thư' : 'Thư mới'}</h1>
      </div>
      {isGmailNotConnected(error) && <GmailConnectHint />}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {senders.length > 1 && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mail-from">Gửi từ</Label>
            <select
              id="mail-from"
              value={senderId ?? ''}
              disabled={!!pending}
              onChange={(e) => setSenderId(Number(e.target.value))}
              className="h-10 rounded-md border border-input bg-background px-3 text-base outline-none focus:ring-2 focus:ring-ring"
            >
              {senders.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.email}
                  {a.role === 'primary' ? ' (chính)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mail-to">Tới</Label>
          <Input id="mail-to" type="text" inputMode="email" autoComplete="off" value={to} disabled={!!pending} onChange={(e) => setTo(e.target.value)} placeholder="ten@example.com, ..." />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mail-cc">Cc</Label>
          <Input id="mail-cc" type="text" inputMode="email" autoComplete="off" value={cc} disabled={!!pending} onChange={(e) => setCc(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mail-subject">Tiêu đề</Label>
          <Input id="mail-subject" value={subject} disabled={!!pending} onChange={(e) => setSubject(e.target.value)} maxLength={300} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mail-body">Nội dung</Label>
          <Textarea id="mail-body" value={body} disabled={!!pending} onChange={(e) => setBody(e.target.value)} rows={8} maxLength={20000} />
        </div>
        {!!error && !isGmailNotConnected(error) && (
          <p className="text-sm text-destructive" role="alert">
            {getErrorMessage(error)}
          </p>
        )}
        {!pending && (
          <Button type="submit" disabled={saving}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            Tạo thẻ gửi
          </Button>
        )}
      </form>
      {pending && (
        <ConfirmCard
          action={pending}
          className="max-w-full"
          onDecided={(status) => {
            if (status === 'done') navigate('/hop-tin?loai=gmail', { replace: true })
          }}
        />
      )}
    </div>
  )
}
