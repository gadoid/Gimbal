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

/** axios 错误上的状态码(非 HTTP 错误 / 无 response 时 undefined)。 */
function httpStatus(e: unknown): number | undefined {
  return (e as { response?: { status?: number } })?.response?.status
}

export function useInterfaceChange() {
  async function ensure(): Promise<void> {
    if (loaded.value) return
    if (inflight) return inflight
    inflight = (async () => {
      const set = new Set<string>()
      try {
        const report = await catalogDiff()
        // 每个 pending 端点一次 impact,限并发:待处理端点可能十几个,
        // 全并发会瞬时打出同数量请求。
        const pending = report.pending
        let i = 0
        const worker = async () => {
          while (i < pending.length) {
            const p = pending[i++]
            try {
              for (const it of await impact(p.endpointId)) set.add(it.scenarioId)
            } catch { /* 单端点影响面失败不阻断整体信号 */ }
          }
        }
        await Promise.all(Array.from({ length: Math.min(4, pending.length) }, worker))
        changed.value = set
        loaded.value = true
      } catch (e) {
        // 403 = member 无适配中心读权限,永久留白;其余(网络抖动/5xx)
        // 不能置 loaded —— 否则一次抖动就把信号永久打死到刷新为止。
        if (httpStatus(e) === 403) {
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
