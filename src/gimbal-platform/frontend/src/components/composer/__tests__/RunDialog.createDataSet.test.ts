/**
 * RunDialog — 新建数据集入口降级为跳转(P0)
 *
 * 锁死:
 * - 旧的 JSON 文本框创建路径(裸 promptAction + createDataSet)不可达
 * - "+ 新建数据集" link-btn 存在,点击触发 router.push('/scenarios/:id/data-sets/new')
 * - 跳转目标使用 vue-router 真实 push(而非 window.location.href)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import RunDialog from '../RunDialog.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

const DS = [{ datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] }]

const mockRoute = { params: { scenarioId: 'sc-a' }, query: {} }
const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: mockPush, replace: vi.fn().mockResolvedValue(undefined) }),
  }
})

const SCENARIO: Scenario = {
  meta: {
    scenarioId: 'sc-a', name: 'x', description: '', module: 'm',
    priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
  },
  steps: [],
  orchestration: { steps: [], resourceMeta: {} },
  dataSetCount: 0, stepCount: 0, tags: [],
} as unknown as Scenario

function mountDialog() {
  return mount(RunDialog, {
    props: {
      scenario: SCENARIO, dataSets: DS,
      running: false, lastRunId: null, lastRunError: null,
      schemes: [], lastRunOverlay: null, serviceRows: [], authOptions: [],
    },
    global: { plugins: [ElementPlus, createPinia()], stubs: { teleport: true } },
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  mockPush.mockClear()
  vi.spyOn(api, 'createDataSet').mockResolvedValue({
    datasetId: 'ds-x', scenarioId: 'sc-a', name: 'x', rowCount: 0, rows: [],
  })
})

describe('RunDialog — 新建数据集入口', () => {
  it('旧的 JSON 文本框创建路径不可达:createDataSet 不被调用', async () => {
    const w = mountDialog()
    // 模板里不应再出现 promptAction 路径的 textarea / 双 promptAction 调用。
    // 简化锁死:confirm 后 api.createDataSet 不被任何遗留路径触发。
    const go = w.findAll('button').find((b) => b.text().includes('发起运行'))
    await go!.trigger('click')
    expect(api.createDataSet).not.toHaveBeenCalled()
  })

  it('"+ 新建数据集" 按钮点击触发 router.push 到 DataSetEditor', async () => {
    const w = mountDialog()
    const newBtn = w.findAll('button')
      .find((b) => b.text().trim().startsWith('+ 新建数据集'))
    expect(newBtn).toBeDefined()
    await newBtn!.trigger('click')
    expect(mockPush).toHaveBeenCalledTimes(1)
    const arg = mockPush.mock.calls[0][0]
    expect(typeof arg).toBe('string')
    expect(arg).toMatch(/^\/scenarios\/sc-a\/data-sets\/new$/)
  })
})