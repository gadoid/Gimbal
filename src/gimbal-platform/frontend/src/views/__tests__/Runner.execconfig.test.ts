/**
 * Runner.vue 执行配置选择器**退役钉**(账户组合 §8.3/ADR-0003 #26):
 * 运行期换用载体 0 使用判死 —— 下拉不再渲染、发起载荷恒不带
 * execConfigId(默认链自动占位);「以谁的身份跑」由场景绑定
 * (组合/方案)决定,Runner 不提供第三层身份选择。
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

describe('Runner 执行配置选择器退役(账户组合 §8.3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('下拉不再渲染(第三层身份选择移除)', async () => {
    const w = await mountAndQueue()
    expect(w.find('[data-testid="runner-exec-config"]').exists()).toBe(false)
    w.unmount()
  })

  it('发起载荷恒不带 execConfigId(默认链自动占位)', async () => {
    const w = await mountAndQueue()
    await w.get('[data-testid="runner-launch"]').trigger('click')
    await flushPromises()
    expect(runScenario).toHaveBeenCalledWith(
      expect.not.objectContaining({ execConfigId: expect.anything() }))
    w.unmount()
  })
})
