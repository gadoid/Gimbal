/**
 * CarryConfig — 默认值页(配套方案 §2.2,C2 拆分后只剩兜底层)。
 * 服务/别名绑定层的测试已迁 ServiceBindingEditor.test(键详情页内嵌)。
 * 核心契约:载入默认行、加行保存 → putDefaults、重复 path 拦截(R1-M2)、
 * 设 null 编码、?path= 深链高亮(键详情「默认值」来源 chip 的落点)。
 * CSV 解析/合并真源在 utils/carry-csv.test。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import CarryConfig from '@/views/CarryConfig.vue'
import * as carryApi from '@/api/carry'
import { toast } from '@/utils/toast'

vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn(),
  putDefaults: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

async function mountPage(query = ''): Promise<{ w: ReturnType<typeof mount>; router: Router }> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/carry-config', component: CarryConfig }],
  })
  await router.push(`/carry-config${query}`)
  await router.isReady()
  // 每页行数偏好(usePagerSize → useUserPreference → useAuthStore)需要 pinia
  const w = mount(CarryConfig, {
    attachTo: document.body,
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.mocked(carryApi.getDefaults).mockResolvedValue({
    '$.headers.X-Trace-Id': 'default-trace',
    '$.fee': '0.5',
  })
  vi.mocked(carryApi.putDefaults).mockResolvedValue({})
})

describe('CarryConfig — 默认值(兜底层)', () => {
  it('载入默认行;加一行填值保存 → putDefaults;重复 path 拦截', async () => {
    const { w } = await mountPage()
    // 载入的行
    expect(w.find('[data-testid="defaults-row-0"]').exists()).toBe(true)

    // 加一行 → 填重复 path → 拦截
    await w.find('[data-testid="add-default-row"]').trigger('click')
    await flushPromises()
    const newRow = w.find('[data-testid="defaults-row-2"]')
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
      '$.fee': '0.5',
      '$.headers.X-New': 'v1',
    })
    w.unmount()
  })

  it('设 null → 值输入禁用,保存编码 null', async () => {
    const { w } = await mountPage()
    await w.find('[data-testid="defaults-row-0"]').findAll('button').find((b) => b.text().includes('设 null'))!.trigger('click')
    await flushPromises()
    const valueInput = w.find('[data-testid="defaults-row-0"]').findAll('input')[1]
    expect((valueInput.element as HTMLInputElement).disabled).toBe(true)

    await w.find('[data-testid="save-defaults"]').trigger('click')
    await flushPromises()
    expect(carryApi.putDefaults).toHaveBeenCalledWith({
      '$.headers.X-Trace-Id': null,
      '$.fee': '0.5',
    })
    w.unmount()
  })

  it('拆分后不再有服务绑定选择器与保存(已迁键详情)', async () => {
    const { w } = await mountPage()
    expect(w.find('[data-testid="svc-input"]').exists()).toBe(false)
    expect(w.find('[data-testid="save-service"]').exists()).toBe(false)
    // 面板头「全局默认」与页题重复已撤;留下的身份标识是 warn 横幅
    expect(w.text()).not.toContain('全局默认')
    expect(w.text()).toContain('按纯 path 跨服务生效')
    w.unmount()
  })

  it('?path= 深链:命中行高亮(配套方案附录5 的落点)', async () => {
    const { w } = await mountPage(`?path=${encodeURIComponent('$.fee')}`)
    const hit = w.find('[data-path="$.fee"]')
    expect(hit.exists()).toBe(true)
    expect(hit.classes()).toContain('path-hit')
    // 非命中行不高亮
    expect(w.find('[data-path="$.headers.X-Trace-Id"]').classes()).not.toContain('path-hit')
    w.unmount()
  })
})
