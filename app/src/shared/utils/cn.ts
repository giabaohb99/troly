import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// Gộp class Tailwind: điều kiện + giải xung đột (class sau thắng). Cấm nối chuỗi class bằng tay.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
