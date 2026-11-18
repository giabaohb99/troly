import { useRef, useState, type FormEvent } from 'react'
import { Bot, Loader2 } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { getErrorMessage } from '@/core/api/api-error'
import { useLogin, useSession } from '@/modules/auth/hooks/use-session'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

export function LoginPage() {
  const session = useSession()
  const loginMutation = useLogin()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const submittingRef = useRef(false)

  if (session.data) return <Navigate to="/" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (submittingRef.current) return
    submittingRef.current = true
    setError('')
    try {
      await loginMutation.mutateAsync({ email: email.trim(), password })
      navigate('/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      submittingRef.current = false
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-8 px-6 pt-[env(safe-area-inset-top)]">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Bot className="size-8" />
        </div>
        <h1 className="text-2xl font-bold">Trợ lý</h1>
        <p className="text-sm text-muted-foreground">Đăng nhập một lần, app nhớ tới 365 ngày.</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" inputMode="email" autoComplete="username" autoCapitalize="none" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Mật khẩu</Label>
          <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={loginMutation.isPending}>
          {loginMutation.isPending && <Loader2 className="size-4 animate-spin" />}
          Đăng nhập
        </Button>
      </form>
    </div>
  )
}
