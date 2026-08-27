/**
 * mergeSeedFrom —— remove+add 草案合并为 renameField 的种子计算(§6.3)。
 * 仅当:恰好 2 条、全部 pending、同 step、一 removeField 一 addField。
 */
import type { MergeSeed, OpOut } from '@/api/adaptations'

export function mergeSeedFrom(selected: OpOut[]): MergeSeed | null {
  if (selected.length !== 2) return null
  if (!selected.every((o) => o.status === 'pending')) return null
  const [a, b] = selected
  const pair = [a, b].find(
    (o) => o.opType === 'removeField',
  ) as { payload: { step?: number; field?: string } } | undefined
  const added = [a, b].find(
    (o) => o.opType === 'addField',
  ) as { payload: { step?: number; field?: string } } | undefined
  if (!pair || !added) return null
  if (pair.payload.step !== added.payload.step) return null
  if (pair.payload.field == null || added.payload.field == null) return null
  return {
    step: Number(pair.payload.step),
    from: String(pair.payload.field),
    to: String(added.payload.field),
  }
}
