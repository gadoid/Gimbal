/**
 * b2.5(归一 v1.0 §3.4):画像落地页只列 sut —— sutOnly 过滤出口断言
 * (传参 {sutOnly:true} 且 integration 服务不出现)。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const rowsMock = vi.fn()

vi.mock('@/utils/catalog-services', async (orig) => {
  const actual = await orig<typeof import('@/utils/catalog-services')>()
  return { ...actual, loadCatalogServiceRows: (...a: unknown[]) => rowsMock(...a) }
})

import ServicesIndex from '@/views/ServicesIndex.vue'

const ROWS = [
  { name: 'fin-service', system: 'fin', endpointCount: 10, kind: 'sut' },
  { name: 'jira', system: 'jira', endpointCount: 2, kind: 'integration' },
]

describe('ServicesIndex — 画像页只列 sut(§3.4)', () => {
  beforeEach(() => { rowsMock.mockReset() })

  it('sutOnly 过滤:传参 {sutOnly:true},integration 服务不出现', async () => {
    rowsMock.mockImplementation(async (opts?: { sutOnly?: boolean }) =>
      opts?.sutOnly ? ROWS.filter((r) => r.kind !== 'integration') : ROWS)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: ServicesIndex }],
    })
    router.push('/')
    await router.isReady()
    const w = mount(ServicesIndex, { global: { plugins: [router] } })
    await flushPromises()
    expect(rowsMock).toHaveBeenCalledWith({ sutOnly: true })
    expect(w.text()).toContain('fin-service')
    expect(w.text()).not.toContain('jira')
  })
})
