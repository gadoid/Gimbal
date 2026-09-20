/**
 * UnindexedAlert —— C10 未索引警示(原型 H-adaptations-v2 形态):
 *   - 琥珀区块「未索引 · N」+ 白卡带橙色左边粗条;
 *   - 每卡「去场景处理 ›」按钮直跳场景详情(场景名也可点);
 *   - 无缺口 → 不渲染。
 */
import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import UnindexedAlert from '@/components/adaptations/UnindexedAlert.vue'

const steps = [
  { scenarioId: 'sc-a', stepIndex: 0, reason: 'no_endpoint_id' },
  { scenarioId: 'sc-b', stepIndex: 2, reason: 'no_endpoint_id' },
]

function mountWithRouter(props: { steps: typeof steps | [] }) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
  const w = mount(UnindexedAlert, { props, global: { plugins: [router] } })
  return { w, router }
}

describe('UnindexedAlert', () => {
  it('无缺口不渲染', () => {
    const { w } = mountWithRouter({ steps: [] })
    expect(w.find('.unindexed-alert').exists()).toBe(false)
  })

  it('琥珀区标题计数;卡内场景链接与缺失原因', () => {
    const { w } = mountWithRouter({ steps })
    expect(w.text()).toContain('未索引 · 2')
    // 配套方案 §3.4:显式区分于画像「无用例覆盖」的说明在场
    expect(w.text()).toContain('数据质量问题')
    const items = w.findAll('.ux-card')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('sc-a')
    expect(items[0].text()).toContain('步骤 0')
    expect(items[0].text()).toContain('no_endpoint_id')
    expect(items[0].find('a').attributes('href')).toBe('/scenarios/sc-a/detail')
  })

  it('「去场景处理」按钮跳场景详情;点头部可收起', async () => {
    const { w, router } = mountWithRouter({ steps })

    await w.find('[data-testid="unindexed-go-1"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/scenarios/sc-b/detail')

    await w.find('[data-testid="unindexed-toggle"]').trigger('click')
    expect(w.findAll('.ux-card').length).toBe(0)   // 收起
    await w.find('[data-testid="unindexed-toggle"]').trigger('click')
    expect(w.findAll('.ux-card').length).toBe(2)   // 再展开
  })
})
