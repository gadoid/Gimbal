import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeDataSection from '../SchemeDataSection.vue'

// DataSetSummary 权威形状(@/types/scenario-composer):datasetId/scenarioId/name/rowCount/preview
const DS = [
  { datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 3, preview: [] },
  { datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 2, preview: [] },
]

describe('SchemeDataSection', () => {
  it('勾选数据集 → update:modelValue 带上 datasetId 与默认全行', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    // @change 绑在 tile 内部 input 上 — 从 input 驱动(setValue 设 checked 并触发 change)
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    const emitted = w.emitted('update:modelValue')!
    expect(emitted.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [0, 1, 2] },
    ])
  })

  it('失效数据集(不在 dataSets 里)标注并可一键移除', async () => {
    const w = mount(SchemeDataSection, {
      props: {
        modelValue: [{ datasetId: 'ds-gone', rowIndexes: [0] }],
        dataSets: DS,
        scenarioId: 'sc-x',
      },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('已删除')
    await w.find('[data-testid="drop-dead"]').trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })

  it('行级勾选增删(行 r ↔ rowIndex r,0 基)', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    const rows = w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')
    expect(rows).toHaveLength(3)  // rowCount=3 → 行0/行1/行2
    expect(w.text()).toContain('行0')
    expect(w.text()).not.toContain('行-1')
    await rows[1].setValue(true)  // 勾行1 → [0,1]
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [0, 1] },
    ])
    // 受控回写后,再去掉行0 → [1]
    await w.setProps({ modelValue: [{ datasetId: 'ds-001', rowIndexes: [0, 1] }] })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [1] },
    ])
  })

  it('行全清 = 取消整库', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })
})
