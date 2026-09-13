/**
 * useInjectableSurface — 判定面的唯一消费面(spec 架构收敛 §2.1)。
 *
 * - IS-1 死因分组:不依赖判定面的死因(step-oob / legacy)恒入 intrinsic;
 *   仅因**契约未定**而判 path-unresolvable 的入 contractDependent(可能变活)
 * - IS-2 契约落定(声明面命中)→ contractDependent 清空
 * - IS-3 契约取数**失败** → 判定从严:path-unresolvable 归 intrinsic(不悬置)
 *
 * 取数纪律:`ensure()` 是唯一副作用入口(宿主调用);判定只读共享缓存。
 * /full 是**会话级**共享缓存 → 用例间必须显式清空(useEndpointFull.test 同款纪律)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { nextTick, ref, watch } from 'vue'
import { flushPromises } from '@vue/test-utils'

import * as api from '@/api/scenario-composer'
import * as assertionRegistry from '@/utils/assertion-registry'
import {
  _resetEndpointFullCacheForTest, FULL_TTL_MS, surfaceVersion,
} from '@/composables/useEndpointFull'
import { useInjectableSurface } from '@/composables/useInjectableSurface'

beforeEach(() => {
  vi.useRealTimers()          // 隔离上一条用例的假时钟
  _resetEndpointFullCacheForTest()
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

it('IS-1: dead 分两组 — step-oob/legacy 入 intrinsic,契约未定而 path-unresolvable 入 contractDependent', async () => {
  // 契约未回填(getFullEndpoint 挂起)→ pending=true
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise(() => {}) as any)
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-x' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 9, source: 'body', jsonpath: '$.z' }, value: 1, asserts: [] },      // step-oob → intrinsic
    { id: 'b', name: 'B', anchor: {}, asserts: [] },                                                            // legacy → intrinsic
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }, // 契约未定 → contractDependent
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await nextTick()
  expect(s.pending.value).toBe(true)
  expect(s.dead.value.intrinsic.sort()).toEqual(['a', 'b'])
  expect(s.dead.value.contractDependent).toEqual(['c'])
})

it('IS-2: 契约落定后 contractDependent 清空(声明面命中)', async () => {
  // declared_surface 是后端算好的声明面(容器前缀 / 模板形态已展开)——
  // 判定面的声明半只读它,归一化在平台侧完成
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-x',
    request: { declarations: [
      { name: 'carry_field', path: '$.carry_field', state: 'carry', required: true, description: '' }] },
    declared_surface: ['$', '$.carry_field'],
  } as any)
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-x' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 9, source: 'body', jsonpath: '$.z' }, value: 1, asserts: [] },
    { id: 'b', name: 'B', anchor: {}, asserts: [] },
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  expect(s.pending.value).toBe(false)
  expect(s.dead.value.contractDependent).toEqual([])
  // 反空转:契约确实是"由死转活"(否则 contractDependent 空可能与判定恒空同形)
  expect(s.dead.value.intrinsic.sort()).toEqual(['a', 'b'])
})

it('IS-3: 契约取数**失败** → 判定从严,path-unresolvable 归 intrinsic(不是悬置)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const steps = ref([{ request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-down' } } }])
  const entries = ref([{ id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  expect(s.pending.value).toBe(false)                 // 有答案了(失败也是答案)
  expect(s.dead.value.contractDependent).toEqual([])  // 不悬置
  expect(s.dead.value.intrinsic).toEqual(['c'])       // 从严:真死
})

it('IS-5: steps 就地编辑(body 删字段)→ 判定跟着走(记忆化不得粘住旧集合)', async () => {
  // 记忆化的另一个失效面:**就地**深编辑(同一个 step / 同一个 body 对象,
  // 只有深属性变化)。neededEndpoints 只跟踪 view_hints,不跟踪 body ——
  // 光靠它的整表替换清不掉这里的旧集合,判活判死会静默漂移。
  const steps = ref([{ request: { body: { amount: 'x' } }, api: {} }])
  const entries = ref([
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  expect(s.dead.value.intrinsic).toEqual([])              // body 里有 $.amount → 活
  delete (steps.value[0].request.body as Record<string, unknown>).amount
  await nextTick()
  expect(s.dead.value.intrinsic).toEqual(['c'])           // 字段没了 → 判死(不是缓存的旧集合)
})

it('IS-4: `pending` 只看**被条目引用到**的端点 —— 无关端点在途不悬置判定面(但会被预取)', async () => {
  // 旧的四份 contractPending 遍历全部带 endpoint_id 的步骤:一个与条目无关的
  // 端点在途,就把整个判定面悬置(preset 预勾被推迟、禁选态闪烁)。
  // 预取面与在途面**故意不同**:预取要覆盖全部步骤(读端不取数,候选/取态
  // 得问任意 si),在途面只认被引用到的(否则无关端点能悬置整个判定面)。
  const deferred: Record<string, (v: unknown) => void> = {}
  vi.spyOn(api, 'getFullEndpoint').mockImplementation((id: string) =>
    new Promise((res) => { deferred[id] = res }) as any)
  const steps = ref([
    { request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-ref' } } },
    { request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-unrelated' } } },
  ])
  const entries = ref([
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.ghost' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await nextTick()
  expect(s.pending.value).toBe(true)                  // 被引用端点在途 → 悬置
  expect(s.dead.value.contractDependent).toEqual(['c'])
  // 预取面 = 全部带 endpoint_id 的步骤(幂等:每端点在面 TTL 内一次)
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-ref')
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-unrelated')
  // 只落定被引用端点 ⇒ 在途面清空;无关端点即便仍挂着也不悬置
  deferred['ep-ref']({ id: 'ep-ref', request: { declarations: [] }, declared_surface: ['$'] })
  await flushPromises()
  expect(s.pending.value).toBe(false)
  expect(s.dead.value.intrinsic).toEqual(['c'])       // 有答案 ⇒ 从严判死
  expect(s.dead.value.contractDependent).toEqual([])
})

it('IS-6: 未被条目引用的 si —— 该步端点落定后其声明面仍须进候选(键含该 si 自身的端点态)', async () => {
  // 复核探针 PROBE-A:键若用「被引用端点的联合版本」,无条目引用的 si 落定
  // 既不换键也不清缓存 ⇒ 候选永久停在 body 面 —— 而编辑器给新条目挑字段
  // (v3.1 §2.1 放宽服务的那条路径)问的正是这种 si。
  const deferred: Record<string, (v: unknown) => void> = {}
  vi.spyOn(api, 'getFullEndpoint').mockImplementation((id: string) =>
    new Promise((res) => { deferred[id] = res }) as any)
  const steps = ref([
    { request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-a' } } },
    { request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-b' } } },
  ])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await nextTick()
  expect([...s.pathsOfStep(1)]).toEqual(['$'])        // 步骤 1 无条目引用:此刻只有 body 面
  deferred['ep-b']({ id: 'ep-b', request: { declarations: [
    { name: 'carry_x', path: '$.carry_x', state: 'carry', required: true, description: '' }] },
    declared_surface: ['$', '$.carry_x'] })
  await flushPromises()
  expect([...s.pathsOfStep(1)]).toContain('$.carry_x')   // 落定 ⇒ 立即进候选
  expect(s.stateOf(1, '$.carry_x')).toBe('carry')        // 取态同一条读路径
})

it('IS-7: 渲染期零请求 —— 不调 ensure() 时判定/候选/取态都不触达取数口', async () => {
  // 复核探针:读路径必须纯缓存读 —— 若任何读函数内部 `void ensureEndpointFull`,
  // 则只 watchEffect 读一下 deadIds、全程不调 ensure(),getFullEndpoint 照样
  // 被调用(正是本用例要拦的形状)。读 / 取分离 ⇒ 渲染色路径是纯缓存读。
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValue({ id: 'ep-a', request: { declarations: [] }, declared_surface: ['$'] } as any)
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-a' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  // 渲染色路径:computed 消费判定面(宿主与展示面都这么读)
  void s.deadIds.value
  void s.dead.value
  void s.pathsOfStep(0)
  void s.stateOf(0, '$.amount')
  void s.deadOf(entries.value[0])
  void s.pending.value
  await nextTick()
  expect(spy).not.toHaveBeenCalled()                  // ← 全程未调 ensure() ⇒ 零请求
  // 反空转:显式 ensure() 才取数,且幂等(第二次在面 TTL 内不再发)
  s.ensure()
  await flushPromises()
  s.ensure()
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(1)
  expect([...s.pathsOfStep(0)]).toContain('$.amount')
})

it('IS-8: 记忆化**命中**面 — 同一 (si, 版本) 只投影一次,输入变化后才重建', async () => {
  // spec §8 要求「前端集合按 `(stepIndex, 版本)` 记忆化(以调用计数断言)」。
  // IS-5 / IS-6 钉的是**失效**面(陈旧集合不得粘住),命中面此前无人钉:删掉
  // `pathsCache` 整块,全部用例照样绿。故这里**数投影的调用次数** —— 返回值
  // 在「有缓存」与「每次重建」两种实现下同形,只有计数有判别力。
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(
    { id: 'ep-a', request: { declarations: [] }, declared_surface: ['$'] } as any)
  const project = vi.spyOn(assertionRegistry, 'injectablePathSetOf')
  const steps = ref([
    { request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-a' } } },
  ])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  const first = s.pathsOfStep(0)
  const again = s.pathsOfStep(0)
  expect(project).toHaveBeenCalledTimes(1)            // 同键第二次 → 命中,不再投影
  expect(again).toBe(first)                           // 命中的是同一份(不是等值副本)
  // 版本维变化(步骤面深变更)→ 键变 ⇒ 重建(且新集合含新字段)
  const body = steps.value[0].request.body as Record<string, unknown>
  body.amount2 = 'y'
  await nextTick()
  const rebuilt = s.pathsOfStep(0)
  expect(project).toHaveBeenCalledTimes(2)
  expect(rebuilt).not.toBe(first)
  expect([...rebuilt]).toContain('$.amount2')
})

it('IS-9: 换面即重判 —— 面变后按新面重算 dead(灰显),勾选保留、不阻断提交', async () => {
  // spec §3.3 换面 policy:前端缓存的 300s TTL 到期重取 ⇒ 会话中途会换面。
  // 换面 = 面变了(不是面悬置):判定按新面重算,因新面而悬空的条目进 deadIds
  // (悬空标注的唯一口径 ⇒ 灰显);**勾选保留** —— 判定面从不改写 entries,
  // 已选中条目交 dispatch 侧既有 dangling skip 兜底,不新造失败态。
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce({
      id: 'ep-s',
      request: { declarations: [
        { name: 'carry_field', path: '$.carry_field', state: 'carry', required: true, description: '' }] },
      declared_surface: ['$', '$.carry_field'],
    } as any)
    .mockResolvedValue({                                    // 重取回来的新面:carry_field 没了
      id: 'ep-s', request: { declarations: [] }, declared_surface: ['$'],
    } as any)
  const entry = { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-s' } } }])
  const entries = ref([entry] as any)
  const s = useInjectableSurface(steps, entries)
  const selectedBefore = entries.value[0]                // 宿主选中的那条(ref 的代理身份)
  const stepBefore = steps.value[0]
  s.ensure()
  await flushPromises()
  expect(s.dead.value.intrinsic).toEqual([])            // v1 面:条目活
  expect(s.surfaceChanged.value).toBe(false)            // 还没换过面
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  s.ensure()
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)                  // 面确实重取了
  expect(s.dead.value.intrinsic).toEqual(['c'])         // 新面下悬空 ⇒ 重判(不是粘住的旧集合)
  expect(s.deadIds.value).toContain('c')                // 灰显口径 = 门控后死集
  expect(s.pending.value).toBe(false)                   // 换面 ≠ 面悬置:pending 语义不动(§3.3)
  expect(s.surfaceChanged.value).toBe(true)             // 非阻断提示的信号(呈现位由视图绑定)
  expect(entries.value).toHaveLength(1)                 // 条目**不被改写**:判死不等于删条目
  expect(entries.value[0]).toBe(selectedBefore)         // 同一份:勾选状态原样保留
  expect(entries.value[0].path).toEqual(entry.path)     // 路径也没被判定面动过
  expect(steps.value[0]).toBe(stepBefore)               // 步骤面同样不被改写
})

it('IS-10: 面没变的重取不惊动记忆化 —— 版本不动 ⇒ 投影不重算', async () => {
  vi.useFakeTimers()
  const same = { id: 'ep-s', request: { declarations: [] }, declared_surface: ['$'] } as any
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce(same)
    .mockResolvedValue({ ...same } as any)                // 逐字相同、另一份对象
  const project = vi.spyOn(assertionRegistry, 'injectablePathSetOf')
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-s' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  const first = s.pathsOfStep(0)
  expect(project).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  s.ensure()
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)                  // 到期重取了
  expect(s.surfaceChanged.value).toBe(false)            // 但面没变 ⇒ 不算换面
  expect(s.pathsOfStep(0)).toBe(first)                  // 命中同一份投影
  expect(project).toHaveBeenCalledTimes(1)              // 没白算一遍
  expect(s.deadIds.value).toEqual([])                   // 判定面照旧:活条目没被无谓作废
})

it('IS-11: 换面重判锚在**记忆化键**上 —— 不靠「清缓存 watch」的冲刷时机', async () => {
  // 键必须覆盖投影读的每一个输入,换面即键变 —— 这条**正确性**不能依赖调度
  // 时机(清缓存的 pre-flush watch 谁先谁后)。探针用 flush:'sync' 的 watcher
  // 在面版本变化的**同一次**变更里读 pathsOfStep:此刻清缓存的 watch 还没跑,
  // 键若不带面版本,读到的就是按旧面算出的陈旧集合(IS-9 由清缓存兜住,**看不出
  // 这个差别** —— 删掉键里的版本那一半,本例红、IS-9 仍绿)。
  vi.useFakeTimers()
  vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce({
      id: 'ep-s', request: { declarations: [] }, declared_surface: ['$', '$.carry_x'],
    } as any)
    .mockResolvedValue({
      id: 'ep-s', request: { declarations: [] }, declared_surface: ['$'],
    } as any)
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-s' } } }])
  const entries = ref([] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  expect([...s.pathsOfStep(0)]).toContain('$.carry_x')  // v1 面
  const seen: string[][] = []
  const stop = watch(() => surfaceVersion('ep-s'), () => {
    seen.push([...s.pathsOfStep(0)])
  }, { flush: 'sync' })
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  s.ensure()
  await flushPromises()
  stop()
  expect(seen).toHaveLength(1)                          // 面版本恰好变了一次
  expect(seen[0]).toContain('$.amount')                 // 是**真投影**(不是空集)
  expect(seen[0]).not.toContain('$.carry_x')            // 当场已按新面重判,不是陈旧集合
  vi.useRealTimers()
})
