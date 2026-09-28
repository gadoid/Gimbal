/**
 * RunDialog — 总量闸前置(P1,阶段③ v2 改写;P2-05 乘法下沉后单元口径)
 *
 * 后端 dispatch 侧 MAX_RUNS_PER_EXECUTION=200(rows × 注入族)会整单
 * 409 too_many_runs;前端在 confirm 前同闸拦截,免得用户提交才报错。
 *
 * P2-05 口径:nRuns 在执行器内展开(计入台账 attempts 列),不再乘进
 * 总量 —— 总 = Σrows × max(注入条目数, 1);默认方案态恒 1。
 *
 * 锁死:
 * - 默认态 nRuns 300 → 总量 1(乘法下沉)→ 正常 emit confirm
 * - 自建态 3 行 × 100 注入条目 = 300 > 200 → 不 emit + footer chip 带 over 类
 * - 自建态整库 3 行(无注入)= 3 ≤ 200 → 正常 emit
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

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

const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-def', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
/** 整库 3 行 × N 注入条目(注入族撑总量;nRuns 不再乘进) */
const SCHEME_INJ = (nInj: number): SchemeV2 => ({
  schemeId: `rs-i${nInj}`, name: `整库×${nInj}注入`, isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-1' }],
  injectionEntryIds: Array.from({ length: nInj }, (_, i) => `inj-${i}`),
  serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
})

function mountDialog(schemes: SchemeV2[]) {
  return mount(RunDialog, {
    props: {
      scenario, dataSets: DS,
      running: false, lastRunId: null, lastRunError: null,
      schemes, serviceRows: [], authOptions: [],
    },
    global: { plugins: [], stubs: { teleport: true } },
  })
}

/** 默认方案态:nRuns 输入(自建态参数只读,无输入控件)。 */
async function setNRuns(w: ReturnType<typeof mount>, n: number) {
  await w.find('input[data-testid="n-runs"]').setValue(String(n))
}

async function clickConfirm(w: ReturnType<typeof mount>) {
  await w.find('[data-testid="run-confirm"]').trigger('click')
}

describe('RunDialog — 总量闸(两态公式 ≤ 200)', () => {
  it('默认态 nRuns 300:P2-05 乘法下沉 → 总量 1,正常 emit confirm', async () => {
    const w = mountDialog([DEFAULT_SCHEME])
    await setNRuns(w, 300)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeTruthy()
    w.unmount()
  })

  it('自建态:3 行 × 100 注入条目 = 300 超闸 → 不 emit + chip over', async () => {
    const w = mountDialog([DEFAULT_SCHEME, SCHEME_INJ(100)])
    await w.find('[data-testid="scheme-chip-rs-i100"]').trigger('click')
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeUndefined()
    const chip = w.find('.summary-chip.total')
    expect(chip.classes()).toContain('over')
    expect(chip.text()).toContain('300')
    w.unmount()
  })

  it('自建态:整库 3 行(无注入)= 3 ≤ 200 → 正常 emit confirm', async () => {
    // 合法方案(injectionEntryIds 为空 → 无悬空条目):总量由行数撑,
    // 远低于闸 → confirm 正常发出
    const scheme: SchemeV2 = {
      schemeId: 'rs-rows', name: '整库', isDefault: false,
      dataSetSelection: [{ datasetId: 'ds-1' }], injectionEntryIds: [],
      serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1,
      plugins: null, logSub: null,
    }
    const w = mountDialog([DEFAULT_SCHEME, scheme])
    await w.find('[data-testid="scheme-chip-rs-rows"]').trigger('click')
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeTruthy()
    w.unmount()
  })
})
