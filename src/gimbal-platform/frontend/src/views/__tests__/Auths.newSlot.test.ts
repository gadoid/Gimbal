/**
 * Auths.vue — S7.5 导入结果「去绑定」深链:?newSlot=X 直接打开新建表单
 * 并预填 alias/slot(独立文件:需 mock vue-router 的 useRoute)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import * as api from '@/api/auth_sessions'

const routeQuery: Record<string, string> = {}
vi.mock('vue-router', async (orig) => ({
  ...(await orig<typeof import('vue-router')>()),
  useRoute: () => ({ query: routeQuery }),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  for (const k of Object.keys(routeQuery)) delete routeQuery[k]
  vi.spyOn(api, 'list').mockResolvedValue({
    items: [], total: 0, page: 1, pageSize: 50, tokenTypeCounts: {},
  })
})

async function mountPage() {
  const { default: Auths } = await import('@/views/Auths.vue')
  const w = mount(Auths, {
    global: { plugins: [getActivePinia()!] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

describe('Auths ?newSlot 深链(S7.5)', () => {
  it('带 newSlot → 新建表单打开且别名预填(表单无槽字段,取用键=alias)', async () => {
    routeQuery.newSlot = 'maker'
    const w = await mountPage()
    const alias = document.body.querySelector<HTMLInputElement>('[data-testid="f-alias"]')
    expect(alias?.value).toBe('maker')
    // 2026-11-16 四轮:表单不再暴露槽概念(slot 后端缺省 = alias)
    expect(document.body.querySelector('[data-testid="f-slot"]')).toBeNull()
    w.unmount()
  })

  it('无 newSlot → 不自动打开表单', async () => {
    const w = await mountPage()
    expect(document.body.querySelector('[data-testid="f-alias"]')).toBeNull()
    w.unmount()
  })
})
