/**
 * useListSearch — regression tests for the 2026-08 场景库搜索修复:
 *   1. dot-path field resolution ('meta.name' → item.meta.name)
 *   2. external query-ref binding (the Scenarios.vue pattern — the old
 *      bug: caller bound v-model to a local ref the composable never saw)
 */
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useListSearch, resolveField } from '@/utils/useListSearch'

interface Row extends Record<string, unknown> {
  name: string
  meta?: { name?: string; module?: string }
  tags: string[]
}

const rows: Row[] = [
  { name: 'alpha', meta: { name: '登录场景', module: 'auth' }, tags: ['smoke'] },
  { name: 'beta', meta: { name: '下单流程', module: 'order' }, tags: ['e2e'] },
  { name: 'gamma', tags: [] }, // no meta at all — must not throw
]

describe('resolveField', () => {
  it('plain key lookup', () => {
    expect(resolveField(rows[0], 'name')).toBe('alpha')
  })

  it('dot-path lookup', () => {
    expect(resolveField(rows[0], 'meta.name')).toBe('登录场景')
    expect(resolveField(rows[1], 'meta.module')).toBe('order')
  })

  it('dot-path on missing intermediate → undefined (no throw)', () => {
    expect(resolveField(rows[2], 'meta.name')).toBeUndefined()
  })

  it('deep path with null intermediate short-circuits', () => {
    expect(resolveField({ a: null }, 'a.b.c')).toBeUndefined()
  })
})

describe('useListSearch', () => {
  it('searches nested meta.* fields (dot paths)', () => {
    const { query, filtered } = useListSearch(() => rows, ['meta.name', 'meta.module'])
    query.value = '登录'
    expect(filtered.value).toHaveLength(1)
    expect(filtered.value[0].name).toBe('alpha')

    query.value = 'order'
    expect(filtered.value.map((r) => r.name)).toEqual(['beta'])
  })

  it('empty query returns the full list', () => {
    const { query, filtered } = useListSearch(() => rows, ['meta.name'])
    query.value = ''
    expect(filtered.value).toHaveLength(3)
  })

  it('no match on nested field yields empty result (not a crash)', () => {
    const { query, filtered } = useListSearch(() => rows, ['meta.name'])
    query.value = '不存在的东西'
    expect(filtered.value).toEqual([])
  })

  it('binds to an externally-owned query ref (Scenarios.vue pattern)', () => {
    const q = ref('') // declared before, bound via v-model in the template
    const { query, filtered } = useListSearch(() => rows, ['name', 'meta.name', 'tags'], q)

    // The composable must use OUR ref, not create its own.
    expect(query).toBe(q)

    q.value = 'smoke'
    expect(filtered.value.map((r) => r.name)).toEqual(['alpha'])

    // Two-way: writing through the returned ref also works.
    query.value = 'beta'
    expect(q.value).toBe('beta')
    expect(filtered.value).toHaveLength(1)
  })
})
