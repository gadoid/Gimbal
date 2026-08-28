/** RunDialog 默认配置(基线)选项:D12 空 dataSetIds 前端入口。 */
import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'
import type { Scenario } from '@/types/scenario-composer'

const DS = [
  { datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] },
  { datasetId: 'ds-2', scenarioId: 'sc-a', name: 'B', rowCount: 2, preview: [] },
]

function mountDialog(scenario: Scenario | null = null) {
  return mount(RunDialog, {
    props: {
      scenario, dataSets: DS,
      running: false, lastRunId: null, lastRunError: null,
      schemes: [], lastRunOverlay: null, serviceRows: [], authOptions: [],
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

it('默认全选数据集;切基线后 confirm 发空 dataSetIds', async () => {
  const w = mountDialog()
  expect(w.text()).toContain('5 次运行')   // (3+2) × nRuns=1,默认全选
  await w.find('input[data-test="baseline"]').setValue(true)
  expect(w.text()).toContain('1 次运行')   // 基线 = 一个隐式空行
  const go = w.findAll('button').find((b) => b.text().includes('发起运行'))
  await go!.trigger('click')
  const evt = w.emitted('confirm')!
  expect(evt[evt.length - 1][0]).toEqual([])   // dataSetIds = [] → D12 基线执行(首参,无 envId)
})

it('全取消数据集(基线未勾)也按基线显示:基线 ×1 / 1 次运行', async () => {
  const w = mountDialog()
  expect(w.find('.summary-chip.total').text()).toBe('5 次运行')
  // Vue 数组 v-model 把 modelValue 缓存在元素上、补丁期才同步,补丁还可能
  // 重建输入元素 — 每个取消动作都必须重新查找当前 DOM 里的勾选框,
  // 否则第二个 change 事件会读到过期数组(实测会串选)。
  const dsBoxes = () => w.findAll('input[type="checkbox"]')
    .filter((i) => i.attributes('data-test') !== 'baseline')
  expect(dsBoxes().length).toBe(2)   // 两个数据集卡片,基线伪卡片已排除
  for (let i = 0; i < 2; i++) {
    await dsBoxes()[i].setValue(false)
  }
  // 空选择 = 一个隐式空覆盖行(D12 显示对齐):显示如实反映 confirm 将派发 []
  expect(w.find('.summary-chip.total').text()).toBe('1 次运行')
  expect(w.text()).toContain('基线 ×1')
})

// ── 场景标识显示 name(零获取:scenario prop 在手)──────────────────
// 契约:「从 <X> 触发执行」的 X 从裸 scenarioId 改为 `meta.name || id`。
function dialogScenario(over: { name?: string }): Scenario {
  return {
    meta: {
      scenarioId: 'sc-a', name: '订单查询', description: '', module: '订单',
      priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
      ...over,
    },
    steps: [], dataSetCount: 0, stepCount: 0, tags: [],
  } as unknown as Scenario
}

it('场景标识显示 name:从 <name> 触发执行', async () => {
  const w = mountDialog(dialogScenario({}))
  expect(w.text()).toContain('从 订单查询 触发执行')
  expect(w.text()).not.toContain('sc-a')
})

it('未命名(name 为空)回退显示 scenarioId', async () => {
  const w = mountDialog(dialogScenario({ name: '' }))
  expect(w.text()).toContain('从 sc-a 触发执行')
})
