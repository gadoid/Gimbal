/**
 * dataset-grid — 变量即列网格的纯函数回归。
 * 不变式钉子:三态 cell(继承/显式空/覆写)、列派生与后端 `_scalar_vars`
 * 同规则、失效键 `__` 豁免、粘贴铺格、注入槽静态近似。
 */
import { describe, it, expect } from 'vitest'
import {
  SLOT_PREFIX, isScalar, deriveVarColumns, cellDisplay, baselineText,
  gridStats, deadKeysOf, stripDeadKeys, parseTsvPaste, applyPastePlan,
  injectionSlotNames, exportColumnOrder,
} from '@/utils/dataset-grid'

describe('isScalar — 与后端 _scalar_vars 同规则', () => {
  it('标量进列,结构化声明不入列', () => {
    expect(isScalar('a')).toBe(true)
    expect(isScalar(1)).toBe(true)
    expect(isScalar(true)).toBe(true)
    expect(isScalar(null)).toBe(true)
    expect(isScalar({ kind: 'seq' })).toBe(false)
    expect(isScalar(['x'])).toBe(false)
    expect(isScalar(undefined)).toBe(false)
  })
})

describe('deriveVarColumns — 列宇宙派生', () => {
  const configVars = { qty: 3, tag: 'base', gen: { kind: 'seq' }, flag: false }
  const rows = [{ qty: '5' }, { [`${SLOT_PREFIX}qa`]: 'qa-main' }]

  it('标量变量按声明序出列;结构化剔除;账号列按行内首见补入', () => {
    const cols = deriveVarColumns(configVars, rows)
    expect(cols.map((c) => c.key)).toEqual(['qty', 'tag', 'flag', `${SLOT_PREFIX}qa`])
    expect(cols[0].kind).toBe('var')
    expect(cols[0].baseline).toBe(3)
    expect(cols[3].kind).toBe('slot')
    expect(cols[3].name).toBe('qa')
    expect(cols[3].baseline).toBeUndefined()
  })

  it('locked = 变量 ∈ varLocks ∧ ∉ varUnlocks;账号列永不锁', () => {
    const cols = deriveVarColumns(configVars, rows, ['tag'], [])
    expect(cols.find((c) => c.name === 'tag')!.locked).toBe(true)
    expect(cols.find((c) => c.name === 'qty')!.locked).toBe(false)
    const unlocked = deriveVarColumns(configVars, rows, ['tag'], ['tag'])
    expect(unlocked.find((c) => c.name === 'tag')!.locked).toBe(false)
    expect(cols.find((c) => c.kind === 'slot')!.locked).toBe(false)
  })

  it('configVars null/缺省 → 只有行内账号列', () => {
    const cols = deriveVarColumns(null, rows)
    expect(cols.map((c) => c.key)).toEqual([`${SLOT_PREFIX}qa`])
  })
})

describe('cellDisplay — 三态(稀疏行合同)', () => {
  const col = { kind: 'var' as const, name: 'qty', key: 'qty', baseline: 3, locked: false }
  it('键缺省 = inherit,placeholder 显基线', () => {
    expect(cellDisplay({}, col)).toEqual({ value: '', state: 'inherit', placeholder: '3' })
  })
  it("'' = override-empty(显式空,UI 红条)", () => {
    expect(cellDisplay({ qty: '' }, col).state).toBe('override-empty')
  })
  it('有值 = override-value', () => {
    expect(cellDisplay({ qty: '5' }, col)).toEqual({ value: '5', state: 'override-value', placeholder: '3' })
  })
  it('结构化基线 placeholder 为空(baselineText=null)', () => {
    const objCol = { ...col, baseline: { kind: 'seq' } }
    expect(baselineText(objCol.baseline)).toBeNull()
    expect(cellDisplay({}, objCol).placeholder).toBe('')
  })
  it('账号列无基线', () => {
    const slot = { kind: 'slot' as const, name: 'qa', key: '@slot.qa', baseline: undefined, locked: false }
    expect(cellDisplay({}, slot).placeholder).toBe('')
  })
})

