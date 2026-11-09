/**
 * ProjectTokensPanel / ProjectMembersPanel —— authz M2b。
 * Q2 项目令牌:列表(负责人 / 失格提示)、签发(范围 = 别名 + 项目凭证,
 * 负责人缺省本人)、待确认负责人本人见「确认接任」。
 * Q1 项目用户:成员角色下拉含「项目用户」,改角色下发 role='user'。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProjectTokensPanel from '@/components/project/ProjectTokensPanel.vue'
import ProjectMembersPanel from '@/components/project/ProjectMembersPanel.vue'
import * as tokApi from '@/api/project_tokens'
import * as projectsApi from '@/api/projects'
import * as handoffApi from '@/api/handoff'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const TOKEN = {
  id: 11, kind: 'project', name: 'ci', tokenHint: 'ab12…9f3c', status: 'active',
  invalidatedReason: null, invalidationNote: null, expiresAt: '2027-01-01T00:00:00Z',
  invalidatedAt: null, revokedAt: null, lastUsedAt: null, createdAt: null,
  callbackUrl: null, callbackSecretSet: false, signingKeyUsable: null,
  scopeCounts: { aliases: 1, auths: 1 }, taskCounts: { total: 0, unsatisfied: 0 },
  projectId: 3, holderId: 1, holderName: 'A', holderPendingId: 2,
  holderPendingName: 'B', holderValid: false, holderProblem: '令牌负责人已不是项目管理员,待换绑负责人',
}

const MEMBERS = [
  { userId: 1, username: 'a', displayName: 'A', role: 'admin' },
  { userId: 2, username: 'b', displayName: 'B', role: 'admin' },
  { userId: 3, username: 'c', displayName: 'C', role: 'member' },
]

function login(id: number) {
  const auth = useAuthStore()
  auth.currentUser = { id, username: `u${id}`, display_name: `U${id}`, role: 'user' } as never
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(tokApi, 'listProjectTokens').mockResolvedValue({
    items: [TOKEN], quota: { used: 1, limit: 5 },
  } as never)
  vi.spyOn(tokApi, 'getProjectScopeCandidates').mockResolvedValue({
    aliases: ['fin-a'], auths: [{ id: 21, alias: 'qa1', slot: 'qa1' }],
  })
  vi.spyOn(projectsApi, 'listMembers').mockResolvedValue(MEMBERS as never)
})

describe('Q2 项目令牌面板', () => {
  it('列表显示负责人 / 待确认 / 失格提示;待确认本人可接任', async () => {
    login(2)
    const accept = vi.spyOn(tokApi, 'acceptProjectTokenHolder')
      .mockResolvedValue({ id: 11, holderId: 2, holderPendingId: null })
    const w = mount(ProjectTokensPanel, { props: { project: { id: 3 }, canManage: true } })
    await flushPromises()
    const card = w.find('[data-testid="prj-tok-11"]')
    expect(card.text()).toContain('负责人 A')
    expect(card.text()).toContain('待 B 确认接任')
    expect(w.find('[data-testid="prj-tok-holder-invalid"]').exists()).toBe(true)
    await w.find('[data-testid="prj-tok-accept"]').trigger('click')
    await flushPromises()
    expect(accept).toHaveBeenCalledWith(3, 11)
  })

  it('签发:负责人缺省本人,范围 = 勾选的别名 + 项目凭证', async () => {
    login(1)
    const create = vi.spyOn(tokApi, 'createProjectToken')
      .mockResolvedValue({ id: 12, token: 'gtk_xyz', callbackSecret: null })
    const w = mount(ProjectTokensPanel, {
      props: { project: { id: 3 }, canManage: true },
      global: { stubs: { TokenSecretDialog: true } },
    })
    await flushPromises()
    expect(w.find('[data-testid="prj-tok-accept"]').exists()).toBe(false)
    await w.find('[data-testid="prj-tok-add"]').trigger('click')
    await flushPromises()
    const form = w.find('[data-testid="prj-tok-form"]')
    expect((form.find('[data-testid="prj-tok-holder"]').element as HTMLSelectElement).value).toBe('1')
    await form.find('[data-testid="prj-tok-name"]').setValue('deploy')
    const boxes = form.findAll('input[type="checkbox"]')
    for (const b of boxes) await b.setValue(true)
    await form.find('[data-testid="prj-tok-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith(3, expect.objectContaining({
      name: 'deploy', holderId: 1,
      scope: { aliases: ['fin-a'], authIds: [21] },
    }))
  })
})

describe('Q1 成员角色:项目用户', () => {
  it('角色下拉含项目用户,改角色下发 user', async () => {
    vi.spyOn(handoffApi, 'getRoster').mockResolvedValue([] as never)
    const patch = vi.spyOn(projectsApi, 'patchMember')
      .mockResolvedValue({ ...MEMBERS[2], role: 'user' } as never)
    const w = mount(ProjectMembersPanel, {
      props: { project: { id: 3, name: 'P', kind: 'normal', description: '', memberCount: 3, myRole: 'admin' } },
    })
    await flushPromises()
    const sel = w.find('[data-testid="prj-role-3"]')
    expect(sel.findAll('option').map((o) => o.text())).toContain('项目用户')
    await sel.setValue('user')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith(3, 3, 'user')
  })
})
