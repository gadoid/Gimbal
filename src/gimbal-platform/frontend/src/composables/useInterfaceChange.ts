/**
 * useInterfaceChange.ts — 「接口有变更」信号(关注页信号区)。
 *
 * 数据源 = 适配中心:catalogDiff 的 pending 端点 × impact 的受影响场景。
 * 两端点均 admin-only,member 读取 403 → 信号留白(规则驱动、自动展示,
 * 不给配置项)。模块级单例缓存,三页共享同一份计算结果。
 */
import { ref } from 'vue'
import { catalogDiff, impactBulk } from '@/api/adaptations'
import { httpStatusOf } from '@/api/http'

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
        // M5(债 12):一次 impact-bulk 拿回全部 pending 端点的受影响面
        // —— 替换「每端点一次 × 限并发 4」的 N+1。
        if (report.pending.length) {
          const bulk = await impactBulk(report.pending.map((p) => p.endpointId))
          for (const items of Object.values(bulk)) {
            for (const it of items) set.add(it.scenarioId)
          }
        }
        changed.value = set
        loaded.value = true
      } catch (e) {
        // 403 = member 无适配中心读权限,永久留白;其余(网络抖动/5xx)
        // 不能置 loaded —— 否则一次抖动就把信号永久打死到刷新为止。
        if (httpStatusOf(e) === 403) {
          changed.value = set
          loaded.value = true
        }
      } finally {
        inflight = null
      }
    })()
    return inflight
  }

  function hasChange(scenarioId: string): boolean {
    return changed.value.has(scenarioId)
  }

  return { ensure, hasChange, changed }
}
