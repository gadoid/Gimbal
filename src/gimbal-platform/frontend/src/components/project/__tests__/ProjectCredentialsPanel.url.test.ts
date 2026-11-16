/**
 * ProjectCredentialsPanel — r5-2.2:编辑态改登录地址必须重录密码。
 * 改 url 不带密码 → 前置拦截不发请求(后端同口径 422);带密码 →
 * 正常 patch。未改 url 的编辑不受影响。
 * 2026-11-16 重塑后:编辑入口收进 ⋯ 菜单、表单进 ui/Dialog(经 Portal
 * 渲染进 body)→ 查询走 body DOMWrapper(与 Auths.test.ts 同惯例)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount, DOMWrapper } from '@vue/test-utils'
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

/** body 查询(Portal 落点);找不到返回 null(配合 toBeNull 断言) */
function q(sel: string): DOMWrapper<Element> | null {
  const el = document.body.querySelector(sel)
  return el ? new DOMWrapper(el) : null
}

beforeEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.spyOn(credApi, 'listProjectCredentials').mockResolvedValue({
    items: [CRED], canManage: true,
  } as never)
  vi.spyOn(credApi, 'patchProjectCredential').mockResolvedValue(CRED)
  // 环境名拉取(listEnvironments)未 mock → 真实请求拒绝,面板静默回落 #id
})

async function openEdit() {
  const w = mount(ProjectCredentialsPanel, {
    props: { project: { id: 5 } },
    attachTo: document.body,
  })
  await flushPromises()
  // 编辑入口在 ⋯ 菜单(reka Portal → body)
  await w.find('[data-testid="prj-cred-more-11"]').trigger('click')
  await flushPromises()
  await q('[data-testid="prj-cred-edit-11"]')!.trigger('click')
  await flushPromises()
  return w
}

describe('r5-2.2 · 项目凭证改地址须重录密码', () => {
  it('改 url 未录密码:前置拦截,不发 patch,提示可见', async () => {
    const w = await openEdit()
    expect(q('[data-testid="prj-cred-url-hint"]')).toBeNull()
    await q('[data-testid="prj-cred-url"]')!.setValue('https://attacker.example/c')
    expect(q('[data-testid="prj-cred-url-hint"]')).not.toBeNull()
    await q('[data-testid="prj-cred-save"]')!.trigger('click')
    expect(credApi.patchProjectCredential).not.toHaveBeenCalled()
    expect(q('.err')!.text()).toContain('重新录入密码')
    w.unmount()
  })

  it('改 url 并录密码:patch 正常发出', async () => {
    const w = await openEdit()
    await q('[data-testid="prj-cred-url"]')!.setValue('http://new-auth')
    await q('[data-testid="prj-cred-password"]')!.setValue('p2x3y4z')
    await q('[data-testid="prj-cred-save"]')!.trigger('click')
    await flushPromises()
    expect(credApi.patchProjectCredential).toHaveBeenCalledWith(
      5, 11, expect.objectContaining({ url: 'http://new-auth', password: 'p2x3y4z' }))
    w.unmount()
  })
})
