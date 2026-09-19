/**
 * useScenarioRuns.ts — 场景执行记录的读侧缓存与信号口径。
 *
 * 执行记录的 config.schemeId 由 run_dispatcher 写入(方案溯源),据此可
 * 区分「某方案的执行」与「非方案发起的验证执行」(公共原件)。两个信号口径:
 *   - 方案卡顶部状态 / 相对时间 = 该方案最近一次执行;
 *   - 关注页健康趋势 = 我的来源锁默认方案、公共来源锁原件自身(不跨方案聚合)。
 * 列表按后端返回序(新→旧)处理。
 *
 * 缓存是模块级、跨路由存活的,所以**必须按登录用户分键** —— 否则同一浏览器
 * 换账号后会读到上一个用户的执行状态(workbench/layout.ts 早就按用户名分键,
 * 这里是补齐同一纪律)。
 */
import { ref, type Ref } from 'vue'
import { listExecutions, type Execution } from '@/api/executions'
import { useAuthStore } from '@/stores/auth'

/** key = `<username>::<scenarioId>` */
const cache = new Map<string, Ref<Execution[]>>()
const inflight = new Map<string, Promise<Execution[]>>()

function bucket(cacheKey: string): Ref<Execution[]> {
  let r = cache.get(cacheKey)
  if (!r) {
    r = ref([]) as Ref<Execution[]>
    cache.set(cacheKey, r)
  }
  return r
}

export interface RunStamp {
  status: string
  at: string | null
}

function stamp(e: Execution): RunStamp {
  return { status: e.status, at: e.finished_at || e.started_at }
}

export function useScenarioRuns() {
  const auth = useAuthStore()
  const keyOf = (scenarioId: string) => `${auth.currentUser?.username ?? ''}::${scenarioId}`

  /** 拉取某场景近期执行(默认缓存;force 用于执行后刷新)。 */
  async function load(scenarioId: string, force = false): Promise<Execution[]> {
    const key = keyOf(scenarioId)
    if (!force && cache.has(key)) return cache.get(key)!.value
    let p = inflight.get(key)
    if (!p) {
      p = listExecutions({ scenarioId, limit: 30 }).then((r) => r.items)
      inflight.set(key, p)
      p.catch(() => []).finally(() => inflight.delete(key))
    }
    try {
      const items = await p
      bucket(key).value = items
      return items
    } catch {
      return []
    }
  }

  function runsOf(scenarioId: string): Ref<Execution[]> {
    return bucket(keyOf(scenarioId))
  }

  /** 该方案最近一次执行;无记录 = null。 */
  function lastRunOfScheme(scenarioId: string, schemeId: string): RunStamp | null {
    const hit = bucket(keyOf(scenarioId)).value.find((e) => e.config?.schemeId === schemeId)
    return hit ? stamp(hit) : null
  }

  /** 健康趋势(近 5 次,旧→新)。isPublic = 公共原件(自身验证执行);
   *  否则锁 defaultSchemeId,无默认方案/无记录 = 空数组(留白)。 */
  function trend(scenarioId: string, defaultSchemeId: string | null, isPublic: boolean): string[] {
    const all = bucket(keyOf(scenarioId)).value
    const relevant = isPublic
      ? all
      : defaultSchemeId
        ? all.filter((e) => e.config?.schemeId === defaultSchemeId)
        : []
    return relevant.slice(0, 5).map((e) => e.status).reverse()
  }

  /** 执行发起后作废缓存,下次读重新拉。 */
  function invalidate(scenarioId: string) {
    cache.delete(keyOf(scenarioId))
  }

  return { load, runsOf, lastRunOfScheme, trend, invalidate }
}
