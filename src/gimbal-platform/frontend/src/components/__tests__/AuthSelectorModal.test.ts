/**
 * AuthSelectorModal — 认证注入选择器(配套方案 §1.1 C3a 预填)。
 * 核心契约:
 *   - preselectAlias:打开即预填别名绑定的凭证(从服务注册的身份面绑定带出),
 *     一步「确认插入」落 ${auth.<bound>.token};
 *   - originNote:预填来源说明;预填名不在本人池 → 提示仍可插入
 *     (执行时按执行者本人池解析);
 *   - 手工改选仍是逃生舱(不预填/改选均可)。
 * 2026-09-22(任务6):alias 下拉换 CredentialSelect 样式化组件(自管
 * 面板,无 portal),交互 = 点触发器 → 点选项;预填态直接读触发器文案。
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AuthSelectorModal from '@/components/AuthSelectorModal.vue'
import type { ServiceAliasRow } from '@/api/service-aliases'

// 2c:modal 打开即拉环境名(条目按环境分组;失败退平铺)— mock 防真实 XHR
vi.mock('@/api/environments', () => ({
  listEnvironments: vi.fn().mockResolvedValue([
    { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
  ]),
}))

/** registry:选择域 = 身份条目(aliasName 即 ${auth.<X>} 的 X 域)。 */
const AUTHS: ServiceAliasRow[] = [
  { aliasName: 'qa1', baseService: 'fin-service', slot: 'qa1', kind: 'plate',
    envId: 1, refMode: 'default', refUsername: null, display: '',
    createdAt: '', updatedAt: '' },
  { aliasName: 'uat-cred', baseService: 'fin-service', slot: 'uat-cred',
    kind: 'external', envId: 1, refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
]

async function openModal(props?: { preselectAlias?: string | null; originNote?: string | null }) {
  const w = mount(AuthSelectorModal, {
    props: {
      modelValue: false,
      auths: AUTHS,
      preselectAlias: props?.preselectAlias ?? null,
      originNote: props?.originNote ?? null,
    },
    // reka Dialog 内容 teleport 到 body;attachTo 后直接查 document
    attachTo: document.body,
  })
  await w.setProps({ modelValue: true })
  await flushPromises()
  return w
}

/** teleport 内容不在 wrapper 内,经 document 查。 */
function q(sel: string): HTMLElement | null {
  return document.querySelector(sel)
}

async function click(sel: string): Promise<void> {
  const el = q(sel)
  expect(el, sel).not.toBeNull()
  el!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

describe('AuthSelectorModal — 别名绑定预填(C3a)', () => {
  it('preselectAlias 打开即预填;确认插入直接落绑定凭证模板', async () => {
    const w = await openModal({
      preselectAlias: 'uat-cred',
      originNote: 'fin-service-uat 的绑定凭证(可改选)',
    })
    // 预填态:触发器直接显示绑定凭证名(两行选项组件的收拢态)
    const trigger = q('[data-testid="auth-alias"] [data-testid="credential-trigger"]')
    expect(trigger?.textContent).toContain('uat-cred')
    expect(q('[data-testid="auth-origin-note"]')?.textContent).toContain('fin-service-uat')

    const confirmBtn = [...document.querySelectorAll('button')]
      .find((b) => b.textContent!.includes('确认插入'))!
    confirmBtn.click()
    await flushPromises()
    expect(w.emitted('select')?.[0]).toEqual(['${auth.uat-cred.token}'])
    w.unmount()
  })

  it('预填名不在本人池:提示可插入(执行时按执行者池解析),模板照发', async () => {
    const w = await openModal({ preselectAlias: 'other-team-cred' })
    expect(!!q('[data-testid="auth-preselect-missing"]')).toBe(true)
    const confirmBtn = [...document.querySelectorAll('button')]
      .find((b) => b.textContent!.includes('确认插入'))!
    confirmBtn.click()
    await flushPromises()
    expect(w.emitted('select')?.[0]).toEqual(['${auth.other-team-cred.token}'])
    w.unmount()
  })

  it('无预填:展开下拉手选(逃生舱不变)', async () => {
    const w = await openModal()
    // 展开面板 → 选项两行化:alias + token_type 在上,username · url 在下
    await click('[data-testid="auth-alias"] [data-testid="credential-trigger"]')
    expect(q('[data-testid="auth-alias"] [data-testid="credential-panel"]')).not.toBeNull()
    // 2c:环境分组头(v6 范式)— envNames 拉到即分组渲染
    expect(q('[data-testid="auth-alias"] .cred-group-label')?.textContent).toContain('测试')
    const opt = q('[data-testid="auth-alias"] [data-testid="credential-option-qa1"]')
    expect(opt?.textContent).toContain('qa1')
    expect(opt?.textContent).toContain('plate')
    expect(opt?.textContent).toContain('fin-service')
    await click('[data-testid="auth-alias"] [data-testid="credential-option-qa1"]')
    // 选中即收起
    expect(q('[data-testid="auth-alias"] [data-testid="credential-panel"]')).toBeNull()

    const confirmBtn = [...document.querySelectorAll('button')]
      .find((b) => b.textContent!.includes('确认插入'))!
    confirmBtn.click()
    await flushPromises()
    expect(w.emitted('select')?.[0]).toEqual(['${auth.qa1.token}'])
    expect(!!q('[data-testid="auth-origin-note"]')).toBe(false)
    w.unmount()
  })
})
