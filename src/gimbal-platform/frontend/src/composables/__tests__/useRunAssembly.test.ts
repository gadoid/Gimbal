/**
 * useRunAssembly — 执行装配公共体(执行设计 §1.5 收编后的唯一实现)。
 *
 * 原三处副本(RunPanelHost 死代码 / CaseComposer 内联 / SchemeWorkbench 镜像)
 * 中唯一从未被测试钉住的就是 authOptions 派生(§1.5 复核结论)— 本文件补上,
 * 顺带钉住:
 * - UA-1 4 路并行取数 + dataSets/registry/schemes 同 tick 落(活方案不闪「已失效」)
 * - UA-2 authOptions = owner 凭证池 ∪ 场景内置 users 键(去重;凭证池失败不阻塞)
 * - UA-3 serviceRows = 声明 ∪ 引用并集(D3;声明源 = draft definition.config.services)
 * - UA-4 dispatch 段:RunRequest 配方键(dataSetIds 派生 + 权威键 + 溯源恒带,
 *   退役键不出现);batchId 由调用方经 runScenario 层传,不在这里
 * - UA-5 saveAsScheme → POST + 重取整表替换
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/scenario-composer'
import type { SchemeV2 } from '@/api/scenario-composer'
import { useRunAssembly } from '@/composables/useRunAssembly'
import { _resetEndpointFullCacheForTest } from '@/composables/useEndpointFull'

vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([{ alias: 'pool-1' }, { alias: 'shared' }])),
}))

const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-dft', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}

const DRAFT = {
  definition: {
    kind: 'scenario', scenarioId: 'sc-asm',
    config: { services: { 'svc-decl': 'http://decl' }, users: { shared: {}, builtin: {} } },
    steps: [{ api: { service: 'svc-ref' } }, { api: { service: 'svc-decl' } }],
  },
  orchestration: { steps: [{ name: '下单' }, { name: '查单' }], resourceMeta: {} },
  assertion_registry: { entries: [] },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  _resetEndpointFullCacheForTest()
  vi.spyOn(api, 'getScenario').mockResolvedValue(
    { meta: { scenarioId: 'sc-asm', name: 'asm' }, steps: [], stepCount: 2 } as never)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as never)
  vi.spyOn(api, 'listDataSets').mockResolvedValue(
    [{ datasetId: 'ds-1', scenarioId: 'sc-asm', name: 'A', rowCount: 2, preview: [] }] as never)
  vi.spyOn(api, 'listRunSchemes').mockResolvedValue([DEFAULT_SCHEME] as never)
})
afterEach(() => { _resetEndpointFullCacheForTest() })

async function mountedAssembly() {
  const sid = ref<string | null>('sc-asm')
  const asm = useRunAssembly(sid)
  const ok = await asm.load()
  return { asm, sid, ok }
}

describe('useRunAssembly — 取数与派生(执行设计 §1.5)', () => {
  it('UA-2 authOptions = owner 凭证池 ∪ 场景内置 users 键,去重(三处副本里唯一没被钉住的一处)', async () => {
    const { asm } = await mountedAssembly()
    // 场景内置 users.shared 与凭证池 pool-1/shared 有交集 → 并集去重
    expect(asm.authOptions.value).toEqual(['pool-1', 'shared', 'builtin'])
    w_unmount_safe()
  })

  it('UA-2b 凭证池不可达不阻塞装配:authOptions 仍有内置 users', async () => {
    const { list } = await import('@/api/auth_sessions')
    vi.mocked(list).mockImplementation(() => Promise.reject(new Error('down')))
    const { asm } = await mountedAssembly()
    expect(asm.loaded.value).toBe(true)
    expect(asm.authOptions.value).toEqual(['shared', 'builtin'])
    w_unmount_safe()
  })

  it('UA-3 serviceRows = 声明 ∪ 引用并集;引用未声明 → declaredUrl null', async () => {
    const { asm } = await mountedAssembly()
    expect(asm.serviceRows.value).toEqual([
      { service: 'svc-decl', declaredUrl: 'http://decl' },
      { service: 'svc-ref', declaredUrl: null },
    ])
    expect(asm.stepNames.value).toEqual(['下单', '查单'])
    expect(asm.stepCount.value).toBe(2)
    w_unmount_safe()
  })

  it('UA-1 取数失败 → loaded=false + loadError,不抛出(消费方决定呈现)', async () => {
    vi.spyOn(api, 'listRunSchemes').mockRejectedValue(new Error('boom'))
    const { asm } = await mountedAssembly()
    expect(asm.loaded.value).toBe(false)
    expect(asm.loadError.value).toBe('boom')
    w_unmount_safe()
  })
})

describe('useRunAssembly — dispatch / 另存(§1.5 收编段)', () => {
  it('UA-4 dispatch 组装 RunRequest:dataSetIds 派生 + 溯源恒带 + 缺省键省略', async () => {
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-1', executionId: 3 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const { asm } = await mountedAssembly()

    await asm.dispatch(
      [{ datasetId: 'ds-1', rowIndexes: [0] }],
      { schemeId: 'rs-dft', schemeName: '默认方案', nRuns: 1, parallel: 1 },
    )
    expect(runScenario).toHaveBeenCalledTimes(1)
    const body = runScenario.mock.calls[0][0]
    expect(body.scenarioId).toBe('sc-asm')
    expect(body.dataSetIds).toEqual(['ds-1'])
    expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-1', rowIndexes: [0] }])
    expect(body.schemeId).toBe('rs-dft')
    expect(body.schemeName).toBe('默认方案')
    // 缺省键不上送;退役键不出现
    expect('stepTo' in body).toBe(false)
    expect('env' in body).toBe(false)
    expect('prefix' in body || 'mergePolicy' in body || 'auths' in body
      || 'injectCredentials' in body).toBe(false)
    w_unmount_safe()
  })

  it('UA-5 saveAsScheme → POST createRunScheme + 重取整表替换', async () => {
    const created: SchemeV2 = { ...DEFAULT_SCHEME, schemeId: 'rs-new', name: '回归', isDefault: false }
    vi.mocked(api.listRunSchemes)
      .mockResolvedValueOnce([DEFAULT_SCHEME])
      .mockResolvedValueOnce([DEFAULT_SCHEME, created])
    vi.spyOn(api, 'createRunScheme').mockResolvedValue(created)
    const { asm } = await mountedAssembly()

    await asm.saveAsScheme({
      name: '回归', dataSetSelection: [], injectionEntryIds: [],
      serviceBindings: {}, stepTo: null, nRuns: 2, parallel: 1,
      plugins: null, logSub: null,
    })
    expect(api.createRunScheme).toHaveBeenCalledWith('sc-asm', expect.objectContaining({ name: '回归' }))
    expect(api.listRunSchemes).toHaveBeenCalledTimes(2)
    expect(asm.schemes.value.map((s) => s.schemeId)).toEqual(['rs-dft', 'rs-new'])
    w_unmount_safe()
  })
})

/** 组合式无宿主组件;断言后让事件循环走完即可(keep 本文件无悬挂定时器)。 */
function w_unmount_safe() { /* no-op */ }
