/**
 * Auths.vue — registry 重构(账户实体化)后的测试。
 *
 * ①测试弹框状态流(2026-08-25 认证改造,迁移前已有,语义原样保留):
 *   锁死:开弹框即"认证中";返回后切 认证成功/认证失败 终态;失败详情默认展开。
 * ②创建表单 zod 校验 + 条件 password;编辑:实体键锁定 + 留空密码 = 不修改;
 *   删除的输入 username 硬确认。
 * ③账户语义:system 分组、(system,env) 默认聚合、引用双计数(条目/场景)、
 *   反查侧板(identityRefs + 场景)、组折叠、只看问题。
 * 交互注意:shadcn Dialog 经 Portal 渲染 → body 查询(DOMWrapper)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import Auths from '@/views/Auths.vue'
import * as api from '@/api/auth_sessions'
import * as envApi from '@/api/environments'
import * as servicesApi from '@/api/services'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1, system: 'pay', envId: 3, username: 'u',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
  loginUrl: 'https://x/auth',
  identityRefCount: 1, scenarioRefCount: 2,
}

function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

function mountPage() {
  return mount(Auths, {
    global: { plugins: [getActivePinia()!] },
    attachTo: document.body,
  })
}

/** 原型 H-auths-v2:行操作收进 ⋯ 下拉 → 先开菜单(内容经 Portal 进 body)再点项。 */
async function openRowMenu(w: ReturnType<typeof mount>, id = 1) {
  await w.find(`[data-testid="auth-more-${id}"]`).trigger('click')
  await flushPromises()
}

async function clickMenuItem(testid: string) {
  await q(`[data-testid="${testid}"]`).trigger('click')
  await flushPromises()
}

/** 状态优先改造:测试连通升为行内一键(auth-test-inline-{id}),不再进菜单。 */
async function clickInlineTest(w: ReturnType<typeof mount>, id = 1) {
  await w.find(`[data-testid="auth-test-inline-${id}"]`).trigger('click')
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'list').mockResolvedValue({
      items: [sample], total: 1, page: 1, pageSize: 50,
      tokenTypeCounts: { Bearer: 1 },
    })
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue(
    [{ id: 3, name: '测试' }] as never)
  // 主档:pay 系统已登记(其余测试里的 jira/svc-* 等按未注册处理)
  vi.spyOn(servicesApi, 'listServices').mockResolvedValue({
    services: [
      { name: 'pay-service', system: 'pay', kind: 'plate', abbr: '',
        description: '', inCatalog: true, createdAt: '', updatedAt: '' },
    ],
    unregistered: [], plateReachable: true,
  })
  vi.spyOn(api, 'create').mockResolvedValue(sample)
  vi.spyOn(api, 'patch').mockResolvedValue(sample)
  vi.spyOn(api, 'remove').mockResolvedValue(undefined)
  vi.spyOn(api, 'getReferences').mockResolvedValue({
    identityRefs: [
      { aliasName: 'fin-service-uat', baseService: 'fin-service', envId: 3,
        refMode: 'username', refUsername: 'u' },
    ],
    scenarioRefs: {
      visible: [
        { scenarioId: 'sc-1', name: '退款审核', kinds: ['template'], ownerId: 1 },
        { scenarioId: 'sc-2', name: '旧快照场景', kinds: ['snapshot'], ownerId: 9 },
      ],
      hidden_count: 3,
    },
  })
})

afterEach(() => {
  document.body.innerHTML = ''
  localStorage.removeItem('auths.test-memory:v1')
})

