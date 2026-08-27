/**
 * RunDialog — 用户与服务绑定区(spec §4,Task 11 重写)
 *
 * 锁死:
 * - referencedServices 每服务一行绑定(authAlias 下拉 + url 覆盖),默认无绑定
 * - 选方案 → serviceBindings 整体替换预填;alias 不在 authOptions → 行标红降级
 * - confirm 携带 serviceBindings(空绑定条目剔除)
 * - 存为方案 → emit saveScheme(当前 env/ds/bindings)
 * - 退役语义不存在:无 prefix 输入 / 无 policy 选择 / 无「合并策略」文案
 *
 * 与 task-11-brief Step 1 的两处最小对齐(其余逐字):
 * - mountDlg 加 `stubs: { teleport: true }`(本仓 RunDialog 弹层走 Teleport,
 *   不 stub 则 find 不可达 — 同目录 4 个兄弟文件同款 harness);
 * - 「存为方案」用例先填方案名:brief 自带 onSaveScheme 有 `if (!name) return`
 *   空名守卫,不填名则永不 emit,断言 emitted('saveScheme') 必炸。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'

const BASE_PROPS = {
  envs: [{ envId: 'dev', name: 'dev', baseUrl: 'https://dev' }],
  dataSets: [],
  schemes: [{ name: '冒烟-qa1', envId: 'dev', dataSetIds: [],
              serviceBindings: { 'fin-service': { authAlias: 'qa1' } } }],
  lastRunOverlay: null,
  referencedServices: ['fin-service'],
  authOptions: ['qa1', 'qa2'],
}

function mountDlg(props: Partial<typeof BASE_PROPS> = {}) {
  return mount(RunDialog, {
    props: { visible: true, ...BASE_PROPS, ...props },
    global: { stubs: { teleport: true } },
  })
}

describe('用户与服务绑定区', () => {
  it('referencedServices 每服务一行,默认无绑定', () => {
    const w = mountDlg()
    expect(w.findAll('.rd-bind-row')).toHaveLength(1)
  })

  it('选方案 → 绑定 authAlias 预填;alias 不在 authOptions → 标红降级', async () => {
    const w = mountDlg({ schemes: [BASE_PROPS.schemes[0]], authOptions: [] })
    await w.find('.rd-scheme-select').setValue('冒烟-qa1')     // 或触发选择 handler
    expect(w.find('.rd-bind-row.is-degraded').exists()).toBe(true)
  })

  it('confirm 携带 serviceBindings', async () => {
    const w = mountDlg()
    await w.find('.rd-bind-user').setValue('qa1')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    // emitted() 返回 unknown[][](VTU 不按 defineEmits 收窄)— 同旧文件断言收窄写法
    const evt = w.emitted('confirm')![0] as unknown[]
    const opts = evt[2] as { serviceBindings?: Record<string, { authAlias?: string }> }
    expect(opts.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa1' } })
  })

  it('存为方案 → emit saveScheme,携带当前 env/ds/bindings', async () => {
    const w = mountDlg()
    await w.find('.rd-bind-user').setValue('qa1')
    await w.find('.rd-scheme-name').setValue('冒烟-新方案')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const s = w.emitted('saveScheme')![0][0] as any
    expect(s.serviceBindings['fin-service'].authAlias).toBe('qa1')
    expect(s.envId).toBe('dev')
  })

  it('退役语义不存在:无 prefix 输入/无 policy 选择', () => {
    const w = mountDlg()
    expect(w.find('.rd-prefix').exists()).toBe(false)
    expect(w.find('.rd-policy').exists()).toBe(false)
    expect(w.text()).not.toContain('合并策略')
  })
})
