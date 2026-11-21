/**
 * UsersCard.vue — ③ 配置页凭证卡(凭证治理 §3.3 双入口,2c 重建)。
 *
 * 覆盖:§7 遗留明文只读透传 + 显式清空(confirmAction 闸)、手配草稿
 * (字段/注册表重名预检/自定义字段/移除)、检索凭证池(双源徽标/拍板
 * #10 项目池 username 可见/scope 过滤/引用条目名/未设条目深链/FE-02
 * 降级)、快照导入退役断言。api 层全 mock — 不碰网络。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import UsersCard from '@/components/composer/UsersCard.vue'
import { list } from '@/api/auth_sessions'
import { listServices } from '@/api/services'
import { listEnvironments } from '@/api/environments'
import { listAllAliases } from '@/api/service-aliases'
import { loadCatalogSystemByService } from '@/utils/catalog-services'
import { confirmAction } from '@/utils/confirmAction'
import { toast } from '@/utils/toast'
import type { UserAuthView } from '@/types/plate'
import type { AuthDraftView } from '@/types/scenario-composer'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
// toast 单例由 ToastHost 渲染 — 测试一律 mock 本模块(模块规范)
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
// 清空存量明文的确认闸(默认放行;取消分支单测内翻转)
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(true),
}))
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn() }))
vi.mock('@/api/services', () => ({ listServices: vi.fn() }))
vi.mock('@/api/environments', () => ({ listEnvironments: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({ listAllAliases: vi.fn() }))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogSystemByService: vi.fn(),
}))

const mine = {
  id: 1, source: 'personal', system: 'fin', envId: 1, username: 'ua',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
  isDefault: true,
}
const proj = {
  id: 2, source: 'project', system: 'fin', envId: 1, username: 'svc1',
  token_type: 'Basic', expires_in: 60,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}
/** 注册表:qa1(username-ref ua)装配 mine;ub 无条目。 */
const registry = [{
  aliasName: 'qa1', baseService: 'fin-svc', slot: '', kind: 'plate',
  envId: 1, refMode: 'username', refUsername: 'ua', display: '',
  createdAt: '', updatedAt: '',
}]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(list).mockResolvedValue({
    items: [mine, proj], total: 2, page: 1, pageSize: 200,
  } as any)
  vi.mocked(listServices).mockResolvedValue({
    services: [
      { name: 'fin-svc', system: 'fin' },
      { name: 'pay-svc', system: 'pay' },
    ],
    unregistered: [], plateReachable: true,
  } as any)
  vi.mocked(listEnvironments).mockResolvedValue([
    { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
  ] as any)
  vi.mocked(listAllAliases).mockResolvedValue(registry as any)
  vi.mocked(loadCatalogSystemByService).mockResolvedValue(
    new Map([['fin-svc', 'fin'], ['pay-svc', 'pay']]))
})

function mountCard(opts: {
  users?: Record<string, UserAuthView>
  drafts?: AuthDraftView[]
  projectId?: number | null
  services?: Record<string, string>
} = {}) {
  const users = ref(opts.users ?? {})
  const drafts = ref(opts.drafts ?? [])
  const Parent = defineComponent({
    setup() {
      return () => h(UsersCard, {
        modelValue: users.value,
        'onUpdate:modelValue': (v: Record<string, UserAuthView>) => { users.value = v },
        authDrafts: drafts.value,
        'onUpdate:authDrafts': (v: AuthDraftView[]) => { drafts.value = v },
        projectId: opts.projectId ?? null,
        services: opts.services ?? {},
      })
    },
  })
  const w = mount(Parent, { attachTo: document.body })
  return { w, users, drafts }
}

const flush = () => new Promise((r) => setTimeout(r, 0))
const q = (sel: string) => document.querySelector(sel) as HTMLElement

