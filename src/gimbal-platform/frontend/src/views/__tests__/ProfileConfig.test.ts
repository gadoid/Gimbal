/**
 * ProfileConfig —— S7.3 个人设置「我的配置」。
 * 默认环境偏好(run.environment)读写 + 个人层 carry 默认编辑器
 * (scope=user 透传);保存后按钮回到禁用(值未再变)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ProfileConfig from '@/views/ProfileConfig.vue'
import * as prefApi from '@/api/preferences'
import * as envApi from '@/api/environments'
import * as carryApi from '@/api/carry'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/errorFallback', () => ({ showError: vi.fn() }))
vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn().mockResolvedValue({}),
  putDefaults: vi.fn().mockResolvedValue({}),
  // S7.6 我的 carry 漂移面板(CarryDriftPanel)读面
  getDrift: vi.fn().mockResolvedValue({ services: [], plateReachable: true }),
}))

/** CarryDriftPanel 用 useRouter(S7.6)→ 挂真 router */
function mountCfg() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(ProfileConfig, { global: { plugins: [router, createPinia()] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  // restoreAllMocks 会清 factory 里设的实现 —— carry 编辑器读面重钉
  vi.mocked(carryApi.getDefaults).mockResolvedValue({})
  vi.mocked(carryApi.putDefaults).mockResolvedValue({})
  vi.mocked(carryApi.getDrift).mockResolvedValue({ services: [], plateReachable: true })
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([
    { id: 7, name: 'dev', description: '', lines: {}, owner_id: null, is_default: false },
    { id: 8, name: 'sit', description: '', lines: {}, owner_id: null, is_default: false },
  ] as never)
})

describe('ProfileConfig — 我的默认环境偏好', () => {
  it('回显已存偏好;改选保存 → PUT run.environment', async () => {
    vi.spyOn(prefApi, 'getPreferences').mockResolvedValue({
      'run.environment': { environmentId: 7 },
    } as never)
    const put = vi.spyOn(prefApi, 'putPreference').mockResolvedValue(undefined as never)
    const w = mountCfg()
    await flushPromises()

    const sel = w.find('[data-testid="my-env-select"]')
    expect((sel.element as HTMLSelectElement).value).toBe('7')
    await sel.setValue('8')
    await w.find('[data-testid="my-env-save"]').trigger('click')
    await flushPromises()
    expect(put).toHaveBeenCalledWith('run.environment', { environmentId: 8 })
    w.unmount()
  })

  it('已设偏好 → 清空保存 → PUT null(显式解除偏好)', async () => {
    vi.spyOn(prefApi, 'getPreferences').mockResolvedValue({
      'run.environment': { environmentId: 7 },
    } as never)
    const put = vi.spyOn(prefApi, 'putPreference').mockResolvedValue(undefined as never)
    const w = mountCfg()
    await flushPromises()

    await w.find('[data-testid="my-env-select"]').setValue('')
    await w.find('[data-testid="my-env-save"]').trigger('click')
    await flushPromises()
    expect(put).toHaveBeenCalledWith('run.environment', { environmentId: null })
    w.unmount()
  })
})

describe('ProfileConfig — 我的 carry 漂移(S7.6)', () => {
  it('按个人层拉漂移并渲染清单', async () => {
    vi.spyOn(prefApi, 'getPreferences').mockResolvedValue({} as never)
    vi.mocked(carryApi.getDrift).mockResolvedValue({
      services: [{ service: 'fin-service', orphaned: ['$.mine'],
        uncovered: [], renamedSuggestions: [] }],
      plateReachable: true, scope: 'user',
    })
    const w = mountCfg()
    await flushPromises()
    expect(carryApi.getDrift).toHaveBeenCalledWith({ scope: 'user' })
    const panel = w.find('[data-testid="carry-drift-my-carry"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('$.mine')
    w.unmount()
  })
})
