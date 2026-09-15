/**
 * DataSetEditor 变量锁定(var-lock spec §2):
 * 锁定未放开的列沉底/只读/带锁徽标;本地放开写 varUnlocks(wire 键 camelCase);
 * 恢复默认 = 清全部行键 + 撤放开;TSV 拒写;CSV 导出排除 + 导入跳过提示。
 * 骨架(api mock + mountEditor)复制 DataSetEditor.varview.test.ts。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'ds-1' } }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('@/api/query-views', () => ({
  fetchQueryViewIndex: vi.fn(async () => []),
  fetchQueryViewRows: vi.fn(async () => ({ view: '', rows: [], truncated: false, fetched_at: '', cached: false, stale: false })),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '@/views/DataSetEditor.vue'

/** env(锁定过程变量)+ amount(业务变量);env 有历史行覆盖。 */
const DEF_LOCKED = {
  kind: 'scenario', scenarioId: 'sc-ds', meta: { name: 's' },
  config: { vars: { env: 'qa', amount: 100 }, var_locks: ['env'] },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} }, request: { kind: 'request', body: { env: '${var.env}', amount: '${var.amount}' } }, strategy: [] },
  ],
}

/** mountEditor:varUnlocks(wire 键)由 getDataSet 回显(默认 [])*/
async function mountEditor(
  def: typeof DEF_LOCKED,
  rows: Array<Record<string, any>> = [{ amount: '-1', env: 'prod' }],
  varUnlocks: string[] = [],
) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: def, orchestration: { steps: def.steps.map((s: any) => ({ name: s.description })), resourceMeta: {} } } as any,
  )
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'getDataSet').mockResolvedValue(
    { name: 'n', description: '', rows, varUnlocks: varUnlocks } as any,
  )
  vi.spyOn(api, 'getFullEndpoint').mockImplementation(async (eid: string) => ({
    id: eid, request: { declarations: [] },
  } as any))
  const w = mount(DataSetEditor, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => { setActivePinia(createPinia()); routerMock.push.mockReset() })
afterEach(() => { vi.restoreAllMocks() })

