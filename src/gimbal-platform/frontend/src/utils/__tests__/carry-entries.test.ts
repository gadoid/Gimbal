import { describe, expect, it } from 'vitest'
import { buildServiceEntries } from '../carry-entries'

/** 首次配置核心场景:面有字段、绑定表全空(全部 hasRow=false)。 */
const FRESH_FACE = [
  { path: '$.remark', value: '', isNull: false, hasRow: false },
  { path: '$.trace_id', value: '', isNull: false, hasRow: false },
]

describe('buildServiceEntries — 行三态 → CarryValues 编码', () => {
  it('无行无输入 → 跳过(不注入,回退全局默认)', () => {
    expect(buildServiceEntries(FRESH_FACE)).toEqual({})
  })

  it('B1 回归:无行但用户填了值 → 建行(旧编码 !hasRow→continue 会静默丢弃)', () => {
    const rows = [{ ...FRESH_FACE[0], value: 'qa-env-remark' }, FRESH_FACE[1]]
    expect(buildServiceEntries(rows)).toEqual({ '$.remark': 'qa-env-remark' })
  })

  it('无行 + isNull → 建行且值 null(设 null 隐含建行;编码层独立于 UI toggle)', () => {
    const rows = [{ ...FRESH_FACE[0], isNull: true }, FRESH_FACE[1]]
    expect(buildServiceEntries(rows)).toEqual({ '$.remark': null })
  })

  it("hasRow 行清空输入 → 仍存空串值('' 是合法值,不是删行)", () => {
    const rows = [{ path: '$.remark', value: '', isNull: false, hasRow: true }]
    expect(buildServiceEntries(rows)).toEqual({ '$.remark': '' })
  })

  it('hasRow + isNull → 存显式 null(绑定层屏蔽全局默认,spec §3.1)', () => {
    const rows = [{ path: '$.remark', value: '', isNull: true, hasRow: true }]
    expect(buildServiceEntries(rows)).toEqual({ '$.remark': null })
  })

  it('删行后保存仍删:removeBindingRow 语义 = hasRow/value/isNull 全清 → 跳过', () => {
    // 曾有绑定 → 点删行 → 保存时整表替换,该 path 不在 entries 中即被移除
    const rows = [
      { path: '$.remark', value: '', isNull: false, hasRow: false },
      { path: '$.trace_id', value: 't-1', isNull: false, hasRow: true },
    ]
    expect(buildServiceEntries(rows)).toEqual({ '$.trace_id': 't-1' })
  })

  it('混合批次一次过:首次配置只填一个字段 → 仅该字段入表', () => {
    const rows = [
      ...FRESH_FACE,
      { path: '$.channel', value: 'app', isNull: false, hasRow: false },
      { path: '$.operator', value: '', isNull: true, hasRow: false },
    ]
    expect(buildServiceEntries(rows)).toEqual({
      '$.channel': 'app',
      '$.operator': null,
    })
  })
})
