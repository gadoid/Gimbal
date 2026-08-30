/**
 * useSystemPrefill.test.ts — 选系统 → 场景骨架预填(meta 通用 / config·resource 按系统)。
 *
 * 锁定的行为契约(用户已确认的设计):
 * 1. 仅新建场景预填;编辑场景(isNew=false)永不预填。
 * 2. config/resource 已有内容(用户编辑过)→ 不覆盖。
 * 3. meta 只从 common 通用定义加载公共项(version/priority/expire/
 *    requirementRef);name 等用户字段与 system 选择永不采用。
 * 4. config = common 基座(timePolicy/retry/setup/teardown)+ 各选中系统
 *    services/users/vars 浅合并(命名约定防碰撞)。
 * 5. resource = 各选中系统资源并集。
 * 6. 首次预填成功后,切换系统不重载;plate 不可达时静默保留默认结构。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import * as plateApi from '@/api/plate'
import type { ConfigView, MetaView, ResourceView, ScenarioView } from '@/types/plate'
import { useSystemPrefill } from '@/composables/useSystemPrefill'

function newDefinition(system: string[]): ScenarioView {
  return {
    kind: 'scenario',
    scenarioId: 'sc-new',
    meta: {
      name: '', description: '', module: '', priority: 1,
      author: '', owner: '', tags: [],
      version: 'v0.1.0',
      createTime: '2026-08-30T00:00:00.000Z',
      expire: false, requirementRef: [], system,
    },
    config: {
      setup: [], teardown: [], services: {}, users: {},
      timePolicy: { kind: 'record' }, retry: null, vars: {},
    },
    resource: {},
    steps: [],
  }
}

const COMMON_CONFIG: ConfigView = {
  setup: [{ do: 'common.init' }], teardown: [{ do: 'common.cleanup' }],
  services: {}, users: {},
  timePolicy: { kind: 'timeout', seconds: 60 },
  retry: null, vars: {},
}

const COMMON_META: MetaView = {
  name: '', description: '', module: '', priority: 2,
  author: '', owner: '', tags: [],
  version: '1.0.0',
  createTime: '2026-01-01T00:00:00Z',
  expire: true, requirementRef: ['REQ-1'], system: ['common'],
}

const FIN_CONFIG: ConfigView = {
  setup: [], teardown: [],
  services: { 'fin-service': 'https://fin' },
  users: { fin_a: { username: 'a' } as ConfigView['users'][string] },
  timePolicy: { kind: 'record' },
  retry: null,
  vars: { fin_base_url: 'https://fin' },
}

const LOGI_CONFIG: ConfigView = {
  setup: [], teardown: [],
  services: { 'logi-service': 'https://logi' },
  users: {},
  timePolicy: { kind: 'record' },
  retry: null,
  vars: { logi_base_url: 'https://logi' },
}

const FIN_RESOURCES: Record<string, ResourceView> = {
  'fin.tidb_test': { kind: 'mock', name: 'fin.tidb_test', image: 'img', config: {}, portMapping: {} },
}

/** 挂载纯逻辑单元:definition ref + composable,不渲染组件。 */
function setup(definition: ScenarioView, isNew: boolean) {
  const def = ref(definition)
  useSystemPrefill(def, ref(isNew))
  return def
}

/** 默认 mock:common seed + fin/logi config/resource。 */
function mockPlateAll() {
  vi.spyOn(plateApi, 'fetchSystemConfig').mockImplementation(async (system: string) => {
    if (system === 'common') return COMMON_CONFIG
    if (system === 'fin') return FIN_CONFIG
    if (system === 'logi') return LOGI_CONFIG
    return null
  })
  vi.spyOn(plateApi, 'fetchSystemMeta').mockImplementation(async (system: string) =>
    system === 'common' ? COMMON_META : null)
  vi.spyOn(plateApi, 'fetchSystemResources').mockImplementation(async (system: string) =>
    system === 'fin' ? FIN_RESOURCES : {})
}

describe('useSystemPrefill', () => {
  beforeEach(() => mockPlateAll())
  afterEach(() => vi.restoreAllMocks())

  it('新建场景:挂载即按默认选中系统预填(immediate),多系统 services/users/vars 浅合并 + resource 并集', async () => {
    const def = setup(newDefinition(['fin', 'logi']), true)
    await flushPromises()

    // config:common 基座 + 两系统业务段合并
    expect(def.value.config.timePolicy).toEqual({ kind: 'timeout', seconds: 60 })
    expect(def.value.config.setup).toEqual([{ do: 'common.init' }])
    expect(def.value.config.services).toEqual({
      'fin-service': 'https://fin', 'logi-service': 'https://logi',
    })
    expect(def.value.config.vars).toEqual({
      fin_base_url: 'https://fin', logi_base_url: 'https://logi',
    })
    expect(def.value.config.users).toEqual({ fin_a: { username: 'a' } })
    // resource:fin 并集
    expect(def.value.resource).toEqual(FIN_RESOURCES)
  })

  it('meta 只采用 common 公共项;name/createTime/system 保持本地值', async () => {
    const def = setup(newDefinition(['fin']), true)
    await flushPromises()

    expect(def.value.meta.version).toBe('1.0.0')
    expect(def.value.meta.priority).toBe(2)
    expect(def.value.meta.expire).toBe(true)
    expect(def.value.meta.requirementRef).toEqual(['REQ-1'])
    // 用户/本地字段不被通用定义覆盖
    expect(def.value.meta.name).toBe('')
    expect(def.value.meta.createTime).toBe('2026-08-30T00:00:00.000Z')
    expect(def.value.meta.system).toEqual(['fin'])
  })

  it('编辑场景(isNew=false)永不预填', async () => {
    const def = setup(newDefinition(['fin']), false)
    await flushPromises()
    expect(def.value.config.services).toEqual({})
    expect(def.value.resource).toEqual({})
    expect(def.value.meta.version).toBe('v0.1.0')
  })

  it('config/resource 已有内容(用户编辑过)→ 不预填', async () => {
    const draft = newDefinition(['fin'])
    draft.config.vars = { custom: 'x' }
    const def = setup(draft, true)
    await flushPromises()
    expect(def.value.config.services).toEqual({})
    expect(def.value.meta.version).toBe('v0.1.0')
  })

  it('首次预填成功后切换系统不重载', async () => {
    const def = setup(newDefinition(['fin']), true)
    await flushPromises()
    expect(def.value.config.services).toEqual({ 'fin-service': 'https://fin' })

    def.value.meta.system = ['logi']
    await flushPromises()
    // 仍是首次(fin)的结果
    expect(def.value.config.services).toEqual({ 'fin-service': 'https://fin' })
  })

  it('plate 不可达 → 静默保留默认结构,后续选择仍可重试', async () => {
    vi.restoreAllMocks()
    vi.spyOn(plateApi, 'fetchSystemConfig').mockRejectedValue(new Error('net'))
    vi.spyOn(plateApi, 'fetchSystemMeta').mockRejectedValue(new Error('net'))
    vi.spyOn(plateApi, 'fetchSystemResources').mockRejectedValue(new Error('net'))

    const def = setup(newDefinition(['fin']), true)
    await flushPromises()

    expect(def.value.config.services).toEqual({})
    expect(def.value.resource).toEqual({})
    expect(def.value.meta.version).toBe('v0.1.0')

    // 失败可重试:守卫仍放行后续选择变化
    mockPlateAll()
    def.value.meta.system = ['fin', 'logi']
    await flushPromises()
    expect(def.value.config.services).toEqual({
      'fin-service': 'https://fin', 'logi-service': 'https://logi',
    })
  })
})
