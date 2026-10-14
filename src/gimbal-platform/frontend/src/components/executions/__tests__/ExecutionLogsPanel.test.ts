/**
 * ExecutionLogsPanel — 面板核心逻辑单测(批 3)。
 *
 * 走 mock fetch 流:验证 ①tail 帧插入按 (ts,id) 排序(晚到行插上位);
 * ②done 帧收口;③筛选变更重连(带参);④open/close 生命周期(收起断流)。
 * 视口锚定依赖布局(offsetTop),jsdom 全 0,断言其逻辑分支不炸即可。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExecutionLogsPanel from '@/components/executions/ExecutionLogsPanel.vue'
import { useAuthStore } from '@/stores/auth'

function sseResp(frames: string[]): Response {
  const enc = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      for (const f of frames) c.enqueue(enc.encode(f))
      c.close()
    },
  })
  return { ok: true, status: 200, body: stream } as unknown as Response
}

function logFrame(id: number, ts: string, msg: string, extra: object = {}): string {
  return `id: ${id}\nevent: log\ndata: ${JSON.stringify({
    id, ts, level: 'INFO', category: 'core', step: null, message: msg, ...extra,
  })}\n\n`
}

const URLs: string[] = []

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().accessToken = 'tok'
  URLs.length = 0
})

describe('ExecutionLogsPanel', () => {
  it('tail 帧按 (ts,id) 插入排序(晚到行插上位),done 收口', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => {
      URLs.push(url)
      return sseResp([
        logFrame(3, '2026-10-14T01:00:03Z', 'third-ts'),
        logFrame(1, '2026-10-14T01:00:01Z', 'first-ts'),   // 晚到但 ts 早 → 插上位
        logFrame(2, '2026-10-14T01:00:02Z', 'second-ts'),
        'id: 4\nevent: done\ndata: {"status":"done"}\n\n',
      ])
    }))
    const w = mount(ExecutionLogsPanel, { props: { executionId: 9, running: false } })
    w.vm.open()
    await flushPromises()
    const msgs = w.findAll('.log-msg').map((n) => n.text())
    expect(msgs).toEqual(['first-ts', 'second-ts', 'third-ts'])
    expect(w.find('[data-testid="logs-state"]').text()).toContain('已收口')
    w.unmount()
  })

  it('筛选变更重连并带服务端参数;close 断流(abort 在飞)', async () => {
    const calls: { url: string; signal: AbortSignal }[] = []
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string, init: RequestInit) => {
      calls.push({ url, signal: init.signal as AbortSignal })
      URLs.push(url)
      return sseResp([logFrame(1, '2026-10-14T01:00:00Z', 'a')])
    }))
    const w = mount(ExecutionLogsPanel, { props: { executionId: 9, running: true } })
    w.vm.open()
    await flushPromises()
    await new Promise((r) => setTimeout(r, 50))   // 让首连泵稳定(connState=live)

    // 级别筛选变更 → 重连,URL 带 level_min(全量环境下重连 fetch
    // 可能稍滞后,轮询等待而非单次 flushPromises)
    const levelSelect = w.find('[data-testid="logs-level"]')
    await levelSelect.setValue('WARNING')
    for (let i = 0; i < 50 && !URLs.some((u) => u.includes('level_min=WARNING')); i++) {
      await new Promise((r) => setTimeout(r, 10))
    }
    expect(URLs.some((u) => u.includes('level_min=WARNING'))).toBe(true)

    // close:断流 —— 后续不再有新 fetch(退避重连被 generation 作废)
    const callsBefore = calls.length
    w.vm.close()
    await new Promise((r) => setTimeout(r, 30))
    expect(calls.length).toBe(callsBefore)
  })

  it('404 → 连接失败态(执行已删)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      { ok: false, status: 404 } as Response))
    const w = mount(ExecutionLogsPanel, { props: { executionId: 404, running: false } })
    w.vm.open()
    await flushPromises()
    expect(w.find('[data-testid="logs-state"]').text()).toContain('连接失败')
    w.unmount()
  })
})
