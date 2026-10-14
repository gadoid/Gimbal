/** FunctionCard — 集成功能卡(外部系统集成 §7):状态叠加 + 取数 +
 * 立即执行。def 经 workbenchCardDefKey 注入(fn:<id> 定位自身)。
 * 集成线 v2(I3,§2.5 验收):主状态灯 = 检查结论(pass 绿/fail 红/
 * none 无灯/unknown 灰);运行异常角标 + 主结论置灰 + 上次结论;
 * D13 角标优先级(暂停 > 停用 > 过期);四模板 × 四态不混淆。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FunctionCard from '@/components/workbench/FunctionCard.vue'
import {
  cardSizeKey, workbenchCardDefKey, type WorkbenchCardDef,
} from '../registry'
import * as api from '@/api/integration'

vi.mock('@/api/integration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/integration')>()
  return {
    ...actual,   // RUN_BADGE_TEXT / runAbnormalOf 等映射用真值
    fetchFunctionCards: vi.fn(),
    runIntegrationTask: vi.fn(),
    integrationErr: vi.fn((e: unknown) => String(e)),
  }
})
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

const RAN = new Date().toISOString()
const OLD = new Date(Date.now() - 3 * 3600_000).toISOString()

describe('FunctionCard — 状态叠加(§7 卡片状态表)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('未执行:灰灯 +「未执行」;M 档展示等待首执行', async () => {
    const w = mountCard({ state: 'idle', lastRunAt: null })
    await flushPromises()
    expect(w.find('[data-testid="wb-card-fn:7"]').text()).toContain('未执行')
    w.unmount()
  })

  it('执行中:运行灯(保留上次结果);检查通过/不通过换灯', async () => {
    const run = mountCard({ state: 'running', lastRunAt: RAN, runStatus: 'ok', checkStatus: 'pass' })
    await flushPromises()
    expect(run.find('[data-testid="wb-card-fn:7"]').text()).toContain('执行中')
    run.unmount()

    const ok = mountCard({ state: 'idle', lastRunAt: RAN, runStatus: 'ok', checkStatus: 'pass' })
    await flushPromises()
    expect(ok.find('.fn-dot').classes()).toContain('ok')
    ok.unmount()

    // 断言失败 = run ok + check fail:红灯 + checkMessage
    const bad = mountCard({ state: 'idle', lastRunAt: RAN, runStatus: 'ok',
      checkStatus: 'fail', checkMessage: 'FAIL: expected SUCCESS eq FAILED' })
    await flushPromises()
    expect(bad.find('.fn-dot').classes()).toContain('bad')
    expect(bad.text()).toContain('检查不通过')
    expect(bad.text()).toContain('FAIL: expected SUCCESS eq FAILED')
    bad.unmount()
  })

  it('运行异常:角标 + 主结论置灰 + 上次结论 + lastError;灯不绿', async () => {
    const w = mountCard({ state: 'idle', lastRunAt: RAN, runStatus: 'transport',
      checkStatus: 'pass', checkChangedAt: OLD, lastError: 'connect refused',
      outputs: { mr_count: 3 } })
    await flushPromises()
    expect(w.find('.fn-dot').classes()).toContain('muted')   // 置灰
    expect(w.text()).toContain('网络异常')                     // 角标
    expect(w.text()).toContain('上次结论:通过')               // 保留结论
    expect(w.text()).toContain('connect refused')             // lastError 摘要
    // kv 数据保留不清空(§2.3)
    w.unmount()
  })

  it('过期(stale):提示;暂停/停用角标在场时不叠加(D13)', async () => {
    const w = mountCard({ state: 'idle', lastRunAt: OLD, runStatus: 'ok',
      checkStatus: 'pass', stale: true })
    await flushPromises()
    expect(w.text()).toContain('错过两次触发未刷新')
    w.unmount()

    // 暂停(凭证失效)> 过期:角标在,过期提示不叠加
    const paused = mountCard({ state: 'idle', lastRunAt: OLD,
      runStatus: 'auth', checkStatus: 'unknown', stale: true,
      pausedReason: 'auth_failed' })
    await flushPromises()
    expect(paused.text()).toContain('凭证失效')
    expect(paused.text()).not.toContain('错过两次触发未刷新')
    paused.unmount()

    // 停用 > 过期
    const off = mountCard({ state: 'idle', lastRunAt: OLD, enabled: false,
      runStatus: 'ok', checkStatus: 'pass', stale: true })
    await flushPromises()
    expect(off.text()).toContain('已停用')
    expect(off.text()).not.toContain('错过两次触发未刷新')
    off.unmount()

    // 缺凭证暂停
    const miss = mountCard({ state: 'paused', pausedReason: 'missing_credential' })
    await flushPromises()
    expect(miss.text()).toContain('缺凭证')
    miss.unmount()

    // 已移除
    const rm = mountCard({ state: 'removed' })
    await flushPromises()
    expect(rm.text()).toContain('已移除')
    rm.unmount()
  })

  it('四模板 × {pass, fail, none, 运行异常}:数据区保留、只置灰不清空', async () => {
    // 各模板的取数规则:counter 取首个数值键、list 取首个数组键、kv 全量
    const outputsOf: Record<string, Record<string, unknown>> = {
      status: {},
      kv: { mr_count: 7, state: 'ok' },
      counter: { count: 7 },
      list: { items: ['a', 'b'] },
    }
    const tplKinds = ['status', 'kv', 'counter', 'list'] as const
    const states = [
      { label: 'pass', data: { runStatus: 'ok', checkStatus: 'pass' } },
      { label: 'fail', data: { runStatus: 'ok', checkStatus: 'fail', checkMessage: 'FAIL' } },
      { label: 'none', data: { runStatus: 'ok', checkStatus: 'none' } },
      { label: 'abnormal', data: { runStatus: 'timeout', checkStatus: 'pass' } },
    ]
    for (const kind of tplKinds) {
      for (const st of states) {
        const w = mountCard({ state: 'idle', lastRunAt: RAN,
          outputs: outputsOf[kind], cardTemplate: kind, ...st.data }, 'M')
        await flushPromises()
        const text = w.text()
        // 数据不被运行异常清空
        if (kind === 'kv') expect(text).toContain('mr_count')
        if (kind === 'counter') expect(text).toContain('7')
        if (kind === 'list') expect(text).toContain('2 条')
        if (kind === 'status') {
          expect(text).toContain(
            st.label === 'pass' ? '检查通过'
            : st.label === 'fail' ? '检查不通过'
            : st.label === 'none' ? '运行正常' : '上次结论:通过')
        }
        if (st.label === 'abnormal') expect(text).toContain('超时')
        w.unmount()
      }
    }
  })

  it('none(无断言):无灯只显运行状态(§2.5)', async () => {
    const w = mountCard({ state: 'idle', lastRunAt: RAN, runStatus: 'ok',
      checkStatus: 'none' }, 'M')
    await flushPromises()
    expect(w.find('.fn-dot').exists()).toBe(false)
    expect(w.text()).toContain('运行正常')
    w.unmount()
  })

  it('L 档立即执行:两段式回显(运行状态 · 检查结论)并刷新;失败走 toast', async () => {
    vi.mocked(api.runIntegrationTask).mockResolvedValue({
      result: { status: 'failed', durationMs: 1200, error: '' },
      instance: { state: 'idle', enabled: true,
        lastRunAt: null, lastError: '', pausedReason: '',
        nextRunAt: null, failStreak: 0, runStatus: 'ok',
        checkStatus: 'fail', checkMessage: '期望 SUCCESS 实际 FAILED',
        checkChangedAt: null },
    } as never)
    const w = mountCard({ state: 'idle', lastRunAt: null }, 'L')
    await flushPromises()
    await w.find('[data-testid="fn-card-fn:7-run"]').trigger('click')
    await flushPromises()
    expect(api.runIntegrationTask).toHaveBeenCalledWith(7)
    expect(api.fetchFunctionCards).toHaveBeenCalledTimes(2)   // 挂载 + 执行后刷新
    const { toast } = await import('@/utils/toast')
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining('运行正常 · 检查不通过'))
    w.unmount()
  })
})
