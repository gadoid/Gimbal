/**
 * UsersAdmin — 批次 2 新栈迁移测试(本页此前**无任何测试**,首批补齐)。
 * 功能契约与迁移前逐条对齐:列表/搜索/自助标记;创建表单(zod 校验 +
 * 角色映射);行操作(编辑昵称/升降级/重置密码/删除的输入用户名硬确认)。
 *
 * jsdom 交互注意:
 * - shadcn Dialog/DropdownMenu 经 Portal 渲染到 body → 一律 body 查询
 *   (DOMWrapper),wrapper.find 够不到;
 * - reka Select 在 jsdom 打不开(PointerEvent 语义),角色筛选只断言
 *   触发器在场,过滤逻辑由搜索路径覆盖;
 * - RadioGroupItem 是 role=radio 的 button,点击选择。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import UsersAdmin from '@/views/UsersAdmin.vue'
import * as usersApi from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

vi.mock('@/api/users', () => ({
  list: vi.fn(),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
  resetPassword: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const USERS = [
  { id: 1, username: 'root', display_name: 'Root', is_admin: true, is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 2, username: 'alice', display_name: '', is_admin: false, is_active: true, created_at: '2026-02-01T00:00:00Z' },
  { id: 3, username: 'bob', display_name: 'Bob', is_admin: false, is_active: false, created_at: '2026-03-01T00:00:00Z' },
]

/** Portal 内元素查询(shadcn Dialog/DropdownMenu 渲染在 body) */
function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}
function qAll(sel: string): Element[] {
  return [...document.body.querySelectorAll(sel)]
}

