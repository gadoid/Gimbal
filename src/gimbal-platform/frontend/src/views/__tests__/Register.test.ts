/**
 * Register — 批次 1 新栈迁移回归。
 * 契约:canSubmit 门控(用户名≥3 / 密码强度≥3 / 两次一致 / 同意协议);
 * 强度清单实时点亮;提交 → auth.register + 成功条 + 倒计时跳 /home;
 * 失败 → 卡内错误条,按钮恢复可用。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Register from '@/views/Register.vue'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push }),
  }
})

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const WEAK = 'abc'
const STRONG = 'Str0ng!Pass'

async function fill(w: ReturnType<typeof mount>, over: Partial<Record<string, string>> = {}) {
  await w.find('#reg-username').setValue(over.username ?? 'alice')
  await w.find('#reg-password').setValue(over.password ?? STRONG)
  await w.find('#reg-confirm').setValue(over.confirm ?? over.password ?? STRONG)
}

const STUBS = {
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}

function mountPage() {
  return mount(Register, { global: { plugins: [createPinia()], stubs: STUBS } })
}

describe('Register — canSubmit 门控', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('弱密码 → 按钮禁用;强度标签 WEAK', async () => {
    const w = mountPage()
    await fill(w, { password: WEAK, confirm: WEAK })
    const btn = w.find('button[type="submit"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    expect(w.text()).toContain('WEAK')
    w.unmount()
  })

  it('两次密码不一致 → ✗ 且禁用;一致后 ✓ 可提交', async () => {
    const w = mountPage()
    await fill(w, { confirm: 'Mismatch1!' })
    expect(w.text()).toContain('✗')
    expect((w.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)

    await w.find('#reg-confirm').setValue(STRONG)
    expect(w.find('[data-testid="confirm-match"]').text()).toBe('✓')
    expect((w.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(false)
    w.unmount()
  })

  it('取消协议勾选 → 禁用', async () => {
    const w = mountPage()
    await fill(w)
    await w.find('[data-testid="privacy-check"]').setValue(false)
    expect((w.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
    w.unmount()
  })

  it('用户名非法字符 → 提交时字段错误(仅字母数字下划线连字符)', async () => {
    const w = mountPage()
    await fill(w, { username: '非法 名!' })
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('仅允许字母、数字、下划线和连字符')
    w.unmount()
  })
})

describe('Register — 提交流', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('合法 → register(creds) + 成功条 + 倒计时结束跳 /home', async () => {
    const w = mountPage()
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'register').mockResolvedValue(undefined as never)
    await fill(w)
    await w.find('form').trigger('submit')
    await vi.runAllTimersAsync()

    expect(spy).toHaveBeenCalledWith('alice', STRONG, '')
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith('注册成功')
    expect(w.find('[data-testid="register-success"]').exists()).toBe(true)
    expect(push).toHaveBeenCalledWith('/home')
    w.unmount()
  })

  it('注册失败 → 错误条 + 按钮恢复(不再 loading)', async () => {
    const w = mountPage()
    const auth = useAuthStore()
    vi.spyOn(auth, 'register').mockRejectedValue({ msg: '用户名已存在' })
    await fill(w)
    await w.find('form').trigger('submit')
    await vi.advanceTimersByTimeAsync(0)
    expect(w.text()).toContain('用户名已存在')
    expect((w.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(false)
    w.unmount()
  })
})
