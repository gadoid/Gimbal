/**
 * value-display — 值展示格式化(判别 + 紧凑 JSON 共享收口):
 * 数据集容器基线此前经 String() 腐化成 "[object Object]";
 * 本组钉两件事:判别语义(null 是显式标量叶)/ JSON 通道保结构。
 */
import { describe, expect, it } from 'vitest'
import { isStructuredValue, valueJson } from '@/utils/value-display'

describe('value-display — isStructuredValue', () => {
  it('VD-0: 对象/数组 = true;null/标量/undefined = false(null 是显式标量叶)', () => {
    expect(isStructuredValue({})).toBe(true)
    expect(isStructuredValue([])).toBe(true)
    expect(isStructuredValue(null)).toBe(false)
    expect(isStructuredValue('x')).toBe(false)
    expect(isStructuredValue(undefined)).toBe(false)
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
