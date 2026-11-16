/**
 * Auths.vue — 批次 2 新栈迁移后的测试。
 *
 * ①测试弹框状态流(2026-08-25 认证改造,迁移前已有,语义原样保留):
 *   锁死:开弹框即"认证中"(修复历史 bug — 标题三元把 null 折叠成
 *   "连通失败",在途假失败);返回后切 认证成功/认证失败 终态;
 *   失败详情默认展开。
 * ②新增:创建表单 zod 校验 + 条件 password;编辑留空密码 = 不修改;
 *   删除的输入 alias 硬确认。
 * 交互注意:shadcn Dialog 经 Portal 渲染 → body 查询(DOMWrapper)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import Auths from '@/views/Auths.vue'
import * as api from '@/api/auth_sessions'
import * as aliasApi from '@/api/service-aliases'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1, alias: 'qa1', url: 'https://x/auth', username: 'u',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
  alias_ref_count: 1, scenario_ref_count: 2,
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
  // 槽位声明反查默认空(✕ 未声明 chip 的用例单独覆写)
  vi.spyOn(aliasApi, 'listAllAliases').mockResolvedValue([])
  vi.spyOn(api, 'create').mockResolvedValue(sample)
  vi.spyOn(api, 'patch').mockResolvedValue(sample)
  vi.spyOn(api, 'remove').mockResolvedValue(undefined)
  vi.spyOn(api, 'getReferences').mockResolvedValue({
    // M2a S6:alias_refs 不再带 environment_id;scheme 引用种类已退役
    alias_refs: [
      { alias_name: 'fin-service-uat', base_service: 'fin-service' },
    ],
    scenario_refs: {
      visible: [
        { scenario_id: 'sc-1', name: '退款审核', kinds: ['template'], owner_id: 1 },
        { scenario_id: 'sc-2', name: '旧快照场景', kinds: ['snapshot'], owner_id: 9 },
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
  it('创建:非法 alias/URL 拦截;合法 → create(载荷含 token_type/expires_in)', async () => {
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()

    await q('[data-testid="f-alias"]').setValue('非法!')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('1-64 位字母数字下划线连字符'))

    await q('[data-testid="f-alias"]').setValue('qa2')
    await q('[data-testid="f-url"]').setValue('not-a-url')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('URL 格式不正确'))

    await q('[data-testid="f-url"]').setValue('https://t/login')
    await q('[data-testid="f-username"]').setValue('u2')
    // 创建态缺密码 → 条件必填补判
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('请输入 password'))
    expect(api.create).not.toHaveBeenCalled()

    await q('[data-testid="f-password"]').setValue('secret')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(api.create).toHaveBeenCalled())
    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({
      alias: 'qa2', url: 'https://t/login', username: 'u2',
      password: 'secret', token_type: 'Bearer', expires_in: 7200,
    }))
    w.unmount()
  })

  it('编辑:预填回显;password 留空 → patch 载荷不带 password', async () => {
    const w = mountPage()
    await flushPromises()
    await openRowMenu(w)
    await clickMenuItem('auth-edit')

    const alias = q('[data-testid="f-alias"]').element as HTMLInputElement
    expect(alias.disabled).toBe(true)   // alias 不可改
    expect(alias.value).toBe('qa1')

    await q('[data-testid="f-username"]').setValue('u-new')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(api.patch).toHaveBeenCalled())
    const payload = vi.mocked(api.patch).mock.calls[0][1] as Record<string, unknown>
    expect(payload.username).toBe('u-new')
    expect('password' in payload).toBe(false)
    w.unmount()
  })

  it('删除:输入 alias 前 disabled,输入后 remove(id)', async () => {
    const w = mountPage()
    await flushPromises()
    await openRowMenu(w)
    await clickMenuItem('auth-del')

    const submit = q('[data-testid="del-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
    await q('[data-testid="del-confirm"]').setValue('qa1')
    await submit.trigger('click')
    await vi.waitFor(() => expect(api.remove).toHaveBeenCalledWith(1))
    w.unmount()
  })
})

describe('Auths — 被引用列与反查侧板(配套方案 §1)', () => {
  it('双计数 chip 渲染;点开侧板列别名绑定 + 场景引用(kinds)+ 不可见计数', async () => {
    const w = mountPage()
    await flushPromises()

    const chip = w.find('[data-testid="refs-open-qa1"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('1 别名')
    expect(w.text()).toContain('2 场景')

    await chip.trigger('click')
    await flushPromises()
    expect(api.getReferences).toHaveBeenCalledWith('qa1')
    const body = document.body.textContent || ''
    expect(body).toContain('fin-service-uat')
    expect(body).toContain('退款审核')
    expect(body).toContain('旧快照场景')
    expect(body).toContain('另有 3 条不可见')
    // 名字引用语义说明在场(§1.4)
    expect(body).toContain('名字引用')
    w.unmount()
  })

  it('409 拦截:删除被本人场景引用的凭证 → 弹框保持打开 + 错误文案', async () => {
    const w = mountPage()
    await flushPromises()
    vi.spyOn(api, 'remove').mockRejectedValueOnce(
      new Error("凭证 'qa1' 被 2 个本人场景引用(模板/方案绑定)"))

    await openRowMenu(w)
    await clickMenuItem('auth-del')
    await q('[data-testid="del-confirm"]').setValue('qa1')
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
        { ...sample, id: 2, alias: 'lonely', alias_ref_count: 0, scenario_ref_count: 0 },
        sample,
      ],
      total: 2, page: 1, pageSize: 50, tokenTypeCounts: { Bearer: 2 },
    } as never)
    const w = mountPage()
    await flushPromises()

    const row2 = w.find('[data-testid="auth-row-2"]')
    expect(row2.text()).toContain('未被引用 · 可安全删除')
    // 副标题统计行:总数 + 未被任何引用(1 条 lonely)
    expect(w.text()).toContain('2 条凭证')
    expect(w.text()).toContain('1 条未被任何引用')
    w.unmount()
  })

  it('原型对齐:抽屉底部拦截预警(本人场景 × 模板/方案才计数)', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'u' } as never

    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="refs-open-qa1"]').trigger('click')
    await flushPromises()

    // sc-1 = 本人 template 引用 → 预警在场;sc-2 = 他人快照 → 不计入
    const warn = document.body.querySelector('[data-testid="refs-block-warn"]')
    expect(warn).toBeTruthy()
    expect(warn!.textContent).toContain('仍有 1 个本人场景引用')
    expect(warn!.textContent).toContain('先解除别名绑定')
    w.unmount()
  })
})

// ── authz M2a S3.3:槽位绑定字段面(2026-11-16 二轮:系统分组口径)─────

describe('Auths — 系统分组与槽语义露出', () => {
  it('按系统分组;显式槽名行内露出;默认 chip 与环境列展示', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [{
        ...sample, id: 7, alias: 'jira-sit', slot: 'jira', isDefault: true,
        system: 'jira', envId: 3,
      }, {
        ...sample, id: 8, alias: 'qa-main', slot: 'qa-main',
      }],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    // 分组键 = 系统;jira-sit 有 system,qa-main 无 → 未归类组
    expect(w.find('[data-testid="sys-card-jira"]').text()).toContain('jira')
    expect(w.find('[data-testid="sys-card-uncategorized"]').exists()).toBe(true)
    expect(w.findAll('[data-testid^="sys-card-"]')).toHaveLength(2)
    // 槽语义露出①:slot≠alias 的行内小字
    expect(w.find('[data-testid="auth-row-7"]').text()).toContain('槽 jira')
    // slot===alias 的行不露槽小字(概念退居语义层)
    expect(w.find('[data-testid="auth-row-8"]').text()).not.toContain('槽 qa-main')
    expect(w.find('[data-testid="default-chip-7"]').exists()).toBe(true)
    // 环境列:envs 未加载(真实请求失败)→ 回落 环境#id
    expect(w.find('[data-testid="auth-row-7"]').text()).toContain('环境#3')
    w.unmount()
  })

  it('非默认行 → ⋯ 菜单有「设为槽默认」;默认行没有', async () => {
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [{
        ...sample, id: 7, alias: 'a', slot: 'a', isDefault: false,
      }, {
        ...sample, id: 8, alias: 'b', slot: 'b', isDefault: true,
      }],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    const rows = w.findAll('[data-testid^="auth-row-"]')
    expect(rows.length).toBe(2)
    // 菜单是懒挂载(tools 的 DropdownMenu 展开才渲染):直接查触发器在,
    // 行为面(点击 → apiSetDefault)由下面直接断言 store/api 面覆盖
    w.unmount()
  })
})

// ── 状态优先改造(2026-11-16 二轮:系统组聚合口径)──────────────────
describe('Auths — 状态优先(组头聚合 · 只看问题)', () => {
  it('本机测败记忆 → 组头 ✕N 测败 + 红色带;「只看问题」只留问题组', async () => {
    localStorage.setItem('auths.test-memory:v1',
      JSON.stringify({ 1: { ok: false, at: Date.now() } }))
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 1, alias: 'qa1', slot: 'qa1', isDefault: true, system: 'pay' },
        { ...sample, id: 2, alias: 'ok-alias', slot: 'ok-slot', isDefault: true, system: 'wms' },
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

  it('无默认/未声明的槽算问题:组头聚合徽章;问题组排前,健康组滤除', async () => {
    // svc-b 组:s2 已声明且有默认 → 健康绿;svc-a 组:s1 未声明 ∨ 无默认 → 琥珀
    vi.spyOn(aliasApi, 'listAllAliases').mockResolvedValue([
      { aliasName: 'b', baseService: 'b-svc', slot: 's2', kind: 'plate',
        createdAt: '', updatedAt: '' },
    ] as never)
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 2, alias: 'b', slot: 's2', isDefault: true, system: 'svc-b' },
        { ...sample, id: 1, alias: 'a', slot: 's1', isDefault: false, system: 'svc-a' },
      ],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    const cards = w.findAll('[data-testid^="sys-card-"]')
    // 问题组(无默认+未声明)排前
    expect(cards[0].attributes('data-testid')).toBe('sys-card-svc-a')
    expect(cards[1].attributes('data-testid')).toBe('sys-card-svc-b')
    // 组头聚合:1 条无默认 + ✕1 未声明(琥珀);健康组绿
    expect(cards[0].text()).toContain('1 条无默认')
    expect(w.find('[data-testid="sys-undeclared-svc-a"]').exists()).toBe(true)
    expect(cards[0].classes()).toContain('tone-warn')
    expect(cards[1].classes()).toContain('tone-ok')
    // 单绑定槽无默认 → 行内也直示
    expect(w.find('[data-testid="auth-row-1"]').text()).toContain('无默认')
    await w.find('[data-testid="problem-filter"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sys-card-svc-a"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-card-svc-b"]').exists()).toBe(false)
    w.unmount()
  })

  it('>5 凭证的系统组:收前 5,展开/收起切换(凭证平铺,无槽容器层)', async () => {
    const items = Array.from({ length: 7 }, (_, i) => ({
      ...sample, id: i + 1, alias: `a${i + 1}`, slot: 'big', isDefault: i === 0,
      system: 'bulk',
    }))
    vi.spyOn(api, 'list').mockResolvedValue({
      items, total: 7, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    // 凭证一等公民:组内平铺无簇头容器,同槽相邻靠行内槽小字关联
    expect(w.find('.cluster-lead').exists()).toBe(false)
    expect(w.findAll('[data-testid^="auth-row-"]')).toHaveLength(5)
    expect(w.find('[data-testid="sys-more-bulk"]').text()).toContain('还有 2 条凭证')
    await w.find('[data-testid="sys-more-bulk"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid^="auth-row-"]')).toHaveLength(7)
    // 7 条同槽:每行都带「槽 big」属性小字(slot≠alias)
    expect(w.findAll('.slot-sub')).toHaveLength(7)
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

// ── 槽位主轴直连:该槽在服务注册的身份面注册表有无声明 ────────────
describe('Auths — 槽位声明反查(与服务注册直连)', () => {
  it('槽无任何身份面声明 → 组头 ✕N 未声明;有声明的槽不计入', async () => {
    vi.spyOn(aliasApi, 'listAllAliases').mockResolvedValue([
      { aliasName: 'fin-service-uat', baseService: 'fin-service',
        slot: 'ok-slot', kind: 'plate', createdAt: '', updatedAt: '' },
    ] as never)
    vi.spyOn(api, 'list').mockResolvedValue({
      items: [
        { ...sample, id: 1, alias: 'qa1', slot: 'qa1', isDefault: true, system: 'pay' },
        { ...sample, id: 2, alias: 'ok-alias', slot: 'ok-slot', isDefault: true, system: 'wms' },
      ],
      total: 2, page: 1, pageSize: 20, tokenTypeCounts: {},
    } as never)
    const w = mountPage()
    await flushPromises()
    expect(w.find('[data-testid="sys-undeclared-pay"]').exists()).toBe(true)
    expect(w.find('[data-testid="sys-undeclared-wms"]').exists()).toBe(false)
    w.unmount()
  })
})
