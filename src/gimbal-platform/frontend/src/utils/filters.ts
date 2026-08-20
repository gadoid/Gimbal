/** filter.ts — advanced filter helpers shared by the scenario library.

 * Pulled out of FilterPopover.vue so consumers can import them from
 * a plain .ts file (Vue <script setup> doesn't allow runtime exports
 * from .vue SFCs).
 */

/** Minimal row shape the filter layer understands (was ScenarioFilterRow
 * from the retired api/cases.ts; inlined here in P4)。Cases 时代的
 * visibility / audited / owner_id 随 CasesMine/CasesPublic 退役移除。 */
export interface ScenarioFilterRow {
  module?: string
  tags?: string[]
  author?: string
  priority?: number
  updated_at?: string
}

export interface ScenarioFilters {
  modules: string[]
  tags: string[]
  authors: string[]
  priorities: number[]
  systems: string[]
  updatedWithin: 'all' | '24h' | '7d' | '30d'
}

export function emptyFilters(): ScenarioFilters {
  return {
    modules: [],
    tags: [],
    authors: [],
    priorities: [],
    systems: [],
    updatedWithin: 'all',
  }
}

/** A row the filter layer understands: ``Partial<ScenarioFilterRow>``
 * plus the optional ``system`` array (Scenarios.vue flattens
 * ``meta.system`` into it).  Rows that omit the field match no system
 * filter — which is why the system UI is gated on
 * ``availableSystems.length > 0``. */
export type FilterRow = Partial<ScenarioFilterRow> & { system?: string[] }

/** Pure filter — exported for parents and tests.
 *
 * Defensive against partially-shaped rows: the V3 scenario-composer
 * rows flattened by Scenarios.vue may lack ``tags`` / ``module`` /
 * ``updated_at`` fields, so every field access below must tolerate
 * ``undefined`` instead of throwing mid-filter.
 */
export function applyFiltersToList(
  pool: readonly FilterRow[],
  f: ScenarioFilters,
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
    if (f.authors.length && !f.authors.includes(c.author || '')) return false
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
    return true
  })
}
