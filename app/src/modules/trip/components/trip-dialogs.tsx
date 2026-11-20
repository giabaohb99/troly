import { useState } from 'react'
import { Check, Loader2, MapPin, TriangleAlert } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { Maps, placeUrl } from '@/core/native/maps'
import { chooseCandidate, chooseOption, resolveStop, skipStop } from '@/modules/trip/api/trip-api'
import type { NeedsConfirmation, PlaceCandidate, Risk, Trip, TripOption } from '@/modules/trip/types/trip'
import { formatDuration, formatKm } from '@/modules/trip/utils/trip-utils'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { cn } from '@/shared/utils/cn'

interface DialogProps {
  trip: Trip
  open: boolean
  onOpenChange: (open: boolean) => void
}

function useInvalidateTrip(id: number) {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.trip.all }).then(() => queryClient.invalidateQueries({ queryKey: queryKeys.trip.detail(id) }))
}

function ConfirmPlaceRow({ trip, item }: { trip: Trip; item: NeedsConfirmation }) {
  const invalidate = useInvalidateTrip(trip.id)
  const [query, setQuery] = useState(item.place_query ?? item.title)
  const [found, setFound] = useState<PlaceCandidate[] | null>(null)
  const candidates = found ?? item.candidates
  const search = useMutation({
    mutationFn: () => resolveStop(trip.id, item.stop_id, query.trim()),
    onSuccess: (data) => setFound(data.candidates),
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const choose = useMutation({
    mutationFn: (index: number) => chooseCandidate(trip.id, item.stop_id, candidates[index]),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const skip = useMutation({
    mutationFn: () => skipStop(trip.id, item.stop_id),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const busy = choose.isPending || skip.isPending || search.isPending
  return (
    <li className="flex min-w-0 flex-col gap-2 py-3">
      <span className="text-sm">
        <span className="text-xs text-muted-foreground">Ngày {item.day_no} · trong tệp: </span>
        <span className="font-medium">{item.title}</span>
      </span>
      {candidates.length === 0 && <span className="text-xs text-muted-foreground">Google không tìm thấy điểm nào khớp, sửa chữ rồi Tìm lại.</span>}
      {candidates.map((candidate, index) => (
        <div key={candidate.place_id} className="flex min-w-0 items-center gap-1 rounded-xl bg-secondary py-2 pr-1 pl-3">
          <MapPin className="size-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1 text-sm">
            <span className="block truncate">{candidate.name}</span>
            {candidate.address && <span className="block truncate text-xs text-muted-foreground">{candidate.address}</span>}
          </span>
          <Button size="sm" variant="ghost" onClick={() => void Maps.openUrl({ url: placeUrl([candidate.name, candidate.address].filter(Boolean).join(', '), candidate.place_id) }).catch(() => toast.error('Không mở được bản đồ.'))}>
            Xem
          </Button>
          <Button size="sm" disabled={busy} onClick={() => choose.mutate(index)}>
            Chọn
          </Button>
        </div>
      ))}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (query.trim()) search.mutate()
        }}
      >
        <Input aria-label={`Tìm lại ${item.title}`} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={200} />
        <Button type="submit" size="sm" variant="secondary" className="h-9" disabled={busy || !query.trim()}>
          {search.isPending && <Loader2 className="size-4 animate-spin" />}
          Tìm lại
        </Button>
      </form>
      <Button size="sm" variant="outline" className="self-start" disabled={busy} onClick={() => skip.mutate()}>
        Bỏ qua, để chưa định vị
      </Button>
    </li>
  )
}

// Điểm cần xác nhận (41 mục 5.3): 1 tới 3 gợi ý, Chọn hoặc Bỏ qua.
export function ConfirmPlacesDialog({ trip, open, onOpenChange }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Điểm cần xác nhận</DialogTitle>
          <DialogDescription>Chọn đúng chỗ để dẫn đường và tính giờ chạy. Bỏ qua thì điểm không có Dẫn đường.</DialogDescription>
        </DialogHeader>
        {trip.needs_confirmation.length === 0 ? (
          <p className="text-sm text-muted-foreground">Đã xác nhận hết.</p>
        ) : (
          <ul className="min-w-0 divide-y">
            {trip.needs_confirmation.map((item) => (
              <ConfirmPlaceRow key={item.stop_id} trip={trip} item={item} />
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function RisksDialog({ trip, open, onOpenChange }: DialogProps) {
  const risks: Risk[] = [...(trip.evaluation?.risks ?? [])].sort((a, b) => (a.day_no ?? 0) - (b.day_no ?? 0) || Number(b.level === 'red') - Number(a.level === 'red'))
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Rủi ro</DialogTitle>
          <DialogDescription>Tính bằng luật trên giờ chạy Google ước tính cho xe máy.</DialogDescription>
        </DialogHeader>
        <ul className="divide-y">
          {risks.map((risk, index) => (
            <li key={index} className="flex gap-2 py-2.5 text-sm">
              <TriangleAlert className={cn('mt-0.5 size-4 shrink-0', risk.level === 'red' ? 'text-destructive' : 'text-warning')} />
              <span>
                <span className="text-xs text-muted-foreground">{risk.day_no ? `Ngày ${risk.day_no} · ` : ''}</span>
                {risk.message}
                {risk.suggestion && <span className="block text-xs text-muted-foreground">{risk.suggestion}</span>}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}

function OptionCard({ option, estimated, onChoose }: { option: TripOption; estimated: boolean; onChoose: () => void }) {
  return (
    <div className={cn('flex flex-col gap-1.5 rounded-2xl border p-3 text-sm', option.chosen && 'border-primary')}>
      <span className="flex items-center gap-2 font-semibold">
        {option.name}
        {option.chosen && (
          <span className="flex items-center gap-1 text-xs font-normal text-primary">
            <Check className="size-3.5" /> đang dùng
          </span>
        )}
      </span>
      {option.summary && <span className="text-muted-foreground">{option.summary}</span>}
      <span className="text-xs text-muted-foreground">
        {[formatKm(option.total_km), option.total_ride_minutes ? `chạy ${formatDuration(option.total_ride_minutes)}` : null, option.night_ride_minutes ? `chạy đêm ${formatDuration(option.night_ride_minutes)}` : null]
          .filter(Boolean)
          .join(' · ')}
        {estimated && (option.total_km || option.total_ride_minutes) ? ' (ước tính)' : ''}
      </span>
      <span className="flex gap-3 text-xs">
        <span className={option.red_count ? 'text-destructive' : 'text-muted-foreground'}>{option.red_count} đỏ</span>
        <span className={option.yellow_count ? 'text-warning' : 'text-muted-foreground'}>{option.yellow_count} vàng</span>
      </span>
      {option.changes.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground">
          {option.changes.map((change, index) => (
            <li key={index}>{change}</li>
          ))}
        </ul>
      )}
      {!option.chosen && (
        <Button size="sm" variant="secondary" className="self-start" onClick={onChoose}>
          Chọn phương án này
        </Button>
      )}
    </div>
  )
}

// So sánh phương án (41 mục 5.3): chọn phương án khác hỏi lại bằng ConfirmDialog vì ghi đè danh sách điểm.
export function OptionsDialog({ trip, open, onOpenChange }: DialogProps) {
  const invalidate = useInvalidateTrip(trip.id)
  const [picked, setPicked] = useState<TripOption | null>(null)
  const choose = useMutation({
    mutationFn: (optionId: number) => chooseOption(trip.id, optionId),
    onSuccess: () => {
      void invalidate()
      toast.success('Đã đổi phương án')
      onOpenChange(false)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85dvh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>So sánh phương án</DialogTitle>
            <DialogDescription>Số liệu do máy tính; lời tóm tắt do trợ lý viết.</DialogDescription>
          </DialogHeader>
          {choose.isPending && <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />}
          <div className="flex flex-col gap-3">
            {trip.options.length === 0 && <p className="text-sm text-muted-foreground">Chưa đánh giá nên chưa có phương án.</p>}
            {trip.options.map((option) => (
              <OptionCard key={option.id} option={option} estimated={trip.evaluation?.estimated === true} onChoose={() => setPicked(option)} />
            ))}
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={!!picked}
        onOpenChange={(value) => !value && setPicked(null)}
        title={`Đổi sang ${picked?.name ?? ''}?`}
        description="Danh sách điểm và giờ của chuyến sẽ thay theo phương án này."
        confirmLabel="Đổi phương án"
        danger={false}
        onConfirm={() => picked && choose.mutate(picked.id)}
      />
    </>
  )
}
