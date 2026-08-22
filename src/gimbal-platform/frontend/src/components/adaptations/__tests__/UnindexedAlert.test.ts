/**
 * UnindexedAlert —— C10 未索引警示条:
 *   - 有缺口 → warning 条 + 计数;点标题展开清单;
 *   - 无缺口 → 不渲染。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import UnindexedAlert from '@/components/adaptations/UnindexedAlert.vue'

const steps = [
  { scenarioId: 'sc-a', stepIndex: 0, reason: 'no_endpoint_id' },
  { scenarioId: 'sc-b', stepIndex: 2, reason: 'no_endpoint_id' },
]

function mountIt(props: { steps: typeof steps | [] }) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
  return mount(UnindexedAlert, {
    props,
    global: { plugins: [router, ElementPlus] },
  })
}

describe('UnindexedAlert', () => {
  it('无缺口不渲染', () => {
    const w = mountIt({ steps: [] })
    expect(w.find('.unindexed-alert').exists()).toBe(false)
  })

  it('展示计数;点开展开清单并带场景详情链接', async () => {
    const w = mountIt({ steps })
    expect(w.text()).toContain('2 个步骤缺 endpoint_id')
    expect(w.find('li').exists()).toBe(false)   // 默认收起

    await w.find('.title').trigger('click')
    const items = w.findAll('li')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('sc-a')
    expect(items[0].text()).toContain('步骤 0')
    expect(items[0].find('a').attributes('href')).toBe('/scenarios/sc-a/detail')
  })
})
