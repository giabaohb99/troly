import { cn } from '@/shared/utils/cn'

// Biểu tượng app (bong bóng chat có tia), cùng hình với ic_launcher_mark.xml của Android.
// Nền là ô bo góc màu chủ đạo; dùng ở màn đăng nhập và màn chat trống.
export function AppMark({ className }: { className?: string }) {
  return (
    <div className={cn('flex size-16 items-center justify-center rounded-2xl bg-primary', className)}>
      <svg viewBox="26 28 56 58" className="size-4/5" aria-hidden="true">
        <path
          className="fill-primary-foreground"
          d="M42,32 H66 A12,12 0 0 1 78,44 V58 A12,12 0 0 1 66,70 H52 L38,82 L42,70 A12,12 0 0 1 30,58 V44 A12,12 0 0 1 42,32 Z"
        />
        <path
          className="fill-primary"
          d="M54,39 C55.2,46.8 58.2,49.8 66,51 C58.2,52.2 55.2,55.2 54,63 C52.8,55.2 49.8,52.2 42,51 C49.8,49.8 52.8,46.8 54,39 Z"
        />
      </svg>
    </div>
  )
}
