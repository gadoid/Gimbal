/**
 * UsersCard.vue — 实例 → 调用身份 → 凭证映射(紧凑行;2026-11-21 交互轮)。
 *
 * 一行 = 一个实例:[实例名+「+」] [身份下拉] [凭证下拉] [×]。
 * 覆盖:身份/凭证下拉按实例 system 过滤、Admin 选中凭证即 PATCH、
 * 非 Admin 选中凭证 → 新建身份草稿、Admin 新建身份、新建凭证、
 * 待保存草稿、× 移出范围、遗留明文清除。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import UsersCard from '@/components/composer/UsersCard.vue'
import {
  list as listAuths, create as createAuth,
} from '@/api/auth_sessions'
import { listEnvironments } from '@/api/environments'
import { createAlias, patchAlias } from '@/api/service-aliases'
import { confirmAction } from '@/utils/confirmAction'
import { useAuthStore } from '@/stores/auth'
import type { AuthDraftView } from '@/types/scenario-composer'

vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(),
  create: vi.fn(),
}))
vi.mock('@/api/environments', () => ({ listEnvironments: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({
  createAlias: vi.fn(),
  patchAlias: vi.fn(),
}))
vi.mock('@/utils/confirmAction', () => ({ confirmAction: vi.fn() }))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const ACCOUNTS = [
  { id: 1, source: 'personal', system: 'fin', envId: 1, username: 'qa1',
    token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
    password_masked: '***', isDefault: true },
  { id: 2, source: 'personal', system: 'fin', envId: 1, username: 'qa2',
    token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
    password_masked: '***', isDefault: false },
  { id: 3, source: 'project', system: 'fin', envId: 2, username: 'qa3',
    token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
    password_masked: '***', isDefault: false },
  { id: 4, source: 'personal', system: 'logi', envId: 2, username: 'u1',
    token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
    password_masked: '***', isDefault: false },
]

const INSTANCES = [
  {
    service: 'fin', system: 'fin', groupId: 'g-fin',
    envId: 1, envName: 'dev', tags: ['dev'], envIds: [1],
    baseUrl: 'https://fin-dev', loginUrl: '', line: '',
    identities: [
      { aliasName: 'fin-qa', refMode: 'username', refUsername: 'qa1',
        display: 'QA', envId: 1, envName: 'dev' },
      { aliasName: 'fin-default', refMode: 'default', refUsername: '',
        display: '', envId: 1, envName: 'dev' },
    ],
  },
  {
    service: 'logi', system: 'logi', groupId: 'g-logi',
    envId: 2, envName: 'test', tags: ['test'], envIds: [2],
    baseUrl: 'https://logi-test', loginUrl: '', line: '',
    identities: [],
  },
]

let activePinia: ReturnType<typeof createPinia>
const flush = () => new Promise((r) => setTimeout(r, 0))
const q = (sel: string) => document.querySelector(sel) as HTMLElement | null

function setCapabilities(caps: string[]) {
  useAuthStore().capabilities = caps
}

function mountCard(opts: {
  instances?: any[]
  drafts?: AuthDraftView[]
  caps?: string[]
  legacy?: Record<string, any>
} = {}) {
  setCapabilities(opts.caps ?? ['ops.write'])
  const drafts = ref<AuthDraftView[]>(opts.drafts ?? [])
  const model = ref<Record<string, any>>(opts.legacy ?? {})
  const Parent = defineComponent({
    setup() {
      return () => h(UsersCard, {
        modelValue: model.value,
        authDrafts: drafts.value,
        projectId: null,
        scopedInstances: opts.instances ?? INSTANCES,
        'onUpdate:modelValue': (v: Record<string, any>) => { model.value = v },
        'onUpdate:authDrafts': (v: AuthDraftView[]) => { drafts.value = v },
      })
    },
  })
  const w = mount(Parent, {
    global: { plugins: [activePinia] },
    attachTo: document.body,
  })
  return { w, drafts, model }
}

const FIN_ROW = 'fin:g-fin'
const LOGI_ROW = 'logi:g-logi'

beforeEach(() => {
  vi.clearAllMocks()
  activePinia = createPinia()
  setActivePinia(activePinia)
  vi.mocked(listAuths).mockResolvedValue({
    items: ACCOUNTS, total: ACCOUNTS.length, page: 1, pageSize: 200,
    tokenTypeCounts: {},
  } as any)
  vi.mocked(listEnvironments).mockResolvedValue([
    { id: 1, name: 'dev', description: '', lines: {},
      owner_id: null, is_default: true },
    { id: 2, name: 'test', description: '', lines: {},
      owner_id: null, is_default: false },
  ] as any)
  vi.mocked(confirmAction).mockResolvedValue(true)
  vi.mocked(patchAlias).mockResolvedValue({} as any)
  vi.mocked(createAlias).mockResolvedValue({} as any)
  vi.mocked(createAuth).mockResolvedValue({
    id: 5, source: 'personal', system: 'fin', envId: 1, username: 'new1',
    token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
    password_masked: '***', isDefault: false,
  } as any)
})

describe('UsersCard — 实例 → 身份 → 凭证映射(紧凑行)', () => {
  it('一行 = 一个实例;身份/凭证下拉按实例 system 过滤', async () => {
    const { w } = mountCard()
    await flush()
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-0"]`).exists()).toBe(true)
    expect(w.find(`[data-testid="uc-row-${LOGI_ROW}-0"]`).exists()).toBe(true)

    const idSel = w.find(`[data-testid="uc-id-select-${FIN_ROW}-0"]`)
    const idVals = idSel.findAll('option').map((o) => o.attributes('value'))
    expect(idVals).toEqual(['fin-qa', 'fin-default', '__new__'])
    // 默认选第一身份;凭证下拉值 = 映射账户 qa1(id=1)
    const credSel = w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`)
    expect((credSel.element as HTMLSelectElement).value).toBe('1')
    const credVals = credSel.findAll('option').map((o) => o.attributes('value'))
    expect(credVals).toContain('2')
    expect(credVals).toContain('3')       // 项目池 fin 账户
    expect(credVals).not.toContain('4')   // logi 被 system 过滤
    w.unmount()
  })

  it('切换身份 → 凭证下拉跟随该身份的映射;default 身份取系统默认账户', async () => {
    const { w } = mountCard()
    await flush()
    await w.find(`[data-testid="uc-id-select-${FIN_ROW}-0"]`).setValue('fin-default')
    await flush()
    const credSel = w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`)
    expect((credSel.element as HTMLSelectElement).value).toBe('1')
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-0"]`).text())
      .toContain('默认账户:qa1')
    w.unmount()
  })

  it('Admin 选中凭证 → PATCH 身份 ref + registry-changed', async () => {
    const { w } = mountCard({ caps: ['ops.write'] })
    await flush()
    await w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`).setValue('2')
    await flush()
    expect(patchAlias).toHaveBeenCalledWith('fin-qa', {
      refMode: 'username', refUsername: 'qa2',
    })
    expect(w.findComponent(UsersCard).emitted('registry-changed'))
      .toBeTruthy()
    w.unmount()
  })

  it('非 Admin 选中凭证 → 新建身份弹窗 → 追加 username-ref 草稿', async () => {
    const { w, drafts } = mountCard({ caps: [] })
    await flush()
    await w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`).setValue('2')
    await flush()
    expect((q('[data-testid="uc-id-username"]') as HTMLInputElement).value)
      .toBe('qa2')
    q('[data-testid="uc-id-submit"]')!.click()
    await flush()
    expect(patchAlias).not.toHaveBeenCalled()
    expect(drafts.value).toContainEqual({
      name: 'fin-qa2', baseService: 'fin', envId: 1, username: 'qa2',
    })
    w.unmount()
  })

  it('新建凭证:system/env 由实例/身份派生;Admin 建后自动绑定', async () => {
    const { w } = mountCard()
    await flush()
    await w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`).setValue('__new__')
    await flush()
    await new DOMWrapper(q('[data-testid="uc-cred-username"]')!)
      .setValue('new1')
    await new DOMWrapper(q('[data-testid="uc-cred-password"]')!)
      .setValue('secret1')
    q('[data-testid="uc-cred-submit"]')!.click()
    await flush()
    expect(createAuth).toHaveBeenCalledWith({
      system: 'fin', envId: 1, username: 'new1', password: 'secret1',
    })
    expect(patchAlias).toHaveBeenCalledWith('fin-qa', {
      refMode: 'username', refUsername: 'new1',
    })
    w.unmount()
  })

  it('「+」为同一实例再加一行映射(不是新建实例/身份)', async () => {
    const { w } = mountCard({ caps: ['ops.write'] })
    await flush()
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-1"]`).exists()).toBe(false)
    await w.find(`[data-testid="uc-inst-add-${FIN_ROW}-0"]`).trigger('click')
    await flush()
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-1"]`).exists()).toBe(true)
    // 新行默认取下一个未用身份(fin-default)
    expect((w.find(`[data-testid="uc-id-select-${FIN_ROW}-1"]`)
      .element as HTMLSelectElement).value).toBe('fin-default')
    // 没有创建新身份
    expect(createAlias).not.toHaveBeenCalled()
    w.unmount()
  })

  it('身份下拉「新建身份…」:createAlias 带 baseService/env/default', async () => {
    const { w } = mountCard({ caps: ['ops.write'] })
    await flush()
    await w.find(`[data-testid="uc-id-select-${FIN_ROW}-0"]`).setValue('__new__')
    await flush()
    await new DOMWrapper(q('[data-testid="uc-id-name"]')!)
      .setValue('fin-admin')
    q('[data-testid="uc-id-submit"]')!.click()
    await flush()
    expect(createAlias).toHaveBeenCalledWith(expect.objectContaining({
      aliasName: 'fin-admin', baseService: 'fin', envId: 1,
      refMode: 'default',
    }))
    expect(w.findComponent(UsersCard).emitted('registry-changed'))
      .toBeTruthy()
    w.unmount()
  })

  it('待保存草稿进身份下拉;选中后凭证下拉禁用并提示', async () => {
    const { w } = mountCard({
      drafts: [{ name: 'fin-draft', baseService: 'fin', envId: 1,
                 username: 'qa2' }],
    })
    await flush()
    const idSel = w.find(`[data-testid="uc-id-select-${FIN_ROW}-0"]`)
    expect(idSel.findAll('option').map((o) => o.text()).join('|'))
      .toContain('fin-draft(待保存)')
    await idSel.setValue('fin-draft')
    await flush()
    const credSel = w.find(`[data-testid="uc-cred-select-${FIN_ROW}-0"]`)
    expect((credSel.element as HTMLSelectElement).disabled).toBe(true)
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-0"]`).text())
      .toContain('待保存:qa2')
    w.unmount()
  })

  it('「×」删映射行;最后一行才移出服务范围', async () => {
    const { w } = mountCard()
    await flush()
    // 加一行 → 两行
    await w.find(`[data-testid="uc-inst-add-${FIN_ROW}-0"]`).trigger('click')
    await flush()
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-1"]`).exists()).toBe(true)
    // 删第一行:实例仍在范围,第二行升为 index 0,不 emit remove-instance
    await w.find(`[data-testid="uc-rm-${FIN_ROW}-0"]`).trigger('click')
    await flush()
    expect(w.find(`[data-testid="uc-row-${FIN_ROW}-0"]`).exists()).toBe(true)
    expect(w.findComponent(UsersCard).emitted('remove-instance'))
      .toBeUndefined()
    // 删最后一行 → emit remove-instance
    await w.find(`[data-testid="uc-rm-${FIN_ROW}-0"]`).trigger('click')
    const emitted = w.findComponent(UsersCard).emitted('remove-instance')
    expect(emitted).toBeTruthy()
    expect((emitted![0][0] as any).service).toBe('fin')
    w.unmount()
  })

  it('遗留明文快照:只读列出 + 确认后清空', async () => {
    const { w, model } = mountCard({
      legacy: { old: { url: 'https://x', username: 'u', token_type: 'Bearer' } },
    })
    await flush()
    expect(w.find('[data-testid="uc-clear"]').exists()).toBe(true)
    await w.find('[data-testid="uc-clear"]').trigger('click')
    await flush()
    expect(confirmAction).toHaveBeenCalled()
    expect(model.value).toEqual({})
    w.unmount()
  })
})
