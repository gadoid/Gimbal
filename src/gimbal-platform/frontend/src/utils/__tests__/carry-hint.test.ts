import { describe, expect, it } from 'vitest'
import { carryHint } from '../carry-hint'

/** 字段面:$.unbound 永不配置(验证面内键缺席值表 → 不提示)。 */
const FACE = ['$.operator', '$.channel', '$.trace_id', '$.unbound']

describe('carryHint — face ∩ (bound ∪ defaults) → Map<path, 来源>', () => {
  it('服务绑定优先于全局默认:同键命中两层 → 只标「服务绑定」(与运行时注入同序)', () => {
    const out = carryHint(FACE, { '$.operator': 'qa' }, { '$.operator': 'prod' })
    expect(out.get('$.operator')).toBe('服务绑定')
    expect(out.size).toBe(1)
  })

  it('两层各命中不同键 → 分别标注', () => {
    const out = carryHint(FACE, { '$.operator': 'qa' }, { '$.channel': 'app' })
    expect(out.get('$.operator')).toBe('服务绑定')
    expect(out.get('$.channel')).toBe('全局默认')
    expect(out.size).toBe(2)
  })

  it('null 值行算已配置:显式 null 是配置(绑定层屏蔽默认),不是缺席', () => {
    // 绑定层 null = 显式屏蔽该键的全局默认 → 来源仍是「服务绑定」
    const out = carryHint(FACE, { '$.trace_id': null }, {})
    expect(out.get('$.trace_id')).toBe('服务绑定')
    // 默认层 null 同理算已配置
    const out2 = carryHint(FACE, {}, { '$.trace_id': null })
    expect(out2.get('$.trace_id')).toBe('全局默认')
  })

  it('绑定层 null 仍优先于默认层有值(缺席才轮到默认层)', () => {
    const out = carryHint(FACE, { '$.trace_id': null }, { '$.trace_id': 'abc' })
    expect(out.get('$.trace_id')).toBe('服务绑定')
  })

  it('无交集 → 空 Map:值表全空 / 面为空 / 值表键全不在面内', () => {
    expect(carryHint(FACE, {}, {})).toEqual(new Map())
    expect(carryHint([], { '$.operator': 'qa' }, { '$.channel': 'app' })).toEqual(new Map())
    expect(carryHint(FACE, { '$.other': 'x' }, { '$.another': 'y' }).size).toBe(0)
  })

  it('面内键两层都未配置 → 不进 Map(运行时无值可注入,不提示)', () => {
    const out = carryHint(FACE, { '$.operator': 'qa' }, {})
    expect(out.has('$.unbound')).toBe(false)
    expect(out.size).toBe(1)
  })
})
