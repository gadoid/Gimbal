/** var-registry.ts — 推导/收集/三类校验 coverage. */
import { describe, it, expect } from 'vitest'
import {
  deriveVarRegistry,
  varRefsIn,
  collectVarRefs,
  checkVarRefs,
  varUsages,
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

  it('order: headers 消费 extract 要求 producer < consumer', () => {
    // step0 消费、step1 产出 → 时序冲突
    const steps = [
      mkStep({ api: { headers: { H: '${var.token}' } } }),
      token,
    ]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('order')
    expect(issues[0].producerIdx).toBe(1)
    expect(issues[0].stepIdx).toBe(0)
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

  it('body 深扫 + 时序', () => {
    const steps = [
      mkStep({ request: { body: { deep: { deeper: ['${var.token}'] } } } }),
      token,
    ]
    const reg = deriveVarRegistry(steps, {})
    const issues = checkVarRefs(steps, reg, [])
    expect(issues).toHaveLength(1)
    expect(issues[0].kind).toBe('order')
    expect(issues[0].where).toBe('body')
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
