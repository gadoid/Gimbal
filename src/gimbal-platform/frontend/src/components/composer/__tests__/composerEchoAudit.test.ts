/**
 * composer 回声递归审计 — 与 CaseComposerConfig regression 同类问题全仓排查。
 *
 * 复测 ① Meta 与 ② Resource 两个同拓扑组件(入向回灌 watch + 出向 emit watch,
 * 无回声守卫)。挂载方式与生产一致:父持状态 + v-model 双向。
 *
 * 期望(Meta):Object.assign 同值回灌不触发 reactive → 收敛,编辑正常写回。
 * 期望(Resource):若添加 mock 后行被吞 / Maximum recursive updates → 与
 * Config 同病,需同款修复。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import CaseComposerMeta from '@/components/composer/CaseComposerMeta.vue'
import CaseComposerResource from '@/components/composer/CaseComposerResource.vue'
import type { MetaView, ResourceView } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function makeMeta(): MetaView {
  return {
    name: '', description: '', module: '', priority: 1,
    author: '', owner: '', tags: [], version: 'v0.1.0',
    createTime: '', expire: false, requirementRef: [], system: ['fin'],
  } as unknown as MetaView
}

describe('CaseComposerMeta — 回声审计(预期收敛,锁死不回归)', () => {
  it('编辑 name 写回父级且不递归', async () => {
    const meta = ref<MetaView>(makeMeta())
    const Parent = defineComponent({
      setup: () => () => h(CaseComposerMeta, {
        modelValue: meta.value,
        'onUpdate:modelValue': (v: MetaView) => { meta.value = v },
      }),
    })
    const w = mount(Parent, { global: { plugins: [ElementPlus] } })
    const input = w.find('input[placeholder="订单创建 e2e"]')
    await input.setValue('订单 e2e')
    await flush()
    expect(meta.value.name).toBe('订单 e2e')
  })
})

describe('CaseComposerResource — 回声审计', () => {
  function mountWithParent(initial: Record<string, ResourceView>) {
    const resource = ref<Record<string, ResourceView>>(initial)
    const resourceMeta = ref<Record<string, string>>({})
    const Parent = defineComponent({
      setup: () => () => h(CaseComposerResource, {
        resource: resource.value,
        resourceMeta: resourceMeta.value,
        'onUpdate:resource': (v: Record<string, ResourceView>) => { resource.value = v },
        'onUpdate:resourceMeta': (v: Record<string, string>) => { resourceMeta.value = v },
      }),
    })
    const w = mount(Parent, { global: { plugins: [ElementPlus] } })
    return { w, resource }
  }

  it('添加 file 资源后行出现并保留(不吞行/不递归)', async () => {
    const { w } = mountWithParent({})
    // 空状态 → 选类型添加:类型卡点击后 setTimeout(100) 落行
    const fileCard = w.findAll('.resource-card').find((c) => c.text().includes('文件'))
    await fileCard!.trigger('click')
    await new Promise((r) => setTimeout(r, 150))
    await flush()
    expect(w.findAll('.resource-row').length).toBe(1)
  })

  it('编辑已有 mock 的 image 写回父级(回灌不砍正常同步)', async () => {
    const initial: Record<string, ResourceView> = {
      'mock-1': {
        kind: 'mock', name: 'mock-1', image: 'old',
        config: {}, portMapping: {},
      } as ResourceView,
    }
    const { w, resource } = mountWithParent(initial)
    await flush()
    const img = w.find('input[placeholder^="harbor.example.com"]')
    await img.setValue('new-img')
    await flush()
    expect((resource.value['mock-1'] as any).image).toBe('new-img')
  })
})
