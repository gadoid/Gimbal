/** filter.ts — advanced filter helpers shared by CasesMine / CasesPublic.
 *
 * Pulled out of FilterPopover.vue so consumers can import them from
 * a plain .ts file (Vue <script setup> doesn't allow runtime exports
 * from .vue SFCs).
 */
import type { CaseSummary } from '@/api/cases'

export interface CaseFilters {
  modules: string[]
  tags: string[]
  authors: string[]
  priorities: number[]
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
    updatedWithin: 'all',
    visibility: 'all',
    audited: 'all',
  }
}

/** Pure filter — exported for parents and tests. */
export function applyFiltersToList(
  pool: CaseSummary[],
  f: CaseFilters,
): CaseSummary[] {
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
    if (f.tags.length && !c.tags.some((t) => f.tags.includes(t))) return false
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
      const ts = Date.parse(c.updated_at)
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
