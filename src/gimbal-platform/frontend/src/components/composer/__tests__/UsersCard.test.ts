/**
 * UsersCard.vue — ③ 配置页用户认证卡(2026-08-25 认证改造)。
 *
 * 覆盖:已有 users 明文渲染、手动添加/删除 emit 快照、凭证池导入
 * (已存在 alias 置灰、明文快照写入、422 跳过该条继续)。
 * api/auth_sessions 全 mock — 不碰网络。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import UsersCard from '@/components/composer/UsersCard.vue'
import { list, get } from '@/api/auth_sessions'
import type { UserAuthView } from '@/types/plate'

vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(),
  get: vi.fn(),
}))

const poolA = {
  id: 1, alias: 'pool-a', url: 'https://a/auth', username: 'ua',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}
const poolB = {
  id: 2, alias: 'pool-b', url: 'https://b/auth', username: 'ub',
  token_type: 'Basic', expires_in: 60,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(list).mockResolvedValue([poolA, poolB] as any)
  vi.mocked(get).mockImplementation((id: number) =>
    Promise.resolve(
      id === 1 ? { ...poolA, password: 'plain-pw-1' } : { ...poolB, password: 'plain-pw-2' },
    ) as any,
  )
})

function mountCard(initial: Record<string, UserAuthView>) {
  const users = ref<Record<string, UserAuthView>>(initial)
  const Parent = defineComponent({
    setup() {
      return () => h(UsersCard, {
        modelValue: users.value,
        'onUpdate:modelValue': (v: Record<string, UserAuthView>) => { users.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] }, attachTo: document.body })
  return { w, users }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

function setInput(placeholderPrefix: string, value: string) {
  const el = [...document.querySelectorAll('.el-dialog input')]
    .find((i) => (i as HTMLInputElement).placeholder.startsWith(placeholderPrefix)) as HTMLInputElement
  el.value = value
  el.dispatchEvent(new Event('input'))
}

function clickDialogButton(text: string) {
  ;([...document.querySelectorAll('.el-dialog__footer button')]
    .find((b) => b.textContent!.includes(text)) as HTMLElement).click()
}

describe('UsersCard — 渲染与手动 CRUD', () => {
  it('已有 users 明文渲染(alias/url/username/password 列)', async () => {
    const { w } = mountCard({
      qa1: { url: 'https://x/auth', username: 'alice', password: 'plain-pw', token_type: 'Bearer', expires_in: 3600 },
    })
    await flush() // el-table 列注册在 mounted 后微任务刷新,同步读 DOM 拿不到行
    expect(w.text()).toContain('qa1')
    expect(w.text()).toContain('plain-pw')
    w.unmount()
  })

  it('手动添加用户 → emit 5 字段快照', async () => {
    const { w, users } = mountCard({})
    await w.findAll('button').filter((b) => b.text().includes('添加用户'))[0].trigger('click')
    await flush()
    setInput('例 qa1', 'new-user')
    setInput('https://target', 'https://y/login')
    setInput('登录用户名', 'u1')
    setInput('登录密码', 'p1')
    await flush()
    clickDialogButton('添加')
    await flushPromises()
    expect(users.value['new-user']).toEqual({
      url: 'https://y/login', username: 'u1', password: 'p1',
      token_type: 'Bearer', expires_in: 7200,
    })
    w.unmount()
  })

  it('alias 冲突时手动添加被拒(不静默覆盖)', async () => {
    const { w, users } = mountCard({
      qa1: { url: 'https://x', username: 'a', password: 'p', token_type: 'Bearer', expires_in: 60 },
    })
    await w.findAll('button').filter((b) => b.text().includes('添加用户'))[0].trigger('click')
    await flush()
    setInput('例 qa1', 'qa1')
    setInput('https://target', 'https://y')
    setInput('登录用户名', 'u2')
    setInput('登录密码', 'p2')
    await flush()
    clickDialogButton('添加')
    await flushPromises()
    expect(users.value['qa1'].username).toBe('a') // 未被覆盖
    w.unmount()
  })

  it('空表时 alias=constructor(原型链同名属性)不被误判已存在', async () => {
    const { w, users } = mountCard({})
    await w.findAll('button').filter((b) => b.text().includes('添加用户'))[0].trigger('click')
    await flush()
    setInput('例 qa1', 'constructor')
    setInput('https://target', 'https://y/login')
    setInput('登录用户名', 'u1')
    setInput('登录密码', 'p1')
    await flush()
    clickDialogButton('添加')
    await flushPromises()
    expect(users.value['constructor']).toEqual({
      url: 'https://y/login', username: 'u1', password: 'p1',
      token_type: 'Bearer', expires_in: 7200,
    })
    expect(
      [...document.querySelectorAll('.el-message')]
        .some((m) => m.textContent!.includes('已存在') && m.textContent!.includes('constructor')),
    ).toBe(false)
    w.unmount()
  })

  it('删除用户 → emit 移除后的字典', async () => {
    const { w, users } = mountCard({
      qa1: { url: 'https://x', username: 'a', password: 'p' },
      qa2: { url: 'https://y', username: 'b', password: 'q' },
    })
    await flush() // 同上:表格行异步渲染,先等一拍再找删除按钮
    await w.findAll('button').filter((b) => b.text() === '删除')[0].trigger('click')
    await flush()
    expect(users.value['qa1']).toBeUndefined()
    expect(users.value['qa2']).toBeTruthy()
    w.unmount()
  })
})

describe('UsersCard — 凭证池导入', () => {
  it('已存在 alias 置灰;导入写入明文快照', async () => {
    const { w, users } = mountCard({
      'pool-b': { url: 'https://old', username: 'old', password: 'old' },
    })
    await w.findAll('button').filter((b) => b.text().includes('从凭证池导入'))[0].trigger('click')
    await flushPromises()
    const items = [...document.querySelectorAll('.pool-item')] as HTMLElement[]
    const taken = items.find((el) => el.textContent!.includes('pool-b'))!
    expect(taken.classList.contains('disabled')).toBe(true)
    const fresh = items.find((el) => el.textContent!.includes('pool-a'))!
    expect(fresh.classList.contains('disabled')).toBe(false)
    fresh.click()
    await flush()
    clickDialogButton('导入')
    await flushPromises()
    expect(users.value['pool-a']).toEqual({
      url: 'https://a/auth', username: 'ua', password: 'plain-pw-1',
      token_type: 'Bearer', expires_in: 3600,
    })
    expect(users.value['pool-b'].username).toBe('old') // 已存在未被覆盖
    w.unmount()
  })

  it('单条 422 → 跳过该条、其余继续导入', async () => {
    vi.mocked(get).mockImplementation((id: number) =>
      id === 1
        ? Promise.reject(new Error('加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存'))
        : Promise.resolve({ ...poolB, password: 'plain-pw-2' } as any),
    )
    const { w, users } = mountCard({})
    await w.findAll('button').filter((b) => b.text().includes('从凭证池导入'))[0].trigger('click')
    await flushPromises()
    ;([...document.querySelectorAll('.pool-item')] as HTMLElement[])
      .filter((el) => !el.classList.contains('disabled'))
      .forEach((el) => el.click())
    await flush()
    clickDialogButton('导入')
    await flushPromises()
    expect(users.value['pool-a']).toBeUndefined()
    expect(users.value['pool-b']).toMatchObject({ password: 'plain-pw-2' })
    w.unmount()
  })
})
