/** FunctionCard — 集成功能卡(外部系统集成 P1 §7):状态叠加 + 取数 +
 * 立即执行。def 经 workbenchCardDefKey 注入(fn:<id> 定位自身)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FunctionCard from '@/components/workbench/FunctionCard.vue'
import {
  cardSizeKey, workbenchCardDefKey, type WorkbenchCardDef,
} from '../registry'
import * as api from '@/api/integration'

vi.mock('@/api/integration', () => ({
  fetchFunctionCards: vi.fn(),
  runIntegrationTask: vi.fn(),
  integrationErr: vi.fn((e: unknown) => String(e)),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const DEF: WorkbenchCardDef = {
  id: 'fn:7', title: '保活', accent: 'gold',
  component: () => Promise.resolve(FunctionCard),
}

function mountCard(data: Partial<api.FunctionCardData> = {}, size: 'S' | 'M' | 'L' = 'M') {
  vi.mocked(api.fetchFunctionCards).mockResolvedValue([
    { id: 'fn:7', name: '下单服务保活', cronText: '每 5 分钟', ...data },
  ] as never)
  return mount(FunctionCard, {
    global: {
      provide: {
        [workbenchCardDefKey]: ref(DEF),
        [cardSizeKey]: ref(size),
      },
      stubs: { RouterLink: true },
    },
  })
}

describe('FunctionCard — 状态叠加(§7 卡片状态表)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('未执行:灰灯 +「未执行」;M 档展示等待首执行', async () => {
    const w = mountCard({ state: 'idle', lastRunAt: null, lastStatus: '' })
    await flushPromises()
    expect(w.find('[data-testid="wb-card-fn:7"]').text()).toContain('未执行')
    w.unmount()
  })

  it('执行中:运行灯(保留上次结果);正常/失败换灯', async () => {
    const run = mountCard({ state: 'running', lastRunAt: new Date().toISOString(), lastStatus: 'passed' })
    await flushPromises()
    expect(run.find('[data-testid="wb-card-fn:7"]').text()).toContain('执行中')
    run.unmount()

    const ok = mountCard({ state: 'idle', lastRunAt: new Date().toISOString(), lastStatus: 'passed' })
    await flushPromises()
    expect(ok.find('.fn-dot').classes()).toContain('ok')
    ok.unmount()

    const bad = mountCard({ state: 'idle', lastRunAt: new Date().toISOString(), lastStatus: 'failed', lastError: 'connect refused' })
    await flushPromises()
    expect(bad.find('.fn-dot').classes()).toContain('bad')
    expect(bad.text()).toContain('connect refused')
    bad.unmount()
  })

  it('过期(stale):置灰 +「数据可能过期」提示;已移除:可删卡提示', async () => {
    const old = new Date(Date.now() - 3 * 3600_000).toISOString()
    const w = mountCard({ state: 'idle', lastRunAt: old, lastStatus: 'passed', stale: true })
    await flushPromises()
    expect(w.text()).toContain('数据可能过期')
    expect(w.text()).toContain('超过 1 小时未刷新')
    w.unmount()

    const rm = mountCard({ state: 'removed' })
    await flushPromises()
    expect(rm.text()).toContain('已移除')
    rm.unmount()
  })

  it('L 档立即执行:调 runIntegrationTask 并刷新;失败走 toast', async () => {
    vi.mocked(api.runIntegrationTask).mockResolvedValue({
      result: { status: 'passed', durationMs: 1200, error: '' },
      instance: { state: 'idle', enabled: true, lastStatus: 'passed',
        lastRunAt: null, lastError: '', pausedReason: '',
        nextRunAt: null, failStreak: 0 },
    } as never)
    const w = mountCard({ state: 'idle', lastRunAt: null, lastStatus: '' }, 'L')
    await flushPromises()
    await w.find('[data-testid="fn-card-fn:7-run"]').trigger('click')
    await flushPromises()
    expect(api.runIntegrationTask).toHaveBeenCalledWith(7)
    expect(api.fetchFunctionCards).toHaveBeenCalledTimes(2)   // 挂载 + 执行后刷新
    w.unmount()
  })
})
