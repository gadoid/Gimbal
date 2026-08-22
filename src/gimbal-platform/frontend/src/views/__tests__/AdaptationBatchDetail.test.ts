/**
 * AdaptationBatchDetail —— 批次工作台(§6,admin-only):
 *   - ops 按状态渲染(pending 有操作组,applied/conflict 无);
 *   - 应用 → applyOp + 重载;
 *   - member 直入 → getBatch 403 admin_only → 「仅管理员」占位(§8);
 *   - 合并:selection → 种子 → 构造成功后 skip 两条源 op;取消 → 清种子;
 *   - 回滚:确认 → rollbackBatch → restored/conflicts 面板。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus, { ElMessageBox } from 'element-plus'
import AdaptationBatchDetail from '@/views/AdaptationBatchDetail.vue'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api/adaptations'
import { ApiError } from '@/api/http'
import * as scenarioApi from '@/api/scenario-composer'

const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{ api: { view_hints: {}, headers: {}, query: {} },
            request: { body: { amount: '${var.amount}', legacy_field: 'L',
                               settle_type: '1' } } }],
  config: { vars: { amount: 100 } },
  dataSetCount: 0, stepCount: 1, tags: [],
} as never

function opIn(id: number, opType: string, payload: Record<string, unknown>,
              status = 'pending'): api.OpOut {
  return {
    id, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null, opType,
    payload, status: status as api.OpOut['status'], appliedAt: null,
    note: null,
  } as api.OpOut
}

const detail: api.BatchDetail = {
  batchId: 'bt-1', endpointId: 'fin.order.add', fromVersion: '1.0.0',
  toVersion: '1.1.0', status: 'open', operatorId: 1,
  createdAt: '2026-08-22T10:00:00Z', closedAt: null,
  opCounts: { pending: 3 },
  ops: [
    opIn(11, 'addField', { step: 0, field: 'extra', value: 'E' }),
    opIn(12, 'removeField', { step: 0, field: 'legacy_field' }),
    opIn(13, 'mapValue', { step: 0, field: 'settle_type', map: {} },
         'conflict'),
  ],
  snapshots: [
    { entityType: 'scenario', entityId: 'sc-1' },
    { entityType: 'dataset', entityId: 'ds-1' },
  ],
}

function login(admin: boolean) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = { id: admin ? 1 : 2, username: 'u', is_admin: admin } as never
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/adaptations/batches/:batchId', component: { template: '<div/>' } },
      { path: '/adaptations', component: { template: '<div/>' } },
    ],
  })
  router.push('/adaptations/batches/bt-1')
  await router.isReady()
  const w = mount(AdaptationBatchDetail, {
    global: { plugins: [router, ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('AdaptationBatchDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'getBatch').mockResolvedValue(detail)
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
  })

  it('头部 + ops 按状态渲染:pending 有操作组,conflict 只显示状态', async () => {
    login(true)
    const w = await mountPage()

    expect(w.text()).toContain('fin.order.add')
    expect(w.text()).toContain('1.0.0 → 1.1.0')
    const rows = w.findAll('.op-row')
    expect(rows.length).toBe(3)
    expect(rows[0].findAll('.op-action').length).toBeGreaterThan(0)  // pending
    expect(rows[2].findAll('.op-action').length).toBe(0)             // conflict
    expect(w.text()).toContain('快照')
    expect(w.text()).toContain('sc-1')
    w.unmount()
  })

  it('应用一条 pending op → applyOp(id) + 重载', async () => {
    login(true)
    const applySpy = vi.spyOn(api, 'applyOp').mockResolvedValue(
      opIn(11, 'addField', {}, 'applied'))
    const w = await mountPage()

    await w.findAll('.op-row')[0].find('[data-action="apply"]').trigger('click')
    await flushPromises()

    expect(applySpy).toHaveBeenCalledWith(11)
    expect(api.getBatch).toHaveBeenCalledTimes(2)   // 初载 + 重载
    w.unmount()
  })

  it('member:getBatch 403 admin_only → 「仅管理员」占位(工作台不可达)', async () => {
    login(false)
    // 真实 member 路径:GET /batches/{id} 为 admin-only → 403 admin_only
    // (后端 detail 为字符串,http.ts 归一为 status=403,code=0)
    vi.mocked(api.getBatch).mockRejectedValue(
      new ApiError(403, 0, 'admin_only: adaptation routes require an administrator'))
    const w = await mountPage()

    expect(w.text()).toContain('仅管理员')
    expect(w.find('.op-row').exists()).toBe(false)     // 工作台不渲染
    expect(w.text()).not.toContain('批次不存在或已清理')  // 非 404 空态
    expect(w.text()).not.toContain('fin.order.add')
    w.unmount()
  })

  it('合并:选中一删一增 → 构造 renameField 成功后 skip 两条源 op', async () => {
    login(true)
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue(
      opIn(99, 'renameField', { step: 0, from: 'legacy_field', to: 'extra' }))
    const skipSpy = vi.spyOn(api, 'skipOp').mockImplementation(
      (id: number) => Promise.resolve(opIn(id, 'removeField', {}, 'skipped')))
    const w = await mountPage()
    const vm = w.vm as unknown as {
      selectedOps: api.OpOut[]
      startMerge: () => void
    }

    vm.selectedOps = [detail.ops[0], detail.ops[1]]   // add + remove 同 step
    await vm.startMerge()

    // startMerge 只打开预填对话框(§6.3);listScenarios 未 mock(真实请求
    // 必败 → 下拉为空),经 defineExpose({form, submit}) 契约手填场景并提交
    const dlg = w.findComponent(OpConstructDialog)
    const dvm = dlg.vm as unknown as {
      form: { scenarioId: string }
      submit: () => Promise<void>
    }
    dvm.form.scenarioId = 'sc-1'
    await dvm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameField', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    expect(skipSpy).toHaveBeenCalledWith(11)
    expect(skipSpy).toHaveBeenCalledWith(12)
    expect(api.getBatch).toHaveBeenCalledTimes(2)      // 末尾重载
    w.unmount()
  })

  it('回滚:确认 → rollbackBatch → restored/conflicts 面板', async () => {
    login(true)
    vi.spyOn(ElMessageBox, 'confirm')
      .mockResolvedValue('confirm' as never)   // 只关心 resolve,值不用于类型
    const rbSpy = vi.spyOn(api, 'rollbackBatch').mockResolvedValue({
      batchId: 'bt-1', status: 'rolled_back',
      restored: [{ entityType: 'scenario', entityId: 'sc-1' }],
      conflicts: [
        { entityType: 'dataset', entityId: 'ds-1', note: '恢复写入被拒,已跳过' },
      ],
    })
    const w = await mountPage()

    await w.find('[data-action="rollback"]').trigger('click')
    await flushPromises()

    expect(rbSpy).toHaveBeenCalledWith('bt-1')
    expect(w.text()).toContain('sc-1')
    expect(w.text()).toContain('恢复写入被拒,已跳过')
    w.unmount()
  })
})
