/**
 * AdaptationCenter —— 总览页双形态(spec §3/§5):
 *   admin:未索引警示 + 待适配卡片(C12 异常卡无开批次入口)+ 全量批次表
 *         + carry 漂移面板(T16:三类勾选 → openCarryBatch + createOp);
 *   member:无警示/无卡片,批次表走 scope=mine 且零 diff/drift 调用
 *         (carry 漂移 section 不渲染,后端 drift 为 AdminUser);
 *   抽屉 [开批次] → openBatch → 跳工作台;
 *   plateReachable=False → 清单不渲染 + 警示 + 批生成禁用(T11 硬性契约)。
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
import * as carryApi from '@/api/carry'
import type { ServiceDrift } from '@/api/carry'

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

/** T16 漂移样本:fin.order 三类齐全;fin.settle 对齐(三列表全空)。 */
const drift: ServiceDrift[] = [
  {
    service: 'fin.order',
    orphaned: ['$.legacy_fee'],
    uncovered: ['$.fee'],
    renamedSuggestions: [{ from: '$.legacy_fee', to: '$.fee' }],
  },
  { service: 'fin.settle', orphaned: [], uncovered: [],
    renamedSuggestions: [] },
]

function mockDrift(services: ServiceDrift[] = drift, plateReachable = true) {
  return vi.spyOn(carryApi, 'getDrift')
    .mockResolvedValue({ services, plateReachable })
}

