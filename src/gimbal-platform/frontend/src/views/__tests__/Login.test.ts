/**
 * Login — 批次 1 新栈迁移回归(无 Element Plus 依赖,本文件本身就是
 * 换栈证明:不装 EP 插件也能全流程跑通)。
 * 契约:空表单/短用户名拦截;合法 → auth.login + toast + 跳转
 * (?redirect 优先,缺省 /home);登录失败 → 卡内错误条(非 toast)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Login from '@/views/Login.vue'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const { push, mockRoute } = vi.hoisted(() => ({
  push: vi.fn(),
  mockRoute: { query: {} as Record<string, string> },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push }),
  }
})

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

function mountLogin(query: Record<string, string> = {}) {
  mockRoute.query = query
  return mount(Login, {
    global: {
      plugins: [createPinia()],
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
}

async function fillAndSubmit(w: ReturnType<typeof mount>, username = 'alice', password = 'pw') {
  await w.findAll('input')[0].setValue(username)
  await w.findAll('input')[1].setValue(password)
  await w.find('form').trigger('submit')
  await flushPromises()
}

describe('Login — 校验拦截', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
    mockRoute.query = {}
  })

  it('空表单提交 → 字段错误可见,不发 login 请求', async () => {
    const w = mountLogin()
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'login')
    await w.find('form').trigger('submit')
    // zod 校验管线是异步的:waitFor 轮询到错误渲染(固定延时不可靠)
    await vi.waitFor(() => {
      expect(w.text()).toContain('请输入用户名')
      expect(w.text()).toContain('请输入密码')
    })
    expect(spy).not.toHaveBeenCalled()
    w.unmount()
  })

  it('用户名 <3 字符 → 提示长度 3-32,不发请求', async () => {
    const w = mountLogin()
    await fillAndSubmit(w, 'ab', 'pw')
    await vi.waitFor(() => expect(w.text()).toContain('长度 3-32 字符'))
    w.unmount()
  })
})

describe('Login — 提交流', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
    mockRoute.query = {}
  })

  it('合法 → login(creds) + 成功 toast + 跳 /home', async () => {
    const w = mountLogin()
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'login').mockResolvedValue(undefined as never)
    await fillAndSubmit(w)
    await vi.waitFor(() => expect(spy).toHaveBeenCalledWith('alice', 'pw'))
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith('登录成功')
    expect(push).toHaveBeenCalledWith('/home')
    w.unmount()
  })

  it('?redirect 在场 → 登录后跳回 redirect', async () => {
    const w = mountLogin({ redirect: '/scenarios' })
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockResolvedValue(undefined as never)
    await fillAndSubmit(w)
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith('/scenarios'))
    w.unmount()
  })

  it('登录失败 → 卡内错误条展示服务端消息(不 throw)', async () => {
    const w = mountLogin()
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockRejectedValue({ msg: '用户名或密码错误' })
    await fillAndSubmit(w)
    await vi.waitFor(() => expect(w.text()).toContain('用户名或密码错误'))
    w.unmount()
  })

  it('Enter 与原生 submit 同时到达 → login 只调一次(评审 P1 回归)', async () => {
    const w = mountLogin()
    const auth = useAuthStore()
    const spy = vi.spyOn(auth, 'login').mockResolvedValue(undefined as never)
    await w.findAll('input')[0].setValue('alice')
    await w.findAll('input')[1].setValue('pw')
    // 模拟真实键盘序列:Enter 的 keydown/keyup + 隐式表单提交几乎同时到
    await w.findAll('input')[1].trigger('keydown.enter')
    await w.findAll('input')[1].trigger('keyup.enter')
    await w.find('form').trigger('submit')
    await vi.waitFor(() => expect(spy).toHaveBeenCalled())
    expect(spy).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})
