/** var-registry.ts — 推导/收集/三类校验 coverage. */
import { describe, it, expect } from 'vitest'
import {
  deriveVarRegistry,
  varRefsIn,
  collectVarRefs,
  checkVarRefs,
  varUsages,
  assignVarRefs,
  type StepLike,
} from '@/utils/var-registry'

/** step 工厂:默认一个带 extract 的 step */
function mkStep(over: Partial<StepLike> = {}): StepLike {
  return {
    strategy: [],
    api: { headers: {} },
    request: { body: {} },
    ...over,
  }
}

describe('deriveVarRegistry', () => {
  it('config.vars 先注册,extract 按 step 序追加', () => {
    const reg = deriveVarRegistry(
      [
        mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.data.t' }] }),
        mkStep({ strategy: [{ kind: 'extract', target: 'order_id', expression: '$.data.id' }] }),
      ],
      { base_url: 'http://x' },
    )
    expect(reg.entries.map((e) => e.name)).toEqual(['base_url', 'token', 'order_id'])
    expect(reg.entries[0].origin).toBe('config')
    expect(reg.entries[0].stepIdx).toBeNull()
    expect(reg.entries[1].origin).toBe('extract')
    expect(reg.entries[1].stepIdx).toBe(0)
    expect(reg.byName.get('token')!.expression).toBe('$.data.t')
  })

  it('同名 extract 覆盖 config(byName 指向后者,layer 语义)', () => {
    const reg = deriveVarRegistry(
      [mkStep({ strategy: [{ kind: 'extract', target: 'qty', expression: '$.q' }] })],
      { qty: 1 },
    )
    expect(reg.entries).toHaveLength(2)
    expect(reg.byName.get('qty')!.origin).toBe('extract')
  })

  it('空 target / 非 extract 策略不注册', () => {
    const reg = deriveVarRegistry(
      [mkStep({ strategy: [
        { kind: 'extract', target: '', expression: '$.x' },
        { kind: 'assertion' as string, target: '$.status' },
      ] })],
      undefined,
    )
    expect(reg.entries).toHaveLength(0)
  })
})

describe('varRefsIn / collectVarRefs', () => {
  it('深扫嵌套 body(对象/数组/字符串),auth 域不收', () => {
    const out = varRefsIn({
      a: '${var.x}',
      b: ['plain', { c: 'prefix ${var.y} suffix' }],
      d: '${auth.qa1.token}',
    })
    expect([...out].sort()).toEqual(['x', 'y'])
  })

  it('collectVarRefs 带 headers/body/strategy 三类位置', () => {
    const steps = [
      mkStep({
        api: { headers: { Authorization: '${var.token}' } },
        request: { body: { nested: { q: '${var.qty}' } } },
        strategy: [{ kind: 'extract', target: 't', expression: '${var.base}$.x' }],
      }),
    ]
    const sites = collectVarRefs(steps)
    expect(sites).toHaveLength(3)
    const byWhere = Object.fromEntries(sites.map((s) => [s.ref.alias, s.where]))
    expect(byWhere.token).toBe('headers')
    expect(byWhere.qty).toBe('body')
    expect(byWhere.base).toBe('strategy')
    expect(sites[0].detail).toBe('Authorization')
  })
})

describe('checkVarRefs — 三类校验', () => {
  const token = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' }] })

  it('dangling: 未注册且无数据集', () => {
    const steps = [mkStep({ api: { headers: { X: '${var.nope}' } } })]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('dangling')
    expect(issues[0].name).toBe('nope')
  })

  it('missing_column: 未注册但选了数据集且列名对不上', () => {
    const steps = [mkStep({ api: { headers: { X: '${var.typo}' } } })]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, ['qty', 'customer_id'])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('missing_column')
  })

  it('数据集列命中 → 不报(运行期 dispatcher layer)', () => {
    const steps = [mkStep({ api: { headers: { X: '${var.qty}' } } })]
    const reg = deriveVarRegistry(steps, {})
    expect(checkVarRefs(steps, reg, ['qty'])).toHaveLength(0)
  })

  it('headers 消费 extract 出身变量 → 新语义不报 order(静态展开不参与时序)', () => {
    // 旧语义:${var.token} 判 order。新语义(#10):${var.x} 是 preprocess
    // 静态展开,时序锚点改为 assign 的 $.source;此处名字已注册,不报
    const steps = [
      mkStep({ api: { headers: { H: '${var.token}' } } }),
      token,
    ]
    const reg = deriveVarRegistry(steps, {})
    expect(checkVarRefs(steps, reg, [])).toHaveLength(0)
  })

  it('order: strategy 允许同 step 消费(producer ≤ consumer)', () => {
    // 同一 step:extract 产出 token,后续策略消费 — 合法
    const steps = [
      mkStep({
        strategy: [
          { kind: 'extract', target: 'token', expression: '$.t' },
          { kind: 'assertion', target: '${var.token}' },
        ],
      }),
    ]
    const reg = deriveVarRegistry(steps, {})
    expect(checkVarRefs(steps, reg, [])).toHaveLength(0)
  })

  it('config 出身不限时序(全局声明)', () => {
    const steps = [
      mkStep({ api: { headers: { H: '${var.base}' } } }),
    ]
    const reg = deriveVarRegistry(steps, { base: 'x' })
    expect(checkVarRefs(steps, reg, [])).toHaveLength(0)
  })

  it('body 深扫引用已注册变量 → 不报(order 判定已重定向到 assign source)', () => {
    const steps = [
      mkStep({ request: { body: { deep: { deeper: ['${var.token}'] } } } }),
      token,
    ]
    const reg = deriveVarRegistry(steps, {})
    expect(checkVarRefs(steps, reg, [])).toHaveLength(0)
  })
})

