/**
 * Auths.vue — 深链预填(独立文件:需 mock vue-router 的 useRoute)。
 * registry 重构:?system=X 直接打开新建表单并预填系统(实体键);
 * 旧 ?newSlot=X(槽概念退役)兼容收敛到 system 预填位。
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

describe('Auths ?system 深链(分层③)', () => {
  it('带 system → 新建表单打开且系统预填(实体键,账户无槽概念)', async () => {
    routeQuery.system = 'fin-service'
    const w = await mountPage()
    const sys = document.body.querySelector<HTMLInputElement>('[data-testid="f-system"]')
    expect(sys?.value).toBe('fin-service')
    w.unmount()
  })

  it('旧 ?newSlot= 兼容收敛到 system 预填位', async () => {
    routeQuery.newSlot = 'maker'
    const w = await mountPage()
    const sys = document.body.querySelector<HTMLInputElement>('[data-testid="f-system"]')
    expect(sys?.value).toBe('maker')
    w.unmount()
  })

  it('无深链参数 → 不自动打开表单', async () => {
    const w = await mountPage()
    expect(document.body.querySelector('[data-testid="f-system"]')).toBeNull()
    w.unmount()
  })
})
