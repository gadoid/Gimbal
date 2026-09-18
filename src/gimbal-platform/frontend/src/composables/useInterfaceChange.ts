/**
 * useInterfaceChange.ts — 「接口有变更」信号(关注页信号区)。
 *
 * 数据源 = 适配中心:catalogDiff 的 pending 端点 × impact 的受影响场景。
 * 两端点均 admin-only,member 读取 403 → 信号留白(规则驱动、自动展示,
 * 不给配置项)。模块级单例缓存,三页共享同一份计算结果。
 */
import { ref } from 'vue'
import { catalogDiff, impact } from '@/api/adaptations'

const changed = ref<Set<string>>(new Set())
const loaded = ref(false)
let inflight: Promise<void> | null = null

export function useInterfaceChange() {
  async function ensure(): Promise<void> {
    if (loaded.value) return
    if (inflight) return inflight
    inflight = (async () => {
      const set = new Set<string>()
      try {
        const report = await catalogDiff()
        await Promise.all(
          report.pending.map(async (p) => {
            try {
              const items = await impact(p.endpointId)
              for (const it of items) set.add(it.scenarioId)
            } catch { /* 单端点影响面失败不阻断整体信号 */ }
          }),
        )
      } catch { /* member 无适配中心读权限 → 留白 */ }
      changed.value = set
      loaded.value = true
      inflight = null
    })()
    return inflight
  }

  function hasChange(scenarioId: string): boolean {
    return changed.value.has(scenarioId)
  }

  return { ensure, hasChange, changed }
}
