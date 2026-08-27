/**
 * pool-var — F10: seedPoolVarIntoDefinition 快照播种语义。
 * ??= 语义: 同名已存在不覆盖且 seeded=false;不存在则快照拷贝 spec 且不回灌。
 */
import { describe, it, expect } from 'vitest'
import { seedPoolVarIntoDefinition } from '@/utils/pool-var'

const SPEC = { kind: 'random_decorated', length: 6, head: 'GIMBAL728' }

describe('seedPoolVarIntoDefinition', () => {
  it('F10a: config/vars 缺失时创建并播种', () => {
    const def = { meta: { name: 'x' } } as { meta: unknown; config?: undefined }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.seeded).toBe(true)
    expect((r.definition as { config?: { vars?: Record<string, unknown> } }).config?.vars)
      .toEqual({ bl_no: SPEC })
  })

  it('F10b: 同名已存在 → 不覆盖,seeded=false,原值保留', () => {
    const def = {
      config: { vars: { bl_no: { kind: 'seq', width: 8 } } },
    }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.seeded).toBe(false)
    expect(r.definition.config?.vars?.['bl_no']).toEqual({ kind: 'seq', width: 8 })
  })

  it('F10c: 播种后改动源 spec 对象不回灌(快照仅引用当次对象,原 def 不变异)', () => {
    const def = { config: { vars: {} } }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.definition).not.toBe(def) // 不可变更新
    expect(def.config?.vars).toEqual({}) // 原 def 未被改动
  })

  it('F10d: 其他变量共存,新增变量追加而非替换整表', () => {
    const def = { config: { vars: { keep: 'x' } } }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.definition.config?.vars).toEqual({ keep: 'x', bl_no: SPEC })
  })
})
