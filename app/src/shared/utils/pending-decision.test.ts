import { describe, expect, it } from 'vitest'
import { ApiError } from '@/core/api/api-error'
import { classifyDecisionError, decidedLabel, extraResult, initialStatus, isFinalStatus, outcomeFromAction, outcomeFromServer } from '@/shared/utils/pending-decision'

describe('thẻ duyệt', () => {
  it('chỉ tin trạng thái đã quyết trong tin; pending hoặc chưa biết thì hỏi máy chủ', () => {
    expect(isFinalStatus('done')).toBe(true)
    expect(isFinalStatus('expired')).toBe(true)
    expect(isFinalStatus('pending')).toBe(false)
    expect(isFinalStatus(undefined)).toBe(false)
  })

  it('bấm lại thẻ đã duyệt: giữ giờ duyệt của máy chủ, không lấy giờ bấm', () => {
    const o = outcomeFromAction({ status: 'done', decided_at: '2026-11-19T03:53:21Z' }, 'Đã làm xong.')
    expect(o.decidedAt).toBe('2026-11-19T03:53:21Z')
    expect(decidedLabel(o.decidedAt, '2026-11-19')).toBe('lúc 10:53')
    expect(decidedLabel(o.decidedAt, '2026-11-20')).toBe('lúc 10:53 19/11')
    expect(decidedLabel(null)).toBe('')
    expect(extraResult(o.resultText)).toBeNull()
    expect(extraResult('Đã không còn, không cần xóa.')).toBe('Đã không còn, không cần xóa.')
  })

  it('trạng thái ban đầu theo máy chủ, không tự tính hết hạn', () => {
    expect(initialStatus('failed', 'pending')).toBe('failed')
    expect(initialStatus(undefined, 'done')).toBe('done')
    expect(initialStatus(undefined, undefined)).toBe('pending')
  })

  it('kết quả duyệt: failed có lý do, không cho Thử lại', () => {
    expect(outcomeFromAction({ status: 'done' })).toMatchObject({ status: 'done', reason: null, transient: false })
    expect(outcomeFromAction({ status: 'failed', error: 'Chuyến đã bị xóa.' }, 'thất bại')).toMatchObject({ status: 'failed', reason: 'Chuyến đã bị xóa.', transient: false })
    expect(outcomeFromAction({ status: 'failed' }, 'Không tìm thấy chuyến.').reason).toBe('Không tìm thấy chuyến.')
    expect(outcomeFromAction({ status: 'pending' }).status).toBe('done')
  })

  it('trạng thái đọc lại từ máy chủ giữ nguyên, pending vẫn là pending', () => {
    expect(outcomeFromServer({ status: 'pending' }).status).toBe('pending')
    expect(outcomeFromServer({ status: 'failed', error: 'Đã xóa trước đó.' })).toMatchObject({ status: 'failed', reason: 'Đã xóa trước đó.', transient: false })
  })

  it('409 tải lại trạng thái; mạng, 5xx, 429 là lỗi tạm; 4xx khác là lỗi cuối', () => {
    expect(classifyDecisionError(new ApiError(409, 'Đã xử lý', 'ACTION_NOT_PENDING'))).toBe('refetch')
    expect(classifyDecisionError(new ApiError(409, 'Nháp đã bị sửa, hãy xem lại', 'ACTION_PAYLOAD_CHANGED'))).toBe('final')
    expect(classifyDecisionError(new ApiError(0, 'Mất mạng', 'NETWORK'))).toBe('transient')
    expect(classifyDecisionError(new ApiError(503, 'Bận', 'INTERNAL_ERROR'))).toBe('transient')
    expect(classifyDecisionError(new ApiError(429, 'Nhanh quá', 'RATE_LIMITED'))).toBe('transient')
    expect(classifyDecisionError(new ApiError(404, 'Không thấy', 'NOT_FOUND'))).toBe('final')
    expect(classifyDecisionError(new Error('lạ'))).toBe('transient')
  })
})
