/**
 * ProjectCredentialsPanel — r5-2.2:编辑态改登录地址必须重录密码。
 * 改 url 不带密码 → 前置拦截不发请求(后端同口径 422);带密码 →
 * 正常 patch。未改 url 的编辑不受影响。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ProjectCredentialsPanel from '@/components/project/ProjectCredentialsPanel.vue'
import * as credApi from '@/api/project_credentials'
import type { AuthSession } from '@/api/auth_sessions'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/errorFallback', () => ({ showError: vi.fn() }))

const CRED = {
  id: 11, slot: 'qa1', alias: 'qa1', isDefault: true,
  system: 'fin', envId: null, token_type: 'Bearer',
  username: 'proj-u', url: 'http://real-auth',
} as unknown as AuthSession

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(credApi, 'listProjectCredentials').mockResolvedValue({
    items: [CRED], canManage: true,
  } as never)
  vi.spyOn(credApi, 'patchProjectCredential').mockResolvedValue(CRED)
})

async function openEdit() {
  const w = mount(ProjectCredentialsPanel, {
    props: { project: { id: 5 } },
    global: { stubs: { teleport: true } },
  })
  await flushPromises()
  await w.findAll('button').find(b => b.text() === '编辑')!.trigger('click')
  return w
}

describe('r5-2.2 · 项目凭证改地址须重录密码', () => {
  it('改 url 未录密码:前置拦截,不发 patch,提示可见', async () => {
    const w = await openEdit()
    expect(w.find('[data-testid="prj-cred-url-hint"]').exists()).toBe(false)
    await w.find('[data-testid="prj-cred-url"]').setValue('https://attacker.example/c')
    expect(w.find('[data-testid="prj-cred-url-hint"]').exists()).toBe(true)
    await w.find('[data-testid="prj-cred-save"]').trigger('click')
    expect(credApi.patchProjectCredential).not.toHaveBeenCalled()
    expect(w.find('.err').text()).toContain('重新录入密码')
    w.unmount()
  })

  it('改 url 并录密码:patch 正常发出', async () => {
    const w = await openEdit()
    await w.find('[data-testid="prj-cred-url"]').setValue('http://new-auth')
    await w.find('[data-testid="prj-cred-password"]').setValue('p2')
    await w.find('[data-testid="prj-cred-save"]').trigger('click')
    await flushPromises()
    expect(credApi.patchProjectCredential).toHaveBeenCalledWith(
      5, 11, expect.objectContaining({ url: 'http://new-auth', password: 'p2' }))
    w.unmount()
  })
})
