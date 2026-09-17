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
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1, alias: 'qa1', url: 'https://x/auth', username: 'u',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
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

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'list').mockResolvedValue([sample])
  vi.spyOn(api, 'create').mockResolvedValue(sample)
  vi.spyOn(api, 'patch').mockResolvedValue(sample)
  vi.spyOn(api, 'remove').mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Auths — 测试弹框状态流', () => {
  it('认证中 → 认证成功(在途不出现"连通失败"/"认证失败")', async () => {
    let resolve!: (v: { ok: boolean; status_code: number | null; message: string }) => void
    vi.spyOn(api, 'testConnection').mockImplementation(
      () => new Promise((r) => { resolve = r }),
    )
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')

    expect(document.body.textContent).toContain('认证中')
    expect(document.body.textContent).not.toContain('连通失败')
    expect(document.body.textContent).not.toContain('认证失败')

    resolve({ ok: true, status_code: 200, message: '连通成功,已提取 token(前 12 字符:abc…)' })
    await flushPromises()
    expect(document.body.textContent).toContain('认证成功')
    expect(document.body.textContent).toContain('HTTP 200')
    w.unmount()
  })

  it('认证中 → 认证失败 + 详情默认展开', async () => {
    vi.spyOn(api, 'testConnection').mockResolvedValue({
      ok: false, status_code: null, message: '网络/认证错误: HTTPStatusError: 401',
    })
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('认证失败')
    expect(document.body.textContent).toContain('网络/认证错误: HTTPStatusError: 401')
    w.unmount()
  })

  it('请求异常 → 认证失败终态(不悬挂在认证中)', async () => {
    vi.spyOn(api, 'testConnection').mockRejectedValue(new Error('Network Error'))
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')
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
    await w.find('[data-testid="auth-edit"]').trigger('click')
    await flushPromises()

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
    await w.find('[data-testid="auth-del"]').trigger('click')
    await flushPromises()

    const submit = q('[data-testid="del-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
    await q('[data-testid="del-confirm"]').setValue('qa1')
    await submit.trigger('click')
    await vi.waitFor(() => expect(api.remove).toHaveBeenCalledWith(1))
    w.unmount()
  })
})
