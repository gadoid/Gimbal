/**
 * ProjectMembersPanel — A 级批次(2026-11-18)补齐:负责资产计数列 +
 * 权限清单 CSV 导出(papaparse unparse + downloadFile,全量成员口径)。
 * 角色行内改成员已有覆盖在 views/__tests__/Projects.test.ts
 * (prj-tab-members)与 ProjectTokensPanel.test.ts,不重复。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProjectMembersPanel from '@/components/project/ProjectMembersPanel.vue'
import * as projectsApi from '@/api/projects'
import { downloadFile } from '@/utils/download'

vi.mock('@/api/handoff', () => ({
  getRoster: vi.fn().mockResolvedValue({ items: [] }),
}))
vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(false),
}))

const proj: projectsApi.ProjectOut = {
  id: 3, name: 'P3', kind: 'normal', description: '', memberCount: 2,
  myRole: 'admin', canManage: true,
}

const members: projectsApi.ProjectMember[] = [
  { userId: 1, username: 'alice', displayName: 'Alice', role: 'admin',
    addedAt: '2026-11-01T10:00:00Z', scenarioCount: 5, suiteCount: 2 },
  { userId: 2, username: 'bob', displayName: 'Bob', role: 'member',
    addedAt: '2026-11-02T10:00:00Z', scenarioCount: 0, suiteCount: 1 },
]

function mountPanel() {
  return mount(ProjectMembersPanel, { props: { project: proj } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(projectsApi, 'listMembers').mockResolvedValue(
    structuredClone(members))
})

describe('ProjectMembersPanel — 资产计数 + CSV 导出(A 级批次)', () => {
  it('成员行带场景/用例集计数列(端点新字段直渲染)', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(w.find('[data-testid="prj-mem-scen-1"]').text()).toBe('5')
    expect(w.find('[data-testid="prj-mem-suite-1"]').text()).toBe('2')
    expect(w.find('[data-testid="prj-mem-scen-2"]').text()).toBe('0')
    expect(w.find('[data-testid="prj-mem-suite-2"]').text()).toBe('1')
    w.unmount()
  })

  it('导出 CSV:全量成员(不受前端筛选影响)+ BOM + 中文表头', async () => {
    const w = mountPanel()
    await flushPromises()
    // 前端筛掉 bob(浏览态)—— 清单仍是台账口径(2 行)
    await w.find('[data-testid="prj-mem-q"]').setValue('alice')
    await flushPromises()
    expect(w.findAll('[data-testid^="prj-member-"]').length).toBe(1)

    await w.find('[data-testid="prj-mem-export"]').trigger('click')
    expect(downloadFile).toHaveBeenCalledTimes(1)
    const [filename, content, mime] = vi.mocked(downloadFile).mock.calls[0]!
    expect(filename).toContain('项目成员权限清单-P3-')
    expect(filename.endsWith('.csv')).toBe(true)
    expect(mime).toContain('text/csv')
    expect(content.startsWith('\uFEFF')).toBe(true)      // BOM:Excel 中文不乱码
    expect(content).toContain('姓名,用户名,项目角色,场景数,用例集数,加入时间')
    expect(content).toContain('Alice,alice,项目管理员,5,2,')
    expect(content).toContain('Bob,bob,成员,0,1,')        // 全量:被筛掉的也在
    w.unmount()
  })

  it('CSV 公式注入防护:= + - @ 开头的姓名/用户名前缀单引号', async () => {
    vi.spyOn(projectsApi, 'listMembers').mockResolvedValue([
      { ...members[0]!, displayName: '=HYPERLINK("x")', username: 'alice' },
      { ...members[1]!, displayName: '+SUM(1,1)', username: '-dash' },
    ] as never)
    const w = mountPanel()
    await flushPromises()
    await w.find('[data-testid="prj-mem-export"]').trigger('click')
    const content = vi.mocked(downloadFile).mock.calls[0]![1]
    // 前缀单引号存在(papaparse 对含引号/逗号单元格再包一层 CSV 引号)
    expect(content).toContain("'=HYPERLINK")
    expect(content).toContain("'+SUM(1,1)")
    expect(content).toContain("'-dash")
    // 普通值不加前缀
    expect(content).toContain(',alice,')
    w.unmount()
  })

  it('无成员时不渲染导出按钮', async () => {
    vi.spyOn(projectsApi, 'listMembers').mockResolvedValue([])
    const w = mountPanel()
    await flushPromises()
    expect(w.find('[data-testid="prj-mem-export"]').exists()).toBe(false)
    w.unmount()
  })
})
