/**
 * useScenarioName.ts — collapsed topbar 面包屑的场景名解析(Phase 1)。
 *
 * 面包屑契约(CaseComposer.crumb.test 同款):显示 `meta.name || id`。
 * 模块级缓存 + 去重 inflight:同一 scenarioId 一次会话只拉一次;拉取
 * 失败静默回退 id(面包屑不值得一次错误提示)。页面在手场景对象时可
 * `seedScenarioName` 零获取注入(composer 已有自己的 crumb,暂未接)。
 */
import { ref, watch, type Ref } from 'vue'
import { getScenario } from '@/api/scenario-composer'

const cache = new Map<string, string>()
const inflight = new Map<string, Promise<void>>()

export function seedScenarioName(scenarioId: string, name: string): void {
  if (name) cache.set(scenarioId, name)
}

export function useScenarioName(scenarioId: Ref<string>): Ref<string> {
  const name = ref(cache.get(scenarioId.value) ?? '')

  watch(
    scenarioId,
    (id) => {
      if (!id) return
      const hit = cache.get(id)
      if (hit) {
        name.value = hit
        return
      }
      name.value = ''
      if (!inflight.has(id)) {
        inflight.set(
          id,
          getScenario(id)
            .then((s) => seedScenarioName(id, s.meta.name))
            .catch(() => {
              /* 静默:面包屑回退展示 id */
            })
            .finally(() => inflight.delete(id)),
        )
      }
      void inflight.get(id)!.then(() => {
        name.value = cache.get(id) ?? ''
      })
    },
    { immediate: true },
  )

  return name
}
