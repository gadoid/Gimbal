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

it('IS-4: 只对「被条目引用到的端点」在途 —— 无关端点挂起不悬置判定面', async () => {
  // 旧的四份 contractPending 遍历全部带 endpoint_id 的步骤:一个与条目无关的
  // 端点在途,就把整个判定面悬置(preset 预勾被推迟、禁选态闪烁)。
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise(() => {}) as any)
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
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-ref')
  expect(api.getFullEndpoint).not.toHaveBeenCalledWith('ep-unrelated')
  expect(s.pending.value).toBe(true)                  // 被引用端点在途 → 悬置
  expect(s.dead.value.contractDependent).toEqual(['c'])
})
