/**
 * SubscriptionDialog — authz M2a S8 凭证来源选择。
 * 普通项目模板(projectCredentialsAvailable = true):默认「项目凭证」,
 * 确认时随 subscribe 下发 credentialSource;私有/公共模板不显示选择,
 * 下发不带该字段(缺省 = 模板默认)。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SubscriptionDialog from '@/components/integration/SubscriptionDialog.vue'
import * as integrationApi from '@/api/integration'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const SUMMARY = {
  fingerprint: 'fp-1',
  steps: [{ service: 'fin', method: 'GET', path: '/x', readonly: true }],
  authAliases: ['qa'],
  baseUrls: { fin: 'http://fin' },
  datasetName: null,
  cron: '*/5 * * * *',
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(integrationApi, 'fetchSubscriptionSummary')
    .mockResolvedValue(SUMMARY as never)
})

function mountDlg(props: Record<string, unknown> = {}) {
  // watch(open) 不带 immediate —— 挂载后再开窗,模拟宿主 subTask 置位
  const w = mount(SubscriptionDialog, {
    props: { open: false, taskId: 9, ...props },
  })
  return { w, open: async () => { await w.setProps({ open: true }) } }
}

describe('S8 订阅凭证来源', () => {
  it('普通项目模板:默认项目凭证,确认随 subscribe 下发', async () => {
    const sub = vi.spyOn(integrationApi, 'subscribeIntegrationTask')
      .mockResolvedValue({ id: 9 } as never)
    const { w, open } = mountDlg({ projectCredentialsAvailable: true })
    await open()
    await flushPromises()
    const sel = w.find('[data-testid="sub-cred-source"]')
    expect(sel.exists()).toBe(true)
    expect((sel.element as HTMLSelectElement).value).toBe('project')
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(sub).toHaveBeenCalledWith(9, 'fp-1', 'project')
  })

  it('可选个人凭证;私有/公共模板不显示选择、不带字段', async () => {
    const sub = vi.spyOn(integrationApi, 'subscribeIntegrationTask')
      .mockResolvedValue({ id: 9 } as never)
    const { w, open } = mountDlg({ projectCredentialsAvailable: true })
    await open()
    await flushPromises()
    await w.find('[data-testid="sub-cred-source"]').setValue('personal')
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(sub).toHaveBeenCalledWith(9, 'fp-1', 'personal')

    const w2m = mountDlg()
    await w2m.open()
    const w2 = w2m.w
    await flushPromises()
    expect(w2.find('[data-testid="sub-cred-source"]').exists()).toBe(false)
    await w2.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(sub).toHaveBeenLastCalledWith(9, 'fp-1')
  })
})