describe('Auths — 测试弹框状态流', () => {
  it('认证中 → 认证成功(在途不出现"连通失败"/"认证失败")', async () => {
    let resolve!: (v: { ok: boolean; status_code: number | null; message: string }) => void
    vi.spyOn(api, 'testConnection').mockImplementation(
      () => new Promise((r) => { resolve = r }),
    )
    const w = mountPage()
    await flushPromises()
    await clickInlineTest(w)

    expect(document.body.textContent).toContain('认证中')
    expect(document.body.textContent).not.toContain('连通失败')
    expect(document.body.textContent).not.toContain('认证失败')

    resolve({ ok: true, status_code: 200, message: '连通成功,已提取 token(前 12 字符:abc…)' })
    await flushPromises()
    expect(document.body.textContent).toContain('认证成功')
    expect(document.body.textContent).toContain('HTTP 200')
    // 终态回写本机记忆:行内出现 ✓ 测通 chip + localStorage 落盘
    expect(w.find('[data-testid="test-mem-1"]').text()).toContain('✓ 测通')
    expect(localStorage.getItem('auths.test-memory:v1')).toContain('"ok":true')
    w.unmount()
  })

  it('认证中 → 认证失败 + 详情默认展开', async () => {
    vi.spyOn(api, 'testConnection').mockResolvedValue({
      ok: false, status_code: null, message: '网络/认证错误: HTTPStatusError: 401',
    })
    const w = mountPage()
    await flushPromises()
    await clickInlineTest(w)
    await flushPromises()

    expect(document.body.textContent).toContain('认证失败')
    expect(document.body.textContent).toContain('网络/认证错误: HTTPStatusError: 401')
    // 失败同样回写:行内 ✗ 测败 chip
    expect(w.find('[data-testid="test-mem-1"]').text()).toContain('✗ 测败')
    w.unmount()
  })

  it('请求异常 → 认证失败终态(不悬挂在认证中)', async () => {
    vi.spyOn(api, 'testConnection').mockRejectedValue(new Error('Network Error'))
    const w = mountPage()
    await flushPromises()
    await clickInlineTest(w)
    await flushPromises()

    expect(document.body.textContent).toContain('认证失败')
    expect(document.body.textContent).toContain('Network Error')
    w.unmount()
  })
})

describe('Auths — 创建 / 编辑 / 删除', () => {
  it('创建:缺 system/envId/密码 拦截;合法 → create(四元组载荷)', async () => {
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()

    // 实体键缺位逐个拦截
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('请选择系统'))
    expect(api.create).not.toHaveBeenCalled()

    // 系统是主档选择:pay 自主档选项
    await q('[data-testid="f-system"]').setValue('pay')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('请选择环境'))

    // 原生 select(listEnvironments 已 mock):直接置值
    await q('[data-testid="f-env"]').setValue('3')
    await flushPromises()

    await q('[data-testid="f-username"]').setValue('u2')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('请输入 password'))
    expect(api.create).not.toHaveBeenCalled()

    await q('[data-testid="f-password"]').setValue('secret')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(api.create).toHaveBeenCalled())
    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({
      system: 'pay', envId: 3, username: 'u2',
      password: 'secret', token_type: 'Bearer', expires_in: 7200,
    }))
    w.unmount()
  })

  it('编辑:实体键预填且锁定;password 留空 → patch 载荷不带 password/username', async () => {
    const w = mountPage()
    await flushPromises()
    await openRowMenu(w)
    await clickMenuItem('auth-edit')

    const sys = q('[data-testid="f-system"]').element as HTMLInputElement
    const uname = q('[data-testid="f-username"]').element as HTMLInputElement
    expect(sys.disabled).toBe(true)      // 实体键不可改
    expect(uname.disabled).toBe(true)
    expect(sys.value).toBe('pay')
    expect(uname.value).toBe('u')

    await q('form').trigger('submit')
    await vi.waitFor(() => expect(api.patch).toHaveBeenCalled())
    const payload = vi.mocked(api.patch).mock.calls[0][1] as Record<string, unknown>
    expect('password' in payload).toBe(false)
    expect('username' in payload).toBe(false)
    expect('system' in payload).toBe(false)
    w.unmount()
  })

  it('系统主档:未注册系统的组头标「未注册」,已注册的不标', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 1, system: 'pay', isDefault: true },
        { ...sample, id: 2, username: 'j-bot', system: 'jira', isDefault: true },
      ],
      total: 2, page: 1, pageSize: 50, tokenTypeCounts: {},
    })
    const w = mountPage()
    await flushPromises()
    // jira 不在主档 → 组头徽章 + 深链服务注册;pay 已登记 → 无徽章
    expect(w.find('[data-testid="sys-unreg-jira"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-unreg-pay"]').exists()).toBe(false)
    w.unmount()
  })

  it('删除:输入 username 前 disabled,输入后 remove(id)', async () => {
    const w = mountPage()
    await flushPromises()
    await openRowMenu(w)
    await clickMenuItem('auth-del')

    const submit = q('[data-testid="del-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
    await q('[data-testid="del-confirm"]').setValue('u')
    await submit.trigger('click')
    await vi.waitFor(() => expect(api.remove).toHaveBeenCalledWith(1))
    w.unmount()
  })
})

