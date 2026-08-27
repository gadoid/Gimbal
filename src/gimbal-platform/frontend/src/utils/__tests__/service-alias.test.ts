import { describe, expect, it } from 'vitest'
import { deriveBase } from '../service-alias'

const CAT = new Set(['fin-service', 'fin-order-service', 'fin.tidb-test'])

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
