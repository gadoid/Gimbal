/**
 * WorkbenchView — /home 占位版(Phase 1)。
 * 承接 TopNav.pool.test F20 的意图迁移:常量池入口对 member/admin 均
 * 可达 —— 落点从顶导航改为工作台卡(F-sitemap:完整页不再占侧栏坑位)。
 */
import { describe, it, expect, beforeEach } from 'vitest'
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

describe('WorkbenchView — /home 占位', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('常量池深链在场(所有角色可达,无 admin 门控)', () => {
    const w = mountPage()
    const link = w.findAll('a.wb-card').find((a) => a.text().includes('常量池'))
    expect(link).toBeTruthy()
    expect(link!.attributes('href')).toBe('/constants')
    w.unmount()
  })

  it('场景库 / 执行历史快捷入口在场', () => {
    const w = mountPage()
    const hrefs = w.findAll('a.wb-card').map((a) => a.attributes('href'))
    expect(hrefs).toContain('/scenarios')
    expect(hrefs).toContain('/executions')
    w.unmount()
  })
})
