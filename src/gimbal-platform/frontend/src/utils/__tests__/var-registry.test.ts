/** var-registry.ts — 推导/收集/消费统计 coverage. */
import { describe, it, expect } from 'vitest'
import {
  deriveVarRegistry,
  varRefsIn,
  collectVarRefs,
  varUsages,
  assignVarRefs,
  type StepLike,
} from '@/utils/var-registry'

/** step 工厂:默认一个带 extract 的 step */
function mkStep(over: Partial<StepLike> = {}): StepLike {
  return {
    strategy: [],
    call: { headers: {} },
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
        call: { headers: { Authorization: '${var.token}' } },
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


describe('assignVarRefs — assign source $.name 收集', () => {
  it('T1: 收集整体 $.<name> source(带位置),忽略嵌套/字面量/${var.x}', () => {
    const steps = [
      mkStep({
        strategy: [
          { kind: 'assign', source: '$.token', target: '$.call.request.body.a' },
          { kind: 'assign', source: '$.data.deep.x', target: '$.call.request.body.b' }, // 嵌套 — 不收
          { kind: 'assign', source: 'literal', target: '$.call.request.body.c' },        // 字面量 — 不收
          { kind: 'extract', target: 't', expression: '${var.x}$.q' },              // 模板 — 不收
        ],
      }),
      mkStep({
        strategy: [{ kind: 'assign', source: '$.order_id', target: '$.call.request.body.d' }],
      }),
    ]
    const sites = assignVarRefs(steps)
    expect(sites).toHaveLength(2)
    expect(sites[0]).toMatchObject({ name: 'token', stepIdx: 0, where: 'strategy', detail: 'strategy[0].source' })
    expect(sites[1]).toMatchObject({ name: 'order_id', stepIdx: 1, where: 'strategy', detail: 'strategy[0].source' })
  })
})

describe('varUsages', () => {
  it('按变量聚合消费处', () => {
    const steps = [
      mkStep({
        call: { headers: { A: '${var.x}', B: '${var.x}' } },
        request: { body: { k: '${var.y}' } },
      }),
    ]
    const usage = varUsages(steps)
    expect(usage.get('x')!.sites).toHaveLength(2)
    expect(usage.get('y')!.sites).toHaveLength(1)
  })
})
