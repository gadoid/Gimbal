/**
 * AdaptationCenter 重做后的测试（RS4a Release v4.4 §5.10）。
 * 旧版测试（admin 目录变更模型）已随旧页面替换删除。
 * 新版：AdaptationFlow 为主体 + 批次表 + carry 面板 + 未索引警示。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/adaptations', () => ({
  listBatches: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  unindexedSteps: vi.fn().mockResolvedValue([]),
  errMsg: vi.fn().mockReturnValue('error'),
  openCarryBatch: vi.fn(),
  createOp: vi.fn(),
}))

vi.mock('@/api/carry', () => ({
  getDrift: vi.fn().mockResolvedValue({ plateReachable: true, services: [] }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAdmin: true,
    hasRole: (...roles: string[]) => roles.includes('admin'),
  }),
}))

import AdaptationCenter from '@/views/AdaptationCenter.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div/>' } },
    { path: '/adaptations', component: AdaptationCenter },
    { path: '/adaptations/batches/:batchId', component: { template: '<div/>' } },
  ],
})

function mountPage() {
  return mount(AdaptationCenter, {
    global: { plugins: [router, createPinia()] },
  })
}

describe('AdaptationCenter (RS4a rewrite)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('renders AdaptationFlow as main content (4-step wizard)', () => {
    const w = mountPage()
    expect(w.findAll('.af-step')).toHaveLength(4)
  })

  it('renders batch table section', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('批次')
  })

  it('renders carry drift section', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('carry 漂移')
  })

  it('shows empty state when no batches', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.text()).toContain('暂无批次')
  })
})
