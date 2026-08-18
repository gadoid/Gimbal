/**
 * CaseComposerConfig.vue — ③ 配置步 regression (#3 后发现)。
 *
 * 症状:父级 v-model="definition.config" 时,点 "+ 添加变量"/"+ 添加服务"
 * 行不出现(添加服务/前置/后置同理)。
 *
 * 根因是 props 回灌 watch 无条件重建 rows:addVar() push 空 row →
 * emit watch 折叠出 vars 不含空 key 的 dict → 父 v-model 回写 →
 * props watch 深比较不等(多了一个空 key row)→ varsRows/serviceRows
 * 被重建为新数组,用户刚 push 的 row 引用丢失 → 视觉上"没加上"。
 *
 * 这组用例把组件挂成生产用法(父持 config,v-model 双向),
 * 复现并锁死该行为。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import type { ConfigView } from '@/types/plate'

function makeConfig(): ConfigView {
  return {
    setup: [],
    teardown: [],
    services: {},
    users: {},
    timePolicy: { kind: 'record' },
    retry: null,
    vars: {},
  } as ConfigView
}

/** 生产用法镜像:父持 config ref,子 v-model 双向绑定 */
function mountWithParent(initial: ConfigView) {
  const config = ref<ConfigView>(initial)
  const Parent = defineComponent({
    setup() {
      return () => h(CaseComposerConfig, {
        modelValue: config.value,
        'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, config }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('CaseComposerConfig — 添加行与父级 v-model 共存', () => {
  it('点 + 添加变量后空行出现并保留', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加变量'))[0].trigger('click')
    await flush()
    // 空行仍在渲染(varsBySystem 空 key 落 common 组)
    const inputs = w.findAll('.c-kv-row input')
    expect(inputs.length).toBeGreaterThanOrEqual(2) // key + value 两个输入框
  })

  it('点 + 添加服务后空行出现并保留', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加服务'))[0].trigger('click')
    await flush()
    const inputs = w.findAll('.c-kv-row input')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
  })

  it('+ 添加前置/后置同样不被回灌吞掉', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加前置'))[0].trigger('click')
    await flush()
    expect(w.findAll('.action-row').length).toBe(1)
  })

  it('编辑已有变量值能写回父 config(回灌修复不能砍掉正常同步)', async () => {
    const initial = makeConfig()
    initial.vars = { 'fin.api': 'old' }
    const { w, config } = mountWithParent(initial)
    const val = w.findAll('.c-kv-row input')[1] // 第 1 行 value
    await val.setValue('new')
    await flush()
    expect(config.value.vars['fin.api']).toBe('new')
  })
})

describe('CaseComposerConfig — 变量注册表已迁 Canvas(#11 摘除)', () => {
  it('渲染文本不再含"变量注册表"(配置步只管编辑,总览在步骤编辑页)', () => {
    const { w } = mountWithParent(makeConfig())
    expect(w.text()).not.toContain('变量注册表')
  })
})
