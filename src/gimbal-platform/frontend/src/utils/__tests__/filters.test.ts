/** filters.ts — applyFiltersToList / emptyFilters coverage. */
import { describe, it, expect } from 'vitest'
import {
  applyFiltersToList,
  emptyFilters,
  type ScenarioFilters,
  type ScenarioFilterRow,
  type FilterRow,
} from '@/utils/filters'

/** 测试专用行形状:ScenarioFilterRow + 断言键 case_id(便于 .map 断言顺序)。 */
type TestRow = ScenarioFilterRow & { case_id: string; name?: string }

function mkCase(overrides: Partial<TestRow> = {}): TestRow {
  return {
    case_id: 'x',
    module: 'm',
    updated_at: new Date().toISOString(),
    tags: ['t1'],
    priority: 2,
    author: 'alice',
    ...overrides,
  }
}

describe('emptyFilters', () => {
  it('returns a no-op filter (all defaults)', () => {
    const f = emptyFilters()
    expect(f.modules).toEqual([])
    expect(f.tags).toEqual([])
    expect(f.authors).toEqual([])
    expect(f.priorities).toEqual([])
    expect(f.systems).toEqual([])
    expect(f.updatedWithin).toBe('all')
  })
})

describe('applyFiltersToList', () => {
  const pool: TestRow[] = [
    mkCase({ case_id: 'a', module: 'biz', tags: ['smoke'], priority: 1 }),
    mkCase({ case_id: 'b', module: 'ops', tags: ['regression'], priority: 2 }),
    mkCase({ case_id: 'c', module: 'biz', tags: ['perf'], priority: 3 }),
  ]

  it('returns everything when filters are empty', () => {
    expect(applyFiltersToList(pool, emptyFilters())).toHaveLength(3)
  })

  it('filters by module', () => {
    const f: ScenarioFilters = { ...emptyFilters(), modules: ['biz'] }
    expect(applyFiltersToList(pool, f).map((c) => (c as TestRow).case_id)).toEqual(['a', 'c'])
  })

  it('filters by tag union (any-of)', () => {
    const f: ScenarioFilters = { ...emptyFilters(), tags: ['smoke', 'perf'] }
    expect(applyFiltersToList(pool, f).map((c) => (c as TestRow).case_id)).toEqual(['a', 'c'])
  })

  it('filters by priority', () => {
    const f: ScenarioFilters = { ...emptyFilters(), priorities: [1, 3] }
    expect(applyFiltersToList(pool, f).map((c) => (c as TestRow).case_id)).toEqual(['a', 'c'])
  })

  it('filters by 24h window', () => {
    const recent = applyFiltersToList(pool, {
      ...emptyFilters(),
      updatedWithin: '24h',
    })
    expect(recent).toHaveLength(3) // all just-now

    const tooOld = mkCase({
      case_id: 'old',
      updated_at: new Date(Date.now() - 7 * 24 * 3600_000).toISOString(),
    })
    const f: ScenarioFilters = { ...emptyFilters(), updatedWithin: '24h' }
    expect(
      applyFiltersToList([...pool, tooOld], f).map((c) => (c as TestRow).case_id),
    ).toEqual(['a', 'b', 'c'])
  })
})

// ── defensive against partially-shaped rows (2026-08 pass) ──────────
// 场景库(Scenarios.vue)摊平的行可能缺 tags/module/author 等字段;
// filter 必须容忍 undefined 而不是中途抛错。
describe('applyFiltersToList with partial rows', () => {
  const partial = [
    { case_id: 'case-001', name: 'One' },
    { case_id: 'case-002', name: 'Two', tags: ['smoke'] },
  ] as Partial<TestRow>[]

  it('no-op filters keep all partial rows without throwing', () => {
    expect(applyFiltersToList(partial, emptyFilters())).toHaveLength(2)
  })

  it('tag filter does not crash on rows missing tags', () => {
    const f: ScenarioFilters = { ...emptyFilters(), tags: ['smoke'] }
    expect(
      applyFiltersToList(partial, f).map((c) => (c as TestRow).case_id),
    ).toEqual(['case-002'])
  })

  it('module filter excludes rows without a module', () => {
    const f: ScenarioFilters = { ...emptyFilters(), modules: ['billing'] }
    expect(applyFiltersToList(partial, f)).toEqual([])
  })

  it('updatedWithin filter keeps rows missing updated_at (no false drop)', () => {
    const f: ScenarioFilters = { ...emptyFilters(), updatedWithin: '24h' }
    // missing updated_at → NaN → kept by design (can't prove it's old)
    expect(applyFiltersToList(partial, f)).toHaveLength(2)
  })
})

// ── system filter (场景库系统字段过滤, 2026-08) ──────────────────────
describe('applyFiltersToList system filter', () => {
  const rows: (FilterRow & { case_id: string; name?: string })[] = [
    { case_id: 's1', name: 'Fin scenario', system: ['fin', 'common'] },
    { case_id: 's2', name: 'Logi scenario', system: ['logi'] },
    { case_id: 's3', name: 'Legacy row' }, // no system field
  ]

  it('empty systems selection keeps all rows (legacy default)', () => {
    expect(applyFiltersToList(rows, emptyFilters())).toHaveLength(3)
  })

  it('single system tag matches rows carrying it', () => {
    const f: ScenarioFilters = { ...emptyFilters(), systems: ['fin'] }
    expect(applyFiltersToList(rows, f).map((c) => (c as TestRow).case_id)).toEqual(['s1'])
  })

  it('multiple system tags use OR semantics', () => {
    const f: ScenarioFilters = { ...emptyFilters(), systems: ['fin', 'logi'] }
    expect(applyFiltersToList(rows, f).map((c) => (c as TestRow).case_id)).toEqual(['s1', 's2'])
  })

  it('rows without a system field are excluded when filtering by system', () => {
    const f: ScenarioFilters = { ...emptyFilters(), systems: ['fin'] }
    expect(applyFiltersToList(rows, f)).not.toContainEqual(
      expect.objectContaining({ case_id: 's3' }),
    )
  })
})
