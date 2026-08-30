import { describe, expect, it } from 'vitest'
import { deriveBase, deriveSystem } from '../service-alias'

const CAT = new Set(['fin-service', 'fin-order-service', 'fin.tidb-test'])
/** 目录 service → system 权威映射(endpoint 条目自带 system 字段)。 */
const SYS = new Map([['fin-service', 'fin'], ['fin-order-service', 'fin'], ['fin.tidb-test', 'fin']])

describe('deriveBase — 最后一个 "-" 切分 + 目录名集合成员判定(spec D5)', () => {
  it('目录名直引:key ∈ 目录集合 → key 本身', () => {
    expect(deriveBase('fin-service', CAT)).toBe('fin-service')
  })
  it('别名:base = 目录名 → 归属 base(切分点固定,绝不切成 fin)', () => {
    expect(deriveBase('fin-service-2', CAT)).toBe('fin-service')
  })
  it('目录名含多个 "-":fin-order-service-2 → fin-order-service', () => {
    expect(deriveBase('fin-order-service-2', CAT)).toBe('fin-order-service')
  })
  it('后缀含 "-":fin-order-service-x-1 → null(裸声明,不猜)', () => {
    // 后缀含 `-` = 非构造性别名键 → 裸声明 null,不猜(D5 固定切分)
    expect(deriveBase('fin-order-service-x-1', CAT)).toBeNull()
  })
  it('目录名含 ".":fin.tidb-test-2 → fin.tidb-test', () => {
    expect(deriveBase('fin.tidb-test-2', CAT)).toBe('fin.tidb-test')
  })
  it('不搜索前缀:目录只有 fin-service 时 fin-x 的 base=fin 不在集合 → null', () => {
    expect(deriveBase('fin-x', CAT)).toBeNull()
  })
  it('base 不在集合(裸声明/违规键)→ null,不猜', () => {
    expect(deriveBase('whatever-key', CAT)).toBeNull()
  })
  it('无 "-" 且不在集合 → null;空串 → null', () => {
    expect(deriveBase('loose-name', CAT)).toBeNull()
    expect(deriveBase('', CAT)).toBeNull()
  })
  it('目录集合为空(目录不可达)→ 一律 null(派生是视图不是配置源)', () => {
    expect(deriveBase('fin-service', new Set())).toBeNull()
    expect(deriveBase('fin-service-2', new Set())).toBeNull()
  })
})

describe('deriveSystem — step 系统派生(权威源优先,杜绝把服务名当系统)', () => {
  it('endpoint_id 直引:fin.settlement.create_order → fin(step 自带,最权威)', () => {
    expect(deriveSystem({ service: 'fin-service', view_hints: { endpoint_id: 'fin.settlement.create_order' } }, CAT, SYS)).toBe('fin')
  })
  it('别名步骤:fin-service-codfish2 经 deriveBase 归 fin-service → 目录映射 → fin', () => {
    expect(deriveSystem({ service: 'fin-service-codfish2' }, CAT, SYS)).toBe('fin')
  })
  it('目录直引步骤:fin-service 无 view_hints → 目录映射 → fin(不再整串当系统)', () => {
    expect(deriveSystem({ service: 'fin-service' }, CAT, SYS)).toBe('fin')
  })
  it('点语法服务名(无映射命中):fin.settlement → 首段 fin(存量启发式保留)', () => {
    expect(deriveSystem({ service: 'fin.settlement' }, CAT, SYS)).toBe('fin')
  })
  it('目录不可达(空集合/空映射):降级存量启发式 — 点名取首段,中划线名原样(黄警仍在,不崩)', () => {
    expect(deriveSystem({ service: 'fin.settlement' }, new Set(), new Map())).toBe('fin')
    expect(deriveSystem({ service: 'fin-service' }, new Set(), new Map())).toBe('fin-service')
  })
  it('无 service → null(调用方跳过该 step)', () => {
    expect(deriveSystem({ service: '' }, CAT, SYS)).toBeNull()
    expect(deriveSystem({}, CAT, SYS)).toBeNull()
  })
})
