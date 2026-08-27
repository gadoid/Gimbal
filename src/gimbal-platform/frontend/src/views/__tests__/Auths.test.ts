/**
 * Auths.vue — 测试弹框状态流(2026-08-25 认证改造)。
 *
 * 锁死:开弹框即"认证中"(修复历史 bug — 标题三元把 null 折叠成
 * "连通失败",在途假失败);返回后切 认证成功/认证失败 终态;
 * 失败详情默认展开。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import Auths from '@/views/Auths.vue'
import * as api from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1, alias: 'qa1', url: 'https://x/auth', username: 'u',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}

function mountPage() {
  return mount(Auths, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'list').mockResolvedValue([sample])
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
