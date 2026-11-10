/**
 * SuiteRunPreflight — S8 收口:suite 运行的凭证来源选择。
 * suite 属我所在的普通项目(projectId 传入)→ 弹窗出「凭证来源」
 * 选择;换来源按新池重新预检(validate 带 credentialSource);
 * 开始运行回传所选来源。无项目上下文 → 不显示、不带参数。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { DOMWrapper, mount, flushPromises } from '@vue/test-utils'
import SuiteRunPreflight from '@/components/suites/SuiteRunPreflight.vue'
import * as suitesApi from '@/api/suites'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const OUT = {
  ok: true, unitCount: 2, estimatedRuns: 2, runCap: 200, gates: 0,
  items: [], degraded: false,
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(suitesApi, 'validateSuite').mockResolvedValue(OUT as never)
})

/** shadcn Dialog 渲染在 body(Teleport)—— 从 body 里查 */
function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

// watch(open) 不带 immediate —— 挂载后再开窗,模拟宿主置位
async function mountDlg(props: Record<string, unknown> = {}) {
  const w = mount(SuiteRunPreflight, {
    props: { open: false, suiteId: 7, ...props },
    global: { stubs: { QTip: true } },
  })
  await w.setProps({ open: true })
  await flushPromises()
  return w
}

describe('S8 收口 · suite 预检凭证来源', () => {
  it('项目上下文:选择可见,切换按新池重新预检,运行回传来源', async () => {
    const w = await mountDlg({ projectId: 5 })
    expect(suitesApi.validateSuite).toHaveBeenCalledWith(7)
    const sel = q('[data-testid="pf-cred-source"]')
    await sel.setValue('project')
    await flushPromises()
    expect(suitesApi.validateSuite).toHaveBeenCalledWith(7, 'project')
    await q('[data-testid="suite-preflight-run"]').trigger('click')
    expect(w.emitted('run')?.[0]).toEqual(['project'])
    w.unmount()
  })

  it('无项目上下文:不显示选择、validate 不带来源、运行回传 personal', async () => {
    const w = await mountDlg()
    expect(document.body.querySelector('[data-testid="pf-cred-source"]')).toBeNull()
    expect(suitesApi.validateSuite).toHaveBeenCalledWith(7)
    await q('[data-testid="suite-preflight-run"]').trigger('click')
    expect(w.emitted('run')?.[0]).toEqual(['personal'])
    w.unmount()
  })
})
