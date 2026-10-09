/**
 * useSuiteSchemes.ts — Suite 页共用的方案/数据集缓存(第 2 步)。
 *
 * 管理页单元设置(方案 chip、数据行选择)、运行预检(多行方案告警、
 * 精确 runs 估算)都要读成员场景的方案与数据集行数;模块级缓存避免
 * 行内展开 / 预检弹窗各自打一遍 N 个请求。失败静默返回空(增强信息,
 * 不阻断主链);resolve(id, true) 可强刷。
 */
import { listRunSchemes, getDataSet } from '@/api/scenario-composer'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { DataSet } from '@/types/scenario-composer'

const schemesCache = new Map<string, SchemeV2[]>()
const datasetsCache = new Map<string, DataSet>()

export function useSuiteSchemes() {
  async function schemesOf(
    scenarioId: string, force = false,
  ): Promise<SchemeV2[]> {
    if (!force && schemesCache.has(scenarioId)) {
      return schemesCache.get(scenarioId) as SchemeV2[]
    }
    try {
      const list = await listRunSchemes(scenarioId)
      schemesCache.set(scenarioId, list)
      return list
    } catch {
      return schemesCache.get(scenarioId) ?? []
    }
  }

  async function datasetOf(datasetId: string, force = false): Promise<DataSet | null> {
    if (!force && datasetsCache.has(datasetId)) {
      return datasetsCache.get(datasetId) ?? null
    }
    try {
      const ds = await getDataSet(datasetId)
      datasetsCache.set(datasetId, ds)
      return ds
    } catch {
      return null
    }
  }

  /** 场景默认方案(null = 无方案,单元将跑裸基线)。 */
  async function defaultSchemeOf(scenarioId: string): Promise<SchemeV2 | null> {
    const list = await schemesOf(scenarioId)
    return list.find((s) => s.isDefault) ?? list[0] ?? null
  }

  return { schemesOf, datasetOf, defaultSchemeOf }
}
