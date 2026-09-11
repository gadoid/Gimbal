/**
 * CaseComposer — registryAdd 落条目通路(spec v2 §4 / Task 4):Canvas
 * emit('registryAdd', anchor) → onRegistryAdd 落 registry.entries(偏离
 * injection 默认取基线 config.vars)+ 显式保存调度(registry 不在 dirty
 * watch 源 → 防抖自动 PUT 须携带 assertion_registry,标记不丢)。
 *
 * 骨架 = CaseComposer.vardemote.test.ts 的 mock 面(模块 mock 构造器 impl
 * + 真实 vue-router memory history);挂载直取 ?step=4 进 Canvas 步,
 * 断言落在 draft store 同步面与 updateScenario spy。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import * as api from '@/api/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
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
    // §4 fixture:base_url = 基线值(偏离 injection 默认取它)
    config: { vars: { base_url: 'http://x', exp_code: 200 } },
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
  // loadScenario 二级取数(spec v2 §3 断言注册表):mock 掉防真实 XHR 悬挂
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({} as any)
  vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
  vi.spyOn(api, 'listStrategyKinds').mockResolvedValue([])
  // registryAdd 触发 dirty → 防抖自动 PUT;fake timers 推进 2.5s 后发,
  // spy 兜底保证任何时序下都不碰真实网络。
  vi.spyOn(api, 'updateScenario').mockResolvedValue(sampleScenario())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — registryAdd 落条目 + 保存调度(spec v2 §4)', () => {
  const ANCHOR = { stepIndex: 0, source: 'body' as const, jsonpath: '$.base_url', varName: 'base_url' }

  it('registryAdd → registry.entries 落偏离条目(injection 取基线 vars)→ draft store 同步', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    canvas.vm.$emit('registryAdd', ANCHOR)
    await nextTick()
    await flushPromises()
    const reg = (useScenarioDraftStore().draft as any).assertion_registry
    expect(reg.entries).toHaveLength(1)
    expect(reg.entries[0].id).toMatch(/^inj-/)
    expect(reg.entries[0].name).toBe('偏离 1')
    expect(reg.entries[0].anchor).toEqual(ANCHOR)
    // 偏离值默认取基线 config.vars.base_url
    expect(reg.entries[0].injection).toEqual([{ varName: 'base_url', value: 'http://x' }])
    expect(reg.entries[0].asserts).toEqual([])
    w.unmount()
  })

  it('registryAdd 触发防抖自动保存 — PUT 携带 assertion_registry(registry 不在 dirty watch 源)', async () => {
    const w = await mountPage()
    ;(api.updateScenario as any).mockClear()   // 隔离挂载期噪音
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', ANCHOR)
    await nextTick()
    await flushPromises()
    expect(api.updateScenario).not.toHaveBeenCalled()   // 防抖未到不发
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    const draft = (api.updateScenario as any).mock.calls[0][1]
    expect(draft.assertion_registry.entries).toHaveLength(1)
    expect(draft.assertion_registry.entries[0].anchor).toEqual(ANCHOR)
    w.unmount()
  })
})
