/**
 * Scenarios.vue — 「方案」直接入口(Task 8,spec 2026-09-14 §6)。
 *
 * 锁死:
 * - 操作列每行渲染 [data-testid="schemes-entry"] 直接按钮(在 ⋯ dropdown
 *   之前),文案带方案数徽标「方案 ·N」;schemeCount 缺省时只显示「方案」
 *   不带数字(旧缓存过渡兼容)
 * - 点击 → router.push(scenarioSchemesUrl(id)) 跳方案工作台;@click.stop
 *   不触发行点开(openScenario)
 * - ⋯ dropdown 菜单项不在本任务契约内(datasets 项收敛属计划 B 阶段③)
 *
 * 骨架仿 CaseDataSetsList.test.ts(store mock + router push spy);
 * 行形状按 Scenarios.vue 实际消费的读侧 Scenario。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: pushMock.push }),
  }
})

const storeMock = vi.hoisted(() => ({
  scenarios: [] as unknown[],
  scenariosStatus: 'idle',
  starredScenarios: [] as unknown[],
  lastError: '',
  fetchScenarios: vi.fn(async () => {}),
}))
vi.mock('@/stores/scenario-composer', () => ({
  useScenarioComposerStore: () => storeMock,
}))

import Scenarios from '@/views/Scenarios.vue'
import type { Scenario } from '@/types/scenario-composer'

/** 列表行 —— Scenarios.vue 消费的读侧 Scenario 形状(meta.* / tags /
 *  dataSetCount / stepCount / visibility / starred;schemeCount 为本任务新增)。 */
function row(over: Partial<Scenario> = {}): Scenario {
  return {
    meta: {
      scenarioId: 'sc-x', name: '下单链路', description: '', module: '订单',
      priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
    },
    steps: [], dataSetCount: 0, stepCount: 0, tags: [],
    visibility: 'private', starred: false,
    ...over,
  }
}

async function mountList() {
  const w = mount(Scenarios, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia()) // 真实 auth store(isMine 渲染依赖)
  pushMock.push.mockReset()
  storeMock.fetchScenarios.mockClear()
  storeMock.scenarios = []
})

describe('Scenarios — 「方案」直接入口', () => {
  it('行内渲染「方案 ·3」直接按钮并跳工作台', async () => {
    storeMock.scenarios = [row({ schemeCount: 3 })]
    const w = await mountList()
    const btn = w.find('[data-testid="schemes-entry"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('方案 ·3')
    await btn.trigger('click')
    expect(pushMock.push).toHaveBeenCalledWith('/scenarios/sc-x/schemes')
    w.unmount()
  })

  it('schemeCount 缺省 → 只显示「方案」不带数字(旧缓存兼容),点击仍跳工作台', async () => {
    storeMock.scenarios = [row()] // 无 schemeCount
    const w = await mountList()
    const btn = w.find('[data-testid="schemes-entry"]')
    expect(btn.text()).toBe('方案')
    await btn.trigger('click')
    expect(pushMock.push).toHaveBeenCalledWith('/scenarios/sc-x/schemes')
    w.unmount()
  })
})