describe('Auths — 被引用列与反查侧板(重构 §1)', () => {
  it('双计数 chip 渲染;点开侧板列身份条目 + 场景引用(kinds)+ 不可见计数', async () => {
    const w = mountPage()
    await flushPromises()

    const chip = w.find('[data-testid="refs-open-1"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('1 条目')
    expect(w.text()).toContain('2 场景')

    await chip.trigger('click')
    await flushPromises()
    expect(api.getReferences).toHaveBeenCalledWith(1)
    const body = document.body.textContent || ''
    expect(body).toContain('fin-service-uat')
    expect(body).toContain('退款审核')
    expect(body).toContain('旧快照场景')
    expect(body).toContain('另有 3 条不可见')
    // 装载语义说明在场(§1.4)
    expect(body).toContain('ref')
    w.unmount()
  })

  it('409 拦截:删除被本人场景引用的账户 → 弹框保持打开 + 错误文案', async () => {
    const w = mountPage()
    await flushPromises()
    vi.spyOn(api, 'remove').mockRejectedValueOnce(
      new Error("账户 'u' 被 2 个本人场景引用(模板/方案绑定)"))

    await openRowMenu(w)
    await clickMenuItem('auth-del')
    await q('[data-testid="del-confirm"]').setValue('u')
    await q('[data-testid="del-submit"]').trigger('click')
    await flushPromises()

    // 弹框未关(拦截语义),错误文案经 showError → toast.error 透出
    expect(q('[data-testid="del-submit"]').exists()).toBe(true)
    expect(vi.mocked(toast.error).mock.calls.some(
      (c) => String(c[0]).includes('本人场景引用'))).toBe(true)
    w.unmount()
  })

  it('原型对齐:0 引用行灰字「未被引用 · 可安全删除」;副标题含未被引用统计', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 2, username: 'lonely', identityRefCount: 0, scenarioRefCount: 0 },
        sample,
      ],
      total: 2, page: 1, pageSize: 50, tokenTypeCounts: { Bearer: 2 },
    } as never)
    const w = mountPage()
    await flushPromises()

    const row2 = w.find('[data-testid="auth-row-2"]')
    expect(row2.text()).toContain('未被引用 · 可安全删除')
    // 副标题统计行:总数 + 未被任何引用(1 个 lonely)
    expect(w.text()).toContain('2 个账户')
    expect(w.text()).toContain('1 个未被任何引用')
    w.unmount()
  })

  it('原型对齐:抽屉底部拦截预警(本人场景 × 模板才计数)', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'u' } as never

    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="refs-open-1"]').trigger('click')
    await flushPromises()

    // sc-1 = 本人 template 引用 → 预警在场;sc-2 = 他人快照 → 不计入
    const warn = document.body.querySelector('[data-testid="refs-block-warn"]')
    expect(warn).toBeTruthy()
    expect(warn!.textContent).toContain('仍有 1 个本人场景引用')
    expect(warn!.textContent).toContain('先解除身份条目的 ref')
    w.unmount()
  })
})

// ── registry:系统分组与账户语义露出 ─────────────────────────────

describe('Auths — 系统分组与默认语义露出', () => {
  it('按系统分组;username 领衔;默认 chip 与环境列展示', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [{
        ...sample, id: 7, username: 'jira-bot', isDefault: true,
        system: 'jira', envId: 3,
      }, {
        ...sample, id: 8, username: 'pay-bot', system: 'jira', envId: 3,
      }],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    // 分组键 = 系统;两组各自成组
    expect(w.find('[data-testid="sys-card-jira"]').text()).toContain('jira')
    // 组内默认在前
    expect(w.find('[data-testid="auth-row-7"]').text()).toContain('jira-bot')
    expect(w.find('[data-testid="default-chip-7"]').exists()).toBe(true)
    expect(w.find('[data-testid="default-chip-8"]').exists()).toBe(false)
    // 环境列:envs 已 mock(id=3 → 测试)→ 显示环境名
    expect(w.find('[data-testid="auth-row-7"]').text()).toContain('测试')
    // 登录地址回显(实例只读)
    expect(w.find('[data-testid="auth-row-7"]').text()).toContain('https://x/auth')
    w.unmount()
  })
})

