/**
 * dataset-segments — 叶子路径扫描器单测(spec v2 §4)。
 * 纯函数零 IO:body 深扫 / headers 浅扫全叶子,模板叶带 varName。
 */
import { describe, it, expect } from 'vitest'
import { fieldPathsOf } from '../dataset-segments'

describe('fieldPathsOf — 全叶子扫描(spec v2 §4)', () => {
  it('FP-1: body 深扫全叶子(模板/直填/深层/数组),path 带 $. 前缀,模板叶带 varName', () => {
    const step = {
      request: { body: {
        amount: '${var.amount}', remark: '直填',
        items: [{ id: 'x' }, { id: '${var.no}' }],
        nested: { deep: '1' },
      } },
    }
    expect(fieldPathsOf(step)).toEqual([
      { source: 'body', path: '$.amount', varName: 'amount' },
      { source: 'body', path: '$.remark' },
      { source: 'body', path: '$.items[0].id' },
      { source: 'body', path: '$.items[1].id', varName: 'no' },
      { source: 'body', path: '$.nested.deep' },
    ])
  })

  it('FP-2: 非字符串/null 叶仍报路径;空容器无叶;headers 浅扫且 ${auth.*} 不算 varName', () => {
    const step = {
      call: { headers: { Authorization: 'Bearer ${auth.u1.token}', X: '1' } },
      request: { body: { n: 5, b: true, nil: null, empty: {}, list: [] } },
    }
    expect(fieldPathsOf(step)).toEqual([
      { source: 'body', path: '$.n' },
      { source: 'body', path: '$.b' },
      { source: 'body', path: '$.nil' },
      { source: 'headers', path: '$.Authorization' },
      { source: 'headers', path: '$.X' },
    ])
  })

  it('FP-3: null step / 空 body 返回空数组', () => {
    expect(fieldPathsOf(null)).toEqual([])
    expect(fieldPathsOf({})).toEqual([])
    expect(fieldPathsOf({ request: {} })).toEqual([])
  })

  it('FP-4: 根数组 body 路径带 $ 前缀(评审修复轮 1)', () => {
    expect(fieldPathsOf({ request: { body: [1, '${var.x}'] } })).toEqual([
      { source: 'body', path: '$[0]' },
      { source: 'body', path: '$[1]', varName: 'x' },
    ])
  })

  it('FP-5: 契约边界钉 — 根标量/null body 单叶 $;headers 浅扫不下钻;undefined header 无叶', () => {
    expect(fieldPathsOf({ request: { body: 5 } })).toEqual([{ source: 'body', path: '$' }])
    expect(fieldPathsOf({ request: { body: null } })).toEqual([{ source: 'body', path: '$' }])
    expect(fieldPathsOf({ call: { headers: { A: { b: 1 } } }, request: {} }))
      .toEqual([{ source: 'headers', path: '$.A' }])
    expect(fieldPathsOf({ call: { headers: { A: undefined } }, request: {} })).toEqual([])
  })
})
