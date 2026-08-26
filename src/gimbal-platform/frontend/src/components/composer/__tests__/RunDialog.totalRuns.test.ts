/**
 * RunDialog — 总量闸前置(P1)
 *
 * 后端 dispatch 侧 MAX_RUNS_PER_EXECUTION=200(rows × nRuns)会整单
 * 409 too_many_runs;前端在 confirm 前同闸拦截,免得用户提交才报错。
 *
 * 锁死:
 * - 3 行数据集 × nRuns 100 = 300 > 200 → 不 emit confirm + 提示
 * - 同数据集 nRuns 50 = 150 ≤ 200 → 正常 emit
 * - footer 次数 chip 超限时带 over 类(红色警示)
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'
import type { Scenario } from '@/types/scenario-composer'

const ENV = [{ envId: 'dev', name: 'dev', baseUrl: 'http://x' }]
const DS = [{ datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] }]

const scenario = {
  meta: {
    scenarioId: 'sc-a', name: 'x', description: '', module: 'm',
    priority: 1, author: 'qa', owner: 'qa', tags: [], system: [],
  },
  steps: [],
  orchestration: { steps: [], resourceMeta: {} },
  dataSetCount: 1,
  stepCount: 0,
  tags: [],
  config: {},
} as unknown as Scenario

function mountDialog() {
  return mount(RunDialog, {
    props: {
      scenario, dataSets: DS, envs: ENV,
      running: false, lastRunId: null, lastRunError: null,
      ownerAuthAliases: [],
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

/** 高级区第一个 number input = nRuns(第二个是 parallel)。 */
async function setNRuns(w: ReturnType<typeof mount>, n: number) {
  await w.findAll('input[type="number"]')[0].setValue(String(n))
}

async function clickConfirm(w: ReturnType<typeof mount>) {
  const go = w.findAll('button').find((b) => b.text().includes('发起运行'))
  await go!.trigger('click')
}

describe('RunDialog — 总量闸(rows × nRuns ≤ 200)', () => {
  it('3 行 × nRuns 100 = 300:不 emit confirm', async () => {
    const w = mountDialog()
    // 默认全选 ds-1(3 行),nRuns 输入 100 → 300 超闸
    await setNRuns(w, 100)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeUndefined()
    w.unmount()
  })

  it('3 行 × nRuns 50 = 150:正常 emit confirm', async () => {
    const w = mountDialog()
    await setNRuns(w, 50)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeTruthy()
    w.unmount()
  })

  it('footer 次数 chip 超限带 over 警示类', async () => {
    const w = mountDialog()
    await setNRuns(w, 100)
    const chip = w.find('.summary-chip.total')
    expect(chip.classes()).toContain('over')
    w.unmount()
  })
})
