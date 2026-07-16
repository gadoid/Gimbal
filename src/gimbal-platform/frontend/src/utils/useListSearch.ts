/**
 * useListSearch — case-insensitive multi-field substring search.
 *
 * Used by 4 list views (CasesMine, CasesPublic, Auths, UsersAdmin) that
 * share the same shape: a reactive `query` ref + a list of records,
 * filtering by any of `fields` whose stringified value contains the
 * query (locale-lowercased).
 *
 * Usage:
 *   const { query, filtered } = useListSearch(items, ['name', 'alias', 'author'])
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

export function useListSearch<T extends Record<string, unknown>>(
  items: Ref<T[]> | T[],
  fields: (keyof T & string)[],
): UseListSearchApi<T> {
  const query = ref('')

  const filtered = computed(() => {
    // Accept both a Ref and a plain array — Pinia stores can be
    // destructured into a plain array in tests, and `computed` doesn't
    // auto-track it.
    const list = unref(items)
    const q = query.value.trim().toLocaleLowerCase()
    if (!q) return list
    return list.filter((item) =>
      fields.some((f) => {
        const v = item[f]
        return v != null && String(v).toLocaleLowerCase().includes(q)
      }),
    )
  })

  return { query, filtered }
}
