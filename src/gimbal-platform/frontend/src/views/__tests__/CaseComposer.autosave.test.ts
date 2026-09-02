/**
 * CaseComposer — 防抖自动保存 + 脏标记状态机修复(2026-09-02):
 * - 已保存场景编辑停顿 2.5s → 自动 PUT 最新草稿(自动路径不弹 lint/错误 toast);
 * - 加载完成不触发伪 dirty 的自动保存(watch 在 loadScenario 赋值上也会触发);
 * - 保存进行中的编辑不被吞:保存完成后 dirty 保留,防抖再存最新草稿;
 * - 运行前 flush:dirty 未到防抖窗口即点运行 → 先保存再开弹窗/发起;
 * - 离开防线:dirty 时 beforeunload preventDefault;onBeforeRouteLeave 三选
 *   (保存并离开 / 放弃修改并离开 / ESC 留下)。
 *
 * 建件:真实 vue-router(memory history + router-view 挂载)而非模块 mock —
 * onBeforeRouteLeave 只在真实路由上下文注册。fake timers 仅 fake
 * setTimeout/clearTimeout(Vue 调度器走微任务,flushPromises 不受影响)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ElementPlus, { ElMessageBox, type MessageBoxData } from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

/** 与组件内 AUTOSAVE_DEBOUNCE_MS 保持一致(实现侧常量,勿漂移)。 */
const AUTOSAVE_MS = 2500

// 模块 mock(构造器 impl 防 vi.restoreAllMocks 清实现,run 测试同款):
// openRunDialog 会拉执行历史/凭证池,onMounted 拉常量池 — 全部静默化。
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))

