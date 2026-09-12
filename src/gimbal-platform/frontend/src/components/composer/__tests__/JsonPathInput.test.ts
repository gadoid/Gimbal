/**
 * JsonPathInput — jsonpath 输入 + 按层提示(纯函数 path-suggest 的界面层)。
 *
 * 行为契约:输入即按层提示;点选叶子补全、点选容器补全并留一个 `.` 便于继续;
 * 打开即高亮首项、Enter 采纳、Esc 关闭;无候选时退化为普通输入框(零行为变化)。
 *
 * 挂载走带 v-model 的父包装(生产用法同款)—— 受控输入的值以模型为准。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import JsonPathInput from '../JsonPathInput.vue'

const CANDIDATES = [
  '$.amount',
  '$.items[0].sku',
  '$.items[1].sku',
  '$.items[2].qty',
]

function mountInput(props: Record<string, unknown> = {}) {
  const value = ref('')
  const Parent = defineComponent({
    setup() {
      return () =>
        h(JsonPathInput, {
          modelValue: value.value,
          'onUpdate:modelValue': (v: string) => { value.value = v },
          candidates: CANDIDATES,
          ...props,
        })
    },
  })
  const w = mount(Parent)
  return {
    w,
    value,
    input: () => w.find('input'),
    items: () => w.findAll('.jpi-item'),
  }
}

describe('JsonPathInput — 按层提示', () => {
  it('JP-1: 输入根前缀 → 列出该层各段,并标注叶子/容器', async () => {
    const { input, items } = mountInput()
    await input().setValue('$.')
    expect(items().length).toBe(2)
    expect(items()[0].text()).toContain('amount')
    expect(items()[0].text()).toContain('叶子')
    expect(items()[1].text()).toContain('items')
    expect(items()[1].text()).toContain('容器')
  })

  it('JP-2: 点选叶子 → 补全完整路径并关闭下拉', async () => {
    const { input, items, value } = mountInput()
    await input().setValue('$.a')
    await items()[0].trigger('click')
    expect(value.value).toBe('$.amount')
    expect(items().length).toBe(0)
  })

  it('JP-3: 点选容器 → 补全并留一个 . 便于继续;数组层提示首实例与实例数', async () => {
    const { input, items, value } = mountInput()
    await input().setValue('$.i')
    await items()[0].trigger('click')
    expect(value.value).toBe('$.items.')
    await input().setValue('$.items.')
    expect(items()[0].text()).toContain('[0]')
    expect(items()[0].text()).toContain('共 3 项')
  })

  it('JP-4: 无候选 → 不渲染下拉,输入照常(零回归)', async () => {
    const { input, items, value } = mountInput({ candidates: [] })
    await input().setValue('$.anything')
    expect(items().length).toBe(0)
    expect(value.value).toBe('$.anything')
  })

  it('JP-5: 叶子写完 → 无提示(下拉关闭)', async () => {
    const { input, items } = mountInput()
    await input().setValue('$.amount')
    expect(items().length).toBe(0)
  })

  it('JP-6: 打开即高亮首项 — 直接 Enter 采纳首项,↓ 后 Enter 采纳次项', async () => {
    const { input, value } = mountInput()
    await input().setValue('$.')
    await input().trigger('keydown', { key: 'Enter' })
    expect(value.value).toBe('$.amount')          // 首项 = 叶子
    await input().setValue('$.')
    await input().trigger('keydown', { key: 'ArrowDown' })
    await input().trigger('keydown', { key: 'Enter' })
    expect(value.value).toBe('$.items.')          // 次项 = 容器,补 .
  })

  it('JP-7: Esc 关闭下拉但保留已输入文本', async () => {
    const { input, items, value } = mountInput()
    await input().setValue('$.')
    expect(items().length).toBeGreaterThan(0)
    await input().trigger('keydown', { key: 'Escape' })
    expect(items().length).toBe(0)
    expect(value.value).toBe('$.')
  })
})
