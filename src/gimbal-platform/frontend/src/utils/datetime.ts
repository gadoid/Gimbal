/**
 * datetime.ts — 共享日期/相对时间格式化。
 *
 * relTime：短相对时间（"刚刚" / "3m 前" / "2h 前" / "5d 前"），
 * 供 CaseDataSetsList / CaseDetailView 等视图共用。
 */
export function relTime(v?: string): string {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}m 前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h 前`
  return `${Math.floor(hr / 24)}d 前`
}
