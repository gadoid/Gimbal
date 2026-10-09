/** GatesPanel — 横切断言表单(重构方案收尾:「选择器 + 断言表单,
 * 不再手写 JSON」)。语义对执行器 CheckDecl:on(bracket + refs,不选 =
 * 该段全部)+ strategy(kind=assertion,编译期追加到命中单元策略尾)。 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GatesPanel from '@/components/suites/GatesPanel.vue'
import type { SuiteModeConfig } from '@/api/suites'

function mountPanel(cfg: SuiteModeConfig = {}, over: {
  mode?: string; readonly?: boolean; roster?: { scenarioId: string; role?: string }[]
} = {}) {
  return mount(GatesPanel, {
    props: {
      config: cfg,
      members: [{ scenarioId: 'sc-a' }, { scenarioId: 'sc-b' }],
      roster: over.roster ?? [
        { scenarioId: 'sc-a', role: 'main' },
        { scenarioId: 'sc-b', role: 'main' },
        { scenarioId: 'sc-setup', role: 'before' },
      ],
      mode: over.mode ?? 'compose',
      readonly: over.readonly,
      runCap: 1000,
    },
  })
}

describe('GatesPanel — 横切断言表单', () => {
  it('加一条:主体全部单元 + eq 200 → patch checks(on 无 refs,expected 数字)', async () => {
    const w = mountPanel()
    await w.find('[data-testid="suite-check-target"]').setValue('$.call.response.status')
    await w.find('[data-testid="suite-check-op"]').setValue('eq')
    await w.find('[data-testid="suite-check-expected"]').setValue('200')
    await w.find('[data-testid="suite-check-form"]').trigger('submit')

    const events = w.emitted('patch')
    const last = events?.at(-1)?.[0] as { checks: unknown[] }
    expect(last.checks).toHaveLength(1)
    expect(last.checks[0]).toEqual({
      on: { bracket: 'main' },
      strategy: {
        kind: 'assertion',
        target: '$.call.response.status',
        operator: 'eq',
        expected: 200,
      },
    })
    // 提交后断言部分重置、选择器保留
    expect((w.find('[data-testid="suite-check-target"]').element as HTMLInputElement).value).toBe('')
    w.unmount()
  })

  it('选单元 chips → on.refs 只含所选;in 算子逗号串解析成数组', async () => {
    const w = mountPanel({ units: { 'sc-a': { ref: 'login' }, 'sc-b': { ref: 'order' } } })
    await w.find('[data-testid="suite-check-ref-login"]').trigger('click')
    await w.find('[data-testid="suite-check-target"]').setValue('$.call.response.body.tag')
    await w.find('[data-testid="suite-check-op"]').setValue('in')
    await w.find('[data-testid="suite-check-expected"]').setValue('a, b')
    await w.find('[data-testid="suite-check-form"]').trigger('submit')

    const last = (w.emitted('patch')?.at(-1)?.[0] as { checks: { on: { refs: string[] }; strategy: { expected: unknown } }[] })
    expect(last.checks[0].on.refs).toEqual(['login'])
    expect(last.checks[0].strategy.expected).toEqual(['a', 'b'])
    w.unmount()
  })

  it('切到前置段只列前置单元;exists 算子不出现期望值输入(expected=null)', async () => {
    const w = mountPanel()
    await w.find('[data-testid="suite-check-bracket"]').setValue('before')
    // 名册里只有 sc-setup 是前置
    expect(w.find('[data-testid="suite-check-refs"]').text()).toContain('sc-setup')
    expect(w.find('[data-testid="suite-check-refs"]').text()).not.toContain('sc-a')

    expect(w.find('[data-testid="suite-check-expected"]').exists()).toBe(true)
    await w.find('[data-testid="suite-check-op"]').setValue('exists')
    expect(w.find('[data-testid="suite-check-expected"]').exists()).toBe(false)
    await w.find('[data-testid="suite-check-target"]').setValue('$.call.response.body.uid')
    await w.find('[data-testid="suite-check-form"]').trigger('submit')

    const last = (w.emitted('patch')?.at(-1)?.[0] as { checks: { on: { bracket: string }; strategy: { operator: string; expected: unknown } }[] })
    expect(last.checks[0].on.bracket).toBe('before')
    expect(last.checks[0].strategy.operator).toBe('exists')
    expect(last.checks[0].strategy.expected).toBeNull()
    w.unmount()
  })

  it('已有断言列表回显(作用范围 + 断言行)并可删除;message 透传', async () => {
    const w = mountPanel({
      checks: [
        { on: { bracket: 'main' },
          strategy: { kind: 'assertion', target: '$.call.status', operator: 'eq', expected: 200 } },
        { on: { bracket: 'before', refs: ['setup'] },
          strategy: { kind: 'assertion', target: '$.x', operator: 'exists', expected: null, message: 'setup 必须留痕' } },
      ] as never,
    })
    expect(w.find('[data-testid="suite-check-0"]').text()).toContain('主体段全部单元')
    expect(w.find('[data-testid="suite-check-0"]').text()).toContain('$.call.status 等于 200')
    expect(w.find('[data-testid="suite-check-1"]').text()).toContain('前置段 · setup')
    expect(w.find('[data-testid="suite-check-1"]').text()).toContain('$.x 存在')

    await w.find('[data-testid="suite-check-remove-0"]').trigger('click')
    const last = w.emitted('patch')?.at(-1)?.[0] as { checks: unknown[] }
    expect(last.checks).toHaveLength(1)
    w.unmount()
  })

  it('聚合模式:表单隐藏并说明不消费;只读态不出现表单', async () => {
    const agg = mountPanel({}, { mode: 'aggregate' })
    expect(agg.find('[data-testid="suite-check-form"]').exists()).toBe(false)
    expect(agg.text()).toContain('聚合走批次通道')
    agg.unmount()

    const ro = mountPanel({}, { readonly: true })
    expect(ro.find('[data-testid="suite-check-form"]').exists()).toBe(false)
    ro.unmount()
  })
})
