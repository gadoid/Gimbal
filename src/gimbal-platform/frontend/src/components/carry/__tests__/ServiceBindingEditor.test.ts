/**
 * ServiceBindingEditor — 绑定键编辑器(配套方案 §2,C2 从 CarryConfig
 * 服务 tab 提取)。核心契约:
 *   - 三态行模型(无行/isNull/值)+ degraded 保存门控 + R1-B1 编码(真源
 *     utils/carry-csv.test / carry-entries.test,此处验视图接线);
 *   - 「来源」列(§2.4):本别名 / 服务级 / 默认值 / 无行 各有显式位置,
 *     继承层经 placeholder 透出有效值;
 *   - 保存只写本键(putBindings(serviceKey)),base/默认层不动。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import * as carryApi from '@/api/carry'
import { toast } from '@/utils/toast'

vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn(),
  getBindingsFor: vi.fn(),
  putBindings: vi.fn(),
  getServiceFields: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const FIELDS = [
  { path: '$.own-val', type: 'string', description: '字段A' },
  { path: '$.own-null', type: 'string', description: '字段B' },
  { path: '$.from-base', type: 'string', description: '字段C' },
  { path: '$.from-default', type: 'string', description: '字段D' },
  { path: '$.from-nowhere', type: 'string', description: '字段E' },
]

function mockLayers(opts?: { degraded?: boolean }) {
  vi.mocked(carryApi.getDefaults).mockResolvedValue({ '$.from-default': 'def-v' })
  vi.mocked(carryApi.getServiceFields).mockResolvedValue({
    fields: FIELDS, degraded: opts?.degraded ?? false,
  })
  vi.mocked(carryApi.putBindings).mockResolvedValue({})
}

function ownBindings(calledWith: string): Record<string, string | null> {
  // 按调用键区分:别名键 → 本键行;base 键 → 服务级行
  if (calledWith === 'fin-service-uat') {
    return { '$.own-val': 'v1', '$.own-null': null }
  }
  return { '$.from-base': 'base-v' }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockLayers()
  vi.mocked(carryApi.getBindingsFor).mockImplementation(
    async (svc: string) => ownBindings(svc))
})

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/carry-config', component: { template: '<div />' } }],
  })
}

async function mountEditor(props?: { serviceKey?: string; baseService?: string | null }) {
  const router = makeRouter()
  const w = mount(ServiceBindingEditor, {
    props: {
      serviceKey: props?.serviceKey ?? 'fin-service-uat',
      baseService: props?.baseService === undefined ? 'fin-service' : props.baseService,
    },
    global: { plugins: [router] },
  })
  await flushPromises()
  return w
}

describe('ServiceBindingEditor — 别名键(三层视图)', () => {
  it('来源列 + placeholder 把三层摊开:本别名/服务级/默认值/无行', async () => {
    const w = await mountEditor()
    expect(w.find('[data-testid="svc-source-$.own-val"]').text()).toBe('本别名')
    expect(w.find('[data-testid="svc-source-$.own-null"]').text()).toBe('本别名')
    expect(w.find('[data-testid="svc-source-$.from-base"]').text()).toBe('服务级')
    // 「默认值」来源 chip 可点跳默认值页(原型对齐后是 button,带 ↗)
    const defChip = w.find('[data-testid="svc-source-$.from-default"]')
    expect(defChip.text()).toContain('默认值')
    expect(defChip.element.tagName).toBe('BUTTON')
    expect(w.find('[data-testid="svc-source-$.from-nowhere"]').text()).toBe('无行')

    const ph = (path: string) =>
      (w.find(`[data-testid="svc-row-${path}"] input`).element as HTMLInputElement).placeholder
    expect(ph('$.from-base')).toContain('base-v')
    expect(ph('$.from-default')).toContain('def-v')
    expect(ph('$.from-nowhere')).toContain('未配置(不注入)')
    // 显式 null 行:值输入禁用
    const nullInput = w.find('[data-testid="svc-row-$.own-null"] input').element as HTMLInputElement
    expect(nullInput.disabled).toBe(true)
    // 原型 H-alias-detail 表底统计:共 N 字段 · 本别名已覆盖 N · 兜底完整度
    const stats = w.find('[data-testid="editor-stats"]').text()
    expect(stats).toContain('共 5 字段')
    expect(stats).toContain('本别名已覆盖 2')
    expect(stats).toContain('链路兜底完整度 4/5')
    w.unmount()
  })

  it('「默认值」chip 点击 → /carry-config?path= 深链', async () => {
    const router = makeRouter()
    const w = mount(ServiceBindingEditor, {
      props: { serviceKey: 'fin-service-uat', baseService: 'fin-service' },
      global: { plugins: [router] },
    })
    await flushPromises()
    await w.find('[data-testid="svc-source-$.from-default"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe(
      `/carry-config?path=${encodeURIComponent('$.from-default')}`)
    w.unmount()
  })

  it('字段面 degraded → 保存禁用(数据安全门控)', async () => {
    mockLayers({ degraded: true })
    const w = await mountEditor()
    expect(w.text()).toContain('字段面部分降级,保存已禁用')
    expect((w.find('[data-testid="save-service"]').element as HTMLButtonElement).disabled).toBe(true)
    w.unmount()
  })

  it('保存只写本键:putBindings(别名键, entries);base/默认层不动', async () => {
    const w = await mountEditor()
    await w.find('[data-testid="save-service"]').trigger('click')
    await flushPromises()
    expect(carryApi.putBindings).toHaveBeenCalledTimes(1)
    const [key] = vi.mocked(carryApi.putBindings).mock.calls[0]
    expect(key).toBe('fin-service-uat')
    expect(vi.mocked(toast.success).mock.calls.some((c) => c[0] === '已保存')).toBe(true)
    w.unmount()
  })
})

describe('ServiceBindingEditor — base 服务键(无服务级层)', () => {
  it('键=base:ownLabel=本服务,不出现「服务级」来源;只拉本键绑定', async () => {
    const w = await mountEditor({ serviceKey: 'fin-service', baseService: 'fin-service' })
    expect(w.text()).toContain('本服务绑定')
    expect(w.text()).not.toContain('服务级')
    // getBindingsFor 只被调一次(本键;无 base 层查询)
    expect(vi.mocked(carryApi.getBindingsFor).mock.calls
      .filter(([k]) => k === 'fin-service')).toHaveLength(1)
    w.unmount()
  })
})
