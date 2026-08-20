/**
 * stores/scenario-composer.ts — 场景编排 Pinia store
 *
 * 字段命名: store 持有全部场景 / 数据集,提供读、写、过滤。
 * 写操作后保持乐观更新 + 错误回滚(失败时 refetch)。
 * Case 层已解散 — 数据集直接挂场景,执行配方在 RunRequest(纯值)。
 */
import { defineStore } from 'pinia'
import * as api from '@/api/scenario-composer'
import type {
  Scenario, DataSet, DataSetSummary,
  ScenarioDraft, DataSetDraft,
} from '@/types/scenario-composer'

type FetchStatus = 'idle' | 'loading' | 'error'

/** 列表内 upsert:命中即位替换,未命中插到表头。 */
function upsertBy<T>(list: T[], match: (x: T) => boolean, item: T): void {
  const idx = list.findIndex(match)
  if (idx >= 0) list.splice(idx, 1, item)
  else list.unshift(item)
}

export const useScenarioComposerStore = defineStore('scenario-composer', {
  state: () => ({
    scenarios: [] as Scenario[],
    dataSets: [] as DataSetSummary[],

    scenariosStatus: 'idle' as FetchStatus,
    dataSetsStatus: 'idle' as FetchStatus,

    lastError: null as string | null,
  }),

  getters: {
    starredScenarios: (s) => s.scenarios.filter((x) => x.starred),

    dataSetsOfScenario:
      (s) => (scenarioId: string) =>
        s.dataSets.filter((d) => d.scenarioId === scenarioId),

    scenarioById:
      (s) => (scenarioId: string) =>
        s.scenarios.find((x) => x.meta.scenarioId === scenarioId),

    dataSetById:
      (s) => (datasetId: string) =>
        s.dataSets.find((d) => d.datasetId === datasetId),
  },

  actions: {
    // ── scenarios ───────────────────────────────────────────
    async fetchScenarios(params?: Parameters<typeof api.listScenarios>[0]) {
      this.scenariosStatus = 'loading'
      try {
        this.scenarios = await api.listScenarios(params ?? {})
        this.scenariosStatus = 'idle'
      } catch (e) {
        this.scenariosStatus = 'error'
        this.lastError = (e as Error).message
      }
    },

    async saveScenario(scenarioId: string | null, draft: ScenarioDraft) {
      const saved = scenarioId
        ? await api.updateScenario(scenarioId, draft)
        : await api.createScenario(draft)
      upsertBy(
        this.scenarios,
        (x) => x.meta.scenarioId === saved.meta.scenarioId,
        saved,
      )
      return saved
    },

    async toggleStar(scenarioId: string) {
      const cur = this.scenarioById(scenarioId)
      if (!cur) return
      cur.starred = !cur.starred
      try {
        await api.starScenario(scenarioId, !!cur.starred)
      } catch {
        cur.starred = !cur.starred
        throw new Error('收藏失败')
      }
    },

    async removeScenario(scenarioId: string) {
      await api.deleteScenario(scenarioId)
      this.scenarios = this.scenarios.filter(
        (x) => x.meta.scenarioId !== scenarioId,
      )
    },

    // ── 发布 / 下架 / 复制(P1)──────────────────────────────
    async publishScenario(scenarioId: string) {
      const saved = await api.publishScenario(scenarioId)
      upsertBy(this.scenarios, (x) => x.meta.scenarioId === saved.meta.scenarioId, saved)
      return saved
    },

    async unpublishScenario(scenarioId: string) {
      const saved = await api.unpublishScenario(scenarioId)
      upsertBy(this.scenarios, (x) => x.meta.scenarioId === saved.meta.scenarioId, saved)
      return saved
    },

    async copyScenario(scenarioId: string) {
      // 深拷贝返回新场景(恒 private),插到列表头
      const saved = await api.copyScenario(scenarioId)
      this.scenarios.unshift(saved)
      return saved
    },

    // ── data-sets ───────────────────────────────────────────
    async fetchDataSets(scenarioId?: string) {
      this.dataSetsStatus = 'loading'
      try {
        this.dataSets = await api.listDataSets({ scenarioId })
        this.dataSetsStatus = 'idle'
      } catch (e) {
        this.dataSetsStatus = 'error'
        this.lastError = (e as Error).message
      }
    },

    async saveDataSet(scenarioId: string, datasetId: string | null, draft: DataSetDraft) {
      const saved = datasetId
        ? await api.updateDataSet(datasetId, draft)
        : await api.createDataSet(scenarioId, draft)
      const toSummary = (base: Partial<DataSetSummary>) => ({
        ...base,
        ...saved,
        rowCount: saved.rows.length,
        preview: saved.rows.slice(0, 3),
      })
      upsertBy(this.dataSets, (d) => d.datasetId === saved.datasetId, toSummary({}))
      return saved
    },
  },
})
