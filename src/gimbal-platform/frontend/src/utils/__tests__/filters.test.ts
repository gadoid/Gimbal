/** filter.ts — applyFiltersToList / emptyFilters coverage. */
import { describe, it, expect } from 'vitest'
import {
  applyFiltersToList,
  emptyFilters,
  type CaseFilters,
} from '@/utils/filters'
import type { CaseSummary } from '@/api/cases'

function mkCase(overrides: Partial<CaseSummary> = {}): CaseSummary {
  return {
    case_id: 'x',
    name: 'X',
    module: 'm',
    description: '',
    visibility: 'public',
    owner_id: null,
    audited: true,
    file_path: 'data/public/x.json',
    updated_at: new Date().toISOString(),
    tags: ['t1'],
    priority: 2,
    author: 'alice',
    favorited_by_me: false,
    copied_by_me: false,
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
