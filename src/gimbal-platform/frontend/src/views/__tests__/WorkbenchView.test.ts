/**
 * WorkbenchView — /home 占位版(Phase 1)。
 * 承接 TopNav.pool.test F20 的意图迁移:常量池入口对 member/admin 均
 * 可达 —— 落点从顶导航改为工作台卡(F-sitemap:完整页不再占侧栏坑位)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'

function mountPage() {
  return mount(WorkbenchView, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))

describe('WorkbenchView — /home(registry 宿主)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('常量池入口由 registry 卡承载(所有角色可达,见 workbench.registry.test)', () => {
    const w = mountPage()
    // 快捷区不再重复常量池(卡内"管理"深链承担);registry 槽在场
    expect(w.findAll('a.wb-card').some((a) => a.text().includes('常量池'))).toBe(false)
    w.unmount()
  })

  it('场景库快捷入口已清理(三页各有 registry 卡);执行历史仍在', () => {
    const w = mountPage()
    const hrefs = w.findAll('a.wb-card').map((a) => a.attributes('href'))
    // 场景库不再占固定快捷位:我的/公共/关注各自有卡,卡头深链即入口
    expect(hrefs).not.toContain('/scenarios')
    expect(hrefs).not.toContain('/scenarios/mine')
    expect(hrefs).toContain('/executions')
    w.unmount()
  })
})
