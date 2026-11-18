import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { onSessionChange } from '@/core/auth/session'
import { fetchMe, login, logout } from '@/modules/auth/api/auth-api'
import { queryKeys } from '@/shared/constants/query-keys'

export function useSession() {
  const queryClient = useQueryClient()
  useEffect(
    () =>
      onSessionChange((loggedIn) => {
        if (!loggedIn) queryClient.setQueryData(queryKeys.auth.me, null)
      }),
    [queryClient],
  )
  return useQuery({ queryKey: queryKeys.auth.me, queryFn: fetchMe, staleTime: 5 * 60_000, retry: 1 })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) => login(email, password),
    onSuccess: (user) => queryClient.setQueryData(queryKeys.auth.me, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(queryKeys.auth.me, null)
    },
  })
}
