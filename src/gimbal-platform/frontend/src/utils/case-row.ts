/** case-row.ts — shared row-helpers for the Cases* list views.
 *
 * Both /workspace (`/cases/mine`) and /public (`/cases/public`) render
 * an `el-table` with the same set of columns and the same per-row
 * permission predicates.  These helpers were previously copy-pasted
 * in both files; centralizing prevents drift.
 */
import type { CaseSummary } from '@/api/cases'

/** Max number of tag chips rendered before collapsing into a "+N" pill. */
export const MAX_VISIBLE_TAGS = 3

/** Stable `el-table :row-key` value.  element-plus passes the row
 *  directly (not a `{ row }` wrapper), so we match that here. */
export function rowKey(row: CaseSummary): string {
  return row.case_id
}

/** Numeric priority 1 / 2 / 3 or null — never lies about other ints. */
export function priorityOf(row: CaseSummary): 1 | 2 | 3 | null {
  return row.priority === 1 || row.priority === 2 || row.priority === 3
    ? row.priority
    : null
}

/** Render the author column.  Falls back to "用户 #<id>" then "匿名". */
export function authorOf(row: CaseSummary): string {
  return row.author || (row.owner_id ? `用户 #${row.owner_id}` : '匿名')
}

/** True when the row's owner_id matches the current user. */
export function isSelfRow(
  row: CaseSummary,
  currentUserId: number | undefined,
): boolean {
  return row.owner_id !== null && row.owner_id === currentUserId
}

/** True when this case is a private copy owned by the current user.
 *  The single source of truth for both the "delete" and "publish"
 *  row actions (and any future "is owned by me" predicates). */
export function isMyPrivateCopy(
  row: CaseSummary,
  currentUserId: number | undefined,
): boolean {
  return (
    row.visibility === 'private' &&
    isSelfRow(row, currentUserId)
  )
}

/** Standard `el-table :row-class-name` signature.  `extra` is the
 *  optional list of additional classes (e.g. mine-only "favorited-row"
 *  that the mine view derives from local store state, not the row). */
export function rowClassName(
  { row }: { row: CaseSummary },
  extra?: string[],
): string {
  const cls: string[] = []
  if (row.favorited_by_me) cls.push('favorited-row')
  if (row.copied_by_me) cls.push('copied-row')
  if (extra) cls.push(...extra.filter(Boolean))
  return cls.join(' ')
}
