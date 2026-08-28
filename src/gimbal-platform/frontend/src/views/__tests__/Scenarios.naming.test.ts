/**
 * Scenarios — 命令文案用场景 name(行对象在手,零获取)。
 *
 * 契约:删除确认 / 删除成功 toast / 复制成功 toast 从裸 scenarioId 改为
 * `meta.name || scenarioId`(与发布/下架确认的既有 name-first 写法对齐;
 * 卡片副行 id、URL、导出文件名不在契约内)。
 * 建件结构抄 Scenarios.expire.test.ts(router mock + listScenarios spyOn)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import Scenarios from '@/views/Scenarios.vue'
import * as api from '@/api/scenario-composer'
import { confirmAction } from '@/utils/confirmAction'
import type { Scenario } from '@/types/scenario-composer'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})
// jsdom 下 ElMessageBox 无人可点 — mock 自动确认,断言捕获的文案。
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
}))

function row(over: Partial<Scenario['meta']>): Scenario {
  return {
    meta: {
      scenarioId: 'sc-x',
      name: '订单查询',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      ...over,
    },
    steps: [],
    dataSetCount: 0,
    stepCount: 0,
    tags: [],
    visibility: 'private',
    starred: false,
  }
}

function mountPage() {
  return mount(Scenarios, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

/** 通过第一行 dropdown 的 @command 真实链路触发 onCmd(与生产绑定同一条路)。 */
async function emitCommand(w: ReturnType<typeof mountPage>, cmd: string) {
  w.findComponent({ name: 'ElDropdown' }).vm.$emit('command', cmd)
  await flushPromises()
}

describe('Scenarios — 删除/复制文案用 name', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // restoreAllMocks 会清 mockResolvedValue — 构造器 impl 的自动确认
    // 存活,但保险起见显式重建(run.test.ts 同款防御注释)。
    vi.mocked(confirmAction).mockResolvedValue(true)
  })

  it('删除确认与删除成功 toast 都用 name', async () => {
    vi.spyOn(api, 'listScenarios').mockResolvedValue([row({})])
    vi.spyOn(api, 'deleteScenario').mockResolvedValue(undefined)
    const toast = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)

    const w = mountPage()
    await flushPromises()
    await emitCommand(w, 'delete')

    const confirmMsg = vi.mocked(confirmAction).mock.calls[0][0] as string
    expect(confirmMsg).toContain('订单查询')
    expect(confirmMsg).not.toContain('sc-x')
    expect(toast).toHaveBeenCalledWith('已删除：订单查询')
    w.unmount()
  })

  it('复制成功 toast 用 name(后端返回的 saved 场景)', async () => {
    vi.spyOn(api, 'listScenarios').mockResolvedValue([row({})])
    vi.spyOn(api, 'copyScenario').mockResolvedValue(
      row({ scenarioId: 'sc-copy', name: '订单查询' }),
    )
    const toast = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)

    const w = mountPage()
    await flushPromises()
    await emitCommand(w, 'copy')

    expect(toast).toHaveBeenCalledWith('已复制到我的场景：订单查询')
    w.unmount()
  })
})