/** 挂载到 beforeEach 设置的同一 pinia(loginAs 写的就是它) */
async function mountPage() {
  const w = mount(UsersAdmin, {
    global: { plugins: [getActivePinia()!] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

function loginAs(id: number, isAdmin = true) {
  useAuthStore().currentUser = { id, username: 'x', is_admin: isAdmin } as never
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(usersApi.list).mockResolvedValue(USERS as never)
  // store 会把返回值写进 list 并渲染 — mock 必须回完整对象,
  // 否则 row.id 渲染崩溃,后续 DOM 更新全部中断(调试教训)
  vi.mocked(usersApi.patch).mockImplementation(
    (async (id: number, p: object) =>
      ({ ...USERS.find((u) => u.id === id)!, ...p })) as never,
  )
  vi.mocked(usersApi.create).mockResolvedValue(
    { id: 99, username: 'newbie', display_name: '', is_admin: false, is_active: true, created_at: 'x' } as never,
  )
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('UsersAdmin — 列表与筛选', () => {
  it('渲染用户表:元信息、自助标记「你」、停用行划线', async () => {
    loginAs(1)
    const w = await mountPage()
    expect(w.text()).toContain('3 个用户 · 2 启用 · 1 admin')
    expect(w.find('[data-testid="user-row-1"]').text()).toContain('你')
    expect(w.find('[data-testid="user-row-1"]').text()).toContain('root')
    expect(w.find('[data-testid="user-row-3"]').classes()).toContain('inactive-row')
    // 自助行无操作菜单,他行有
    expect(w.find('[data-testid="user-more-1"]').exists()).toBe(false)
    expect(w.find('[data-testid="user-more-2"]').exists()).toBe(true)
    // 角色筛选触发器在场(交互在 jsdom 不可达,见文件头注)
    expect(w.find('[data-testid="role-filter"]').exists()).toBe(true)
    w.unmount()
  })

  it('搜索按用户名/昵称过滤(useListSearch 接线)', async () => {
    loginAs(1)
    const w = await mountPage()
    await w.find('[data-testid="user-search"]').setValue('ali')
    expect(w.findAll('tbody tr').length).toBe(1)
    expect(w.find('tbody').text()).toContain('alice')

    await w.find('[data-testid="user-search"]').setValue('Bob')
    expect(w.findAll('tbody tr').length).toBe(1)
    expect(w.find('tbody').text()).toContain('bob')
    w.unmount()
  })
})

describe('UsersAdmin — 创建用户', () => {
  it('校验拦截:非法用户名/弱密码 → 字段错误,不发请求', async () => {
    loginAs(1)
    const w = await mountPage()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()

    await q('[data-testid="create-username"]').setValue('x!')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('3-32 位字母数字下划线'))

    await q('[data-testid="create-username"]').setValue('newbie')
    const pw = qAll('input').find((i) => (i as HTMLInputElement).placeholder.includes('8 位'))!
    await new DOMWrapper(pw).setValue('short')
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('至少 8 位含字母 + 数字'))
    expect(usersApi.create).not.toHaveBeenCalled()
    w.unmount()
  })

  it('合法 + admin 角色 → create(映射 is_admin) + toast + 关闭', async () => {
    loginAs(1)
    const w = await mountPage()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-username"]').setValue('newbie')
    const pw = qAll('input').find((i) => (i as HTMLInputElement).placeholder.includes('8 位'))!
    await new DOMWrapper(pw).setValue('GoodPass123')
    const radios = qAll('[role="radio"]')
    expect(radios.length).toBe(2)
    radios[1].dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    await q('form').trigger('submit')
    await vi.waitFor(() => expect(usersApi.create).toHaveBeenCalled())

    expect(usersApi.create).toHaveBeenCalledWith({
      username: 'newbie',
      display_name: undefined,
      password: 'GoodPass123',
      is_admin: true,
    })
    expect(vi.mocked(toast.success).mock.calls[0][0]).toContain('已创建用户 newbie')
    w.unmount()
  })
})

describe('UsersAdmin — 行操作(DropdownMenu 经 Portal 渲染)', () => {
  async function openMenu(w: ReturnType<typeof mount>, userId: number) {
    await w.find(`[data-testid="user-more-${userId}"]`).trigger('click')
    await flushPromises()
  }

  async function clickMenuItem(label: string) {
    // 作用域 = 最后一个 menu 容器:前一个菜单关闭动画期可能仍挂 body
    const menus = qAll('[role="menu"]')
    const scope = menus.at(-1) ?? document.body
    const item = [...scope.querySelectorAll('[role="menuitem"]')]
      .find((el) => el.textContent?.includes(label))
    expect(item, `menu item ${label}`).toBeTruthy()
    item!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
  }

  it('编辑昵称 → patchUser(display_name)', async () => {
    loginAs(1)
    const w = await mountPage()
    await openMenu(w, 2)
    await clickMenuItem('编辑昵称')
    await q('[data-testid="edit-display"]').setValue('Alice A')
    await q('[data-testid="edit-submit"]').trigger('click')
    await vi.waitFor(() => expect(usersApi.patch).toHaveBeenCalledWith(2, { display_name: 'Alice A' }))
    w.unmount()
  })

  it('升级成员 → patch(is_admin:true);停用用户菜单给「启用」→ patch(is_active:true)', async () => {
    loginAs(1)
    const w = await mountPage()
    await openMenu(w, 2)
    await clickMenuItem('升级为 admin')
    await vi.waitFor(() => expect(usersApi.patch).toHaveBeenCalledWith(2, { is_admin: true }))

    // bob 是停用态(is_active:false)→ 菜单给的是「启用账号」
    await openMenu(w, 3)
    await clickMenuItem('启用账号')
    await vi.waitFor(() => expect(usersApi.patch).toHaveBeenCalledWith(3, { is_active: true }))
    w.unmount()
  })

  it('重置密码 → 结果对话框显示一次性密码', async () => {
    loginAs(1)
    vi.mocked(usersApi.resetPassword).mockResolvedValue({
      user_id: 2, username: 'alice', new_password: 'Tmp-Pw-987654',
    } as never)
    const w = await mountPage()
    await openMenu(w, 2)
    await clickMenuItem('重置密码')
    await vi.waitFor(() =>
      expect(q('[data-testid="reset-pw"]').text()).toBe('Tmp-Pw-987654'))
    w.unmount()
  })

  it('删除:输入用户名前禁用,输入后 remove(id)', async () => {
    loginAs(1)
    const w = await mountPage()
    await openMenu(w, 2)
    await clickMenuItem('删除')
    const submit = q('[data-testid="delete-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
    await q('[data-testid="delete-confirm"]').setValue('alice')
    expect((q('[data-testid="delete-submit"]').element as HTMLButtonElement).disabled).toBe(false)
    await submit.trigger('click')
    await vi.waitFor(() => expect(usersApi.remove).toHaveBeenCalledWith(2))
    w.unmount()
  })
})

describe('UsersAdmin — 空态', () => {
  it('无用户 → 引导 CTA 空态', async () => {
    loginAs(1)
    vi.mocked(usersApi.list).mockResolvedValue([] as never)
    const w = await mountPage()
    expect(w.find('[data-testid="users-empty"]').exists()).toBe(true)
    expect(w.text()).toContain('创建第一个用户')
    w.unmount()
  })
})
