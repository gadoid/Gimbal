import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * shadcn-vue 约定的类名合并工具:clsx 条件拼接 + tailwind-merge 冲突消解。
 * 组件源码里统一从 '@/lib/utils' 引 cn,不直接引 clsx/tailwind-merge。
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
