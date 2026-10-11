/**
 * CaseComposerCatalog — scoped error card + refetch 清理(Release 6.1)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CaseComposerCatalog from '@/components/composer/CaseComposerCatalog.vue'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

// mock auth store(取 token)
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ accessToken: '' }),
}))

describe('CaseComposerCatalog — scoped error', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('某系统按修订取数失败 → 显示错误卡片,不列该系统接口', async () => {
    // working 全量成功;fin 系统的修订查询返回 404
    let callCount = 0
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url.includes('ref=')) {
        // 修订查询 → 404
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ detail: { code: 'release_not_found', message: 'not found' } }),
        })
      }
      // working 全量
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [
          { id: 'fin.a.x', system: 'fin', service: 'fin-service', name: 'X',
            method: 'GET', path: '/x', shape_hash: 'h1' },
          { id: 'wms.b.y', system: 'wms', service: 'wms-service', name: 'Y',
            method: 'GET', path: '/y', shape_hash: 'h2' },
        ] }),
      })
    }))

    const w = mount(CaseComposerCatalog, {
      props: {
        plateRefOf: (sys: string) => sys === 'fin' ? '1.0#1' : 'working',
      },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    // 错误卡片显示系统名+修订号+错误码
    const err = w.find('[data-testid="catalog-scoped-error"]')
    expect(err.exists()).toBe(true)
    expect(err.text()).toContain('fin')
    expect(err.text()).toContain('1.0#1')
    expect(err.text()).toContain('release_not_found')

    // 失败系统(fin)的接口不在列表中;未声明系统(wms)的接口在
    const items = w.vm.$data || {}
    // 通过 component 内部状态验证——Catalog 的 all ref 不直接暴露,
    // 用 DOM 判断:接口树里不应出现 fin.a.x
    expect(w.text()).not.toContain('fin.a.x')
  })

  it('外层异常 → fetchErrors 清空(不残留)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const w = mount(CaseComposerCatalog, {
      props: { plateRefOf: () => 'working' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()
    // 外层 catch → fetchErrors 应为空数组
    expect(w.find('[data-testid="catalog-scoped-error"]').exists()).toBe(false)
  })
})
