/**
 * value-display — 值展示格式化(语义提示 + 紧凑 JSON 共享收口):
 * 数据集容器基线此前经 String() 腐化成 "[object Object]";
 * 本组钉三件事:标量零变化 / 容器语义提示可辨有无值 / JSON 通道保结构。
 */
import { describe, expect, it } from 'vitest'
import { isStructuredValue, valueHint, valueJson } from '@/utils/value-display'

describe('value-display — isStructuredValue', () => {
  it('VD-0: 对象/数组 = true;null/标量/undefined = false(null 是显式标量叶)', () => {
    expect(isStructuredValue({})).toBe(true)
    expect(isStructuredValue([])).toBe(true)
    expect(isStructuredValue(null)).toBe(false)
    expect(isStructuredValue('x')).toBe(false)
    expect(isStructuredValue(undefined)).toBe(false)
  })
})

describe('value-display — valueHint(语义提示)', () => {
  it('VD-1: 标量原样(与 String 一致);undefined/null → 空(基线空态约定)', () => {
    expect(valueHint(100)).toBe('100')
    expect(valueHint('BL1')).toBe('BL1')
    expect(valueHint(true)).toBe('true')
    expect(valueHint(undefined)).toBe('')
    expect(valueHint(null)).toBe('')
  })

  it('VD-2: 对象 — 空对象/字段计数,绝不出现 [object Object]', () => {
    expect(valueHint({})).toBe('空对象')
    expect(valueHint({ a: 1, b: 2 })).toBe('对象 · 2 字段')
  })

  it('VD-3: 数组 — 空数组/项数计数', () => {
    expect(valueHint([])).toBe('空数组')
    expect(valueHint(['x', 'y'])).toBe('数组 · 2 项')
  })

  it('VD-4: 直接子值含容器 → 追加「嵌套」;纯标量子值不追加', () => {
    expect(valueHint({ a: 1, box: { b: 2 } })).toBe('对象 · 2 字段 · 嵌套')
    expect(valueHint([{ id: 1 }, { id: 2 }])).toBe('数组 · 2 项 · 嵌套')
    expect(valueHint({ a: 1, b: 'x' })).toBe('对象 · 2 字段')
  })
})

describe('value-display — valueJson(机读通道)', () => {
  it('VD-5: 容器紧凑 JSON 保结构;标量退化 String(与 prettyVal 同语义)', () => {
    expect(valueJson({ a: 1, b: [2, 3] })).toBe('{"a":1,"b":[2,3]}')
    expect(valueJson(['x'])).toBe('["x"]')
    expect(valueJson(100)).toBe('100')
    expect(valueJson('BL')).toBe('BL')
  })
})
