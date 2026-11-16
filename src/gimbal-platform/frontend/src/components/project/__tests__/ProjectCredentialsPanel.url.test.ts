/**
 * ProjectCredentialsPanel — registry 重构:账户实体键编辑态锁定。
 * (system, env, username) 不可改,编辑表单只留密码(留空 = 不改);
 * 改密一处、所有装载条目同时生效(旧 r5-2.2「改地址须重录密码」
 * 随 url 字段退役 —— 地址在环境×系统实例,不在账户上)。
 * 表单进 ui/Dialog(经 Portal 渲染进 body)→ 查询走 body DOMWrapper。
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
  id: 11, system: 'fin-service', envId: 1, isDefault: true,
  token_type: 'Bearer', username: 'proj-u', loginUrl: 'http://real-auth',
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

describe('registry · 项目账户编辑态:实体键锁定,只改密码', () => {
  it('实体键(system/env/username)禁改;无 url 字段(地址归实例)', async () => {
    const w = await openEdit()
    const sys = q('[data-testid="prj-cred-system"]')!.element as HTMLInputElement
    expect((sys as HTMLInputElement).disabled).toBe(true)
    expect((q('[data-testid="prj-cred-username"]')!.element as HTMLInputElement).disabled).toBe(true)
    expect(q('[data-testid="prj-cred-url"]')).toBeNull()   // url 字段已退役
    w.unmount()
  })

  it('密码留空 → 无改动:不发 patch,表单直接关闭', async () => {
    const w = await openEdit()
    await q('[data-testid="prj-cred-save"]')!.trigger('click')
    await flushPromises()
    expect(credApi.patchProjectCredential).not.toHaveBeenCalled()
    expect(q('[data-testid="prj-cred-save"]')).toBeNull()   // Dialog 已关
    w.unmount()
  })

  it('录密码 → patch 只带 password(一处改密,装载条目同时生效)', async () => {
    const w = await openEdit()
    await q('[data-testid="prj-cred-password"]')!.setValue('p2x3y4z')
    await q('[data-testid="prj-cred-save"]')!.trigger('click')
    await flushPromises()
    expect(credApi.patchProjectCredential).toHaveBeenCalledWith(
      5, 11, { password: 'p2x3y4z' })
    w.unmount()
  })

  it('短密码(<6)前置拦截:不发 patch,提示可见', async () => {
    const w = await openEdit()
    await q('[data-testid="prj-cred-password"]')!.setValue('p1')
    await q('[data-testid="prj-cred-save"]')!.trigger('click')
    expect(credApi.patchProjectCredential).not.toHaveBeenCalled()
    expect(q('.err')!.text()).toContain('至少 6 位')
    w.unmount()
  })
})
