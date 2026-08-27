/**
 * mergeSeedFrom —— remove+add 同 step → renameField 种子(§6.3 合并交互)。
 * 不满足条件一律 null:数量≠2、非 pending、非同 step、类型不是一删一增。
 */
import { describe, it, expect } from 'vitest'
import { mergeSeedFrom } from '@/utils/adaptation-merge'
import type { OpOut } from '@/api/adaptations'

function op(id: number, opType: string, payload: Record<string, unknown>,
            status = 'pending'): OpOut {
  return {
    id, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
    opType, payload, status: status as OpOut['status'],
    appliedAt: null, note: null,
  } as OpOut
}

describe('mergeSeedFrom', () => {
  it('同 step 一删一增 → 种子;remove 为 from、add 为 to', () => {
    const seed = mergeSeedFrom([
      op(1, 'removeField', { step: 0, field: 'legacy_field' }),
      op(2, 'addField', { step: 0, field: 'extra', value: 'E' }),
    ])
    expect(seed).toEqual({ step: 0, from: 'legacy_field', to: 'extra' })
  })

  it('非法组合 → null(数量/状态/step/类型)', () => {
    const rm = op(1, 'removeField', { step: 0, field: 'a' })
    const add = op(2, 'addField', { step: 0, field: 'b', value: 'x' })
    expect(mergeSeedFrom([rm])).toBeNull()                      // 只选一条
    expect(mergeSeedFrom([rm, add, op(3, 'removeField',
      { step: 0, field: 'c' })])).toBeNull()                    // 三条
    expect(mergeSeedFrom([rm, op(2, 'addField',
      { step: 0, field: 'b' }, 'applied')])).toBeNull()         // 非 pending
    expect(mergeSeedFrom([rm, op(2, 'addField',
      { step: 1, field: 'b' })])).toBeNull()                    // 跨 step
    expect(mergeSeedFrom([rm, op(2, 'removeField',
      { step: 0, field: 'b' })])).toBeNull()                    // 两条删
  })
})
