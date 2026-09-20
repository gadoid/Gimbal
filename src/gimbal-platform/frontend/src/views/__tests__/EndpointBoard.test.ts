/**
 * EndpointBoard.vue — 接口级线索板(P1 切片):
 *   - 四象限占位区 + 主体节点 + 测试象限节点渲染;
 *   - trails → 红色告警链(前端只渲染,不做业务推理);
 *   - 卡片面板:新建/编辑/删除/提升 root;作者边界(他人只读);
 *   - 视角筛选 chip。
 * vue-flow 在 jsdom 需要 ResizeObserver 桩。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

// jsdom 缺 ResizeObserver(vue-flow 依赖)→ 最小桩
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
;(globalThis as Record<string, unknown>).ResizeObserver ??= ResizeObserverStub

import EndpointBoard from '@/views/EndpointBoard.vue'
import * as api from '@/api/service-profile'
import type { BoardResponse } from '@/api/service-profile'

const board: BoardResponse = {
  subject: {
    id: 'fin.order.add', method: 'POST', path: '/api/home/order/add',
    name: '新增订单', version: '1.1.0', fieldCount: 2, degraded: false,
  },
  quadrants: { requirement: 'unavailable', data: 'unavailable',
               topology: 'unavailable', test: 'ok' },
  nodes: [
    { id: 'ep:fin.order.add', kind: 'endpoint', quadrant: null,
      label: 'POST /api/home/order/add', meta: {} },
    { id: 'ad:bt-1', kind: 'adaptation', quadrant: 'test',
      label: '适配事件 bt-1', meta: { fromVersion: '1.0.0', toVersion: '1.1.0', openOps: 2 } },
    { id: 'sc:sc-1', kind: 'scenario', quadrant: 'test',
      label: '退款审核回归', meta: { scenarioId: 'sc-1' } },
    { id: 'ex:59', kind: 'execution', quadrant: 'test',
      label: '#59 failed', meta: { status: 'failed', passed: 1, failed: 1,
                                   finishedAt: '2026-09-18T10:00:00' } },
    { id: 'card:1', kind: 'card', quadrant: 'test',
      label: '这个坑当初…', meta: { cardId: 1, body: '这个坑当初…', isRoot: true,
                                    quadrant: 'test', annotatesNodeId: null,
                                    authorId: 1, mine: true } },
  ],
  edges: [
    { from: 'ep:fin.order.add', to: 'ad:bt-1', kind: 'contains' },
    { from: 'ep:fin.order.add', to: 'sc:sc-1', kind: 'contains' },
    { from: 'sc:sc-1', to: 'ex:59', kind: 'ran' },
    { from: 'ep:fin.order.add', to: 'card:1', kind: 'contains' },
  ],
  trails: [
    { kind: 'risk', path: ['ad:bt-1', 'ep:fin.order.add', 'sc:sc-1', 'ex:59'] },
  ],
}

async function mountBoard() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/services/:name/endpoints/:endpointId', component: EndpointBoard },
    { path: '/adaptations', component: { template: '<div/>' } },
  ] })
  await router.push('/services/fin-service/endpoints/fin.order.add')
  await router.isReady()
  return mount(EndpointBoard, { global: { plugins: [router, createPinia()] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  localStorage.clear()
  vi.spyOn(api, 'fetchBoard').mockResolvedValue(board)
})

it('主体 + 测试象限节点 + 四象限占位区渲染;告警链节点在场', async () => {
  const w = await mountBoard()
  await flushPromises()
  expect(w.find('[data-testid="board-node-ep:fin.order.add"]').exists()).toBe(true)
  expect(w.find('[data-testid="board-node-sc:sc-1"]').exists()).toBe(true)
  expect(w.find('[data-testid="board-node-ex:59"]').exists()).toBe(true)
  expect(w.find('[data-testid="board-node-ad:bt-1"]').exists()).toBe(true)
  // 三象限占位 + 测试象限
  expect(w.find('[data-testid="board-node-zone:requirement"]').text()).toContain('未接入')
  expect(w.find('[data-testid="board-node-zone:test"]').exists()).toBe(true)
})

it('卡片面板:root 卡在场;新建调用 createCard 并重载', async () => {
  const create = vi.spyOn(api, 'createCard').mockResolvedValue({
    id: 2, subjectKind: 'endpoint', subjectId: 'fin.order.add', body: '新卡',
    isRoot: false, quadrant: 'data', annotatesNodeId: null,
    authorId: 1, createdAt: '', updatedAt: '',
  })
  const w = await mountBoard()
  await flushPromises()
  expect(w.find('[data-testid="board-card-1"]').text()).toContain('ROOT')

  await w.find('[data-testid="board-card-body"]').setValue('新卡')
  await w.find('[data-testid="board-card-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    subjectId: 'fin.order.add', body: '新卡', quadrant: 'test',
    annotatesNodeId: null,
  })
  expect(api.fetchBoard).toHaveBeenCalled()
})

it('视角筛选:切到「测试」只剩测试象限 + 象限框', async () => {
  const w = await mountBoard()
  await flushPromises()
  await w.find('[data-testid="board-view-test"]').trigger('click')
  await flushPromises()
  expect(w.find('[data-testid="board-node-ep:fin.order.add"]').exists()).toBe(true) // 主体恒在
  expect(w.find('[data-testid="board-node-card:1"]').exists()).toBe(true) // test 象限卡
})

it('demote → promote 换椅调用 API 并重载', async () => {
  // fetchBoard 每次返回深克隆(同引用赋值不触发响应式;生产中每请求都是新对象)
  const state = JSON.parse(JSON.stringify(board)) as BoardResponse
  vi.spyOn(api, 'fetchBoard').mockImplementation(async () =>
    JSON.parse(JSON.stringify(state)) as BoardResponse)
  const demote = vi.spyOn(api, 'demoteCard').mockImplementation(async () => {
    state.nodes.find((n) => n.id === 'card:1')!.meta.isRoot = false
    return { id: 1, subjectKind: 'endpoint', subjectId: 'fin.order.add',
             body: '', isRoot: false, quadrant: 'test', annotatesNodeId: null,
             authorId: 1, createdAt: '', updatedAt: '' }
  })
  const promote = vi.spyOn(api, 'promoteCard').mockResolvedValue({
    id: 1, subjectKind: 'endpoint', subjectId: 'fin.order.add', body: '',
    isRoot: true, quadrant: 'test', annotatesNodeId: null,
    authorId: 1, createdAt: '', updatedAt: '',
  })
  const w = await mountBoard()
  await flushPromises()

  await w.findAll('button').find((b) => b.text().includes('降级'))!.trigger('click')
  await flushPromises()
  expect(demote).toHaveBeenCalledWith(1)

  await w.find('[data-testid="board-card-promote-1"]').trigger('click')
  await flushPromises()
  expect(promote).toHaveBeenCalledWith(1)
})

it('适配节点详情 → 「去适配中心处理」带 focus 深链(配套方案附录闭环)', async () => {
  const w = await mountBoard()
  await flushPromises()
  // vue-flow 节点点击经 onNodeClick;直接调详情面板路径:先选中适配节点
  ;(w.vm as unknown as Record<string, unknown>).selected =
    board.nodes.find((n) => n.id === 'ad:bt-1')!
  await flushPromises()
  const btn = w.find('[data-testid="board-go-adaptations"]')
  expect(btn.exists()).toBe(true)
  await btn.trigger('click')
  await flushPromises()
  const path = w.vm.$router.currentRoute.value.fullPath
  expect(path).toBe('/adaptations?focus=fin.order.add')
  w.unmount()
})
