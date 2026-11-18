import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { System, type PermissionSnapshot } from '@/core/native/system'
import { queryKeys } from '@/shared/constants/query-keys'

// Trạng thái quyền của máy; tự đọc lại khi người dùng quay lại từ trang cài đặt hệ thống.
export function usePermissions() {
  const queryClient = useQueryClient()
  useEffect(() => {
    const handle = System.addListener('permissionsChanged', (snapshot: PermissionSnapshot) => {
      queryClient.setQueryData(queryKeys.device.permissions, snapshot)
    })
    return () => {
      void handle.then((h) => h.remove())
    }
  }, [queryClient])
  return useQuery({ queryKey: queryKeys.device.permissions, queryFn: () => System.getPermissions(), staleTime: 0 })
}
