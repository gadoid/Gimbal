/**
 * RunDialog — 执行认证选择器(P0)
 *
 * 锁死:
 * - 选项 = 场景 config.users 别名 ∪ owner 凭证池别名,去重原序(场景在前)
 * - 默认仅勾选场景已引用的别名;凭证池独有别名列出但不勾
 * - 全不勾 → confirm opts 不携带 auths 字段(等价不注入,场景内置 users 原样)
 * - 勾选任一 → opts.auths 为所选 alias 数组
 * - append 预检:mergePolicy=append 且所选与场景内置 users 别名有交集 →
 *   不 emit confirm,提示冲突(后端会 409 整单拒,提交前拦截)
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'
import type { Scenario } from '@/types/scenario-composer'

const ENV = [{ envId: 'dev', name: 'dev', baseUrl: 'http://x' }]
const DS = [{ datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] }]

function sampleScenario(authAliases: string[]): Scenario {
  return {
    meta: {
      scenarioId: 'sc-a', name: 'x', description: '', module: 'm',
      priority: 1, author: 'qa', owner: 'qa', tags: [], system: ['fin'],
    },
    steps: [],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 0,
    tags: [],
    config: {
      users: Object.fromEntries(authAliases.map((a) => [a, { username: a }])),
    },
  } as unknown as Scenario
}

function mountDialog(scenario: Scenario | null, props: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      scenario, dataSets: DS, envs: ENV,
      running: false, lastRunId: null, lastRunError: null,
      ownerAuthAliases: [],
      ...props,
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

function authBoxes(w: ReturnType<typeof mount>) {
  return w.findAll('input[type="checkbox"]')
    .filter((i) => i.attributes('data-test') === 'auth')
}

async function clickConfirm(w: ReturnType<typeof mount>) {
  const go = w.findAll('button').find((b) => b.text().includes('发起运行'))
  await go!.trigger('click')
}

/** 最后一次 confirm 的 opts.auths(emitted() 返回 unknown[][],需断言收窄) */
function lastAuths(w: ReturnType<typeof mount>): string[] | undefined {
  const evt = w.emitted('confirm')!
  const opts = evt[evt.length - 1][2] as { auths?: string[] } | undefined
  return opts?.auths
}

describe('RunDialog — 执行认证 auths', () => {
  it('场景 2 别名:默认全勾;confirm opts.auths 按场景原序', async () => {
    const w = mountDialog(sampleScenario(['qa-token', 'admin-token']))
    expect(authBoxes(w).length).toBe(2)
    await clickConfirm(w)
    expect(lastAuths(w)).toEqual(['qa-token', 'admin-token'])
  })

  it('全取消:opts 不携带 auths 字段(等价 origin 不注入)', async () => {
    const w = mountDialog(sampleScenario(['qa-token', 'admin-token']))
    // Vue 数组 v-model 补丁期可能重建输入元素 — 每次取消都要重新查找
    // 当前 DOM 的勾选框,否则下一个 change 读到过期数组(串选,见
    // RunDialog.baseline.test.ts 同坑注释)。
    const boxes = () => authBoxes(w)
    for (let i = 0; i < boxes().length; i++) {
      await boxes()[i].setValue(false)
    }
    await clickConfirm(w)
    expect(lastAuths(w)).toBeUndefined()
  })

  it('union 去重:场景在前默认勾,凭证池独有别名列出但不勾;勾上后随 confirm 上送', async () => {
    const w = mountDialog(sampleScenario(['qa-token', 'admin-token']), {
      ownerAuthAliases: ['admin-token', 'extra-pool'],
    })
    // admin-token 去重 → 3 个选项
    expect(authBoxes(w).length).toBe(3)
    // 默认仅场景引用被勾
    await clickConfirm(w)
    expect(lastAuths(w)).toEqual(['qa-token', 'admin-token'])
    // 勾上凭证池独有别名 → 一并上送
    const extra = authBoxes(w).find((i) => (i.element as HTMLInputElement).value === 'extra-pool')!
    await extra.setValue(true)
    await clickConfirm(w)
    expect(lastAuths(w)).toEqual(['qa-token', 'admin-token', 'extra-pool'])
  })

  it('append 预检:所选与场景内置 users 交集 → 不 emit confirm', async () => {
    const w = mountDialog(sampleScenario(['qa-token']))
    const appendRadio = w.findAll('input[type="radio"]')
      .find((r) => (r.element as HTMLInputElement).value === 'append')
    await appendRadio!.setValue(true)
    await clickConfirm(w)
    expect(w.emitted('confirm')).toBeUndefined()
  })
})