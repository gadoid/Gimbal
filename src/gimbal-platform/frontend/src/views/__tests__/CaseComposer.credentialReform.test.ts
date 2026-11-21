/**
 * CaseComposer — 凭证治理 2c 保存链接线:
 * - UsersCard 的手配草稿(update:authDrafts)进 ScenarioDraft.authDrafts
 *   随 PUT 发送;空 = 不发键;
 * - 保存响应 newAuths → toast 点名新建 + 清空草稿 + bump 注册表版本;
 * - 登记闸 audit 态(identityWarnings)→ 黄条点名未登记引用。
 * 挂载在 ?step=3(③ 配置页)使 UsersCard 可达;fake timers 驱动防抖保存。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import CaseComposer from '@/views/CaseComposer.vue'
import UsersCard from '@/components/composer/UsersCard.vue'
import * as api from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import type { Scenario } from '@/types/scenario-composer'
import type { AuthDraftView } from '@/types/scenario-composer'

const AUTOSAVE_MS = 2500

vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => false),
  promptAction: vi.fn(async () => null),
}))
// toast 单例由 ToastHost 渲染 — 测试一律 mock 本模块(模块规范)
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, pageSize: 200 })),
  listAll: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/services', () => ({
  listServices: vi.fn(() => Promise.resolve({
    services: [], unregistered: [], plateReachable: true,
  })),
  listServiceInstanceOverview: vi.fn(() => Promise.resolve({ services: [] })),
  putServiceInstance: vi.fn(),
}))
vi.mock('@/api/environments', () => ({
  listEnvironments: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/service-aliases', () => ({
  listAllAliases: vi.fn(() => Promise.resolve([])),
  listAliases: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, pageSize: 200 })),
  createAlias: vi.fn(),
  patchAlias: vi.fn(),
}))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogSystemByService: vi.fn(() => Promise.resolve(new Map())),
  loadCatalogServiceNames: vi.fn(() => Promise.resolve([])),
}))

function sampleScenario(): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo', name: '订单创建 e2e', description: '',
      module: '订单', priority: 1, author: 'qa', owner: 'qa',
      tags: [], system: ['fin'], version: 'v0.1.0', expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: [{ call: { service: 'fin-service', method: 'POST', path: '/x' } }] as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0, stepCount: 1, tags: [],
  }
}

const DRAFT: AuthDraftView = {
  name: 'qa9', baseService: 'fin-service', envId: 1, username: 'ua',
}

let router: Router
async function mountPage(path = '/composer/sc-demo?step=3') {
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
    global: { plugins: [router, createPinia()] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({} as any)
  vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
  vi.spyOn(api, 'listStrategyKinds').mockResolvedValue([])
  vi.spyOn(api, 'getServiceResolution').mockResolvedValue({
    environment: null, envMixed: null, services: [],
  } as any)
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — 手配草稿保存链(凭证治理 2c)', () => {
  it('api 层:X-Identity-Warnings 头解析(黄条链的真实起点)', async () => {
    // updateScenario 返回 {scenario, identityWarnings, baseWarnings} — 头为
    // JSON 对象字符串(阶段 0 载体);坏 JSON/缺头保守空数组,不吵。
    const http = (await import('@/api/http')).default
    const scenario = sampleScenario()
    vi.spyOn(http, 'put').mockResolvedValueOnce({
      data: scenario,
      headers: { 'x-identity-warnings': '{"code":"identity_not_registered","identities":["ghost"]}' },
    } as any)
    const r1 = await api.updateScenario('sc-demo', {} as any)
    expect(r1.identityWarnings).toEqual(['ghost'])
    expect(r1.baseWarnings).toEqual([])
    expect(r1.scenario).toBe(scenario)
    vi.spyOn(http, 'put').mockResolvedValueOnce({
      data: scenario, headers: {},
    } as any)
    expect((await api.updateScenario('sc-demo', {} as any)).identityWarnings).toEqual([])
    vi.spyOn(http, 'put').mockResolvedValueOnce({
      data: scenario, headers: { 'x-identity-warnings': 'not-json' },
    } as any)
    expect((await api.updateScenario('sc-demo', {} as any)).identityWarnings).toEqual([])
  })

  it('api 层 + 黄条:X-Identity-Base-Warnings 头(阶段 3 同 base 闸 audit 载体)', async () => {
    const http = (await import('@/api/http')).default
    const scenario = sampleScenario()
    vi.spyOn(http, 'put').mockResolvedValueOnce({
      data: scenario,
      headers: { 'x-identity-base-warnings': JSON.stringify({
        code: 'identity_base_mismatch',
        refs: [{ index: 1, service: 'fin-service', identity: 'gitlab',
                 identityBase: 'gitlab', serviceBase: 'fin-service' }],
      }) },
    } as any)
    const r = await api.updateScenario('sc-demo', {} as any)
    expect(r.baseWarnings).toHaveLength(1)
    expect(r.baseWarnings[0].identity).toBe('gitlab')
    vi.spyOn(http, 'put').mockResolvedValueOnce({
      data: scenario, headers: { 'x-identity-base-warnings': '{bad' },
    } as any)
    expect((await api.updateScenario('sc-demo', {} as any)).baseWarnings).toEqual([])
  })

  it('调用身份草稿 → 随自动保存 PUT 进 authDrafts;newAuths 回包清草稿 + 点名新建', async () => {
    const update = vi.fn().mockResolvedValue({
      scenario: { ...sampleScenario(), newAuths: ['qa9'] },
      identityWarnings: [],
      serviceWarnings: { unregistered: [], declaredUrls: [] },
    })
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()

    const card = w.findComponent(UsersCard)
    expect(card.exists()).toBe(true)
    card.vm.$emit('update:authDrafts', [DRAFT])
    await flushPromises()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    const draft = update.mock.calls[0][1] as { authDrafts?: AuthDraftView[] }
    expect(draft.authDrafts).toEqual([DRAFT])

    // newAuths 回包:草稿清空(v-model 回传 [])+ toast 点名新建
    expect(vi.mocked(toast.success).mock.calls.some(
      ([m]) => typeof m === 'string' && m.includes('qa9'))).toBe(true)
    // 注册表版本 bump:registryRev 状态翻转(store 状态断言)
    const { useScenarioComposerStore } = await import('@/stores/scenario-composer')
    expect(useScenarioComposerStore().registryRev).toBeGreaterThan(0)
    w.unmount()
  })

  it('无手配草稿 → PUT body 不含 authDrafts 键;identityWarnings → 黄条', async () => {
    const update = vi.fn().mockResolvedValue({
      scenario: sampleScenario(),
      identityWarnings: ['ghost'],
      serviceWarnings: { unregistered: [], declaredUrls: [] },
    })
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()

    const card = w.findComponent(UsersCard)
    card.vm.$emit('update:authDrafts', [])
    await flushPromises()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    const body = update.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('authDrafts')
    // audit 黄条:点名未登记引用 + 指引登记
    expect(vi.mocked(toast.warning).mock.calls.some(
      ([m]) => typeof m === 'object' && m !== null
        && (m as { message: string }).message.includes('ghost'))).toBe(true)
    w.unmount()
  })

  it('serviceWarnings → 服务引用黄条(架构终态:未注册键/待迁移声明)', async () => {
    const update = vi.fn().mockResolvedValue({
      scenario: sampleScenario(),
      identityWarnings: [],
      baseWarnings: [],
      serviceWarnings: { unregistered: ['ghost-svc'],
                         declaredUrls: ['fin-service'] },
    })
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()
    const card = w.findComponent(UsersCard)
    card.vm.$emit('update:authDrafts', [])
    await flushPromises()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(vi.mocked(toast.warning).mock.calls.some(
      ([m]) => typeof m === 'object' && m !== null && (() => {
        const msg = (m as { message: string }).message
        return msg.includes('未注册服务键:ghost-svc')
          && msg.includes('内嵌地址声明待迁移:fin-service')
          && msg.includes('服务注册')
      })())).toBe(true)
    w.unmount()
  })

  it('baseWarnings → 跨源黄条(阶段 3 同 base 闸;保存已放行指引改绑)', async () => {
    const update = vi.fn().mockResolvedValue({
      scenario: sampleScenario(),
      identityWarnings: [],
      baseWarnings: [{ index: 1, service: 'fin-service', identity: 'gitlab',
                       identityBase: 'gitlab', serviceBase: 'fin-service' }],
    })
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()
    const card = w.findComponent(UsersCard)
    card.vm.$emit('update:authDrafts', []) // 触发 dirty → 自动保存
    await flushPromises()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    expect(vi.mocked(toast.warning).mock.calls.some(
      ([m]) => typeof m === 'object' && m !== null && (() => {
        const msg = (m as { message: string }).message
        return msg.includes('跨源引用') && msg.includes('gitlab')
          && msg.includes('步骤2') // index+1 的 1-based 呈现
      })())).toBe(true)
    w.unmount()
  })
})
