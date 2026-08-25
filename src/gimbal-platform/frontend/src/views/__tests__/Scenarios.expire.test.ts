/**
 * Scenarios.vue — 过期(expire)条目置灰(2026-08-25)。
 *
 * 锁死:meta.expire=true 的行带 row-expired class(整行置灰)+ 场景名旁
 * 「已过期」灰 tag;正常行两者皆无。三个 tab 共用同一张表,置灰不挑桶。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import Scenarios from '@/views/Scenarios.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

function row(over: Partial<Scenario['meta']>): Scenario {
  return {
    meta: {
      scenarioId: 'sc-x', name: 'x', description: '', module: '订单',
      priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
      ...over,
    },
    steps: [], dataSetCount: 0, stepCount: 0, tags: [],
    visibility: 'private', starred: false,
  }
}

function mountPage() {
  return mount(Scenarios, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('Scenarios — 过期条目置灰', () => {
  it('expire=true 行:row-expired class + 「已过期」tag;正常行均无', async () => {
    vi.spyOn(api, 'listScenarios').mockResolvedValue([
      row({ scenarioId: 'sc-old', name: '过期用例', expire: true }),
      row({ scenarioId: 'sc-live', name: '在用用例', expire: false }),
    ])
    const w = mountPage()
    await flushPromises()

    const expiredRows = w.findAll('tr.row-expired')
    expect(expiredRows).toHaveLength(1)
    expect(expiredRows[0].text()).toContain('过期用例')
    expect(expiredRows[0].text()).toContain('已过期')

    const allRows = w.findAll('tr.el-table__row')
    expect(allRows).toHaveLength(2)
    const normal = allRows.find((r) => !r.classes().includes('row-expired'))!
    expect(normal.text()).toContain('在用用例')
    expect(normal.text()).not.toContain('已过期')
    w.unmount()
  })
})