describe('assignVarRefs — assign source $.name 收集', () => {
  it('T1: 收集整体 $.<name> source(带位置),忽略嵌套/字面量/${var.x}', () => {
    const steps = [
      mkStep({
        strategy: [
          { kind: 'assign', source: '$.token', target: '$.request_body.a' },
          { kind: 'assign', source: '$.data.deep.x', target: '$.request_body.b' }, // 嵌套 — 不收
          { kind: 'assign', source: 'literal', target: '$.request_body.c' },        // 字面量 — 不收
          { kind: 'extract', target: 't', expression: '${var.x}$.q' },              // 模板 — 不收
        ],
      }),
      mkStep({
        strategy: [{ kind: 'assign', source: '$.order_id', target: '$.request_body.d' }],
      }),
    ]
    const sites = assignVarRefs(steps)
    expect(sites).toHaveLength(2)
    expect(sites[0]).toMatchObject({ name: 'token', stepIdx: 0, where: 'strategy', detail: 'strategy[0].source' })
    expect(sites[1]).toMatchObject({ name: 'order_id', stepIdx: 1, where: 'strategy', detail: 'strategy[0].source' })
  })

  it('T2: order — step2 assign 引用 step3 产出的 extract 变量 → issue;引用 step1 → 无', () => {
    const late = mkStep({ strategy: [{ kind: 'extract', target: 'x', expression: '$.x' }] })
    // step1 产出 y;step2 assign 引用 y(合法);step2 assign 引用 step3 的 x(非法)
    const steps = [
      mkStep({ strategy: [{ kind: 'extract', target: 'y', expression: '$.y' }] }),
      mkStep({ strategy: [{ kind: 'assign', source: '$.y', target: '$.request_body.a' }] }),
      mkStep({ strategy: [{ kind: 'assign', source: '$.x', target: '$.request_body.b' }] }),
      late,
    ]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('order')
    expect(issues[0].name).toBe('x')
    expect(issues[0].stepIdx).toBe(2)
    expect(issues[0].producerIdx).toBe(3)
  })

  it('T2b: 同 step assign 引用本 step extract 变量 → issue(after_request 产出 vs before_request 消费)', () => {
    const steps = [
      mkStep({
        strategy: [
          { kind: 'extract', target: 'x', expression: '$.x' },
          { kind: 'assign', source: '$.x', target: '$.request_body.a' },
        ],
      }),
    ]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('order')
    expect(issues[0].producerIdx).toBe(0)
    expect(issues[0].stepIdx).toBe(0)
  })

  it('T3: ${var.x} 引用不再产生 order issue(静态展开不参与时序)', () => {
    // step0 headers 引用 step1 产出的 extract 变量 — 旧逻辑报 order,
    // 新语义:${var.x} 是 preprocess 静态展开,extract 产物不在其命名空间,
    // 这属于"名字撞车"而非时序问题,不再挂 order(落 dangling/missing_column 语义见前)
    const steps = [
      mkStep({ api: { headers: { H: '${var.token}' } } }),
      mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' }] }),
    ]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues.filter((i) => i.kind === 'order')).toHaveLength(0)
  })
})

describe('varUsages', () => {
  it('按变量聚合消费处', () => {
    const steps = [
      mkStep({
        api: { headers: { A: '${var.x}', B: '${var.x}' } },
        request: { body: { k: '${var.y}' } },
      }),
    ]
    const usage = varUsages(steps)
    expect(usage.get('x')!.sites).toHaveLength(2)
    expect(usage.get('y')!.sites).toHaveLength(1)
  })
})
