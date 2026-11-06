/** TokensSection — 平台令牌「签发人」列(评审 2026-11-05 P2;原型
 * Tokens--platform 第二列):variant=platform 显示 created_by 签发人,
 * 缺省(签发人已删)显「—」;个人令牌视图不出该列。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TokensSection from '@/components/profile/TokensSection.vue'
import * as api from '@/api/access-tokens'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const platformRow: api.AccessTokenListItem = {
  id: 1, kind: 'platform', name: 'nightly-recon', tokenHint: '2f7a…d301',
  status: 'active', invalidatedReason: null, invalidationNote: null,
  expiresAt: null, invalidatedAt: null, revokedAt: null,
  lastUsedAt: null, createdAt: '2026-11-01T00:00:00Z',
  callbackUrl: null, callbackSecretSet: false, signingKeyUsable: null,
  scopeCounts: { aliases: 2, auths: 1 },
  taskCounts: { total: 1, unsatisfied: 0 },
  issuerName: '王同学',
}

async function mountVariant(variant: 'personal' | 'platform' | 'admin') {
  const errors: unknown[] = []
  const w = mount(TokensSection, {
    global: {
      plugins: [createPinia()],
      config: { errorHandler: (e) => { errors.push(e) } },
    },
    props: { variant },
  })
  await flushPromises()
  return Object.assign(w, { errors })
}

describe('TokensSection — 平台令牌签发人列', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'listAccessTokens').mockResolvedValue({
      items: [platformRow], quota: { used: 1, limit: 5 },
    } as never)
    vi.spyOn(api, 'getScopeCandidates').mockResolvedValue({
      aliases: [], auths: [],
    } as never)
  })

  it('platform 视图:名称后一列「签发人」,取 issuerName', async () => {
    const w = await mountVariant('platform')
    expect(w.find('[data-testid="token-list"]').text()).toContain('签发人')
    const row = w.find('[data-testid="token-list"] tbody tr')
    // 名称单元格后第一格 = 签发人
    expect(row.findAll('td')[1]!.text()).toBe('王同学')
    w.unmount()
  })

  it('签发人已删(issuerName 缺省)显「—」', async () => {
    vi.spyOn(api, 'listAccessTokens').mockResolvedValue({
      items: [{ ...platformRow, issuerName: undefined }],
      quota: { used: 1, limit: 5 },
    } as never)
    const w = await mountVariant('platform')
    const row = w.find('[data-testid="token-list"] tbody tr')
    expect(row.findAll('td')[1]!.text()).toBe('—')
    w.unmount()
  })

  it('personal 视图不出签发人列(签发人 = 属主,不重复)', async () => {
    vi.spyOn(api, 'listAccessTokens').mockResolvedValue({
      items: [{ ...platformRow, kind: 'personal' }],
      quota: { used: 1, limit: 5 },
    } as never)
    const w = await mountVariant('personal')
    expect(w.find('[data-testid="token-list"]').text()).not.toContain('签发人')
    w.unmount()
  })
})

/** admin 视图(2026-11-05 修复轮评审 N1):「全部」曾用空串 value,
 * reka-ui SelectItem 挂载即抛错;改哨兵 'all' 后挂载干净,且 'all'
 * 映射为 kind 不收窄 / status 不传。 */
describe('TokensSection — admin 视图筛选', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'listAccessTokens').mockResolvedValue({
      items: [{ ...platformRow, kind: 'personal', ownerId: 7, ownerName: 'alice' }],
      quota: { used: 1, limit: 5 },
    } as never)
  })

  it('挂载不抛错,首屏按个人令牌 + 不带状态筛选取数', async () => {
    const w = await mountVariant('admin')
    expect(w.errors).toEqual([])
    expect(w.find('[data-testid="token-list"]').text()).toContain('alice')
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('personal', expect.objectContaining({
      all: true, status: undefined,
    }))
    w.unmount()
  })

  it('类型/状态选「全部」→ listKind=all、status 不传;选具体状态则透传', async () => {
    const w = await mountVariant('admin')
    const vm = w.vm as unknown as { adminKind: string; adminStatus: string }
    vm.adminKind = 'all'
    await flushPromises()
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('all', expect.objectContaining({
      status: undefined,
    }))
    vm.adminStatus = 'revoked'
    await flushPromises()
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('all', expect.objectContaining({
      status: 'revoked',
    }))
    vm.adminStatus = 'all'
    await flushPromises()
    expect(api.listAccessTokens).toHaveBeenLastCalledWith('all', expect.objectContaining({
      status: undefined,
    }))
    expect(w.errors).toEqual([])
    w.unmount()
  })
})
