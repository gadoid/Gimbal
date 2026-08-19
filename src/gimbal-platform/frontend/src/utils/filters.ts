/** filter.ts — advanced filter helpers shared by the scenario library.

 * Pulled out of FilterPopover.vue so consumers can import them from
 * a plain .ts file (Vue <script setup> doesn't allow runtime exports
 * from .vue SFCs).
 */

/** Minimal row shape the filter layer understands (was CaseSummary
 * from the retired api/cases.ts; inlined here in P4). */
export interface CaseSummary {
  module?: string
  tags?: string[]
  author?: string
  owner_id?: number
  priority?: number
  updated_at?: string
  visibility?: 'public' | 'private'
  audited?: boolean
}

export interface CaseFilters {
  modules: string[]
  tags: string[]
  authors: string[]
  priorities: number[]
  systems: string[]
  updatedWithin: 'all' | '24h' | '7d' | '30d'
  visibility: 'all' | 'public' | 'private'
  audited: 'all' | 'audited' | 'pending'
}

export function emptyFilters(): CaseFilters {
  return {
    modules: [],
    tags: [],
    authors: [],
    priorities: [],
    systems: [],
    updatedWithin: 'all',
    visibility: 'all',
    audited: 'all',
  }
}

/** A row the filter layer understands.
 *
 * ``Partial<CaseSummary>`` covers the legacy case lists; the optional
 * ``system`` array extends it for the scenario library (Scenarios.vue
 * flattens ``meta.system`` into it).  Legacy pools simply omit the
 * field, and a system filter then matches nothing — which is why the
 * system UI is gated on ``availableSystems.length > 0``.
 */
export type FilterRow = Partial<CaseSummary> & { system?: string[] }

/** Pure filter — exported for parents and tests.
 *
 * Defensive against partially-shaped rows: the V3 scenario-composer
 * ``Case`` (used by the Cases.vue overview pool) lacks the legacy
 * ``tags`` / ``module`` / ``updated_at`` fields, so every field access
 * below must tolerate ``undefined`` instead of throwing mid-filter.
 */
export function applyFiltersToList(
  pool: readonly FilterRow[],
  f: CaseFilters,
): FilterRow[] {
  const now = Date.now()
  const cutoff = (() => {
    switch (f.updatedWithin) {
      case '24h':
        return now - 24 * 3600_000
      case '7d':
        return now - 7 * 24 * 3600_000
      case '30d':
        return now - 30 * 24 * 3600_000
      default:
        return 0
    }
  })()

  return pool.filter((c) => {
    if (f.modules.length && !f.modules.includes(c.module || '')) return false
    // System filter: row matches when it carries ANY of the selected
    // system tags (OR semantics, same as tags).
    if (f.systems.length && !f.systems.some((s) => (c.system ?? []).includes(s))) {
      return false
    }
    if (f.tags.length && !(c.tags ?? []).some((t) => f.tags.includes(t))) return false
    if (f.authors.length) {
      const authorName =
        c.author || (c.owner_id ? `用户 #${c.owner_id}` : '')
      if (!f.authors.includes(authorName)) return false
    }
    if (
      f.priorities.length &&
      (!c.priority || !f.priorities.includes(c.priority))
    ) {
      return false
    }
    if (f.updatedWithin !== 'all') {
      const ts = c.updated_at ? Date.parse(c.updated_at) : NaN
      if (!Number.isNaN(ts) && ts < cutoff) return false
    }
    if (f.visibility !== 'all' && c.visibility !== f.visibility) return false
    if (f.audited !== 'all') {
      if (f.audited === 'audited' && !c.audited) return false
      if (f.audited === 'pending' && c.audited) return false
    }
    return true
  })
}
