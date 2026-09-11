/**
 * CaseComposer — onExpNav 路由行为(spec §5.3 断言卡 ↗ 数据集 反向跳):
 * Canvas emit('exp-nav') → router.push(scenarioDataSetsUrl(sid));
 * 未保存路由 'new' 拒跳(/scenarios/new/data-sets 是垃圾址,修轮 7c7660e4)。
 * Canvas emit 面(X4)已有钉,这里钉 CaseComposer 消费端。
 *
 * 骨架 = CaseComposer.vardemote.test.ts 的 mock 面(模块 mock 构造器 impl
 * + 真实 vue-router memory history);挂载直取 ?step=4 进 Canvas 步,
 * 断言落在 router.push spy 调参上。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

// 模块 mock(构造器 impl 防 vi.restoreAllMocks 清实现,vardemote 同款):
// CaseComposer onMounted 拉常量池 / 执行历史,Canvas 拉认证列表 — 静默化。
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
// Canvas onMounted 旁路拉取(CaseComposerCanvas.test.ts mock 面同款):
// carry 值表 / 目录服务名 / 取数视图 — 挂载即触发,全部静默不碰网络。
vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn(() => Promise.resolve({})),
  getBindings: vi.fn(() => Promise.resolve({})),
}))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => []),
  loadCatalogSystemByService: vi.fn(async () => new Map()),
}))
vi.mock('@/api/query-views', () => ({
  fetchQueryViewIndex: vi.fn(async () => []),
  fetchQueryViewRows: vi.fn(),
}))
// /composer/new 挂载路径专用:useSystemPrefill 对 isNew 场景 immediate watch
// 拉 plate common/fin 预填(vardemote 骨架只挂已存场景,isNew=false 不触发)。
vi.mock('@/api/plate', () => ({
  fetchPlateSystems: vi.fn(async () => []),
  fetchSystemConfig: vi.fn(async () => null),
  fetchSystemMeta: vi.fn(async () => null),
  fetchSystemResources: vi.fn(async () => ({})),
}))

function sampleScenario(): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: [{
      kind: 'step',
      description: 's',
      api: { kind: 'api', service: 'fin-service', method: 'POST', path: '/x', headers: {}, view_hints: {} },
      request: { kind: 'request', body: {} },
      strategy: [],
    }] as unknown as Scenario['steps'],
    config: { vars: { base_url: 'http://x' } },
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

let router: Router
async function mountPage(path = '/composer/sc-demo?step=4') {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/composer/:scenarioId', component: CaseComposer },
      { path: '/scenarios', component: { template: '<div id="scen-list" />' } },
    ],
  })
  router.push(path)
  await router.isReady()
  const w = mount({ template: '<router-view />' }, {
    global: { plugins: [router, ElementPlus, createPinia()] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
  vi.spyOn(api, 'listStrategyKinds').mockResolvedValue([])
  vi.spyOn(api, 'updateScenario').mockResolvedValue(sampleScenario())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — onExpNav 路由行为(§5.3 断言卡 ↗ 数据集)', () => {
  it('exp-nav 已存场景:push 该场景的数据集列表页(scenarioDataSetsUrl)', async () => {
    const w = await mountPage()
    // push spy 挂载后装:初始导航不算;mockImplementation 阻真实跳转(断言在调参)
    const pushSpy = vi.spyOn(router, 'push').mockImplementation(async () => {})
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    // emit 名与 Canvas 内部 emit('expNav')(defineEmits 'expNav')同形(X4 同源)
    canvas.vm.$emit('expNav')
    await flushPromises()
    // sid 取已存场景 meta.scenarioId(非路由参数)→ /scenarios/{id}/data-sets
    expect(pushSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).toHaveBeenCalledWith('/scenarios/sc-demo/data-sets')
    w.unmount()
  })

  it('exp-nav 未保存路由 new:拒跳(push 不发 — /scenarios/new/data-sets 是垃圾址)', async () => {
    const w = await mountPage('/composer/new?step=4')
    const pushSpy = vi.spyOn(router, 'push').mockImplementation(async () => {})
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    canvas.vm.$emit('expNav')
    await flushPromises()
    expect(pushSpy).not.toHaveBeenCalled()
    w.unmount()
  })
})
