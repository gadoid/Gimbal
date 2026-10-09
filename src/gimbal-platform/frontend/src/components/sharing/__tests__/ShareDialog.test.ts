/**
 * ShareDialog — P2 分享弹窗钉子(§7.1/§7.11):
 * 打开即拉 roster + 现有引用(out);副本默认选中、引用可选;
 * 提交载荷(resourceType/resourceId/granteeUserId/mode);
 * 已引用者标「已引用」;撤销按钮调 DELETE;失败 toast 后端人话。
 * reka-ui DialogPortal 真实 teleport(ScenarioExportMenu 惯例)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import * as sharesApi from '@/api/shares'
import * as handoffApi from '@/api/handoff'
import { toast } from '@/utils/toast'

vi.mock('@/api/shares', () => ({
  createShare: vi.fn(),
  listShares: vi.fn(),
  deleteShare: vi.fn(),
  forkShare: vi.fn(),
}))
vi.mock('@/api/handoff', () => ({
  getRoster: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const q = (sel: string) => document.querySelector(sel) as HTMLElement | null

const RESOURCE = { type: 'scenario' as const, id: 'sc-1', name: '下单' }

function mountDialog() {
  return mount(ShareDialog, {
    props: { open: true, resource: RESOURCE },
    attachTo: document.body,
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ShareDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(handoffApi.getRoster).mockResolvedValue({
      items: [
        { id: 1, username: 'bob', display_name: 'Bob' },
        { id: 2, username: 'carol', display_name: 'Carol' },
      ],
    })
    vi.mocked(sharesApi.listShares).mockResolvedValue([
      { id: 99, resourceType: 'scenario', scenarioId: 'sc-1',
        suiteId: null, suiteName: null, memberCount: null,
        granteeUserId: 1, granteeName: 'Bob',
        grantedByName: 'owner', grantedAt: '2026-10-09T00:00:00Z' },
    ] as never)
  })

  it('打开即拉现有引用(out)与 roster;已引用者标「已引用」;副本默认', async () => {
    mountDialog()
    await flushPromises()
    expect(sharesApi.listShares).toHaveBeenCalledWith({
      direction: 'out', resourceType: 'scenario', resourceId: 'sc-1' })
    expect(q('[data-testid="share-existing"]')).not.toBeNull()
    expect(q('[data-testid="share-revoke-99"]')).not.toBeNull()
    expect((q('[data-testid="share-mode-copy"]') as HTMLInputElement).checked)
      .toBe(true)
  })

  it('选引用模式 + 选人 → 提交载荷含 mode=ref', async () => {
    vi.mocked(sharesApi.createShare).mockResolvedValue({
      id: 100, resourceType: 'scenario', scenarioId: 'sc-1',
      suiteId: null, suiteName: null, memberCount: null,
      granteeUserId: 2, granteeName: 'Carol',
      grantedByName: 'owner', grantedAt: null,
    } as never)
    const w = mountDialog()
    await flushPromises()
    q('[data-testid="share-mode-ref"]')!.click()
    await flushPromises()
    // radio 选中 bob:找 label 内 input(radio 无 data-testid,按 name)
    const radios = [...document.querySelectorAll(
      'input[name="share-target"]')] as HTMLInputElement[]
    radios[0].click()  // bob
    await flushPromises()
    q('[data-testid="share-confirm"]')!.click()
    await flushPromises()
    expect(sharesApi.createShare).toHaveBeenCalledWith({
      resourceType: 'scenario', resourceId: 'sc-1',
      granteeUserId: 1, mode: 'ref' })
    expect(w.emitted('changed')).toBeTruthy()
    expect(w.emitted('update:open')).toEqual([[false]])
  })

  it('撤销现有引用 → DELETE + toast + emit changed', async () => {
    const w = mountDialog()
    await flushPromises()
    q('[data-testid="share-revoke-99"]')!.click()
    await flushPromises()
    expect(sharesApi.deleteShare).toHaveBeenCalledWith(99)
    expect(toast.success).toHaveBeenCalled()
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('分享失败(409 cap)toast 后端人话,弹窗不关', async () => {
    vi.mocked(sharesApi.createShare).mockRejectedValue(
      new Error('share ref cap per user is 200'))
    const w = mountDialog()
    await flushPromises()
    const radios = [...document.querySelectorAll(
      'input[name="share-target"]')] as HTMLInputElement[]
    radios[1].click()  // carol
    await flushPromises()
    q('[data-testid="share-confirm"]')!.click()
    await flushPromises()
    expect(toast.error).toHaveBeenCalledWith(
      '分享失败:share ref cap per user is 200')
    expect(w.emitted('update:open')).toBeUndefined()
  })
})