describe('DataSetEditor — 锁定列编辑面(var-lock)', () => {
  it('LOCK-1: 锁定列沉底 + 锁徽标;未锁定列在前', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const heads = w.findAll('.row-field .th-data').map((t) => t.text())
    expect(heads[0]).toContain('amount')            // 业务变量在前
    expect(heads[1]).toContain('env')               // 锁定列沉底
    expect(heads[1]).toContain('🔒')                 // 锁徽标
    w.unmount()
  })

  it('LOCK-2: 锁定格只读;历史覆盖格带信息提示', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const cells = w.findAll('input.data-cell-input')
    // 列序 [amount, env] → env 格 = 第 2 数据列
    expect(cells[1].attributes('readonly')).toBeDefined()
    const envTd = w.findAll('.row-data td.td-data')[1]
    expect(envTd.attributes('title')).toContain('已锁定为过程变量,本数据集使用自有值')
    w.unmount()
  })

  it('LOCK-3: 列头「放开」→ varUnlocks 增员 + 格可编辑;「收回」逆操作', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const unlockBtn = w.findAll('button.col-unlock').find((b) => b.text().includes('放开'))
    expect(unlockBtn).toBeTruthy()
    await unlockBtn!.trigger('click')
    await flushPromises()
    expect((w.vm as any).varUnlocks).toEqual(['env'])
    expect(w.findAll('input.data-cell-input')[1].attributes('readonly')).toBeUndefined()
    const relockBtn = w.findAll('button.col-unlock').find((b) => b.text().includes('收回'))
    await relockBtn!.trigger('click')
    await flushPromises()
    expect((w.vm as any).varUnlocks).toEqual([])
    w.unmount()
  })

  it('LOCK-4: 恢复默认 = 清该变量全部行键 + 撤销本地放开', async () => {
    const w = await mountEditor(DEF_LOCKED, [{ amount: '-1', env: 'prod' }, { amount: '2', env: 'staging' }], ['env'])
    const resetBtn = w.findAll('button.col-reset').find((b) => b.text().includes('恢复默认'))
    expect(resetBtn).toBeTruthy()
    await resetBtn!.trigger('click')
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: '-1' }, { amount: '2' }])
    expect((w.vm as any).varUnlocks).toEqual([])
    w.unmount()
  })

  it('LOCK-5: TSV 粘贴对未放开锁定列拒写(不落键,提示)', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const envCell = w.findAll('input.data-cell-input')[1]
    const evt = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(evt, 'clipboardData', { value: { getData: () => 'a\nb' } })
    await envCell.element.dispatchEvent(evt)
    await flushPromises()
    expect((w.vm as any).rows).toEqual([{ amount: '-1', env: 'prod' }])  // 未动
    w.unmount()
  })

  it('LOCK-6: CSV 导出排除锁定列(本地放开的不排除)', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const csv = await import('@/utils/csv-dataset')
    const exportSpy = vi.spyOn(csv, 'exportDataSetCsv').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('导出 CSV'))
    await btn!.trigger('click')
    await flushPromises()
    const args = exportSpy.mock.calls[0][0] as any
    expect(args.columns.map((c: any) => c.varName)).toEqual(['amount'])   // env 排除
    // 本地放开后 → 导出带回
    const unlockBtn = w.findAll('button.col-unlock').find((b) => b.text().includes('放开'))
    await unlockBtn!.trigger('click')
    await flushPromises()
    exportSpy.mockClear()
    await btn!.trigger('click')
    await flushPromises()
    expect((exportSpy.mock.calls[0][0] as any).columns.map((c: any) => c.varName))
      .toEqual(['amount', 'env'])
    w.unmount()
  })

  it('LOCK-7: CSV 导入带锁定列(旧模板)→ 跳过写键 + skippedLocked 提示分流', async () => {
    const w = await mountEditor(DEF_LOCKED)
    const csv = await import('@/utils/csv-dataset')
    const importSpy = vi.spyOn(csv, 'importDataSetCsv').mockReturnValue({
      rows: [{ amount: '9' }], caseNames: ['data-1'], errors: [], skippedLocked: ['env'],
    } as any)
    const file = new File(['x'], 't.csv', { type: 'text/csv' })
    await (w.vm as any).onImportCsv(file)
    await flushPromises()
    expect(importSpy.mock.calls[0][0].lockedVars).toEqual(['env'])
    expect((w.vm as any).rows).toEqual([{ amount: '9' }])   // env 键未被写入
    w.unmount()
  })

  it('LOCK-8: 保存数据集携带 varUnlocks(wire 键);载入回显', async () => {
    const w = await mountEditor(DEF_LOCKED, [{ amount: '-1', env: 'prod' }], ['env'])
    expect((w.vm as any).varUnlocks).toEqual(['env'])
    const saveSpy = vi.spyOn(api, 'updateDataSet').mockResolvedValue({} as any)
    const store = (w.vm as any).store
    store.saveDataSet = vi.fn(async (_sid: string, _did: string | null, draft: any) => draft)
    const btn = w.findAll('button').find((b) => b.text().includes('保存数据集'))
    await btn!.trigger('click')
    await flushPromises()
    expect(store.saveDataSet).toHaveBeenCalled()
    const draft = store.saveDataSet.mock.calls[0][2]
    expect(draft.varUnlocks).toEqual(['env'])
    saveSpy.mockRestore()
    w.unmount()
  })

  it('LOCK-9: 死放开键(共享侧已删变量)静默忽略,载入/保存不崩', async () => {
    // ghost 不在场景 vars(env/amount)中 = 交叉态死配置(spec §5.4:
    // 编辑器静默忽略、不崩溃不清洗,原样保留)
    const w = await mountEditor(DEF_LOCKED, [{ amount: '-1', env: 'prod' }], ['ghost'])
    expect((w.vm as any).varUnlocks).toEqual(['ghost'])
    const store = (w.vm as any).store
    store.saveDataSet = vi.fn(async (_sid: string, _did: string | null, draft: any) => draft)
    const btn = w.findAll('button').find((b) => b.text().includes('保存数据集'))
    await btn!.trigger('click')
    await flushPromises()
    expect(store.saveDataSet).toHaveBeenCalled()
    expect(store.saveDataSet.mock.calls[0][2].varUnlocks).toEqual(['ghost'])
    w.unmount()
  })
})
