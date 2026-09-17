/**
 * ImpactDrawer —— 影响清单抽屉:
 *   - 打开时拉 impact(endpointId),按 field 分组;
 *   - 条目标注 直填/模板 与 datasetId.datasetColumn;
 *   - 底部 [开批次] emit openBatch。
 * 交互注意:shadcn Drawer 经 Portal 渲染 → body 查询(DOMWrapper)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'
import * as api from '@/api/adaptations'

const items = [
  { scenarioId: 'sc-a', stepIndex: 0, source: 'body', field: 'amount',
    viaVar: 'amount', datasetId: 'ds-1', datasetColumn: 'amount' },
  { scenarioId: 'sc-b', stepIndex: 1, source: 'body', field: 'amount',
    viaVar: null, datasetId: null, datasetColumn: null },
  { scenarioId: 'sc-c', stepIndex: 0, source: 'headers', field: 'q1',
    viaVar: null, datasetId: null, datasetColumn: null },
]

function qAll(sel: string): DOMWrapper<Element>[] {
  return [...document.body.querySelectorAll(sel)].map((el) => new DOMWrapper(el))
}

function mountIt() {
  return mount(ImpactDrawer, {
    props: {
      modelValue: true,
      endpointId: 'fin.order.add',
      fromVersion: '1.0.0',
      toVersion: '1.1.0',
    },
    global: { plugins: [getActivePinia()!] },
    attachTo: document.body,
  })
}

describe('ImpactDrawer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('打开时按 field 分组渲染 + 直填/模板与数据集标注', async () => {
    const spy = vi.spyOn(api, 'impact').mockResolvedValue(items as never)
    const w = mountIt()
    await flushPromises()

    expect(spy).toHaveBeenCalledWith('fin.order.add')
    const groups = qAll('.field-group')
    expect(groups.length).toBe(2)          // amount(2 条) + q1(1 条)

    const amountText = groups[0].text()
    expect(amountText).toContain('sc-a')
    expect(amountText).toContain('模板')
    expect(amountText).toContain('ds-1.amount')
    expect(amountText).toContain('sc-b')
    expect(amountText).toContain('直填')
    w.unmount()
  })

  it('[开批次] emit openBatch', async () => {
    vi.spyOn(api, 'impact').mockResolvedValue(items as never)
    const w = mountIt()
    await flushPromises()

    const btn = qAll('.open-batch-btn')[0]
    await btn.trigger('click')
    expect(w.emitted('openBatch')).toHaveLength(1)
    w.unmount()
  })
})
