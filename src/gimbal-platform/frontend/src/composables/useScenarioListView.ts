/**
 * useScenarioListView.ts — 场景库列表视图的共用骨架。
 *
 * 「我的场景」与「公共场景」是**同一个列表的两种分桶**:搜索字段、筛选
 * 摊平、分页、钳页、"筛空 vs 真无"判定全部逐字相同 —— 原先在两个 .vue
 * 里各抄一份(~120 行),改一处必漏另一处。真正的差异只有一个分桶谓词,
 * 于是把它做成入参(§7 计数同源:卡与页必须用同一个谓词,收敛到这里最稳)。
 */
import { computed, ref, watch } from 'vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useListSearch } from '@/utils/useListSearch'
import {
  applyFiltersToList, emptyFilters, isFiltering,
  type FilterRow, type ScenarioFilters,
} from '@/utils/filters'
import { showError } from '@/utils/errorFallback'
import type { Scenario } from '@/types/scenario-composer'

/** Scenario + 筛选层认得的摊平字段(module/author/priority/updated_at/system)。 */
export type ScenarioListRow = Scenario & FilterRow

export const LIST_PAGE_SIZE = 20

const SEARCH_FIELDS = [
  'meta.name', 'meta.scenarioId', 'meta.module', 'meta.description', 'meta.system', 'tags',
]

export function useScenarioListView(predicate: (row: ScenarioListRow) => boolean) {
  const store = useScenarioComposerStore()

  const q = ref('')
  const filters = ref<ScenarioFilters>(emptyFilters())
  const page = ref(1)

  const { filtered } = useListSearch(() => store.scenarios, SEARCH_FIELDS, q)

  // FilterPopover 按摊平键取值,所以先把 meta.* 抄到顶层。
  const filterableRows = computed<ScenarioListRow[]>(() =>
    filtered.value.map((s) => ({
      ...s,
      module: s.meta.module,
      author: s.meta.author || s.meta.owner,
      priority: s.meta.priority,
      updated_at: s.meta.updateTime,
      system: s.meta.system,
      tags: s.meta.tags,
    })),
  )

  const rows = computed<ScenarioListRow[]>(() =>
    applyFiltersToList(filterableRows.value, filters.value).filter(predicate),
  )

  const total = computed(() => rows.value.length)
  const filtering = computed(() => isFiltering(filters.value, q.value))
  const pageCount = computed(() => Math.ceil(total.value / LIST_PAGE_SIZE))
  const paged = computed(() => {
    const start = (page.value - 1) * LIST_PAGE_SIZE
    return rows.value.slice(start, start + LIST_PAGE_SIZE)
  })

  // 结果集变小(删卡/改筛选)时把越界的页码拉回来,避免停在空白页。
  watch(total, () => {
    const maxPage = Math.max(1, Math.ceil(total.value / LIST_PAGE_SIZE))
    if (page.value > maxPage) page.value = maxPage
  })

  /** fetchScenarios 自己吞异常(只置 status/lastError,不 reject),
   *  所以报错要看状态,不能 try/catch。 */
  async function load() {
    await store.fetchScenarios()
    if (store.scenariosStatus === 'error') showError('加载场景', undefined, store.lastError)
  }

  return {
    store, q, filters, page,
    filterableRows, rows, paged, total, pageCount, filtering,
    pageSize: LIST_PAGE_SIZE,
    load,
  }
}
