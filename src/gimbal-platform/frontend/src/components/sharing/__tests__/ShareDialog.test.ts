/**
 * ShareDialog — S7.4 后仅剩副本模式:
 * 打开即拉 roster;提交载荷(resourceType/resourceId/granteeUserId/
 * mode='copy');失败 toast 后端人话。reka-ui DialogPortal 真实
 * teleport(ScenarioExportMenu 惯例)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ShareDialog from '@/components/sharing/ShareDialog.vue'
import * as sharesApi from '@/api/shares'
import * as handoffApi from '@/api/handoff'
import { toast } from '@/utils/toast'

vi.mock('@/api/shares', () => ({
  createShare: vi.fn(),
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

describe('ShareDialog — 副本分享(S7.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(handoffApi.getRoster).mockResolvedValue({
      items: [
        { id: 1, username: 'bob', display_name: 'Bob' },
        { id: 2, username: 'carol', display_name: 'Carol' },
      ],
    })
  })

  it('打开即拉 roster;无引用模式入口(退役)', async () => {
    mountDialog()
    await flushPromises()
    expect(handoffApi.getRoster).toHaveBeenCalled()
    expect(q('[data-testid="share-mode-ref"]')).toBeNull()
    expect(q('[data-testid="share-existing"]')).toBeNull()
  })

  it('选人 → 提交载荷 mode=copy;成功 toast + emit', async () => {
    vi.mocked(sharesApi.createShare).mockResolvedValue({
      mode: 'copy', scenarioId: 'sc-1-copy-abc', suiteId: null,
      suiteName: null, memberCount: 0,
    })
    const w = mountDialog()
    await flushPromises()
    const radios = [...document.querySelectorAll(
      'input[name="share-target"]')] as HTMLInputElement[]
    radios[0].click()  // bob
    await flushPromises()
    q('[data-testid="share-confirm"]')!.click()
    await flushPromises()
    expect(sharesApi.createShare).toHaveBeenCalledWith({
      resourceType: 'scenario', resourceId: 'sc-1',
      granteeUserId: 1, mode: 'copy' })
    expect(toast.success).toHaveBeenCalled()
    expect(w.emitted('changed')).toBeTruthy()
    expect(w.emitted('update:open')).toEqual([[false]])
  })

  it('分享失败 toast 后端人话,弹窗不关', async () => {
    vi.mocked(sharesApi.createShare).mockRejectedValue(
      new Error('suite_is_draft'))
    const w = mountDialog()
    await flushPromises()
    const radios = [...document.querySelectorAll(
      'input[name="share-target"]')] as HTMLInputElement[]
    radios[1].click()  // carol
    await flushPromises()
    q('[data-testid="share-confirm"]')!.click()
    await flushPromises()
    expect(toast.error).toHaveBeenCalledWith('分享失败:suite_is_draft')
    expect(w.emitted('update:open')).toBeUndefined()
  })
})
