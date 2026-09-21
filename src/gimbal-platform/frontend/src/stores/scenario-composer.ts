/**
 * stores/scenario-composer.ts — 场景编排 Pinia store(M1 store 退位改版)。
 *
 * PG迁移方案 §4.3:store 不再把全量场景当全局缓存 —— 检索后移后只存
 * ①列表页的**当前页**(ScenarioListItem 投影,经 useServerList 驱动)
 * ②工作台卡与名称映射共享的**首窗缓存**(第一页 ≤100 条投影行,单飞
 * 合流,替代旧 ensureScenarios 的「三卡一次请求」性质)
 * ③数据集(不变)。详情页直接按 id 拉单条;mutation 后只作废当前页/
 * 首窗重拉,不再维护全量列表的乐观 upsert。
 */
import { defineStore } from 'pinia'
import * as api from '@/api/scenario-composer'
import { FOLLOW_CAP, FollowCapError } from '@/composables/useFollowLayout'
import type {
  Scenario, ScenarioListItem, ScenarioOptionsItem, ScenarioPage,
  ScenarioDraft, DataSetSummary,
} from '@/types/scenario-composer'

type FetchStatus = 'idle' | 'loading' | 'error'

/** 首窗/单飞的 module 作用域 promise:Pinia state 不该持 Promise。 */
let inflightWindow: Promise<void> | null = null
let inflightOptions: Promise<void> | null = null

export const useScenarioComposerStore = defineStore('scenario-composer', {
  state: () => ({
    // ── 列表当前页(场景库两页经 useServerList 驱动)──────────────
    page: null as ScenarioListItem[] | null,
    pageTotal: 0,
    pageStatus: 'idle' as FetchStatus,

    // ── 工作台首窗(4 卡 + 时间线共享,单飞)──────────────────────
    window: [] as ScenarioListItem[],
    windowLoaded: false,
    windowStatus: 'idle' as FetchStatus,

    // ── options 轻量缓存(名称映射类消费方,单飞)─────────────────
    options: [] as ScenarioOptionsItem[],
    optionsLoaded: false,

    dataSets: [] as DataSetSummary[],
    dataSetsStatus: 'idle' as FetchStatus,

    lastError: null as string | null,
  }),

  getters: {
    dataSetsOfScenario:
      (s) => (scenarioId: string) =>
        s.dataSets.filter((d) => d.scenarioId === scenarioId),
  },

  actions: {
    // ── 列表当前页(useServerList 的 fetch 通道)──────────────────
    async fetchPage(params: api.ScenarioListParams): Promise<ScenarioPage> {
      this.pageStatus = 'loading'
      try {
        const env = await api.listScenarios(params)
        this.page = env.items
        this.pageTotal = env.total
        this.pageStatus = 'idle'
        return env
      } catch (e) {
        this.pageStatus = 'error'
        this.lastError = (e as Error).message
        throw e // useServerList 的错误通道接管提示
      }
    },

    // ── 工作台首窗:第一页 ≤100 条投影(单飞合流,旧 ensureScenarios
    //    的「三卡一次请求」性质保留;>100 的精确计数由 M5 聚合端点接管)。
    async fetchWindow(): Promise<void> {
      this.windowStatus = 'loading'
      try {
        const env = await api.listScenarios({ page: 1, page_size: 100 })
        this.window = env.items
        this.windowLoaded = true
        this.windowStatus = 'idle'
      } catch (e) {
        this.windowStatus = 'error'
        this.windowLoaded = false
        this.lastError = (e as Error).message
      }
    },

    async ensureWindow(): Promise<ScenarioListItem[]> {
      if (this.windowLoaded) return this.window
      const p = (inflightWindow
        ??= this.fetchWindow().finally(() => { inflightWindow = null }))
      await p
      return this.window
    },

    // ── options:选择器/名称映射(Runner picker、OpConstructDialog、
    //    台账场景名)——「为拿名字拉全量场景表」就此退役。
    async fetchOptions(): Promise<void> {
      try {
        const env = await api.listScenarioOptions({ page_size: 100 })
        this.options = env.items
        this.optionsLoaded = true
      } catch (e) {
        this.lastError = (e as Error).message
      }
    },

    async ensureOptions(): Promise<ScenarioOptionsItem[]> {
      if (this.optionsLoaded) return this.options
      const p = (inflightOptions
        ??= this.fetchOptions().finally(() => { inflightOptions = null }))
      await p
      return this.options
    },

    /** mutation 后作废缓存:当前页按需重拉(列表页在),首窗/options
     *  置脏下次挂载再拉。不维护全量乐观 upsert —— 那是退位前的形态。 */
    invalidate() {
      this.windowLoaded = false
      this.optionsLoaded = false
    },

    async saveScenario(scenarioId: string | null, draft: ScenarioDraft) {
      const saved = scenarioId
        ? await api.updateScenario(scenarioId, draft)
        : await api.createScenario(draft)
      this.invalidate()
      return saved
    },

    /** ★ 切换(本地乐观翻转在调用方行内;store 只负责请求 + 作废)。 */
    async toggleStar(scenarioId: string, starred: boolean) {
      try {
        await api.starScenario(scenarioId, starred)
        this.invalidate()
      } catch {
        throw new Error('收藏失败')
      }
    },

    /** ★ 切换 + 关注上限守卫。超限抛 FollowCapError,由视图翻成提示。 */
    async toggleStarWithCap(scenarioId: string, starred: boolean) {
      if (!starred) {
        // 取关不设限;上限只拦「新关注」。
        await this.toggleStar(scenarioId, false)
        return
      }
      const env = await api.listScenarios({ starred: true, page_size: FOLLOW_CAP + 1 })
      if (env.total >= FOLLOW_CAP) {
        throw new FollowCapError(`关注上限 ${FOLLOW_CAP} 个 — 请先在关注页取消部分关注`)
      }
      await this.toggleStar(scenarioId, true)
    },

    async removeScenario(scenarioId: string) {
      await api.deleteScenario(scenarioId)
      this.invalidate()
    },

    // ── 发布 / 下架 / 复制(P1)──────────────────────────────
    async publishScenario(scenarioId: string) {
      const saved = await api.publishScenario(scenarioId)
      this.invalidate()
      return saved
    },

    async unpublishScenario(scenarioId: string) {
      const saved = await api.unpublishScenario(scenarioId)
      this.invalidate()
      return saved
    },

    async copyScenario(scenarioId: string) {
      // 深拷贝返回新场景(恒 private);详情数据由调用方接管
      const saved = await api.copyScenario(scenarioId)
      this.invalidate()
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

// saveDataSet/removeDataSet 已随数据集独立路由退役移除(Phase 3 清理,
// 批次 0 登记):创建/编辑/删除由方案工作台 SchemeDataSection 直连 api 承接。

  },
})