// ── 状态优先改造(registry 口径:(system,env) 无默认 = 取用隐患)────
describe('Auths — 状态优先(组头聚合 · 只看问题)', () => {
  it('本机测败记忆 → 组头 ✕N 测败 + 红色带;「只看问题」只留问题组', async () => {
    localStorage.setItem('auths.test-memory:v1',
      JSON.stringify({ 1: { ok: false, at: Date.now() } }))
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 1, isDefault: true, system: 'pay' },
        { ...sample, id: 2, username: 'ok-bot', isDefault: true, system: 'wms' },
      ],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    // pay 组有测败记忆 → 组头红 chip + 红色带;健康组不亮
    expect(w.find('[data-testid="sys-fail-pay"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-fail-wms"]').exists()).toBe(false)
    expect(w.find('[data-testid="sys-card-pay"]').classes()).toContain('tone-bad')
    // 只看问题:健康组整组滤掉
    await w.find('[data-testid="problem-filter"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sys-card-pay"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-card-wms"]').exists()).toBe(false)
    expect(w.findAll('[data-testid^="auth-row-"]')).toHaveLength(1)
    w.unmount()
  })

  it('(system,env) 无默认算问题:组头聚合徽章;问题组排前,健康组滤除', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 2, username: 'b', isDefault: true, system: 'svc-b', envId: 3 },
        { ...sample, id: 1, username: 'a', isDefault: false, system: 'svc-a', envId: 3 },
      ],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    const cards = w.findAll('[data-testid^="sys-card-"]')
    // 问题组(svc-a 无默认)排前
    expect(cards[0].attributes('data-testid')).toBe('sys-card-svc-a')
    expect(cards[1].attributes('data-testid')).toBe('sys-card-svc-b')
    // 组头聚合:1 组无默认(琥珀);健康组绿
    expect(cards[0].text()).toContain('1 组无默认')
    expect(cards[0].classes()).toContain('tone-warn')
    expect(cards[1].classes()).toContain('tone-ok')
    // 独占 (system,env) 组无默认 → 行内也直示
    expect(w.find('[data-testid="auth-row-1"]').text()).toContain('无默认')
    await w.find('[data-testid="problem-filter"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sys-card-svc-a"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-card-svc-b"]').exists()).toBe(false)
    w.unmount()
  })

  it('>5 账户的系统组:收前 5,展开/收起切换(账户平铺)', async () => {
    const items = Array.from({ length: 7 }, (_, i) => ({
      ...sample, id: i + 1, username: `u${i + 1}`, isDefault: i === 0,
      system: 'bulk',
    }))
    vi.spyOn(api, 'list').mockResolvedValue({
      items, total: 7, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('[data-testid^="auth-row-"]')).toHaveLength(5)
    expect(w.find('[data-testid="sys-more-bulk"]').text()).toContain('还有 2 个账户')
    await w.find('[data-testid="sys-more-bulk"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid^="auth-row-"]')).toHaveLength(7)
    expect(w.find('[data-testid="sys-more-bulk"]').text()).toContain('收起')
    w.unmount()
  })
})

// ── 渐进披露:高级区默认收起(v-show 字段常驻,校验不感知)─────────
describe('Auths — 表单渐进披露', () => {
  it('新建:高级区默认收起;点开关展开', async () => {
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    expect((q('[data-testid="f-advanced-body"]').element as HTMLElement).style.display)
      .toBe('none')
    await q('[data-testid="f-advanced-toggle"]').trigger('click')
    await flushPromises()
    expect((q('[data-testid="f-advanced-body"]').element as HTMLElement).style.display)
      .toBe('')
    w.unmount()
  })

  it('编辑:高级项有非缺省值(expires 3600≠7200)自动展开', async () => {
    const w = mountPage()
    await flushPromises()
    await openRowMenu(w)
    await clickMenuItem('auth-edit')
    expect((q('[data-testid="f-advanced-body"]').element as HTMLElement).style.display)
      .toBe('')
    w.unmount()
  })
})
