/**
 * useListSearch — case-insensitive multi-field substring search.
 *
 * Used by 4 list views (CasesMine, CasesPublic, Auths, UsersAdmin) that
 * share the same shape: a reactive `query` ref + a list of records,
 * filtering by any of `fields` whose stringified value contains the
 * query (locale-lowercased).
 *
 * Accepts three shapes for ``items``:
 *   1. ``Ref<T[]>`` — typical when caller holds a Pinia ref directly
 *   2. ``() => T[]`` — recommended for Pinia state slices; the getter
 *      is invoked inside a ``computed`` so Vue tracks reactivity
 *      (passing a plain array reference is NOT reactive because the
 *      array contents can change without the reference changing)
 *   3. ``T[]`` — accepted for test convenience, but NOT reactive
 *      across in-place mutations; prefer (1) or (2) in production
 *
 * Usage:
 *   const { query, filtered } = useListSearch(
 *     () => usersStore.list,
 *     ['name', 'alias', 'author'],
 *   )
 *   <el-input v-model="query" />
 *   <div v-for="row in filtered" :key="row.id">…</div>
 */
import { computed, type ComputedRef, type Ref, ref, unref } from 'vue'

export interface UseListSearchApi<T> {
  /** Two-way bound to the search input. */
  query: Ref<string>
  /** The filtered list, recomputed when query or items change. */
  filtered: ComputedRef<T[]>
}

export type ItemsSource<T> = Ref<T[]> | T[] | (() => T[])

/** Resolve a field specifier against ``item``.
 *
 * Supports two shapes:
 *   - plain key:      ``'name'``            → item.name
 *   - dot path:       ``'meta.name'``       → item.meta?.name (any depth,
 *     short-circuits on ``undefined``/``null`` intermediates)
 *
 * Dot-path support exists because the V3 ``Scenario`` type keeps its
 * searchable strings nested under ``meta`` (Scenarios.vue searches
 * ``meta.name`` / ``meta.module`` / …).
 */
export function resolveField(item: Record<string, unknown>, field: string): unknown {
  if (!field.includes('.')) return item[field]
  let cur: unknown = item
  for (const key of field.split('.')) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur
}

export function useListSearch<T extends Record<string, unknown>>(
  items: ItemsSource<T>,
  fields: string[],
  /**
   * Optional externally-owned query ref.  When given, the composable
   * binds to it instead of creating its own — for callers that declare
   * the input's ``v-model`` ref before/elsewhere (Scenarios.vue pattern:
   * ``const q = ref('')`` + ``useListSearch(src, fields, q)``).
   * Omitted by every existing caller, so behavior is unchanged there.
   */
  queryOverride?: Ref<string>,
): UseListSearchApi<T> {
  const query = queryOverride ?? ref('')

  // Normalize to a getter so the filtered computed always has a
  // reactive dependency.  Vue 3 tracks function calls inside a
  // computed, so a getter is the only safe shape for plain arrays
  // (e.g. Pinia state slices that the store mutates in place).
  const source = computed(() => {
    if (typeof items === 'function') return (items as () => T[])()
    return unref(items)
  })

  const filtered = computed(() => {
    const list = source.value
    const q = query.value.trim().toLocaleLowerCase()
    if (!q) return list
    return list.filter((item) =>
      fields.some((f) => {
        const v = resolveField(item, f)
        return v != null && String(v).toLocaleLowerCase().includes(q)
      }),
    )
  })

  return { query, filtered }
}