async function submitDraftForm() {
  q('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await flushPromises()
  await flush()
}

describe('UsersCard — §7 遗留明文:只读透传 + 显式清空', () => {
  it('存量 users 只读表(无密码列/无编辑钮)+ 提示;确认 → emit {}', async () => {
    const { w, users } = mountCard({
      users: { qa1: { url: 'https://x', username: 'alice', password: 'PLAINPW-MARKER', token_type: 'Bearer' } },
    })
    await flush()
    expect(w.text()).toContain('存量明文快照')
    expect(w.text()).toContain('alice') // username 列原样
    expect(w.text()).not.toContain('PLAINPW-MARKER') // 明文不再展示
    expect(w.find('[data-testid="uc-edit"]').exists()).toBe(false)
    await w.find('[data-testid="uc-clear"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(confirmAction).mock.calls[0][0]).toContain('明文')
    expect(users.value).toEqual({})
    w.unmount()
  })

  it('取消清空 → 快照原样保留', async () => {
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    const { w, users } = mountCard({
      users: { qa1: { url: 'https://x', username: 'a', password: 'p', token_type: 'Bearer' } },
    })
    await flush()
    await w.find('[data-testid="uc-clear"]').trigger('click')
    await flushPromises()
    expect(users.value['qa1']).toBeTruthy()
    w.unmount()
  })
})

describe('UsersCard — 手配草稿(保存期通道)', () => {
  it('填表提交 → emit authDrafts(含自定义字段);移除可撤销', async () => {
    const { w, drafts } = mountCard({})
    await w.find('[data-testid="uc-draft-add"]').trigger('click')
    await flushPromises()
    ;(q('[data-testid="uc-draft-name"]') as HTMLInputElement).value = 'qa9'
    q('[data-testid="uc-draft-name"]').dispatchEvent(new Event('input'))
    ;((q('[data-testid="uc-draft-system"]') as unknown) as HTMLSelectElement).value = 'fin'
    q('[data-testid="uc-draft-system"]').dispatchEvent(new Event('change'))
    ;((q('[data-testid="uc-draft-env"]') as unknown) as HTMLSelectElement).value = '1'
    q('[data-testid="uc-draft-env"]').dispatchEvent(new Event('change'))
    ;(q('[data-testid="uc-draft-username"]') as HTMLInputElement).value = 'ua'
    q('[data-testid="uc-draft-username"]').dispatchEvent(new Event('input'))
    ;(q('[data-testid="uc-draft-password"]') as HTMLInputElement).value = 'pw12345'
    q('[data-testid="uc-draft-password"]').dispatchEvent(new Event('input'))
    // 自定义字段一行(Dialog 经 Portal 渲染到 body — 从 body 找)
    q('[data-testid="uc-af-add"]').click()
    await flush()
    ;(q('[data-testid="uc-af-key-0"]') as HTMLInputElement).value = 'orgNo'
    q('[data-testid="uc-af-key-0"]').dispatchEvent(new Event('input'))
    ;(q('[data-testid="uc-af-val-0"]') as HTMLInputElement).value = '42'
    q('[data-testid="uc-af-val-0"]').dispatchEvent(new Event('input'))
    await submitDraftForm()
    await vi.waitFor(() => expect(drafts.value).toHaveLength(1))
    expect(drafts.value[0]).toMatchObject({
      name: 'qa9', system: 'fin', envId: 1, username: 'ua',
    })
    expect(drafts.value[0].accountFields).toEqual({ orgNo: '42' })
    // 移除
    await w.find('[data-testid="uc-draft-del-qa9"]').trigger('click')
    expect(drafts.value).toHaveLength(0)
    w.unmount()
  })

  it('注册表重名预检:qa1 已登记 → 拒收并提示直接引用', async () => {
    const { w, drafts } = mountCard({})
    await w.find('[data-testid="uc-draft-add"]').trigger('click')
    await flushPromises()
    ;(q('[data-testid="uc-draft-name"]') as HTMLInputElement).value = 'qa1'
    q('[data-testid="uc-draft-name"]').dispatchEvent(new Event('input'))
    // 其余字段先过 zod —— 重名预检在表单回调内,校验先放行才能到
    ;((q('[data-testid="uc-draft-system"]') as unknown) as HTMLSelectElement).value = 'fin'
    q('[data-testid="uc-draft-system"]').dispatchEvent(new Event('change'))
    ;((q('[data-testid="uc-draft-env"]') as unknown) as HTMLSelectElement).value = '1'
    q('[data-testid="uc-draft-env"]').dispatchEvent(new Event('change'))
    ;(q('[data-testid="uc-draft-username"]') as HTMLInputElement).value = 'ua'
    q('[data-testid="uc-draft-username"]').dispatchEvent(new Event('input'))
    ;(q('[data-testid="uc-draft-password"]') as HTMLInputElement).value = 'pw12345'
    q('[data-testid="uc-draft-password"]').dispatchEvent(new Event('input'))
    await submitDraftForm()
    await flush()
    expect(drafts.value).toHaveLength(0)
    expect(vi.mocked(toast.warning).mock.calls.some(
      ([m]) => typeof m === 'string' && m.includes('qa1'))).toBe(true)
    w.unmount()
  })

  it('短密码被 zod 拒(入池掩码阈值 6 位)', async () => {
    const { w, drafts } = mountCard({})
    await w.find('[data-testid="uc-draft-add"]').trigger('click')
    await flushPromises()
    ;(q('[data-testid="uc-draft-name"]') as HTMLInputElement).value = 'qa8'
    q('[data-testid="uc-draft-name"]').dispatchEvent(new Event('input'))
    ;((q('[data-testid="uc-draft-system"]') as unknown) as HTMLSelectElement).value = 'fin'
    q('[data-testid="uc-draft-system"]').dispatchEvent(new Event('change'))
    ;((q('[data-testid="uc-draft-env"]') as unknown) as HTMLSelectElement).value = '1'
    q('[data-testid="uc-draft-env"]').dispatchEvent(new Event('change'))
    ;(q('[data-testid="uc-draft-username"]') as HTMLInputElement).value = 'ua'
    q('[data-testid="uc-draft-username"]').dispatchEvent(new Event('input'))
    ;(q('[data-testid="uc-draft-password"]') as HTMLInputElement).value = 'pw123'
    q('[data-testid="uc-draft-password"]').dispatchEvent(new Event('input'))
    await submitDraftForm()
    await flush()
    expect(drafts.value).toHaveLength(0)
    w.unmount()
  })
})

describe('UsersCard — 检索凭证池(双源 + scope)', () => {
  const services = { 'fin-svc': 'http://fin' }

  it('source=all 双源拉取;徽标 + 拍板 #10 项目池 username 可见', async () => {
    const { w } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(list)).toHaveBeenCalledWith(
      expect.objectContaining({ source: 'all', project_id: 7, page: 1, page_size: 200 }))
    const rowMine = q('[data-testid="uc-pool-row-1"]')
    const rowProj = q('[data-testid="uc-pool-row-2"]')
    expect(rowMine.textContent).toContain('我的池')
    expect(rowMine.textContent).toContain('ua')
    expect(rowProj.textContent).toContain('项目池')
    expect(rowProj.textContent).toContain('svc1') // 拍板 #10:按名引用必需
    w.unmount()
  })

  it('scope 过滤:仅场景服务的系统(fin);开关切换放回全量', async () => {
    vi.mocked(list).mockResolvedValue({
      items: [mine, { ...proj, system: 'pay' }], total: 2, page: 1, pageSize: 200,
    } as any)
    const { w } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    // scopeOnly 默认开:pay 系统行被过滤
    expect(q('[data-testid="uc-pool-row-1"]')).toBeTruthy()
    expect(q('[data-testid="uc-pool-row-2"]')).toBeFalsy()
    // 关掉 scope
    ;(q('[data-testid="uc-scope-only"]') as HTMLInputElement).checked = false
    q('[data-testid="uc-scope-only"]').dispatchEvent(new Event('change'))
    await flush()
    expect(q('[data-testid="uc-pool-row-2"]')).toBeTruthy()
    w.unmount()
  })

  it('引用条目名:username-ref 命中显示 qa1;无条目 → 未设引用 + 深链', async () => {
    const { w } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    expect(q('[data-testid="uc-pool-row-1"]').textContent).toContain('qa1')
    expect(q('[data-testid="uc-pool-row-2"]').textContent).toContain('未设条目引用')
    expect(q('[data-testid="uc-pool-row-2"]').textContent).toContain('去服务注册')
    w.unmount()
  })

  it('主档系统映射:自定义服务(不在 plate 目录)的条目也命中账户,不误报未设引用', async () => {
    // 用户实测复现:账户 system='fin-service'(主档自定义系统),已有同名
    // 条目;plate 目录映射里没有该服务 → 旧实现误报「未设条目引用」,
    // 选用时又提示「已在注册表」。系统取值必须主档优先(与后端连表同源)。
    vi.mocked(loadCatalogSystemByService).mockResolvedValue(new Map())
    vi.mocked(listServices).mockResolvedValue({
      services: [{ name: 'fin-service', system: 'fin-service' }],
      unregistered: [], plateReachable: true,
    } as any)
    vi.mocked(listAllAliases).mockResolvedValue([{
      ...registry[0], aliasName: 'fin-service-18180789650',
      baseService: 'fin-service', refUsername: '18180789650',
    }] as any)
    vi.mocked(list).mockResolvedValue({
      items: [{ ...mine, id: 3, system: 'fin-service', username: '18180789650' }],
      total: 1, page: 1, pageSize: 200,
    } as any)
    const { w } = mountCard({ projectId: 7, services: { 'fin-service': 'http://fin' } })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    const row = q('[data-testid="uc-pool-row-3"]')
    // scope 过滤同样以主档系统判定 → 行在;条目名直接展示
    expect(row).toBeTruthy()
    expect(row.textContent).toContain('fin-service-18180789650')
    expect(row.textContent).not.toContain('未设条目引用')
    expect(q('[data-testid="uc-pick-3"]')).toBeFalsy()
    w.unmount()
  })

  it('池读取失败 → 降级横幅(FE-02:失败≠空态)', async () => {
    vi.mocked(list).mockRejectedValue(new Error('pool down'))
    const { w } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    expect(q('[data-testid="uc-pool-degraded"]')).toBeTruthy()
    expect(q('[data-testid="uc-pool-degraded"]').textContent).toContain('读取失败')
    w.unmount()
  })

  it('单页 200 截断 → 显式提示(P3-1:容量限制不静默)', async () => {
    vi.mocked(list).mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) => ({
        ...mine, id: i + 1, username: `u${i}`,
      })), total: 260, page: 1, pageSize: 200,
    } as any)
    const { w } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    const hint = q('[data-testid="uc-pool-truncated"]')
    expect(hint).toBeTruthy()
    expect(hint.textContent).toContain('200')
    w.unmount()
  })
})

