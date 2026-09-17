/**
 * CarryConfig — 批次 2 新栈迁移测试(本页此前无测试)。
 * 核心契约:三态行模型(无行/isNull/值)、degraded 保存门控、
 * 全局默认编辑 + 重复 path 拦截、datalist 服务选择。
 * CSV 解析/合并逻辑的真源测试在 utils/carry-csv.test,此处只验视图接线。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CarryConfig from '@/views/CarryConfig.vue'
import * as carryApi from '@/api/carry'
import { toast } from '@/utils/toast'

vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn(),
  putDefaults: vi.fn(),
  getBindings: vi.fn(),
  getBindingsFor: vi.fn(),
  putBindings: vi.fn(),
  getServiceFields: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const FIELDS = [
  { path: '$.headers.X-Trace-Id', type: 'string', description: '链路头' },
  { path: '$.headers.X-Account', type: 'string', description: '账号头' },
]

async function mountPage() {
  const w = mount(CarryConfig, { attachTo: document.body })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(carryApi.getDefaults).mockResolvedValue({
    '$.headers.X-Trace-Id': 'default-trace',
  })
  vi.mocked(carryApi.getBindings).mockResolvedValue({
    'fin-service': { '$.headers.X-Account': 'acc-1' },
  })
  vi.mocked(carryApi.getBindingsFor).mockResolvedValue({ '$.headers.X-Account': 'acc-1' })
  vi.mocked(carryApi.getServiceFields).mockResolvedValue({ fields: FIELDS, degraded: false })
  vi.mocked(carryApi.putBindings).mockResolvedValue({})
  vi.mocked(carryApi.putDefaults).mockResolvedValue({})
})

describe('CarryConfig — 服务绑定', () => {
  it('选服务 → 拉字段面 + 既有绑定;三态渲染正确(有行值/null/无行透默认 placeholder)', async () => {
    const w = await mountPage()
    await w.find('[data-testid="svc-input"]').setValue('fin-service')
    await w.find('[data-testid="svc-input"]').trigger('change')
    await flushPromises()

    const bound = w.find('[data-testid="svc-row-$.headers.X-Account"]')
    const unbound = w.find('[data-testid="svc-row-$.headers.X-Trace-Id"]')
    expect(bound.exists() && unbound.exists()).toBe(true)
    // 已绑定行:值在输入框
    expect(bound.find('input:not([disabled])').element as HTMLInputElement).toBeTruthy()
    // 无行:placeholder 透出全局默认
    const ph = (unbound.find('input').element as HTMLInputElement).placeholder
    expect(ph).toContain('default-trace')
    w.unmount()
  })

  it('字段面 degraded → 保存禁用(数据安全门控)', async () => {
    vi.mocked(carryApi.getServiceFields).mockResolvedValue({ fields: FIELDS, degraded: true })
    const w = await mountPage()
    await w.find('[data-testid="svc-input"]').setValue('svc-x')
    await w.find('[data-testid="svc-input"]').trigger('change')
    await flushPromises()
    expect(w.text()).toContain('字段面部分降级,保存已禁用')
    expect((w.find('[data-testid="save-service"]').element as HTMLButtonElement).disabled).toBe(true)
    w.unmount()
  })

  it('保存 → putBindings(编码真源在 buildServiceEntries)+ 成功 toast + 回读', async () => {
    const w = await mountPage()
    await w.find('[data-testid="svc-input"]').setValue('fin-service')
    await w.find('[data-testid="svc-input"]').trigger('change')
    await flushPromises()
    await w.find('[data-testid="save-service"]').trigger('click')
    await flushPromises()
    expect(carryApi.putBindings).toHaveBeenCalledWith('fin-service', expect.anything())
    expect(vi.mocked(toast.success).mock.calls.some((c) => c[0] === '已保存')).toBe(true)
    // 回读:绑定/字段面再拉一次
    expect(carryApi.getServiceFields).toHaveBeenCalledTimes(2)
    w.unmount()
  })
})

describe('CarryConfig — 全局默认', () => {
  async function switchToDefaults(w: ReturnType<typeof mount>) {
    // reka TabsTrigger 在 jsdom 不响应合成 click,keydown Enter 可激活
    await w.findAll('[role="tab"]').find((t) => t.text().includes('全局默认'))!
      .trigger('keydown', { key: 'Enter' })
    await flushPromises()
  }

  it('载入默认行;加一行填值保存 → putDefaults;重复 path 拦截', async () => {
    const w = await mountPage()
    await switchToDefaults(w)
    // 载入的一行
    expect(w.find('[data-testid="defaults-row-0"]').exists()).toBe(true)

    // 加一行 → 填重复 path → 拦截
    await w.find('[data-testid="add-default-row"]').trigger('click')
    await flushPromises()
    const newRow = w.find('[data-testid="defaults-row-1"]')
    await newRow.findAll('input')[0].setValue('$.headers.X-Trace-Id')
    await w.find('[data-testid="save-defaults"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.warning).mock.calls[0][0]).toContain('字段路径重复')
    expect(carryApi.putDefaults).not.toHaveBeenCalled()

    // 改成不同 path → 保存成功
    await newRow.findAll('input')[0].setValue('$.headers.X-New')
    await newRow.findAll('input')[1].setValue('v1')
    await w.find('[data-testid="save-defaults"]').trigger('click')
    await flushPromises()
    expect(carryApi.putDefaults).toHaveBeenCalledWith({
      '$.headers.X-Trace-Id': 'default-trace',
      '$.headers.X-New': 'v1',
    })
    w.unmount()
  })

  it('设 null → 值输入禁用,保存编码 null', async () => {
    const w = await mountPage()
    await switchToDefaults(w)
    await w.find('[data-testid="defaults-row-0"]').findAll('button').find((b) => b.text().includes('设 null'))!.trigger('click')
    await flushPromises()
    const valueInput = w.find('[data-testid="defaults-row-0"]').findAll('input')[1]
    expect((valueInput.element as HTMLInputElement).disabled).toBe(true)

    await w.find('[data-testid="save-defaults"]').trigger('click')
    await flushPromises()
    expect(carryApi.putDefaults).toHaveBeenCalledWith({ '$.headers.X-Trace-Id': null })
    w.unmount()
  })
})
