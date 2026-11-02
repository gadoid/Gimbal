/** InboundActivityPanel — 别名页排查面(收尾评审 2026-11-02 G3/G5):
 * 经由本别名的执行列表 + 回调投递列表;失败/已送达行可补发(新建一行),
 * pending 行无补发按钮;执行号可跳详情。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import InboundActivityPanel from '@/components/integration/InboundActivityPanel.vue'
import * as execApi from '@/api/executions'
import * as whApi from '@/api/webhook-deliveries'

vi.mock('@/api/executions', () => ({ listExecutions: vi.fn() }))
vi.mock('@/api/webhook-deliveries', () => ({
  listWebhookDeliveries: vi.fn(), redeliverWebhook: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/errorFallback', () => ({ showError: vi.fn() }))

function delivery(over: Partial<whApi.WebhookDeliveryRow>): whApi.WebhookDeliveryRow {
  return {
    id: 1, aliasName: 'agent-sys', eventType: 'execution.finished',
    executionId: 42, instanceId: null, url: 'https://cb/x', status: 'failed',
    attempts: 5, lastError: 'HTTP 503', nextRetryAt: null, deliveredAt: null,
    createdAt: '2026-11-02T00:00:00Z', body: '{}', ...over,
  }
}

async function mountPanel(): Promise<{ w: ReturnType<typeof mount>; router: Router }> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/executions/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const w = mount(InboundActivityPanel, {
    props: { aliasName: 'agent-sys' },
    global: { plugins: [router] },
  })
  await flushPromises()
  return { w, router }
}

describe('InboundActivityPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(execApi.listExecutions).mockResolvedValue({
      items: [
        { id: 42, scenario_id: 'sc-1', scenario_display_name: '日结',
          status: 'done', started_at: '2026-11-02T00:00:00Z',
          finished_at: '2026-11-02T00:01:00Z' } as never,
      ],
      total: 1, page: 1, pageSize: 20, failedTotal: 0,
    } as never)
    vi.mocked(whApi.listWebhookDeliveries).mockResolvedValue([
      delivery({ id: 1, status: 'failed' }),
      delivery({ id: 2, status: 'pending', attempts: 1, lastError: null }),
      delivery({ id: 3, status: 'delivered', attempts: 1, lastError: null }),
    ])
  })

  it('按别名拉执行与投递;失败/已送达行有补发,pending 行没有', async () => {
    const { w } = await mountPanel()
    expect(execApi.listExecutions).toHaveBeenCalledWith({ callerAlias: 'agent-sys', limit: 20 })
    expect(whApi.listWebhookDeliveries).toHaveBeenCalledWith({ aliasName: 'agent-sys', limit: 20 })
    const ex = w.find('[data-testid="alias-executions"]')
    expect(ex.exists()).toBe(true)
    expect(ex.text()).toContain('日结')
    expect(ex.text()).toContain('完成')
    expect(w.find('[data-testid="redeliver-1"]').exists()).toBe(true)
    expect(w.find('[data-testid="redeliver-2"]').exists()).toBe(false)
    expect(w.find('[data-testid="redeliver-3"]').exists()).toBe(true)
    expect(w.find('[data-testid="alias-deliveries"]').text()).toContain('HTTP 503')
  })

  it('补发调接口后重拉列表', async () => {
    vi.mocked(whApi.redeliverWebhook).mockResolvedValue({
      ...delivery({ id: 9, status: 'pending', attempts: 0 }), redeliveredFrom: 1,
    })
    const { w } = await mountPanel()
    await w.find('[data-testid="redeliver-1"]').trigger('click')
    await flushPromises()
    expect(whApi.redeliverWebhook).toHaveBeenCalledWith(1)
    expect(whApi.listWebhookDeliveries).toHaveBeenCalledTimes(2)
  })

  it('执行号跳转执行详情', async () => {
    const { w, router } = await mountPanel()
    await w.find('[data-testid="exec-link-42"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/executions/42')
  })

  it('空列表显示占位', async () => {
    vi.mocked(execApi.listExecutions).mockResolvedValue(
      { items: [], total: 0, page: 1, pageSize: 20, failedTotal: 0 } as never)
    vi.mocked(whApi.listWebhookDeliveries).mockResolvedValue([])
    const { w } = await mountPanel()
    expect(w.text()).toContain('尚无经由本别名的执行')
    expect(w.text()).toContain('尚无回调投递记录')
  })
})