describe('gridStats / deadKeysOf / stripDeadKeys', () => {
  const cols = deriveVarColumns({ a: '1', b: '2' }, [])
  it('只数列宇宙内的覆写格', () => {
    const stats = gridStats(cols, [{ a: 'x' }, {}, { a: '', b: 'y' }])
    expect(stats).toEqual({ varCount: 2, rowCount: 3, overrideCount: 3 })
  })
  it('失效键 = 行键 ∉ 宇宙;__ 前缀豁免;首见序去重', () => {
    const dead = deadKeysOf(cols, [{ a: '1', ghost: 'g', __rowKey: 'h' }, { ghost: 'g', gone: 'v' }])
    expect(dead).toEqual(['ghost', 'gone'])
  })
  it('stripDeadKeys 移除失效键、保留 __rowKey', () => {
    const next = stripDeadKeys([{ a: '1', ghost: 'g', __rowKey: 'h' }], ['ghost'])
    expect(next).toEqual([{ a: '1', __rowKey: 'h' }])
  })
})

describe('parseTsvPaste / applyPastePlan — 网格铺格', () => {
  it('单列纵向填充落到起始列', () => {
    const plan = parseTsvPaste('5\n6', ['qty'], 0, 1)
    expect(plan.cells).toEqual([{ qty: '5' }, { qty: '6' }])
    expect(plan.needsAppend).toBe(1)
  })
  it('矩形块按列序右铺;末尾单个空行去掉', () => {
    const plan = parseTsvPaste('5\tx\n6\ty\n', ['qty', 'tag'], 1, 2)
    expect(plan.cells).toEqual([{ qty: '5', tag: 'x' }, { qty: '6', tag: 'y' }])
    expect(plan.needsAppend).toBe(1)
  })
  it('溢出列宽丢弃;空串保留(显式空)', () => {
    const plan = parseTsvPaste('5\tx\tz', ['qty'], 0, 0)
    expect(plan.cells).toEqual([{ qty: '5' }])
    const blank = parseTsvPaste('a\n\nb', ['tag'], 0, 3)
    expect(blank.cells).toEqual([{ tag: 'a' }, { tag: '' }, { tag: 'b' }])
  })
  it('applyPastePlan 不可变;不足行补稀疏 {}', () => {
    const rows = [{ a: '1' }]
    const next = applyPastePlan(rows, parseTsvPaste('5\n6', ['a'], 1, 1))
    expect(rows).toEqual([{ a: '1' }])
    expect(next).toEqual([{ a: '1' }, { a: '5' }, { a: '6' }])
  })
})

describe('injectionSlotNames — 注入槽静态近似(与后端 _injection_slots 同源)', () => {
  it('扫出 ${slot.X. 与 ${auth.X. 两族,首见序去重', () => {
    const steps = [
      { request: { body: { u: '${slot.qa.user}', t: '${auth.qa-main.token}' } } },
      { call: { headers: { A: '${slot.qa.name} ${auth.other.field}' } } },
    ]
    expect(injectionSlotNames(steps, {})).toEqual(['qa', 'qa-main', 'other'])
  })
  it('config 也扫;无引用 → 空', () => {
    expect(injectionSlotNames([], { users: { u: '${auth.dev.token}' } })).toEqual(['dev'])
    expect(injectionSlotNames([{ request: { body: { a: 1 } } }], {})).toEqual([])
  })
})

describe('exportColumnOrder — 导出列序', () => {
  it('列宇宙在前,失效键缀后,__ 前键不出', () => {
    const cols = deriveVarColumns({ a: '1', b: '2' }, [])
    const order = exportColumnOrder(cols, [{ b: 'x', ghost: 'g', __rowKey: 'h' }])
    expect(order).toEqual(['a', 'b', 'ghost'])
  })
})