describe('UsersCard — 选用已有账户(检索面建条目,2026-11-21)', () => {
  const services = { 'fin-svc': 'http://fin' }

  it('未设条目账户「选用」→ 预填条目名 → emit 条目草稿(password 缺省)+ 卡片「已有账户」徽标', async () => {
    const { w, drafts } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    // 项目池 svc1 无条目 → 选用入口在场(不再只有「去服务注册」死路)
    ;(q('[data-testid="uc-pick-2"]') as HTMLElement).click()
    await flushPromises()
    const name = q('[data-testid="uc-pick-name"]') as HTMLInputElement
    expect(name.value).toBe('fin-svc1')   // <system>-<username> 建议名
    name.value = 'pay-svc01'
    name.dispatchEvent(new Event('input'))
    await flush()
    ;(q('[data-testid="uc-pick-submit"]') as HTMLElement).click()
    await flush()
    expect(drafts.value).toHaveLength(1)
    expect(drafts.value[0]).toMatchObject({
      name: 'pay-svc01', system: 'fin', envId: 1, username: 'svc1',
    })
    // 引用已有账户:不携带 password(后端只建条目,不新建账户)
    expect(drafts.value[0].password).toBeUndefined()
    await vi.waitFor(() => expect(w.text()).toContain('已有账户'))
    w.unmount()
  })

  it('账户缺系统标签 → 不提供「选用」(条目须系统入主档);仍可去服务注册', async () => {
    vi.mocked(list).mockResolvedValue({
      items: [{ ...mine, id: 9, system: '', username: 'u9' }],
      total: 1, page: 1, pageSize: 200,
    } as any)
    // 无场景服务 → scope 过滤不生效(空系统标签行不会被系统命中)
    const { w } = mountCard({ projectId: 7 })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    const row = q('[data-testid="uc-pool-row-9"]')
    expect(row.textContent).toContain('未设条目引用')
    expect(q('[data-testid="uc-pick-9"]')).toBeFalsy()
    expect(q('[data-testid="uc-go-registry"]')).toBeTruthy()
    w.unmount()
  })

  it('条目名撞注册表 → 拒收并提示直接引用', async () => {
    const { w, drafts } = mountCard({ projectId: 7, services })
    await w.find('[data-testid="uc-search-open"]').trigger('click')
    await flushPromises()
    ;(q('[data-testid="uc-pick-2"]') as HTMLElement).click()
    await flushPromises()
    const name = q('[data-testid="uc-pick-name"]') as HTMLInputElement
    name.value = 'qa1'
    name.dispatchEvent(new Event('input'))
    await flush()
    ;(q('[data-testid="uc-pick-submit"]') as HTMLElement).click()
    await flush()
    expect(drafts.value).toHaveLength(0)
    expect(q('[data-testid="uc-pick-err"]')!.textContent).toContain('已在注册表')
    w.unmount()
  })
})

describe('UsersCard — 快照导入退役(§3.7 TOK-05 接力)', () => {
  it('旧入口整体退场:无「从凭证池导入」/「+ 添加用户」;新场景空态引导检索/手配', async () => {
    const { w } = mountCard({})
    await flush()
    expect(w.text()).not.toContain('从凭证池导入')
    expect(w.text()).not.toContain('+ 添加用户')
    expect(w.find('[data-testid="uc-search-open"]').exists()).toBe(true)
    expect(w.find('[data-testid="uc-draft-add"]').exists()).toBe(true)
    w.unmount()
  })
})
