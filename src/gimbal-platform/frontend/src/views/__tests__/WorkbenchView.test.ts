/**
 * WorkbenchView — /home(registry 宿主)。
 * 承接 TopNav.pool.test F20 的意图迁移:常量池入口对 member/admin 均
 * 可达 —— 落点从顶导航改为工作台卡(F-sitemap:完整页不再占侧栏坑位)。
 * 「快捷入口」固定区已整块撤除:每个去处都由自己的 registry 卡承载、卡头
 * 深链即入口,在可组装区底下再垫一排不可配置的链接只是多长出一层死角。
 * 这里钉两件事:区不在了,以及撤完没把任何去处变成死路。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'

vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
// 右栏时间线会读场景与适配批次 —— 不 mock 就打真网络,用例慢且不稳
vi.mock('@/api/adaptations', () => ({ listBatches: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/scenario-composer', () => ({ listScenarios: vi.fn().mockResolvedValue([]) }))
// 新增的 registry 卡(认证管理 / 服务画像)同样不能打真网络
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceRows: vi.fn().mockResolvedValue([]),
  loadCatalogEntries: vi.fn().mockResolvedValue([]),
}))

function mountPage() {
  return mount(WorkbenchView, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('WorkbenchView — /home(registry 宿主)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('快捷入口固定区已撤:标题不在、链接卡不在,主区只剩卡片网格', async () => {
    const w = mountPage()
    // 卡体是异步组件,先等它们落地再断言"没有别的东西"
    await vi.waitFor(() => expect(w.findAll('[data-testid^="wb-slot-"]').length).toBeGreaterThan(0))
    expect(w.findAll('h2').some((h) => h.text().includes('快捷入口'))).toBe(false)
    expect(w.find('.wb-card').exists()).toBe(false)
    expect(w.findAll('.wb-main > *')).toHaveLength(1)
    // 常量池同样不再重复一份链接卡(registry 卡内「管理」深链承担)
    expect(w.findAll('a').map((a) => a.text())).not.toContain('进入常量池 →')
    w.unmount()
  })

  it('撤区后执行历史仍有路可达 ——「最近执行」卡卡头深链', async () => {
    const w = mountPage()
    await vi.waitFor(() => expect(w.find('[data-testid="wb-card-recent-executions"]').exists()).toBe(true))
    expect(w.find('[data-testid="wb-card-recent-executions"] .manage-link').attributes('href'))
      .toBe('/executions')
    w.unmount()
  })
})
