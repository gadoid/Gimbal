/** RunDialog 默认配置(基线)选项:D12 空 dataSetIds 前端入口。 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'

const ENV = [{ envId: 'dev', name: 'dev', baseUrl: 'http://x' }]
const DS = [
  { datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] },
  { datasetId: 'ds-2', scenarioId: 'sc-a', name: 'B', rowCount: 2, preview: [] },
]

function mountDialog() {
  return mount(RunDialog, {
    props: {
      scenario: null, dataSets: DS, envs: ENV,
      running: false, lastRunId: null, lastRunError: null,
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
  expect(evt[evt.length - 1][1]).toEqual([])   // dataSetIds = [] → D12 基线执行
})
