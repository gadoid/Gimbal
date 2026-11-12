/** TokensSection — admin 变体(定属主模式,用户管理 → 该用户的访问
 * 令牌子页):ownerId 钉死取数 ?all=1&owner=,kind 恒 personal(原
 * kind/属主筛选已随全局平铺视图退役);仅状态筛选;无创建入口;
 * 缺 ownerId 防呆不发请求。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TokensSection from '@/components/profile/TokensSection.vue'
import * as api from '@/api/access-tokens'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const baseRow: api.AccessTokenListItem = {
  id: 1, kind: 'personal', name: 'nightly-recon', tokenHint: '2f7a…d301',
  status: 'active', invalidatedReason: null, invalidationNote: null,
  expiresAt: null, invalidatedAt: null, revokedAt: null,
  lastUsedAt: null, createdAt: '2026-11-01T00:00:00Z',
  callbackUrl: null, callbackSecretSet: false, signingKeyUsable: null,
  scopeCounts: { aliases: 2, auths: 1 },
  taskCounts: { total: 1, unsatisfied: 0 },
  issuerName: '王同学',
}

async function mountVariant(props: Record<string, unknown>) {
  const errors: unknown[] = []
  const w = mount(TokensSection, {
    global: {
      plugins: [createPinia()],
      config: { errorHandler: (e) => { errors.push(e) } },
    },
    props,
  })
  await flushPromises()
  return Object.assign(w, { errors })
}


describe('TokensSection — admin 定属主视图', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'listAccessTokens').mockResolvedValue({
      items: [{ ...baseRow, ownerId: 7, ownerName: 'alice' }],
      quota: { used: 1, limit: 5 },
    } as never)
  })

  it('首屏按 personal + all=1&owner= 取数;标题/配额带属主口径,无属主列与创建钮', async () => {
    const w = await mountVariant({ variant: 'admin', ownerId: 7, ownerName: 'alice' })
    expect(w.errors).toEqual([])
    expect(api.listAccessTokens).toHaveBeenCalledTimes(1)
    expect(api.listAccessTokens).toHaveBeenCalledWith('personal', {
      all: true, owner: 7, status: undefined,
    })
    const text = w.find('[data-testid="tokens-section"]').text()
    expect(text).toContain('alice 的访问令牌')
    expect(text).toContain('该用户已用 1 · 上限 5')
    expect(text).not.toContain('属主')
    expect(w.find('[data-testid="token-create-toggle"]').exists()).toBe(false)
    w.unmount()
  })

  it('状态筛选透传;「全部」不传 status', async () => {
    const w = await mountVariant({ variant: 'admin', ownerId: 7 })
    const vm = w.vm as unknown as { adminStatus: string }
    vm.adminStatus = 'revoked'
    await flushPromises()
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('personal', expect.objectContaining({
      owner: 7, status: 'revoked',
    }))
    vm.adminStatus = 'all'
    await flushPromises()
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('personal', expect.objectContaining({
      status: undefined,
    }))
    expect(w.errors).toEqual([])
    w.unmount()
  })

  it('缺 ownerId 防呆:不发请求(不退化为全平台平铺)', async () => {
    const w = await mountVariant({ variant: 'admin' })
    expect(w.errors).toEqual([])
    expect(api.listAccessTokens).not.toHaveBeenCalled()
    w.unmount()
  })
})
