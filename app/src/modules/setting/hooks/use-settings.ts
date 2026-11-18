import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { getSettings, patchSettings, type SettingValues } from '@/modules/setting/api/setting-api'
import { queryKeys } from '@/shared/constants/query-keys'

export function useSettings() {
  return useQuery({ queryKey: queryKeys.setting.values, queryFn: getSettings, select: (data) => data.values })
}

// Lưu ngay từng khóa khi đổi; máy chủ kiểm giá trị và trả câu lỗi tiếng Việt.
export function usePatchSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values: Partial<SettingValues>) => patchSettings(values),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.setting.values, (old: { values: SettingValues; defaults: SettingValues } | undefined) =>
        old ? { ...old, values: { ...old.values, ...data.values } } : old,
      )
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}
