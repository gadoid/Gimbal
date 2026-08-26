/**
 * TopNav — F20: 「常量池」入口对 member/admin 均可见,指向 /constants。
 * adaptations store 在 admin 下会拉 badge — mock 掉 api(拒绝即静默落 lastError)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import TopNav from '@/components/TopNav.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ path: '/scenarios' }),
    useRouter: () => ({ push: vi.fn() }),
  }
})
vi.mock('@/api/adaptations', () => ({
  catalogDiff: vi.fn().mockRejectedValue(new Error('offline')),
  errMsg: vi.fn(() => '目录服务不可用'),
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountNav(isAdmin: boolean) {
  const auth = useAuthStore()
  auth.currentUser = {
    username: 'alice',
    display_name: 'Alice',
    is_admin: isAdmin,
  } as never
  return mount(TopNav, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('TopNav — 常量池入口(F20)', () => {
  it('member 与 admin 都能看到「常量池」入口,指向 /constants', () => {
    for (const isAdmin of [false, true]) {
      const w = mountNav(isAdmin)
      const link = w.findAll('a.nav-entry').find((a) => a.text().includes('常量池'))
      expect(link, `isAdmin=${isAdmin}`).toBeTruthy()
      expect(link!.attributes('href')).toBe('/constants')
      w.unmount()
    }
  })
})
