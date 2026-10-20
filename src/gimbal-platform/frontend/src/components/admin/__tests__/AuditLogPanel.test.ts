// AuditLogPanel.test.ts — 审计面板专项(2026-10-20 分页修复批次)。
// 钉住的回归:此前 page 只是 Pagination 的 v-model、没有任何 watcher,
// 点页码只改本地状态不重拉 → 「翻页没反应」。这里第一条用例就是那颗钉子。
// 另钉:筛选下拉按域 optgroup(替代逐动作 chip 行)、每页行数走
// usePagerSize('audit-logs') → 服务端偏好键 pager.sizes、越界页回末页。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AuditLogPanel from '../AuditLogPanel.vue'
import * as adminApi from '@/api/admin'
import * as prefApi from '@/api/preferences'
import {
  PREFERENCE_PUT_DEBOUNCE_MS, resetUserPreferencesForTest,
} from '@/composables/useUserPreferences'
import { useAuthStore } from '@/stores/auth'
import type { AuditLogPage, AuditLogRow } from '@/api/admin'

vi.mock('@/api/admin', () => ({ listAuditLogs: vi.fn() }))
vi.mock('@/api/preferences', () => ({
  getPreferences: vi.fn().mockResolvedValue({}),
  putPreference: vi.fn().mockResolvedValue({}),
}))

const VOCAB = ['user.create', 'user.delete', 'suite.admin_publish']

function row(id: number): AuditLogRow {
  return {
    id, actorId: 1, actorName: '管理员', action: VOCAB[id % VOCAB.length]!,
    resourceType: 'user', resourceId: String(id), detail: { resource_name: `u${id}` },
    createdAt: '2026-10-20T10:00:00Z',
  }
}

/** 按请求参数切页的应答器:total 条、每页 pageSize 条,页码越界给空页;
 *  带 action 过滤时命中数骤减(模拟「该动作只有几条」)。 */
function envByParams(total: number): (p?: {
  action?: string; page?: number; page_size?: number
}) => Promise<AuditLogPage> {
  return (p) => {
    const size = p?.page_size ?? 20
    const pageNo = p?.page ?? 1
    const filtered = !p?.action ? total : Math.max(0, total - 40)
    const start = (pageNo - 1) * size
    const items = start < filtered
      ? Array.from({ length: Math.min(size, filtered - start) }, (_, i) => row(start + i + 1))
      : []
    return Promise.resolve({
      items, total: filtered, page: pageNo, pageSize: size, actions: VOCAB,
    })
  }
}

function calls() {
  return vi.mocked(adminApi.listAuditLogs).mock.calls.map((c) => c[0])
}

async function putLanded() {
  await new Promise((r) => setTimeout(r, PREFERENCE_PUT_DEBOUNCE_MS + 60))
}

describe('AuditLogPanel — 审计面板', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    resetUserPreferencesForTest()
    vi.mocked(prefApi.getPreferences).mockResolvedValue({} as never)
    vi.mocked(prefApi.putPreference).mockClear()
    useAuthStore().currentUser = {
      id: 1, username: 'alice', display_name: 'alice', is_admin: true,
    } as never
    vi.mocked(adminApi.listAuditLogs).mockReset()
  })

  it('翻页会重拉(回归:此前点页码不触发请求)且渲染新页数据', async () => {
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(45))
    const w = mount(AuditLogPanel)
    await flushPromises()
    expect(w.findAll('[data-testid^="audit-row-"]')).toHaveLength(20)

    await w.find('button[aria-label="第 2 页"]').trigger('click')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ page: 2, page_size: 20 })
    // 第 2 页首行是 21 号(新→旧流水分页的第 21 条)
    expect(w.findAll('[data-testid^="audit-row-"]')).toHaveLength(20)
    expect(w.find('[data-testid="audit-row-21"]').exists()).toBe(true)
    w.unmount()
  })

  it('动作筛选是单个下拉:按域 optgroup 分组,选中重拉、选回「全部」清过滤', async () => {
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(45))
    const w = mount(AuditLogPanel)
    await flushPromises()

    // 词表 3 键 → user/suite 两个组;不再渲染逐动作 chip 行
    const sel = w.find('[data-testid="audit-action-filter"]')
    expect(sel.exists()).toBe(true)
    const groups = w.findAll('optgroup')
    expect(groups.map((g) => (g.element as HTMLOptGroupElement).label))
      .toEqual(['用户', '套件'])
    expect(groups[0]!.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['user.create', 'user.delete'])
    expect(w.find('option[value=""]').text()).toBe('全部动作')

    await sel.setValue('user.delete')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ action: 'user.delete', page: 1 })

    await sel.setValue('')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ action: undefined })
    w.unmount()
  })

  it('在高页码上收紧筛选 → 归回第 1 页只发一次请求', async () => {
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(45))
    const w = mount(AuditLogPanel)
    await flushPromises()
    await w.find('button[aria-label="第 3 页"]').trigger('click')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ page: 3 })
    const before = calls().length

    await w.find('[data-testid="audit-action-filter"]').setValue('user.delete')
    await flushPromises()
    expect(calls().length).toBe(before + 1)   // page 3→1 由 watcher 拉,不双发
    expect(calls().at(-1)).toMatchObject({ action: 'user.delete', page: 1 })
    w.unmount()
  })

  it('每页行数:改行数重拉并按用户偏好落库(pager.sizes);镜像存档决定首帧行数', async () => {
    localStorage.setItem('pager-sizes:alice', JSON.stringify({ 'audit-logs': 10 }))
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(45))
    let w = mount(AuditLogPanel)
    await flushPromises()
    expect(calls()[0]).toMatchObject({ page_size: 10 })   // 镜像首帧,不等网络
    w.unmount()

    localStorage.clear()
    resetUserPreferencesForTest()
    vi.mocked(adminApi.listAuditLogs).mockClear()
    w = mount(AuditLogPanel)
    await flushPromises()
    expect(calls()[0]).toMatchObject({ page_size: 20 })   // 无存档 → fallback

    await w.find('[data-testid="pager-size"]').setValue('50')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ page: 1, page_size: 50 })
    await putLanded()
    expect(prefApi.putPreference).toHaveBeenCalledWith(
      'pager.sizes', { sizes: { 'audit-logs': 50 } })
    w.unmount()
  })

  it('越界页回退:停在空页刷新 → 回末页重取一次', async () => {
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(45))
    const w = mount(AuditLogPanel)
    await flushPromises()
    await w.find('button[aria-label="第 3 页"]').trigger('click')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ page: 3 })

    // 记录被清到只剩 5 条:第 3 页成了空页 → 应回第 1 页重拉
    vi.mocked(adminApi.listAuditLogs).mockImplementation(envByParams(5))
    await w.find('[data-testid="audit-refresh"]').trigger('click')
    await flushPromises()
    expect(calls().at(-1)).toMatchObject({ page: 1 })
    expect(w.findAll('[data-testid^="audit-row-"]')).toHaveLength(5)
    w.unmount()
  })
})
