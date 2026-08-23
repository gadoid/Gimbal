/**
 * useFieldDescriptions.ts — 从 Plate /full 拉 IOFieldBinding.description,
 * 按 columnKey (= `stepIndex:source:field`) 索引,供 DataSetEditor 渲染
 * 「字段说明」行。
 *
 * 设计要点:
 *   - 仅 body 字段有 IOFieldBinding;query / headers 优雅降级为空串。
 *   - 复用 CaseComposerCanvas.vue:795-824 的会话级 Map + 并发收敛模式。
 *     共享模块级缓存,所以两个组件同时打开同一 scenario 也只拉一次。
 *   - 零持久化:Plate 是结构权威源,每次进编辑器拿最新结构(发版后零迁移)。
 *
 * 调用方约定:在 setup 阶段调用一次,响应式 draft 变化后,Map 自动重算。
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

import { getFullEndpoint } from '@/api/scenario-composer'
import type { EndpointFullView } from '@/types/plate'

// 会话级缓存(模块作用域;Vue 组件间共享)
const fullByEndpoint = new Map<string, EndpointFullView>()
const fullInFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** 版本号 — Map 变化不触发 computed;bump 让 computed 重算 */
const fullVersion = ref(0)

async function ensureFull(eid: string): Promise<EndpointFullView | undefined> {
  const cached = fullByEndpoint.get(eid)
  if (cached) return cached
  const inFlight = fullInFlight.get(eid)
  if (inFlight) return inFlight
  console.debug('[useFieldDescriptions] fetch /full for', eid)
  fullState.value = 'loading'
  const p = getFullEndpoint(eid)
    .then((full) => {
      console.debug(
        '[useFieldDescriptions] /full ok', eid,
        'fields:', full?.request?.fields?.length ?? 0,
      )
      fullByEndpoint.set(eid, full)
      fullVersion.value++
      fullState.value = ''
      return full
    })
    .catch((e) => {
      console.warn('[useFieldDescriptions] /full failed', eid, e?.message)
      fullState.value = 'failed'
      return undefined
    })
    .finally(() => fullInFlight.delete(eid))
  fullInFlight.set(eid, p)
  return p
}

/** 全局拉取状态(任一 endpoint 失败 → failed)。 */
const fullState = ref<'loading' | 'failed' | ''>('')

export interface FieldDescriptionsApi {
  /** 渲染「字段说明」行时按 columnKey 查询。
   *  columnKey 格式与 dataset-grid.ts / dataset-palette.ts 一致:
   *  `${stepIndex}:${source}:${field}` */
  descriptionByColumnKey: ComputedRef<Map<string, string>>
  /** 'loading' = 还有 endpoint 在拉; 'failed' = 至少一个失败;
   *  '' = 全成功 / 无 endpoint */
  state: ComputedRef<'loading' | 'failed' | ''>
}

export function useFieldDescriptions(
  draft: Ref<{ definition: { steps?: any[] } } | null>,
): FieldDescriptionsApi {
  // 1) 收集 unique endpoint_id(响应式)
  const eids = computed<string[]>(() => {
    const steps = draft.value?.definition?.steps ?? []
    const s = new Set<string>()
    for (const step of steps) {
      const eid = step?.api?.view_hints?.endpoint_id
      if (eid) s.add(eid)
    }
    return [...s]
  })

  // 2) draft 变化(eids 变化)时,触发 fetch;同一 endpoint 不重复请求
  watch(
    eids,
    (ids) => {
      console.debug('[useFieldDescriptions] eids changed:', ids)
      for (const eid of ids) void ensureFull(eid)
    },
    { immediate: true },
  )

  // 3) 计算 columnKey → description
  const descriptionByColumnKey = computed<Map<string, string>>(() => {
    void fullVersion.value  // 显式依赖
    const map = new Map<string, string>()
    const steps = draft.value?.definition?.steps ?? []
    for (let stepIndex = 0; stepIndex < steps.length; stepIndex++) {
      const step = steps[stepIndex]
      const eid = step?.api?.view_hints?.endpoint_id
      if (!eid) continue
      const full = fullByEndpoint.get(eid)
      if (!full?.request?.fields) continue
      const fieldsByName = new Map(full.request.fields.map((f) => [f.name, f]))
      // 只 body 字段在 Plate 里有 IOFieldBinding;query/headers 留空
      const body = step?.request?.body
      if (!body || typeof body !== 'object' || Array.isArray(body)) continue
      for (const fieldName of Object.keys(body)) {
        const fb = fieldsByName.get(fieldName)
        if (!fb) continue
        map.set(`${stepIndex}:body:${fieldName}`, fb.description ?? '')
      }
    }
    return map
  })

  return { descriptionByColumnKey, state: computed(() => fullState.value) }
}

/** 测试钩子:清空缓存。仅供单测使用。 */
export function _resetFullCacheForTest() {
  fullByEndpoint.clear()
  fullInFlight.clear()
  fullVersion.value++
  fullState.value = ''
}