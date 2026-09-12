/**
 * useFieldDescriptions.ts — 从 Plate /full 拉 IOFieldBinding.description,
 * 按 columnKey (= `stepIndex:source:field`) 索引,供 DataSetEditor 渲染
 * 「字段说明」行。
 *
 * 设计要点:
 *   - 仅 body 字段有 IOFieldBinding;headers 优雅降级为空串。
 *   - /full 取数与缓存走**共享模块** `useEndpointFull`(每 endpoint 会话内
 *     恰好一次请求;并发收敛),所以本组合式与画布、编辑器共用同一份缓存。
 *   - 零持久化:Plate 是结构权威源,每次进编辑器拿最新结构(发版后零迁移)。
 *
 * 调用方约定:在 setup 阶段调用一次,响应式 draft 变化后,Map 自动重算。
 */
import { computed, watch, type ComputedRef, type Ref } from 'vue'

import {
  _resetEndpointFullCacheForTest,
  endpointFullState,
  ensureEndpointFull,
  getEndpointFull,
} from '@/composables/useEndpointFull'
import { formBindings } from '@/utils/declarations'

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
      for (const eid of ids) void ensureEndpointFull(eid)
    },
    { immediate: true },
  )

  // 2b) 全局状态 = 各端点状态的聚合(失败优先于加载中)
  const state = computed<'loading' | 'failed' | ''>(() => {
    let loading = false
    for (const eid of eids.value) {
      const s = endpointFullState(eid)
      if (s === 'failed') return 'failed'
      if (s === 'loading') loading = true
    }
    return loading ? 'loading' : ''
  })

  // 3) 计算 columnKey → description
  const descriptionByColumnKey = computed<Map<string, string>>(() => {
    const map = new Map<string, string>()
    const steps = draft.value?.definition?.steps ?? []
    for (let stepIndex = 0; stepIndex < steps.length; stepIndex++) {
      const step = steps[stepIndex]
      const eid = step?.api?.view_hints?.endpoint_id
      if (!eid) continue
      const full = getEndpointFull(eid)
      if (!full?.request?.declarations) continue
      // 目录化:表单字段面 = 解析态非 carry 平铺投影(端点级读穿)
      const fieldsByName = new Map(
        formBindings(full.request.declarations).map((f) => [f.name, f]),
      )
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

  return { descriptionByColumnKey, state }
}

/** 测试钩子:清空共享 /full 缓存。仅供单测使用。 */
export function _resetFullCacheForTest() {
  _resetEndpointFullCacheForTest()
}