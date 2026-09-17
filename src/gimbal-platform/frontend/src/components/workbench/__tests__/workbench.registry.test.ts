/**
 * 工作台 registry(§7)— 首张注册卡 = 常量池摘要卡。
 * 契约:
 * - registry 集中注册,工作台按 registry 渲染 + adminOnly 过滤;
 * - 常量池卡:list 取数喂三行键值,快捷操作 = 复制(生成器 key /
 *   字面量值,与编排面板同款 payload),「管理」深链 /constants;
 * - 空态 = 引导 CTA(不是虚线占位);
 * - 故障隔离:卡片抛渲染异常只落本槽 error 态,工作台其余部分在。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'
import { workbenchRegistry } from '@/components/workbench/registry'
import * as constantsApi from '@/api/constants'
import { copyText } from '@/utils/clipboard'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/constants', () => ({
  list: vi.fn(),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/utils/clipboard', () => ({ copyText: vi.fn().mockResolvedValue(true) }))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const ENTRIES = [
  { id: 1, name: 'bl_no', description: '', entry_kind: 'generator', value: null,
    spec: { kind: 'seq' }, created_at: '', updated_at: '' },
  { id: 2, name: 'bank_id', description: '', entry_kind: 'literal', value: '319', spec: null,
    created_at: '', updated_at: '' },
  { id: 3, name: 'trace', description: '', entry_kind: 'literal', value: 'T1', spec: null,
    created_at: '', updated_at: '' },
  { id: 4, name: 'extra', description: '', entry_kind: 'literal', value: 'X', spec: null,
    created_at: '', updated_at: '' },
]

function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

function mountPage() {
  return mount(WorkbenchView, {
    global: {
      plugins: [getActivePinia()!],
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  useAuthStore().currentUser = { id: 1, username: 'qa', is_admin: false } as never
  vi.mocked(constantsApi.list).mockResolvedValue(ENTRIES as never)
})

afterEach(() => { document.body.innerHTML = '' })

describe('registry 结构(§7 第 2 条)', () => {
  it('首张注册卡 = 常量池;字段契约齐备(id/title/component 懒加载)', () => {
    expect(workbenchRegistry.length).toBeGreaterThanOrEqual(1)
    const first = workbenchRegistry[0]
    expect(first.id).toBe('constants')
    expect(first.title).toBe('常量池')
    expect(first.component).toBeTypeOf('function')
  })
})

describe('常量池摘要卡(§7 落地节奏:首张卡)', () => {
  it('三行键值 + 计数 + 溢出提示 + 管理深链', async () => {
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-constants"]').exists()).toBe(true)
    })
    const card = w.find('[data-testid="wb-card-constants"]')
    expect(card.text()).toContain('4')
    // 三行 = 前 3 条
    expect(card.findAll('.kv-row')).toHaveLength(3)
    expect(card.text()).toContain('bl_no')
    expect(card.text()).toContain('生成器')
    expect(card.text()).toContain('还有 1 条')
    // 管理深链(卡上,非全局快捷区)
    const manage = card.find('.manage-link')
    expect(manage.attributes('href')).toBe('/constants')
    w.unmount()
  })

  it('快捷操作:生成器复制 ${var.name};字面量复制值(编排面板同款 payload)', async () => {
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-constants"]').exists()).toBe(true)
    })
    const rows = w.findAll('.kv-row')
    await rows[0].find('.kv-copy').trigger('click')   // bl_no(generator)
    expect(copyText).toHaveBeenCalledWith('${var.bl_no}')
    await rows[1].find('.kv-copy').trigger('click')   // bank_id(literal)
    expect(copyText).toHaveBeenCalledWith('319')
    expect(vi.mocked(toast.success).mock.calls.some((c) => String(c[0]).includes('bl_no'))).toBe(true)
    w.unmount()
  })

  it('空态 = 引导 CTA(非虚线占位,§7 第 3 条)', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([] as never)
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('.card-empty').exists()).toBe(true)
    })
    const card = w.find('[data-testid="wb-card-constants"]')
    expect(card.find('.cta').attributes('href')).toBe('/constants')
    w.unmount()
  })

  it('list 失败静默回空(不白屏;完整页有重试入口)', async () => {
    vi.mocked(constantsApi.list).mockRejectedValue(new Error('down'))
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('.card-empty').exists()).toBe(true)
    })
    expect(w.find('[data-testid="wb-slot-constants"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-constants-error"]').exists()).toBe(false)
    expect(w.find('.card-empty').exists()).toBe(true)
    w.unmount()
  })
})
