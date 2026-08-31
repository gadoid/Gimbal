/**
 * OpConstructDialog —— 11 类构造表单(§6.3 全量 + T16 三个 carry 值表 op):
 *   - renameVar:from/to 取场景 vars 调色板,payload {from,to},datasetId null;
 *   - mapValue:键值行编辑器,空键行剔除,payload {step,field,map};
 *   - mergeSeed:锁 renameField 并预填;
 *   - CARRY_OPS:免场景校验,请求体不带 scenarioId 键;service 缺省不带键。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import * as api from '@/api/adaptations'
import type { OpOut } from '@/api/adaptations'
import * as scenarioApi from '@/api/scenario-composer'

// Task 9 同款场景;vars 调色板 = config.vars 键
const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{ api: { view_hints: {}, headers: {} },
            request: { body: { amount: '${var.amount}' } } }],
  config: { vars: { amount: 100, fee: 1 } },
  dataSetCount: 0, stepCount: 1, tags: [],
} as never

const created = {
  id: 9, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
  opType: 'renameVar', payload: { from: 'amount', to: 'fee' },
  status: 'pending', appliedAt: null, note: null,
} as OpOut   // as never 会让 {...created} 触发 TS2698(spread never)

async function mountDialog(props: Record<string, unknown> = {}) {
  const w = mount(OpConstructDialog, {
    props: { modelValue: true, batchId: 'bt-1', ...props },
    global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('OpConstructDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // listScenarios 实际返回 Scenario[](scenarioId 在 meta 下)——mock 对齐实际形状
    vi.spyOn(scenarioApi, 'listScenarios').mockResolvedValue(
      [scenario] as never)
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
    vi.spyOn(scenarioApi, 'listDataSets').mockResolvedValue([])
  })

  it('renameVar 提交:调色板选择,payload {from,to},datasetId null', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue(created)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'renameVar'
    vm.form.scenarioId = 'sc-1'
    vm.form.from = 'amount'
    vm.form.to = 'fee'
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameVar', scenarioId: 'sc-1', datasetId: null,
      payload: { from: 'amount', to: 'fee' },
    })
    expect(w.emitted('created')?.[0]).toEqual([created])
    w.unmount()
  })

  it('mapValue:map 行编辑器,空键行剔除', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      ...created, opType: 'mapValue',
    } as never)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: { mapRows: { key: string; value: string }[] } & Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'mapValue'
    vm.form.scenarioId = 'sc-1'
    vm.form.step = 0
    vm.form.field = 'settle_type'
    vm.form.mapRows = [
      { key: '1', value: '2' },
      { key: '', value: 'x' },        // 空键 → 剔除
    ]
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'mapValue', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, field: 'settle_type', map: { '1': '2' } },
    })
    w.unmount()
  })

  it('mergeSeed:锁 renameField 并预填 from/to', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      ...created, opType: 'renameField',
    } as never)
    const w = await mountDialog({
      mergeSeed: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    expect(vm.form.opType).toBe('renameField')   // 打开即预填
    expect(vm.form.step).toBe(0)
    expect(vm.form.from).toBe('legacy_field')
    expect(vm.form.to).toBe('extra')

    vm.form.scenarioId = 'sc-1'
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameField', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    w.unmount()
  })

  it('CARRY_OPS:免场景校验,请求体不带 scenarioId 键;service 缺省不带键(全局默认)', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      ...created, opType: 'addCarryBinding', scenarioId: null,
    } as never)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'addCarryBinding'
    vm.form.service = ''          // 缺省 = 全局默认表
    vm.form.field = '$.fee'
    vm.form.value = 'CNY'
    // 不设 scenarioId —— carry op 不校验、不发送
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'addCarryBinding',
      payload: { path: '$.fee', value: 'CNY' },
    })
    const body = createSpy.mock.calls[0][1] as unknown as Record<string, unknown>
    expect('scenarioId' in body).toBe(false)
    expect('datasetId' in body).toBe(false)
    w.unmount()
  })

  it('CARRY_OPS:renameCarryPath 带 service;removeCarryPath 只带 path', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue(created)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'renameCarryPath'
    vm.form.service = 'fin.order'
    vm.form.from = '$.legacy_fee'
    vm.form.to = '$.fee'
    await vm.submit()
    await flushPromises()

    vm.form.opType = 'removeCarryBinding'
    vm.form.service = 'fin.order'
    vm.form.field = '$.legacy_fee'
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenNthCalledWith(1, 'bt-1', {
      opType: 'renameCarryPath',
      payload: { service: 'fin.order', from: '$.legacy_fee', to: '$.fee' },
    })
    expect(createSpy).toHaveBeenNthCalledWith(2, 'bt-1', {
      opType: 'removeCarryBinding',
      payload: { service: 'fin.order', path: '$.legacy_fee' },
    })
    w.unmount()
  })
})
