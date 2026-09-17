/**
 * RunDialog — 总量闸前置(P1,阶段③ v2 改写:两态公式)
 *
 * 后端 dispatch 侧 MAX_RUNS_PER_EXECUTION=200(rows × nRuns)会整单
 * 409 too_many_runs;前端在 confirm 前同闸拦截,免得用户提交才报错。
 *
 * v2 两态公式:
 * - 默认方案态 = 基线 1 行 × nRuns
 * - 自建方案态 = Σrows × max(注入条目数, 1) × 方案 nRuns(参数只读,取方案值)
 *
 * 锁死:
 * - 默认态 nRuns 300 = 300 > 200 → 不 emit confirm + 提示
 * - 默认态 nRuns 200 = 200 ≤ 200 → 正常 emit(边界含)
 * - 自建态 3 行 × nRuns 100 = 300 > 200 → 不 emit + footer chip 带 over 类
 * - 自建态 3 行 × nRuns 50 = 150 ≤ 200 → 正常 emit
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
/** 整库 3 行 × 方案 nRuns(参数只读 → 总量由方案值决定) */
const SCHEME_NRUNS = (nRuns: number): SchemeV2 => ({
  schemeId: `rs-n${nRuns}`, name: `整库${nRuns}次`, isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-1' }], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns, parallel: 1, plugins: null, logSub: null,
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
  it('默认态:1 × 300 = 300 超闸 → 不 emit confirm', async () => {
    const w = mountDialog([DEFAULT_SCHEME])
    await setNRuns(w, 300)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeUndefined()
    w.unmount()
  })

  it('默认态:1 × 200 = 200 边界 → 正常 emit confirm', async () => {
    const w = mountDialog([DEFAULT_SCHEME])
    await setNRuns(w, 200)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeTruthy()
    w.unmount()
  })

  it('自建态:3 行 × nRuns 100 = 300 超闸 → 不 emit + chip over', async () => {
    const w = mountDialog([DEFAULT_SCHEME, SCHEME_NRUNS(100)])
    await w.find('[data-testid="scheme-chip-rs-n100"]').trigger('click')
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeUndefined()
    const chip = w.find('.summary-chip.total')
    expect(chip.classes()).toContain('over')
    expect(chip.text()).toContain('300')
    w.unmount()
  })

  it('自建态:3 行 × nRuns 50 = 150 → 正常 emit confirm', async () => {
    const w = mountDialog([DEFAULT_SCHEME, SCHEME_NRUNS(50)])
    await w.find('[data-testid="scheme-chip-rs-n50"]').trigger('click')
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeTruthy()
    w.unmount()
  })
})
