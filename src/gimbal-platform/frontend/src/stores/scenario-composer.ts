/**
 * stores/scenario-composer.ts — 场景编排 Pinia store
 *
 * 字段命名: store 持有全部场景 / 用例 / 数据集,提供读、写、过滤。
 * 写操作后保持乐观更新 + 错误回滚(失败时 refetch)。
 */
import { defineStore } from 'pinia'
import * as api from '@/api/scenario-composer'
import type {
  Scenario, Case, DataSet, DataSetSummary,
  ScenarioDraft, DataSetDraft, RunEnv,
} from '@/types/scenario-composer'

type FetchStatus = 'idle' | 'loading' | 'error'

export const useScenarioComposerStore = defineStore('scenario-composer', {
  state: () => ({
    scenarios: [] as Scenario[],
    cases: [] as Case[],
    dataSets: [] as DataSetSummary[],
    envs: [] as RunEnv[],

    scenariosStatus: 'idle' as FetchStatus,
    casesStatus: 'idle' as FetchStatus,
    dataSetsStatus: 'idle' as FetchStatus,

    lastError: null as string | null,
  }),

  getters: {
    starredScenarios: (s) => s.scenarios.filter((x) => x.starred),

    casesOfScenario:
      (s) => (scenarioId: string) =>
        s.cases.filter((c) => c.scenarioId === scenarioId),

    dataSetsOfCase:
      (s) => (caseId: string) =>
        s.dataSets.filter((d) => d.caseId === caseId),

    scenarioById:
      (s) => (scenarioId: string) =>
        s.scenarios.find((x) => x.meta.scenarioId === scenarioId),

    caseById:
      (s) => (caseId: string) =>
        s.cases.find((c) => c.caseId === caseId),

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
      const idx = this.scenarios.findIndex(
        (x) => x.meta.scenarioId === saved.meta.scenarioId,
      )
      if (idx >= 0) this.scenarios.splice(idx, 1, saved)
      else this.scenarios.unshift(saved)
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

    // ── cases ───────────────────────────────────────────────
    async fetchCases(params?: Parameters<typeof api.listCases>[0]) {
      this.casesStatus = 'loading'
      try {
        this.cases = await api.listCases(params ?? {})
        this.casesStatus = 'idle'
      } catch (e) {
        this.casesStatus = 'error'
        this.lastError = (e as Error).message
      }
    },

    async saveCase(caseId: string, patch: Partial<Case>) {
      const saved = await api.updateCase(caseId, patch)
      const idx = this.cases.findIndex((c) => c.caseId === caseId)
      if (idx >= 0) this.cases.splice(idx, 1, saved)
      return saved
    },

    async removeCase(caseId: string) {
      await api.deleteCase(caseId)
      this.cases = this.cases.filter((c) => c.caseId !== caseId)
    },

    // ── data-sets ───────────────────────────────────────────
    async fetchDataSets(caseId?: string) {
      this.dataSetsStatus = 'loading'
      try {
        this.dataSets = await api.listDataSets({ caseId })
        this.dataSetsStatus = 'idle'
      } catch (e) {
        this.dataSetsStatus = 'error'
        this.lastError = (e as Error).message
      }
    },

    async saveDataSet(caseId: string, datasetId: string | null, draft: DataSetDraft) {
      const saved = datasetId
        ? await api.updateDataSet(datasetId, draft)
        : await api.createDataSet(caseId, draft)
      const idx = this.dataSets.findIndex((d) => d.datasetId === saved.datasetId)
      if (idx >= 0) this.dataSets.splice(idx, 1, {
        ...this.dataSets[idx],
        ...saved,
        preview: saved.rows.slice(0, 3),
      })
      else this.dataSets.unshift({
        datasetId: saved.datasetId,
        caseId: saved.caseId,
        caseName: '',
        name: saved.name,
        rowCount: saved.rows.length,
        lastRunStatus: saved.lastRunStatus,
        lastRunAt: saved.lastRunAt,
        preview: saved.rows.slice(0, 3),
      })
      return saved
    },

    async removeDataSet(datasetId: string) {
      await api.deleteDataSet(datasetId)
      this.dataSets = this.dataSets.filter((d) => d.datasetId !== datasetId)
    },

    // ── envs / run ──────────────────────────────────────────
    async fetchEnvs() {
      this.envs = await api.listEnvs()
    },

    async runCase(req: Parameters<typeof api.runCase>[0]) {
      return api.runCase(req)
    },

    async previewPlate(draft: ScenarioDraft) {
      return api.previewPlateDraft(draft)
    },
  },
})
