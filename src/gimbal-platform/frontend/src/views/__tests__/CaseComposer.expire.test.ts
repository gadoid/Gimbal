/**
 * CaseComposer.vue — ① 基本信息的 expire 状态同步到编排页顶栏(2026-08-25)。
 *
 * 锁死:meta.expire=true 时顶栏标题置灰(.expired)+ 灰色「已过期」pill;
 * expire=false 时两者都不出现;在 ① step 实时切换开关,顶栏无需保存立即
 * 跟随(v-model → definition.meta → 顶栏 computed 链路)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

// ── vue-router mock:CaseComposer 只读 params.scenarioId / query.step ──
const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn().mockResolvedValue(undefined) }),
  }
})

function sampleScenario(expire: boolean): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: [],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 0,
    tags: [],
  }
}

function mountPage() {
  return mount(CaseComposer, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
})

describe('CaseComposer — expire 状态同步顶栏渲染', () => {
  it('expire=true:标题置灰 + 「已过期」pill', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(true))
    const w = mountPage()
    await flushPromises()

    const title = w.find('h1.title')
    expect(title.classes()).toContain('expired')
    const pill = w.find('.expire-pill')
    expect(pill.exists()).toBe(true)
    expect(pill.text()).toContain('已过期')
    w.unmount()
  })

  it('expire=false:无置灰、无 pill', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const w = mountPage()
    await flushPromises()

    expect(w.find('h1.title').classes()).not.toContain('expired')
    expect(w.find('.expire-pill').exists()).toBe(false)
    w.unmount()
  })

  it('① step 实时切换开关 → 顶栏立即出现/消失 pill(无需保存)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const w = mountPage()
    await flushPromises()

    // step① 默认展示;Meta 里唯一的 el-switch 就是 过期(expire)
    await w.find('.el-switch').trigger('click')
    await flushPromises()
    expect(w.find('.expire-pill').exists()).toBe(true)
    expect(w.find('h1.title').classes()).toContain('expired')

    await w.find('.el-switch').trigger('click')
    await flushPromises()
    expect(w.find('.expire-pill').exists()).toBe(false)
    w.unmount()
  })
})
