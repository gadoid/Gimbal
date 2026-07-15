/** RenameInputDialog — naming + collision + validation. */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'
import RenameInputDialog from '@/components/RenameInputDialog.vue'

function mountDialog(propsData: Record<string, unknown> = {}) {
  return mount(RenameInputDialog, {
    props: {
      modelValue: true,
      defaultName: 'demo-case',
      existingNames: ['demo-case'],
      title: '为副本取个名字',
      ...propsData,
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('RenameInputDialog', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('emits submit(null) when user picks default (skip)', async () => {
    const w = mountDialog()
    await nextTick()
    const buttons = w.findAll('button')
    const useDefaultBtn = buttons.find((b) => b.text().includes('用默认名'))
    expect(useDefaultBtn).toBeDefined()
    await useDefaultBtn!.trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([false])
    expect(w.emitted('submit')?.[0]).toEqual([null])
  })

  it('emits submit(<name>) when user enters a name and confirms', async () => {
    const w = mountDialog({ existingNames: [] })
    await nextTick()
    const input = w.find('input')
    await input.setValue('my-rename')
    const buttons = w.findAll('button')
    const confirmBtn = buttons.find((b) => b.text().includes('确认'))
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')
    expect(w.emitted('submit')?.[0]).toEqual(['my-rename'])
  })

  it('shows error state for invalid characters', async () => {
    const w = mountDialog()
    await nextTick()
    const input = w.find('input')
    await input.setValue('bad/name')
    await nextTick()
    const status = w.find('.rn-field-status.is-error')
    expect(status.exists()).toBe(true)
    expect(status.text()).toContain('非法字符')
  })

  it('shows warn state for collisions', async () => {
    const w = mountDialog({ existingNames: ['demo-case'] })
    await nextTick()
    const input = w.find('input')
    await input.setValue('other')
    await nextTick()
    // No collision (different name)
    expect(w.find('.rn-field-status.is-warn').exists()).toBe(false)

    // Same as existing
    await input.setValue('demo-case')
    await nextTick()
    expect(w.find('.rn-field-status.is-warn').exists()).toBe(true)
  })

  it('disabled confirm when input has only invalid characters', async () => {
    const w = mountDialog()
    await nextTick()
    const input = w.find('input')
    await input.setValue('ok\\/bad')
    await nextTick()
    const buttons = w.findAll('button')
    const confirmBtn = buttons.find((b) => b.text().includes('确认'))
    expect(confirmBtn).toBeDefined()
    // el-button is rendered with disabled attr
    expect(confirmBtn!.attributes('disabled')).toBeDefined()
  })
})
