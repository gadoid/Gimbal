/** DataSetEditor 重做(spec §4):行 0 虚行两组列 + 稀疏行 + 从基线提取首行。 */
import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'new' } }),
  useRouter: () => ({ push: vi.fn() }),
  // @/api/http → @/router 在模块顶层 createRouter(beforeEach 仅注册,
  // 组件走上面 mock 的 useRoute/useRouter,不会真的导航)— 提供最小桩。
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '@/views/DataSetEditor.vue'

const DRAFT = {
  definition: {
    kind: 'scenario', scenarioId: 'sc-ds', meta: {},
    config: { vars: { amount: 100 } },
    steps: [{
      api: { view_hints: { endpoint_id: 'fin.order.add' } },
      request: { body: { amount: '${var.amount}', customer_id: '261' } },
    }],
  },
  orchestration: { steps: [], resourceMeta: {} },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'createDataSet').mockResolvedValue({ datasetId: 'ds-1', rows: [] } as any)
})

function mountEditor() {
  return mount(DataSetEditor, { global: { plugins: [ElementPlus] } })
}

it('行 0 渲染:变量列显默认值,直填列灰显 + 直填标记', async () => {
  const w = mountEditor()
  await flushPromises()
  expect(w.text()).toContain('amount')        // 变量列头
  expect(w.text()).toContain('customer_id')   // 直填列头
  expect(w.text()).toContain('· 直填')        // 分组标记(列头后缀)
  const amount = w.findAll('input').filter((i) => i.element.value === '100')
  expect(amount.length).toBeGreaterThanOrEqual(1)   // 行 0 基线默认(el-input value)
})

it('行 0 提升直填列:直填标记消失,新变量列默认值 = 原值', async () => {
  const w = mountEditor()
  await flushPromises()
  expect(w.text()).toContain('· 直填')
  const promote = w.findAll('button').find((b) => b.text().includes('提升为变量'))
  expect(promote).toBeTruthy()
  await promote!.trigger('click')
  expect(w.text()).not.toContain('· 直填')   // 唯一直填列已变变量列
  const inputs = w.findAll('input').filter((i) => i.element.value === '261')
  expect(inputs.length).toBeGreaterThanOrEqual(1)   // 行 0 默认值 = 原字面值
})

it('从基线提取首行 + 保存:行键只有变量列', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBaseline = w.findAll('.add-row span').find((el) => el.text().includes('从基线提取首行'))
  expect(addBaseline).toBeTruthy()
  await addBaseline!.trigger('click')
  const save = w.findAll('button').find((b) => b.text().includes('保存数据集'))
  await save!.trigger('click')
  await flushPromises()
  expect(api.createDataSet).toHaveBeenCalledWith('sc-ds', {
    name: expect.any(String),
    description: '',
    rows: [{ amount: '100' }],   // 稀疏:只有变量列键,直填列不进行
  })
})
