/**
 * datetime.ts — 共享日期/相对时间格式化。
 *
 * relTime：短相对时间（"刚刚" / "3m 前" / "2h 前" / "5d 前"），
 * 供 Scenarios / ScenarioDetailView / Executions 等视图共用。
 */
export function relTime(v?: string | Date | null): string {
  if (!v) return ''
  const d = typeof v === 'string' ? new Date(v) : v
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}m 前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h 前`
  return `${Math.floor(hr / 24)}d 前`
}

/** 短绝对时间(MM-DD HH:mm,列表列共用)。无效/空值返回 ``—``。 */
export function shortDateTime(v?: string | Date): string {
  if (!v) return '—'
  const d = typeof v === 'string' ? new Date(v) : v
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

/** 文件名安全时间戳(YYYY-MM-DDTHH-mm-ss),导出文件命名共用。 */
export function exportTimestamp(): string {
  return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
}
