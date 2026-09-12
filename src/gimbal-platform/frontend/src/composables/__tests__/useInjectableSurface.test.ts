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
import { nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import * as api from '@/api/scenario-composer'
import { _resetEndpointFullCacheForTest } from '@/composables/useEndpointFull'
import { useInjectableSurface } from '@/composables/useInjectableSurface'

beforeEach(() => {
  _resetEndpointFullCacheForTest()
})
afterEach(() => { vi.restoreAllMocks() })

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
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({ id: 'ep-x', request: { declarations: [
    { name: 'carry_field', path: '$.carry_field', state: 'carry', required: true, description: '' }] } } as any)
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
  // 预取面 = 全部带 endpoint_id 的步骤(幂等:每端点每会话一次)
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-ref')
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-unrelated')
  // 只落定被引用端点 ⇒ 在途面清空;无关端点即便仍挂着也不悬置
  deferred['ep-ref']({ id: 'ep-ref', request: { declarations: [] } })
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
    { name: 'carry_x', path: '$.carry_x', state: 'carry', required: true, description: '' }] } })
  await flushPromises()
  expect([...s.pathsOfStep(1)]).toContain('$.carry_x')   // 落定 ⇒ 立即进候选
  expect(s.stateOf(1, '$.carry_x')).toBe('carry')        // 取态同一条读路径
})

it('IS-7: 渲染期零请求 —— 不调 ensure() 时判定/候选/取态都不触达取数口', async () => {
  // 复核探针:读路径必须纯缓存读 —— 若任何读函数内部 `void ensureEndpointFull`,
  // 则只 watchEffect 读一下 deadIds、全程不调 ensure(),getFullEndpoint 照样
  // 被调用(正是本用例要拦的形状)。读 / 取分离 ⇒ 渲染色路径是纯缓存读。
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValue({ id: 'ep-a', request: { declarations: [] } } as any)
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
  // 反空转:显式 ensure() 才取数,且幂等(第二次不再发)
  s.ensure()
  await flushPromises()
  s.ensure()
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(1)
  expect([...s.pathsOfStep(0)]).toContain('$.amount')
})
