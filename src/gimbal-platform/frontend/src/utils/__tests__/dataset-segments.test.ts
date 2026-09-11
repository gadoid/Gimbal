/**
 * dataset-segments — 段派生扫描器单测(spec §4.1/§6.2)。
 * 纯函数零 IO:输入列(body/headers ${var.x} 引用,深扫)+ 期望列
 * (assertion expected 模板,带 target/operator/strategyIdx)+
 * 共享 var(跨段)+ 死行键(行键 ∉ config.vars)。
 */
import { describe, it, expect } from 'vitest'
import {
  deriveSegments, gridColumnsOf, sharedVarNames, deadRowKeys,
  expectVarNameOf, fieldPathsOf, type SegmentStepShape,
} from '../dataset-segments'

const VARS = { amount: 100, exp_code: 200, exp_msg: 'ok' }

/** 两步场景:step1 输入列 amount + 期望 exp_code/exp_msg;step2 输入 bl_no */
const STEPS: SegmentStepShape[] = [
  {
    request: { body: { amount: '${var.amount}', nested: { policy: '${var.amount}' } } },
    api: { headers: { 'X-Trace': '${var.bl_no}', Authorization: '${auth.userA.token}' } },
    strategy: [
      { kind: 'extract', target: 't', expression: '$.a' },
      { kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' },
      { kind: 'assertion', target: '$.response_body.msg', operator: 'eq', expected: 'prefix ${var.exp_msg} postfix' },
      { kind: 'assertion', target: '$.response_status', operator: 'eq', expected: 200 },
    ],
  },
  { request: { body: { bl_no: '${var.bl_no}' } }, strategy: [] },
  { request: { body: { plain: '字面量' } }, strategy: [] },   // 无引用 → 不成段
]

describe('deriveSegments', () => {
  it('S1: 段派生 — 输入列(body 深路径/headers/auth 域排除)+ 期望列 + 空段不入', () => {
    const segs = deriveSegments(STEPS, VARS)
    expect(segs.map((s) => s.stepIndex)).toEqual([0, 1])       // step2(索引 2)无引用不成段
    const s0 = segs[0]
    // 输入列:body amount(深路径二次引用同 var 去重)+ headers bl_no;
    // ${auth.*} 非 var 域不产列
    expect(s0.inputs.map((c) => c.varName)).toEqual(['amount', 'bl_no'])
    expect(s0.inputs[0]).toMatchObject({ stepIndex: 0, source: 'body', field: 'amount', baseline: 100 })
    expect(s0.inputs[1]).toMatchObject({ source: 'headers', field: 'X-Trace', baseline: undefined })
    // 期望列:整串 + 混串模板都产列(各带 target/operator/strategyIdx);
    // 非字符串 expected(数字 200)跳过;非 assertion 跳过
    expect(s0.expects.map((e) => e.varName)).toEqual(['exp_code', 'exp_msg'])
    expect(s0.expects[0]).toMatchObject({ target: '$.response_body.code', operator: 'eq', strategyIdx: 1 })
    expect(s0.expects[0].baseline).toBe(200)   // 期望列基线 = config.vars 值(Task 4/5 消费)
    expect(s0.expects[1].strategyIdx).toBe(2)
  })

  it('S2: 共享 var = 跨段引用(bl_no 两段),单段重复引用不算', () => {
    const segs = deriveSegments(STEPS, VARS)
    expect(sharedVarNames(segs)).toEqual(new Set(['bl_no']))
  })

  it('S3: gridColumnsOf — 段内可编辑列,输入在前期望在后,expect 上下文内嵌', () => {
    const cols = gridColumnsOf(deriveSegments(STEPS, VARS)[0])
    expect(cols.map((c) => c.varName)).toEqual(['amount', 'bl_no', 'exp_code', 'exp_msg'])
    expect(cols[2].source).toBe('expect')
    expect(cols[2].expect).toEqual({ target: '$.response_body.code', operator: 'eq', strategyIdx: 1 })
  })
})

describe('expectVarNameOf', () => {
  it('E1: target 末段命名 + 非法字符压 _ + 空 target 兜底', () => {
    expect(expectVarNameOf('$.response_body.code')).toBe('exp_code')
    expect(expectVarNameOf('$.response_status')).toBe('exp_status')
    expect(expectVarNameOf("$.data['weird key']")).toBe('exp_weird_key')
    expect(expectVarNameOf('')).toBe('exp_value')
  })
})

describe('deadRowKeys', () => {
  it('D1: 行键 ∉ config.vars 键集 → 死键(软提示面);∈ 键集不算', () => {
    expect(deadRowKeys({ amount: 1 }, [{ amount: 2, ghost: 3 }, { other: 4 }]))
      .toEqual(['ghost', 'other'])
    expect(deadRowKeys(null, [{ a: 1 }])).toEqual(['a'])
    expect(deadRowKeys({ a: 1 }, [])).toEqual([])
  })
})

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
      api: { headers: { Authorization: 'Bearer ${auth.u1.token}', X: '1' } },
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
})
