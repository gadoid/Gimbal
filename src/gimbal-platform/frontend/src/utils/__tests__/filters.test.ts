/** filter.ts — applyFiltersToList / emptyFilters coverage. */
import { describe, it, expect } from 'vitest'
import {
  applyFiltersToList,
  emptyFilters,
  type CaseFilters,
} from '@/utils/filters'
import type { CaseSummary } from '@/utils/filters'

function mkCase(overrides: Partial<CaseSummary> = {}): CaseSummary {
  return {
    module: 'm',
    visibility: 'public',
    owner_id: 1,
    audited: true,
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
    expect(f.updatedWithin).toBe('all')
    expect(f.visibility).toBe('all')
    expect(f.audited).toBe('all')
  })
})

describe('applyFiltersToList', () => {
  const pool: CaseSummary[] = [
    mkCase({ case_id: 'a', module: 'biz', tags: ['smoke'], priority: 1 }),
    mkCase({ case_id: 'b', module: 'ops', tags: ['regression'], priority: 2 }),
    mkCase({ case_id: 'c', module: 'biz', tags: ['perf'], priority: 3 }),
  ]

  it('returns everything when filters are empty', () => {
    expect(applyFiltersToList(pool, emptyFilters())).toHaveLength(3)
  })

  it('filters by module', () => {
    const f: CaseFilters = { ...emptyFilters(), modules: ['biz'] }
    expect(applyFiltersToList(pool, f).map((c) => c.case_id)).toEqual(['a', 'c'])
  })

  it('filters by tag union (any-of)', () => {
    const f: CaseFilters = { ...emptyFilters(), tags: ['smoke', 'perf'] }
    expect(applyFiltersToList(pool, f).map((c) => c.case_id)).toEqual(['a', 'c'])
  })

  it('filters by priority', () => {
    const f: CaseFilters = { ...emptyFilters(), priorities: [1, 3] }
    expect(applyFiltersToList(pool, f).map((c) => c.case_id)).toEqual(['a', 'c'])
  })

  it('filters by visibility', () => {
    const f: CaseFilters = { ...emptyFilters(), visibility: 'private' }
    expect(applyFiltersToList(pool, f)).toEqual([])
  })

  it('filters by audited', () => {
    const f: CaseFilters = { ...emptyFilters(), audited: 'pending' }
    expect(applyFiltersToList(pool, f)).toEqual([]) // all true in this pool
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
    const f: CaseFilters = { ...emptyFilters(), updatedWithin: '24h' }
    expect(applyFiltersToList([...pool, tooOld], f).map((c) => c.case_id)).toEqual([
      'a', 'b', 'c',
    ])
  })
})

// ── defensive against partially-shaped rows (2026-08 pass) ──────────
// The V3 composer's Case rows (Cases.vue overview pool) lack the legacy
// tags/module/author fields; the filter must tolerate them, not throw.
describe('applyFiltersToList with partial rows (V3 Case shape)', () => {
  const partial = [
    { case_id: 'case-001', name: 'V3 One' },
    { case_id: 'case-002', name: 'V3 Two', tags: ['smoke'] },
  ] as Partial<CaseSummary>[]

  it('no-op filters keep all partial rows without throwing', () => {
    expect(applyFiltersToList(partial, emptyFilters())).toHaveLength(2)
  })

  it('tag filter does not crash on rows missing tags', () => {
    const f: CaseFilters = { ...emptyFilters(), tags: ['smoke'] }
    expect(applyFiltersToList(partial, f).map((c) => c.case_id)).toEqual(['case-002'])
  })

  it('module filter excludes rows without a module', () => {
    const f: CaseFilters = { ...emptyFilters(), modules: ['billing'] }
    expect(applyFiltersToList(partial, f)).toEqual([])
  })

  it('updatedWithin filter keeps rows missing updated_at (no false drop)', () => {
    const f: CaseFilters = { ...emptyFilters(), updatedWithin: '24h' }
    // missing updated_at → NaN → kept by design (can't prove it's old)
    expect(applyFiltersToList(partial, f)).toHaveLength(2)
  })
})

// ── system filter (场景库系统字段过滤, 2026-08) ──────────────────────
describe('applyFiltersToList system filter', () => {
  const rows = [
    { case_id: 's1', name: 'Fin scenario', system: ['fin', 'common'] },
    { case_id: 's2', name: 'Logi scenario', system: ['logi'] },
    { case_id: 's3', name: 'Legacy row' }, // no system field
  ] as Partial<import('@/utils/filters').FilterRow>[]

  it('empty systems selection keeps all rows (legacy default)', () => {
    expect(applyFiltersToList(rows, emptyFilters())).toHaveLength(3)
  })

  it('single system tag matches rows carrying it', () => {
    const f: CaseFilters = { ...emptyFilters(), systems: ['fin'] }
    expect(applyFiltersToList(rows, f).map((c) => c.case_id)).toEqual(['s1'])
  })

  it('multiple system tags use OR semantics', () => {
    const f: CaseFilters = { ...emptyFilters(), systems: ['fin', 'logi'] }
    expect(applyFiltersToList(rows, f).map((c) => c.case_id)).toEqual(['s1', 's2'])
  })

  it('rows without a system field are excluded when filtering by system', () => {
    const f: CaseFilters = { ...emptyFilters(), systems: ['fin'] }
    expect(applyFiltersToList(rows, f)).not.toContainEqual(
      expect.objectContaining({ case_id: 's3' }),
    )
  })
})
