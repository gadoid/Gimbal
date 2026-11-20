/**
 * PromotionDialog.vue — 加入项目对话框(身份条目分区,阶段 4 §5):
 * analyze 返回 identityEntries → 裁决呈现(授权状态 + 项目池账户
 * 就绪指引);无身份条目 → 分区不渲染。api/auth store 全 mock。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PromotionDialog from '@/components/project/PromotionDialog.vue'
import { analyzePromotion } from '@/api/project-promotions'
import type { PromotionAnalysis } from '@/api/project-promotions'

vi.mock('@/api/project-promotions', () => ({
  analyzePromotion: vi.fn(),
  createPromotion: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    projects: [{ id: 7, name: '示例项目', kind: 'normal', role: 'member' }],
  }),
}))

function analysis(partial: Partial<PromotionAnalysis>): PromotionAnalysis {
  return { services: [], conflicts: [], blockers: [], slots: [], ...partial }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(analyzePromotion).mockResolvedValue(analysis({}))
})

async function mountDialog() {
  const w = mount(PromotionDialog, {
    props: {
      open: false, kind: 'scenario' as const,
      sourceId: 'sc-x', sourceName: '示例场景',
    },
    global: { plugins: [createPinia()] },
  })
  // open watch 非 immediate:挂载后翻转触发初始化(projectId → analyze)
  await w.setProps({ open: true })
  await flushPromises()
  return w
}

describe('PromotionDialog — 身份条目分区(阶段 4 §5)', () => {
  it('identityEntries 渲染:条目/基础服务环境/授权态/项目池就绪指引', async () => {
    vi.mocked(analyzePromotion).mockResolvedValue(analysis({
      slots: ['e2'],
      identityEntries: [{
        aliasName: 'e2', baseService: 'fin', envLabel: '测试',
        registered: true, granted: false, projectAccountReady: false,
      }],
    }))
    const w = await mountDialog()
    const sec = w.find('[data-testid="promo-identity-entries"]')
    expect(sec.exists()).toBe(true)
    expect(sec.text()).toContain('共享即授权')
    expect(sec.text()).toContain('e2')
    expect(sec.text()).toContain('fin / 测试')
    expect(sec.text()).toContain('批准时自动授权')
    expect(sec.text()).toContain('配置项目池账户')
    w.unmount()
  })

  it('已授权 + 账户就绪 → 绿色呈现(不再指引配置)', async () => {
    vi.mocked(analyzePromotion).mockResolvedValue(analysis({
      slots: ['e1'],
      identityEntries: [{
        aliasName: 'e1', baseService: 'fin', envLabel: '测试',
        registered: true, granted: true, projectAccountReady: true,
      }],
    }))
    const w = await mountDialog()
    const sec = w.find('[data-testid="promo-identity-entries"]')
    expect(sec.text()).toContain('已授权')
    expect(sec.text()).toContain('✓ 就绪')
    w.unmount()
  })

  it('无身份条目 → 分区不渲染(slots 空同)', async () => {
    const w = await mountDialog()
    expect(w.find('[data-testid="promo-identity-entries"]').exists()).toBe(false)
    w.unmount()
  })
})
