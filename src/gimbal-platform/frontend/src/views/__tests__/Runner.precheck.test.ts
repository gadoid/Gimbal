/**
 * Runner.vue 预检行 — authz W6 内置凭证告警(builtinAuthShadowed)。
 *
 * 场景依赖属主的内置凭证、执行人名下又没有同名别名时,后端预检回
 * builtinAuthShadowed 清单;此前只在接口返回、页面不展示,被分享人
 * 只能在执行后看到 401。这里钉:有清单 → 预检行出告警并指向「我的
 * 凭证」;空清单 → 不出。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Runner from '@/views/Runner.vue'
import { listScenarioOptions, precheckRun } from '@/api/scenario-composer'
import type { PrecheckResult } from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/scenario-composer')>()
  return {
    ...orig,
    listScenarioOptions: vi.fn().mockResolvedValue({
      items: [{ scenarioId: 'sc-1', name: '共享场景', visibility: 'private' }],
      total: 1,
    }),
    listRunSchemes: vi.fn().mockResolvedValue([
      { schemeId: 'default', name: '默认', isDefault: true },
    ]),
    precheckRun: vi.fn(),
    runScenario: vi.fn(),
  }
})

vi.mock('@/composables/useRunAssembly', async () => {
  const { ref } = await import('vue')
  return {
    useRunAssembly: () => ({
      load: vi.fn().mockResolvedValue(undefined),
      loading: ref(false), loadError: ref(''),
      scenario: ref(null), schemes: ref([]), dataSets: ref([]),
      registry: ref({ entries: [] }), serviceRows: ref([]),
      stepNames: ref([]), surface: { deadIds: ref([]) },
    }),
  }
})

function pc(over: Partial<PrecheckResult> = {}): PrecheckResult {
  return {
    scenarioId: 'sc-1', schemeId: 'default', found: true,
    schemeFound: true, schemeValid: true,
    deadDatasetIds: [], danglingEntryIds: [], unboundServices: [],
    builtinAuthShadowed: [], ...over,
  }
}

async function mountAndQueue() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } }],
  })
  const w = mount(Runner, {
    global: {
      plugins: [router],
      stubs: { RunConfigPanel: true, QTip: true },
    },
  })
  await flushPromises()
  await w.get('[data-testid="runner-open-picker"]').trigger('click')
  await w.get('[data-testid="runner-add-btn-sc-1"]').trigger('click')
  await flushPromises()
  return w
}

describe('Runner 场景选择器', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('一律 scope=mine(管理员对他人私有场景无执行权,不再「全列」)', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    useAuthStore().capabilities = ['users.manage', 'ops.write', 'alias.write']
    vi.mocked(listScenarioOptions).mockClear()
    await mountAndQueue()
    const calls = vi.mocked(listScenarioOptions).mock.calls
    expect(calls.length).toBeGreaterThan(0)
    for (const [params] of calls) expect(params).toMatchObject({ scope: 'mine' })
  })
})

describe('Runner 预检行 · 内置凭证告警', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(precheckRun).mockReset()
  })

  it('builtinAuthShadowed 非空 → 告警并指向「我的凭证」', async () => {
    vi.mocked(precheckRun).mockResolvedValue([pc({ builtinAuthShadowed: ['gitlab', 'jira'] })])
    const w = await mountAndQueue()
    const warn = w.get('[data-testid="precheck-shadowed-0"]')
    expect(warn.text()).toContain('gitlab、jira')
    expect(warn.text()).toContain('内置凭证')
    expect(warn.get('a').attributes('href')).toBe('/auths')
  })

  it('空清单(或旧后端无该字段)→ 不出告警', async () => {
    vi.mocked(precheckRun).mockResolvedValue([pc()])
    const w = await mountAndQueue()
    expect(w.text()).toContain('预检通过')
    expect(w.find('[data-testid="precheck-shadowed-0"]').exists()).toBe(false)

    vi.mocked(precheckRun).mockResolvedValue([{ ...pc(), builtinAuthShadowed: undefined }])
    const w2 = await mountAndQueue()
    expect(w2.find('[data-testid="precheck-shadowed-0"]').exists()).toBe(false)
  })
})

describe('Runner 预检行 · 凭证缺槽(S8 收口)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(precheckRun).mockReset()
  })

  it('missingAuths 非空 → 告警;项目池齐备 → 提示可切项目凭证', async () => {
    vi.mocked(precheckRun).mockResolvedValue([pc({
      missingAuths: ['qa1'], projectMissingAuths: [],
    })])
    const w = await mountAndQueue()
    const line = w.get('[data-testid="runner-missing-auths"]')
    expect(line.text()).toContain('qa1')
    expect(line.text()).toContain('项目凭证')
  })

  it('个人池齐备 → 不出缺槽行(旧后端无字段同理)', async () => {
    vi.mocked(precheckRun).mockResolvedValue([pc({ missingAuths: [] })])
    const w = await mountAndQueue()
    expect(w.find('[data-testid="runner-missing-auths"]').exists()).toBe(false)
    vi.mocked(precheckRun).mockResolvedValue([pc({ missingAuths: undefined })])
    const w2 = await mountAndQueue()
    expect(w2.find('[data-testid="runner-missing-auths"]').exists()).toBe(false)
  })
})