function sampleScenario(expire = false): Scenario {
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
    steps: [{ api: { service: 'fin-service', method: 'POST', path: '/x' } }] as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

let router: Router
async function mountPage(path = '/composer/sc-demo') {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/composer/:scenarioId', component: CaseComposer },
      { path: '/scenarios', component: { template: '<div id="scen-list" />' } },
    ],
  })
  router.push(path)
  await router.isReady()
  const w = mount({ template: '<router-view />' }, {
    global: { plugins: [router, ElementPlus, createPinia()] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — 防抖自动保存', () => {
  it('已保存场景编辑停顿 2.5s → 自动 PUT 最新草稿', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const update = vi.fn().mockResolvedValue(sampleScenario(true))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()
    expect(update).not.toHaveBeenCalled()

    // 编辑①:Meta 的唯一 el-switch = 过期开关 → definition.meta.expire=true
    await w.find('.el-switch').trigger('click')
    await flushPromises()
    expect(update).not.toHaveBeenCalled()   // 未到防抖窗口不发

    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update.mock.calls[0][0]).toBe('sc-demo')
    const draft = update.mock.calls[0][1] as unknown as {
      definition: { meta: { expire: boolean } }
    }
    expect(draft.definition.meta.expire).toBe(true)
    w.unmount()
  })

  it('加载完成不触发自动保存(loadScenario 赋值不是编辑)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const update = vi.fn().mockResolvedValue(sampleScenario(true))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()

    // 无任何编辑,长时间推进 → 不得出现「加载即保存」的伪 PUT
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS * 10)
    await flushPromises()
    expect(update).not.toHaveBeenCalled()
    w.unmount()
  })

  it('dirty 未到防抖窗口即点运行 → 先 flush 保存再发起运行', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const update = vi.fn().mockResolvedValue(sampleScenario(true))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-1', executionId: 1 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const w = await mountPage()

    await w.find('.el-switch').trigger('click')   // dirty,但不推进防抖时钟
    await flushPromises()
    expect(update).not.toHaveBeenCalled()

    // 顶栏「运行」:canRun 已满足(scenario + steps>0)
    await w.find('header .primary-btn').trigger('click')
    await flushPromises()
    // 开弹窗前已 flush:防「运行跑的是最后一次保存的旧版」
    expect(update).toHaveBeenCalledTimes(1)

    // 弹窗内确认 → runScenario 在 flush 之后发生
    const dlg = w.findComponent({ name: 'RunDialog' })
    expect(dlg.exists()).toBe(true)
    dlg.vm.$emit('confirm', [])
    await flushPromises()
    expect(runScenario).toHaveBeenCalledTimes(1)
    expect(update.mock.invocationCallOrder[0])
      .toBeLessThan(runScenario.mock.invocationCallOrder[0])
    w.unmount()
  })

  it('保存进行中继续编辑 → 完成后再次自动保存最新草稿(不被 1 号保存吞)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    let resolveSave!: (v: Scenario) => void
    const update = vi.fn().mockImplementation(() => new Promise<Scenario>((res) => {
      resolveSave = res
    }))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()

    // 编辑① → 防抖到点 → save1 挂起(未 resolve)
    await w.find('.el-switch').trigger('click')   // expire=true
    await flushPromises()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)

    // 编辑②发生在 save1 进行中(expire 回到 false)— 不得被 save1 的
    // 「成功即 clean」吞掉:dirty 保留,防抖到点再存最新值
    await w.find('.el-switch').trigger('click')
    await flushPromises()
    resolveSave(sampleScenario(true))
    await flushPromises()

    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS)
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(2)
    const draft2 = update.mock.calls[1][1] as unknown as {
      definition: { meta: { expire: boolean } }
    }
    expect(draft2.definition.meta.expire).toBe(false)
    w.unmount()
  })

  it('dirty 时 beforeunload 拦截;clean 时放行', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    vi.spyOn(api, 'updateScenario').mockResolvedValue(sampleScenario(true))
    const w = await mountPage()

    const clean = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(clean)
    expect(clean.defaultPrevented).toBe(false)

    await w.find('.el-switch').trigger('click')
    await flushPromises()
    const ev = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(ev)
    expect(ev.defaultPrevented).toBe(true)
    w.unmount()
  })

  it('dirty 离开路由:「放弃修改」→ 放行且不保存', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const update = vi.fn().mockResolvedValue(sampleScenario(true))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    const w = await mountPage()
    await w.find('.el-switch').trigger('click')
    await flushPromises()

    // cancel 按钮(distinguishCancelAndClose:reject 'cancel')
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
    await router.push('/scenarios')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/scenarios')
    expect(update).not.toHaveBeenCalled()
    w.unmount()
  })

  it('dirty 离开路由:「保存并离开」→ 先存后走;ESC(close)→ 留下', async () => {
    // ── 保存并离开 ──
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const update = vi.fn().mockResolvedValue(sampleScenario(true))
    vi.spyOn(api, 'updateScenario').mockImplementation(update)
    let w = await mountPage()
    await w.find('.el-switch').trigger('click')
    await flushPromises()
    vi.spyOn(ElMessageBox, 'confirm')
      .mockResolvedValue({ action: 'confirm' } as MessageBoxData)
    await router.push('/scenarios')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/scenarios')
    expect(update).toHaveBeenCalledTimes(1)
    w.unmount()

    // ── ESC/关闭 → 留下 ──
    // 不做中途 restoreAllMocks — 会清掉 beforeEach 的 listDataSets spy,
    // 第二次挂载走真实网络,loadScenario 挂起在 suppressDirty=true 上,
    // 开关编辑被误抑制 → dirty=false → 守卫误放行。改为重设各 spy 行为。
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    update.mockClear()
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('close')
    w = await mountPage()
    await w.find('.el-switch').trigger('click')
    await flushPromises()
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('close')
    await router.push('/scenarios').catch(() => { /* 守卫中止导航 */ })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/composer/sc-demo')
    expect(update).not.toHaveBeenCalled()
    w.unmount()
  })

  it('clean 离开路由:直接放行,不弹确认', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario(false))
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm')
      .mockResolvedValue({ action: 'confirm' } as MessageBoxData)
    const w = await mountPage()

    await router.push('/scenarios')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/scenarios')
    expect(confirmSpy).not.toHaveBeenCalled()
    w.unmount()
  })
})