/** admin 挂载常用的四个 api mock(carry 漂移另测)。 */
function mockAdminBasics() {
  vi.spyOn(api, 'catalogDiff').mockResolvedValue(
    { pending: [], anomalies: [], baselinedNow: 0 } as never)
  vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
  vi.spyOn(api, 'listBatches').mockResolvedValue(batches as never)
}

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
    mockDrift([])

    const { w } = await mountPage()

    expect(diffSpy).toHaveBeenCalledTimes(1)   // 打开页面强制刷新(D3)
    expect(w.text()).toContain('1 个步骤缺 endpoint_id')
    expect(w.findAll('.card.pending').length).toBe(1)
    const anomaly = w.find('.card.anomaly')
    expect(anomaly.exists()).toBe(true)
    expect(anomaly.text()).toContain('fin.order.cancel')
    expect(anomaly.find('button').exists()).toBe(false)   // C12:异常卡无开批次
    expect(w.text()).toContain('bt-1')
    // 详情链接(admin-only 入口)对 admin 渲染
    expect(w.find('a[href="/adaptations/batches/bt-1"]').exists()).toBe(true)
    w.unmount()
  })

  it('admin:空态与 diff 失败保留旧数据', async () => {
    login(true)
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(
      { pending: [], anomalies: [], baselinedNow: 1 } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue([] as never)
    mockDrift([])

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

  it('member:仅批次表(scope=mine + 提示),零 diff/unindexed/drift 调用', async () => {
    login(false)
    const diffSpy = vi.spyOn(api, 'catalogDiff')
    const unindexedSpy = vi.spyOn(api, 'unindexedSteps')
    const driftSpy = vi.spyOn(carryApi, 'getDrift')
    const listSpy = vi.spyOn(api, 'listBatches').mockResolvedValue(
      batches as never)

    const { w } = await mountPage()

    expect(listSpy).toHaveBeenCalledWith('mine')
    expect(diffSpy).not.toHaveBeenCalled()
    expect(unindexedSpy).not.toHaveBeenCalled()
    expect(driftSpy).not.toHaveBeenCalled()   // carry section 不渲染(后端 AdminUser)
    expect(w.find('.drift-svc').exists()).toBe(false)
    expect(w.find('.unindexed-alert').exists()).toBe(false)
    expect(w.findAll('.card').length).toBe(0)
    expect(w.text()).toContain('仅显示触碰你场景的批次')
    // 详情列不渲染:工作台为 admin-only,member 链接只会 403(死链)
    expect(w.find('a[href="/adaptations/batches/bt-1"]').exists()).toBe(false)
    expect(w.text()).not.toContain('详情')
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
    mockDrift([])
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

  it('admin:carry 漂移三类勾选 + 对齐服务正向确认(T16)', async () => {
    login(true)
    mockAdminBasics()
    const driftSpy = mockDrift()

    const { w } = await mountPage()

    expect(driftSpy).toHaveBeenCalledTimes(1)   // admin 首进即拉取
    expect(w.text()).toContain('carry 漂移')
    // 三类勾选项(文案由 utils/carry-drift 组装)
    expect(w.text()).toContain('孤儿绑定 $.legacy_fee → 移除')
    expect(w.text()).toContain('未绑定面字段 $.fee → 补绑定')
    expect(w.text()).toContain('改名建议 $.legacy_fee → $.fee')
    expect(w.text()).toContain('3 项漂移 · 2 服务')
    // 对齐服务:正向确认,不渲染空壳(T11 评审契约)
    expect(w.text()).toContain('已检查,无漂移')
    // 无勾选 → 生成按钮禁用
    const gen = w.find('[data-action="carry-generate"]')
    expect(gen.classes()).toContain('is-disabled')
    w.unmount()
  })

  it('admin:plateReachable=False → 警示 + 清单不渲染 + 生成禁用(T11 契约)', async () => {
    login(true)
    mockAdminBasics()
    mockDrift(drift, false)

    const { w } = await mountPage()

    expect(w.find('.el-alert--warning').exists()).toBe(true)
    expect(w.text()).toContain('plate 目录不可达')
    expect(w.text()).toContain('已禁用勾选与批生成')
    expect(w.find('.el-checkbox').exists()).toBe(false)   // 降级清单不渲染
    expect(w.find('.drift-svc').exists()).toBe(false)
    expect(w.find('[data-action="carry-generate"]').classes())
      .toContain('is-disabled')
    w.unmount()
  })

  it('admin:勾选 → openCarryBatch 按服务分批 + createOp 保序 + 跳批详情', async () => {
    login(true)
    mockAdminBasics()
    mockDrift([
      drift[0],
      { service: 'fin.risk', orphaned: ['$.trace_id'], uncovered: [],
        renamedSuggestions: [] },
    ])
    vi.spyOn(api, 'openCarryBatch').mockImplementation(async (svc) => ({
      batchId: `bt-carry-${svc}`, endpointId: `carry:${svc}`,
      fromVersion: '-', toVersion: '-', status: 'open' as const, operatorId: 1,
      createdAt: '2026-08-31T00:00:00Z', closedAt: null, opCounts: {},
      ops: [], snapshots: [],
    }))
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      id: 1, batchId: 'x', scenarioId: null, datasetId: null,
      opType: 'removeCarryBinding', payload: {}, status: 'pending',
      appliedAt: null, note: null,
    } as never)

    const { w, router } = await mountPage()

    // 勾 2 项:fin.order 的孤儿移除 + fin.risk 的孤儿移除
    const boxes = w.findAll('.drift-checks .el-checkbox')
    await boxes[0].find('input').setValue(true)   // fin.order remove
    await boxes[3].find('input').setValue(true)   // fin.risk remove
    expect(w.find('[data-action="carry-generate"]').classes())
      .not.toContain('is-disabled')

    await w.find('[data-action="carry-generate"]').trigger('click')
    await flushPromises()

    // 按服务分批;ops 逐条 createOp,carry 请求体不带 scenarioId 键
    expect(api.openCarryBatch).toHaveBeenCalledWith('fin.order')
    expect(api.openCarryBatch).toHaveBeenCalledWith('fin.risk')
    expect(createSpy).toHaveBeenCalledTimes(2)
    const firstCall = createSpy.mock.calls[0]
    expect(firstCall[0]).toBe('bt-carry-fin.order')
    expect(firstCall[1]).toEqual({
      opType: 'removeCarryBinding',
      payload: { service: 'fin.order', path: '$.legacy_fee' },
    })
    expect('scenarioId' in (firstCall[1] as unknown as Record<string, unknown>)).toBe(false)
    expect(router.currentRoute.value.path).toBe('/adaptations/batches/bt-carry-fin.risk')
    w.unmount()
  })
})
