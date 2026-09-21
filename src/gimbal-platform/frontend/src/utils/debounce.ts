/**
 * debounce.ts — 全站第一个公共防抖(M1 三件套之一,PG迁移方案 §6.1)。
 *
 * 收编 FieldStateSearch 的内联实现,useServerList 的 300ms 查询防抖
 * 是第一个消费方。trailing 调用(末次触发后 ``ms`` 毫秒执行一次)。
 */

export interface DebouncedFunction<F extends (...args: never[]) => void> {
  (...args: Parameters<F>): void
  cancel(): void
  /** 立即执行挂起中的末次调用(若无挂起则 no-op)。 */
  flush(): void
}

export function debounce<F extends (...args: never[]) => void>(
  fn: F,
  ms = 300,
): DebouncedFunction<F> {
  let timer: ReturnType<typeof setTimeout> | null = null
  let lastArgs: Parameters<F> | null = null

  const wrapped = ((...args: Parameters<F>) => {
    lastArgs = args
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      if (lastArgs) fn(...lastArgs)
      lastArgs = null
    }, ms)
  }) as DebouncedFunction<F>

  wrapped.cancel = () => {
    if (timer) clearTimeout(timer)
    timer = null
    lastArgs = null
  }
  wrapped.flush = () => {
    if (timer) clearTimeout(timer)
    timer = null
    const args = lastArgs
    lastArgs = null
    if (args) fn(...args)
  }
  return wrapped
}
