/**
 * CaseComposer — varDemote 删键通路(§5.2 逆动作):Canvas emit('varDemote')
 * → config.vars 删键(immutable 替换);键不存在 = no-op 不炸。
 *
 * 骨架 = CaseComposer.autosave.test.ts 的 mock 面(模块 mock 构造器 impl
 * + 真实 vue-router memory history);挂载直取 ?step=4 进 Canvas 步,
 * 断言落在 draft store 同步面(CaseComposer deep watch → setDraft)。
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

// 模块 mock(构造器 impl 防 vi.restoreAllMocks 清实现,autosave 同款):
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
    // §5.2 fixture:config.vars 带 exp_code(期望提升登记的基线)+ base_url
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
  // Canvas onMounted 策略 kinds 预热:kinds 空 → 降级 UI(varDemote 链无关)
  vi.spyOn(api, 'listStrategyKinds').mockResolvedValue([])
  // varDemote 触发 dirty → 防抖自动 PUT;fake timers 不推进 → 不发,
  // 但 spy 兜底保证任何时序下都不碰真实网络。
  vi.spyOn(api, 'updateScenario').mockResolvedValue(sampleScenario())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — varDemote 删键通路(§5.2 逆动作)', () => {
  it('varDemote 删 config.vars 键,其余键保留', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    canvas.vm.$emit('varDemote', 'exp_code')
    await nextTick()
    await flushPromises()
    const vars = (useScenarioDraftStore().draft as any).definition.config.vars
    expect('exp_code' in vars).toBe(false)
    expect(vars.base_url).toBe('http://x')     // 其余键保留
    w.unmount()
  })

  it('varDemote 键不存在 = no-op', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    const before = (useScenarioDraftStore().draft as any).definition
    canvas.vm.$emit('varDemote', 'ghost')
    await nextTick()
    await flushPromises()
    const after = (useScenarioDraftStore().draft as any).definition
    // 未发生替换(引用不变)且 vars 原样 — 不抛错、其余键不动
    expect(after).toBe(before)
    expect(after.config.vars).toEqual({ base_url: 'http://x', exp_code: 200 })
    w.unmount()
  })
})
