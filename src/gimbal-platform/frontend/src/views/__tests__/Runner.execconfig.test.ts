/**
 * Runner.vue 执行配置选择器(执行配置分层②)— 启动条整批共用的执行
 * 上下文:不选 = 默认链(不带 execConfigId);选定 → 逐条 runScenario
 * 都带 execConfigId(值 = 选定行 id)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Runner from '@/views/Runner.vue'
import { precheckRun, runScenario } from '@/api/scenario-composer'
import type { PrecheckResult } from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/scenario-composer')>()
  return {
    ...orig,
    listScenarioOptions: vi.fn().mockResolvedValue({
      items: [{ scenarioId: 'sc-1', name: '场景一', visibility: 'private' }],
      total: 1,
    }),
    listRunSchemes: vi.fn().mockResolvedValue([
      { schemeId: 'default', name: '默认', isDefault: true },
    ]),
    precheckRun: vi.fn(),
    runScenario: vi.fn().mockResolvedValue({ runId: 'r', executionId: 1 }),
  }
})

vi.mock('@/api/execConfigs', () => ({
  listExecConfigs: vi.fn().mockResolvedValue([
    { id: 5, name: '商户B视角', isDefault: true, environmentId: null,
      systems: [] },
    { id: 8, name: '审计视角', isDefault: false, environmentId: 2,
      systems: [] },
  ]),
}))

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

function pc(): PrecheckResult {
  return {
    scenarioId: 'sc-1', schemeId: 'default', found: true,
    schemeFound: true, schemeValid: true,
    deadDatasetIds: [], danglingEntryIds: [], unboundServices: [],
    builtinAuthShadowed: [],
  }
}

async function mountAndQueue() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } }],
  })
  vi.mocked(precheckRun).mockResolvedValue([pc()])
  const w = mount(Runner, {
    global: { plugins: [router], stubs: { RunConfigPanel: true, QTip: true } },
  })
  await flushPromises()
  await w.get('[data-testid="runner-open-picker"]').trigger('click')
  await w.get('[data-testid="runner-add-btn-sc-1"]').trigger('click')
  await flushPromises()
  return w
}

describe('Runner 执行配置选择器(分层②)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('选择器列出本人配置(默认行带「默认」标);不选 = 默认链', async () => {
    const w = await mountAndQueue()
    const sel = w.get('[data-testid="runner-exec-config"]')
    const options = sel.findAll('option').map((o) => o.text())
    expect(options).toEqual(['(默认链)', '商户B视角(默认)', '审计视角'])
    w.unmount()
  })

  it('选定 → 逐条发起带 execConfigId;不选 → 不带', async () => {
    const w = await mountAndQueue()
    // 默认链:载荷无 execConfigId
    await w.get('[data-testid="runner-launch"]').trigger('click')
    await flushPromises()
    expect(runScenario).toHaveBeenCalledWith(
      expect.not.objectContaining({ execConfigId: expect.anything() }))

    // 重新入队(发起后队列清空;picker 仍开着,不必再开)→ 显式选定 8 号
    await w.get('[data-testid="runner-add-btn-sc-1"]').trigger('click')
    await flushPromises()
    await w.get('[data-testid="runner-exec-config"]').setValue('8')
    await w.get('[data-testid="runner-launch"]').trigger('click')
    await flushPromises()
    expect(runScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({ execConfigId: 8 }))
    w.unmount()
  })
})
