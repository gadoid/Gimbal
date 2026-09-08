import { describe, expect, it } from 'vitest'
import { groupValueSources } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

const e = (name: string, vs?: { view: string; column?: string; group?: string },
          children?: DeclarationEntryView[]): DeclarationEntryView =>
  ({ name, path: `$.${name}`, required: false, description: '', ui_kind: 'text',
     source_kind: 'independent', ...(children ? { children } : {}),
     ...(vs ? { value_source: { column: '', group: '', ...vs } } : {}) } as DeclarationEntryView)

describe('groupValueSources(spec §3.2/§7.3)', () => {
  it('无绑定 → 空', () => {
    expect(groupValueSources([e('a')])).toEqual([])
  })

  it('缺省组 = view(N=1)', () => {
    const g = groupValueSources([e('bl_no', { view: 'pending_orders', column: 'bl_no' })])
    expect(g).toHaveLength(1)
    expect(g[0].group).toBe('pending_orders')
    expect(g[0].view).toBe('pending_orders')
    expect(g[0].fields).toEqual([{ path: '$.bl_no', name: 'bl_no', column: 'bl_no' }])
  })

  it('同 view 双角色显式拆组互不混合(§3.2 反例)', () => {
    const g = groupValueSources([
      e('cost_c', { view: 'cost_list', column: 'cost_id', group: 'cost_list#to_customer' }),
      e('cost_s', { view: 'cost_list', column: 'cost_id', group: 'cost_list#to_supplier' }),
    ])
    expect(g.map(x => x.group).sort()).toEqual(['cost_list#to_customer', 'cost_list#to_supplier'])
  })

  it('children 树内绑定被扫描(深层)', () => {
    const g = groupValueSources([e('obj', undefined,
      [e('leaf', { view: 'v', column: 'c' })])])
    expect(g[0].fields[0].path).toBe('$.leaf')
  })

  it('column 空 = 前端补 label 列(fields.column 保持空串)', () => {
    const g = groupValueSources([e('f', { view: 'v' })])
    expect(g[0].fields[0].column).toBe('')
  })
})
