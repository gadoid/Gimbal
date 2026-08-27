/**
 * OpPreview —— 单条 op 预览(§6.2,零后端改动):
 *   - STEP_OPS:getScenario 取 steps[step] 的容器片段,body/headers;
 *   - renameVar:from→to + 场景内 ${var.from} 引用计数;
 *   - mapValue:map 键值表;
 *   - 数据集 op:datasetId + 列名(+ map 表)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import OpPreview from '@/components/adaptations/OpPreview.vue'
import * as scenarioApi from '@/api/scenario-composer'
import type { OpOut } from '@/api/adaptations'

const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{
    api: { view_hints: { endpoint_id: 'fin.order.add' }, headers: {} },
    request: { body: { amount: '${var.amount}', legacy_field: 'L',
                       settle_type: '1' } },
  }],
  config: { timePolicy: { kind: 'record' }, vars: { amount: 100, fee: 1 } },
  dataSetCount: 0,
  stepCount: 1,
  tags: [],
} as never

function op(partial: Partial<OpOut>): OpOut {
  return {
    id: 1, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
    opType: 'removeField', payload: {}, status: 'pending',
    appliedAt: null, note: null, ...partial,
  } as OpOut
}

function mountOp(o: OpOut) {
  return mount(OpPreview, {
    props: { op: o },
    global: { plugins: [ElementPlus] },
  })
}

describe('OpPreview', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
  })

  it('STEP_OPS:渲染步骤号 + 容器片段(含被触碰字段)', async () => {
    const w = mountOp(op({
      opType: 'removeField',
      payload: { step: 0, field: 'legacy_field' },
    }))
    await flushPromises()

    expect(w.text()).toContain('步骤 0')
    expect(w.text()).toContain('legacy_field')
    expect(w.find('.fragment').text()).toContain('amount')  // 同容器其他字段可见
    w.unmount()
  })

  it('renameVar:from→to + 引用计数', async () => {
    const w = mountOp(op({
      opType: 'renameVar',
      payload: { from: 'amount', to: 'amt' },
    }))
    await flushPromises()

    expect(w.text()).toContain('${var.amount} → ${var.amt}')
    expect(w.text()).toContain('1 处引用')
    w.unmount()
  })

  it('mapValue:渲染 map 键值表;数据集 op 渲染列名', async () => {
    const w = mountOp(op({
      opType: 'mapValue',
      payload: { step: 0, field: 'settle_type', map: { '1': '2' } },
    }))
    await flushPromises()
    expect(w.text()).toContain('settle_type')
    expect(w.text()).toContain('1 → 2')
    w.unmount()

    const w2 = mountOp(op({
      opType: 'renameDatasetColumn', datasetId: 'ds-1',
      payload: { from: 'amount', to: 'amt' },
    }))
    await flushPromises()
    expect(w2.text()).toContain('ds-1')
    expect(w2.text()).toContain('amount → amt')
    w2.unmount()
  })
})
