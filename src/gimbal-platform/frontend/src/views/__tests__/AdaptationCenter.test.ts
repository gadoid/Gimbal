/**
 * AdaptationCenter —— 总览页双形态(spec §3/§5):
 *   admin:未索引警示 + 待适配卡片(C12 异常卡无开批次入口)+ 全量批次表;
 *   member:无警示/无卡片,批次表走 scope=mine 且零 diff 调用;
 *   抽屉 [开批次] → openBatch → 跳工作台。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import AdaptationCenter from '@/views/AdaptationCenter.vue'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api/adaptations'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/adaptations', component: { template: '<div/>' } },
      { path: '/adaptations/batches/:batchId', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
}

function login(admin: boolean) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = { id: admin ? 1 : 2, username: 'u', is_admin: admin } as never
  return auth
}

async function mountPage() {
  const router = makeRouter()
  router.push('/adaptations')
  await router.isReady()
  const w = mount(AdaptationCenter, { global: { plugins: [router, ElementPlus] } })
  await flushPromises()
  return { w, router }
}

const batches = [{
  batchId: 'bt-1', endpointId: 'fin.order.add', fromVersion: '1.0.0',
  toVersion: '1.1.0', status: 'completed' as const, operatorId: 1,
  createdAt: '2026-08-22T10:00:00Z', closedAt: null, opCounts: { applied: 3 },
}]

describe('AdaptationCenter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('admin:待适配卡片 + C12 异常卡(无开批次)+ 批次表 + 未索引警示', async () => {
    login(true)
    const diffSpy = vi.spyOn(api, 'catalogDiff').mockResolvedValue({
      pending: [{ endpointId: 'fin.order.add', fromVersion: '1.0.0',
                  toVersion: '1.1.0' }],
      anomalies: [{ endpointId: 'fin.order.cancel', reason: 'version_not_bumped',
                    detail: 'updated_at 动了但 version 未动' }],
      baselinedNow: 0,
    } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue(
      [{ scenarioId: 'sc-x', stepIndex: 0, reason: 'no_endpoint_id' }] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue(batches as never)

    const { w } = await mountPage()

    expect(diffSpy).toHaveBeenCalledTimes(1)   // 打开页面强制刷新(D3)
    expect(w.text()).toContain('1 个步骤缺 endpoint_id')
    expect(w.findAll('.card.pending').length).toBe(1)
    const anomaly = w.find('.card.anomaly')
    expect(anomaly.exists()).toBe(true)
    expect(anomaly.text()).toContain('fin.order.cancel')
    expect(anomaly.find('button').exists()).toBe(false)   // C12:异常卡无开批次
    expect(w.text()).toContain('bt-1')
    w.unmount()
  })

  it('admin:空态与 diff 失败保留旧数据', async () => {
    login(true)
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(
      { pending: [], anomalies: [], baselinedNow: 1 } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue([] as never)

    const { w } = await mountPage()
    expect(w.text()).toContain('目录无待适配变更')
    w.unmount()

    // 失败:页面显示错误,不崩
    vi.spyOn(api, 'catalogDiff').mockRejectedValue(
      Object.assign(new Error('boom'), { status: 502 }))
    const { w: w2 } = await mountPage()
    expect(w2.find('.el-alert--error').exists()).toBe(true)
    w2.unmount()
  })

  it('member:仅批次表(scope=mine + 提示),零 diff/unindexed 调用', async () => {
    login(false)
    const diffSpy = vi.spyOn(api, 'catalogDiff')
    const unindexedSpy = vi.spyOn(api, 'unindexedSteps')
    const listSpy = vi.spyOn(api, 'listBatches').mockResolvedValue(
      batches as never)

    const { w } = await mountPage()

    expect(listSpy).toHaveBeenCalledWith('mine')
    expect(diffSpy).not.toHaveBeenCalled()
    expect(unindexedSpy).not.toHaveBeenCalled()
    expect(w.find('.unindexed-alert').exists()).toBe(false)
    expect(w.findAll('.card').length).toBe(0)
    expect(w.text()).toContain('仅显示触碰你场景的批次')
    w.unmount()
  })

  it('member:批次表 renders own batch rows', async () => {
    login(false)
    vi.spyOn(api, 'listBatches').mockResolvedValue(batches as never)
    const { w } = await mountPage()
    expect(w.text()).toContain('bt-1')
    w.unmount()
  })

  it('抽屉 [开批次] → openBatch → 跳工作台', async () => {
    login(true)
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(
      { pending: [{ endpointId: 'fin.order.add', fromVersion: '1.0.0',
                    toVersion: '1.1.0' }], anomalies: [], baselinedNow: 0 } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue([] as never)
    vi.spyOn(api, 'impact').mockResolvedValue([] as never)
    const openSpy = vi.spyOn(api, 'openBatch').mockResolvedValue({
      batchId: 'bt-9', endpointId: 'fin.order.add', fromVersion: '1.0.0',
      toVersion: '1.1.0', status: 'open', operatorId: 1,
      createdAt: '2026-08-22T10:00:00Z', closedAt: null,
      opCounts: { pending: 3 }, ops: [], snapshots: [],
    } as never)

    const { w, router } = await mountPage()
    // 点待适配卡片 → 抽屉打开;抽屉 emit openBatch → 视图调 API 并跳转
    await w.find('.card.pending').trigger('click')
    const drawer = w.findComponent(ImpactDrawer)
    expect(drawer.props('modelValue')).toBe(true)
    expect(drawer.props('endpointId')).toBe('fin.order.add')

    drawer.vm.$emit('openBatch')
    await flushPromises()

    expect(openSpy).toHaveBeenCalledWith('fin.order.add')
    expect(router.currentRoute.value.path).toBe('/adaptations/batches/bt-9')
    w.unmount()
  })
})
