/**
 * RunDialog — stepTo 下拉步骤名(P0)
 *
 * 锁死:
 * - 步骤名读 stepOrchestrationNames(平台编排视图),不再是 steps[i].name/id
 * - orchestration 缺名 → 降级为 "Step N" 兜底文案
 * - orchestration 长度 < steps 长度 → 越界取 "Step N" 兜底
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'
import type { Scenario } from '@/types/scenario-composer'

const ENV = [{ envId: 'dev', name: 'dev', baseUrl: 'http://x' }]
const DS: Array<{ datasetId: string; scenarioId: string; name: string; rowCount: number; preview: never[] }> = []

function sampleScenario(stepCount: number): Scenario {
  return {
    meta: {
      scenarioId: 'sc-a', name: 'x', description: '', module: 'm',
      priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
    },
    steps: Array.from({ length: stepCount }, (_, i) => ({ kind: 'step', description: `desc-${i}` })),
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0, stepCount, tags: [],
  } as unknown as Scenario
}

function mountDialog(scenario: Scenario, orchestrationNames: string[]) {
  return mount(RunDialog, {
    props: {
      scenario, dataSets: DS, envs: ENV,
      running: false, lastRunId: null, lastRunError: null,
      ownerAuthAliases: [],
      stepOrchestrationNames: orchestrationNames,
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

describe('RunDialog — stepTo 下拉步骤名', () => {
  it('orchestration 有名:渲染 · {name}', async () => {
    const w = mountDialog(sampleScenario(2), ['创建订单', '查询详情'])
    const select = w.find('select')
    const opts = select.findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('第 1 步后停止 · 创建订单'))).toBe(true)
    expect(opts.some((t) => t.includes('第 2 步后停止 · 查询详情'))).toBe(true)
  })

  it('orchestration 缺名:降级为 "Step N"', async () => {
    const w = mountDialog(sampleScenario(2), ['', ''])
    const opts = w.find('select').findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('第 1 步后停止 · Step 1'))).toBe(true)
    expect(opts.some((t) => t.includes('第 2 步后停止 · Step 2'))).toBe(true)
  })

  it('orchestration 长度不齐:越界取 "Step N" 兜底', async () => {
    // 3 steps 但 orchestration 只有 1 个名
    const w = mountDialog(sampleScenario(3), ['仅第一步'])
    const opts = w.find('select').findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('· 仅第一步'))).toBe(true)
    expect(opts.some((t) => t.includes('· Step 2'))).toBe(true)
    expect(opts.some((t) => t.includes('· Step 3'))).toBe(true)
  })
})