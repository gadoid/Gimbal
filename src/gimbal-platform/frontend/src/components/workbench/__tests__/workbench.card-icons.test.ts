/**
 * 卡头图标对齐 —— 每张工作台卡左侧那颗,必须就是它指向的功能页上那颗。
 * 形状此前在 12 张卡里各画一遍,已经漂过:服务画像画成太阳、最近执行与
 * 适配中心共用同一颗脉冲、认证管理的锁比页头矮一档。现在两侧都走
 * SlibIcon,这里钉两件事:
 * - 卡片头部图标由 SlibIcon 提供,名字逐张对着功能页钉死;
 * - PageHead 把自己那颗也交给同一个 SlibIcon —— 页头与卡头同源,不存在
 *   "页头改了卡头没跟着改"。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SlibIcon, { type SlibIconName } from '@/components/scenario-lib/SlibIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { workbenchRegistry, type WorkbenchCardDef } from '../registry'

vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/api/scenario-composer', () => ({ listScenarios: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/adaptations', () => ({
  listBatches: vi.fn().mockResolvedValue([]),
  catalogDiff: vi.fn().mockResolvedValue({ pending: [], anomalies: [] }),
  errMsg: (_e: unknown, d: string) => d,
}))
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/service-aliases', () => ({ listAliases: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/carry', () => ({ getDefaults: vi.fn().mockResolvedValue({}) }))
vi.mock('@/api/users', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceRows: vi.fn().mockResolvedValue([]),
  loadCatalogEntries: vi.fn().mockResolvedValue([]),
}))

/**
 * 卡片 → 功能页那颗图标。有页头的八张取页头值(见各 views 的 <PageHead icon>);
 * 执行记录 / 执行器 / 用户管理三页页面上没有图标,全站唯一一颗在侧边栏,
 * 就是 @radix-icons 那个组件本身;常量池既无页头也无侧栏条目,自留 database。
 */
const CARD_ICON: Record<string, SlibIconName> = {
  constants: 'database',
  'recent-executions': 'history',
  'my-scenarios': 'folder',
  'public-scenarios': 'globe',
  'starred-scenarios': 'star',
  services: 'grid',
  auths: 'lock',
  adaptations: 'activity',
  runner: 'play',
  'service-aliases': 'layers',
  carry: 'sliders',
  users: 'gear',
}

afterEach(() => { document.body.innerHTML = '' })

describe('工作台卡头图标 = 功能页那颗', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useAuthStore().currentUser = { id: 1, username: 'admin', display_name: 'A', is_admin: true } as never
  })

  it('注册表每张卡都在映射里(新增卡必须同时交代图标来源)', () => {
    expect(workbenchRegistry.map((d) => d.id).sort()).toEqual(Object.keys(CARD_ICON).sort())
  })

  it('12 张卡的卡头图标全部由 SlibIcon 渲染,名字逐张钉死', async () => {
    const w = mount(WorkbenchView, {
      global: {
        plugins: [getActivePinia()!],
        stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
      },
      attachTo: document.body,
    })
    for (const def of workbenchRegistry) {
      await expectCardIcon(w, def, CARD_ICON[def.id])
    }
    w.unmount()
  })
})

describe('PageHead 与卡头同源', () => {
  it('页头那颗交给同一个 SlibIcon(名字透传,不再自己画一遍)', () => {
    const w = mount(PageHead, { props: { icon: 'grid', title: '服务画像' } })
    const icon = w.find('.icon-badge').findComponent(SlibIcon)
    expect(icon.exists()).toBe(true)
    expect(icon.props('name')).toBe('grid')
    w.unmount()
  })
})

/** 等这张卡的异步组件落地,再核对它卡头那颗图标的来源与形状。 */
async function expectCardIcon(
  w: ReturnType<typeof mount>,
  def: WorkbenchCardDef,
  expected: SlibIconName,
) {
  const card = `[data-testid="wb-card-${def.id}"]`
  await vi.waitFor(() => {
    expect(w.find(card).exists()).toBe(true)
  })
  await flushPromises()
  const badge = w.find(`${card} .chead-icon`)
  expect(badge.exists(), `${def.id} 卡头图标底座`).toBe(true)
  const icon = badge.findComponent(SlibIcon)
  expect(icon.exists(), `${def.id} 卡头图标必须由 SlibIcon 提供(手绘一份就会和页头漂)`).toBe(true)
  expect(icon.props('name')).toBe(expected)
  expect(icon.props('size')).toBe(14)
}
