/**
 * useScenarioName.ts — collapsed topbar 面包屑的场景名解析(Phase 1)。
 *
 * 面包屑契约(CaseComposer.crumb.test 同款):显示 `meta.name || id`。
 * - 模块级缓存为 **reactive Map**:composer 载入/保存改名时
 *   seedScenarioName() 写入,已挂载的消费者(顶条)即时更新 —— 场景
 *   改名后面包屑不再显示旧名(接线点:CaseComposer loadScenario/save)。
 * - inflight 去重:同一 scenarioId 一次会话只拉一次;拉取失败静默
 *   回退 id(面包屑不值得一次错误提示),下次挂载可重试。
 */
import { computed, reactive, watch, type Ref } from 'vue'
import { getScenario } from '@/api/scenario-composer'

const cache = reactive(new Map<string, string>())
const inflight = new Map<string, Promise<void>>()

export function seedScenarioName(scenarioId: string, name: string): void {
  if (name) cache.set(scenarioId, name)
}

function ensureName(id: string): void {
  if (!id || cache.has(id) || inflight.has(id)) return
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

export function useScenarioName(scenarioId: Ref<string>): Ref<string> {
  // 取数副作用与读取分离:seed 写缓存,computed 自动跟随
  watch(scenarioId, (id) => ensureName(id), { immediate: true })
  return computed(() => {
    const id = scenarioId.value
    return id ? (cache.get(id) ?? '') : ''
  })
}
