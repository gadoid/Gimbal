/**
 * useInjectableSurface — 判定面的唯一消费面(spec 架构收敛 §2.1)。
 *
 * - IS-1 死因分组:不依赖判定面的死因(step-oob / legacy)恒入 intrinsic;
 *   仅因**契约未定**而判 path-unresolvable 的入 contractDependent(可能变活)
 * - IS-2 契约落定(声明面命中)→ contractDependent 清空
 * - IS-3 契约取数**失败** → 判定从严:path-unresolvable 归 intrinsic(不悬置)
 * - IS-12..IS-15 降级重试通道:有界退避([10s,30s,60s] 试满即停)、重试成功即解除
 *   降级、`degraded` 的宽定义(含续用旧面那一格 R21)、退避链随宿主作用域而停
 *
 * 取数纪律:取数只发生在显式时机(宿主调 `ensure()` / 降级后的有界退避定时器);
 * 判定只读共享缓存。
 * /full 是**会话级**共享缓存 → 用例间必须显式清空(useEndpointFull.test 同款纪律)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref, watch, type Ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import * as api from '@/api/scenario-composer'
import * as assertionRegistry from '@/utils/assertion-registry'
import {
  _resetEndpointFullCacheForTest, ensureEndpointFull, FULL_TTL_MS, getEndpointFull,
  surfaceVersion,
} from '@/composables/useEndpointFull'
import { useInjectableSurface } from '@/composables/useInjectableSurface'

beforeEach(() => {
  vi.useRealTimers()          // 隔离上一条用例的假时钟
  _resetEndpointFullCacheForTest()
  caseScope = effectScope()   // 每个用例一个宿主作用域(见 surface)
})
afterEach(() => {
  caseScope?.stop()           // 停作用域 = 宿主卸载:退避定时器随之取消
  vi.useRealTimers()
  vi.restoreAllMocks()
})

/** 用例级**宿主作用域** + 实例工厂:实例一律挂在这里,用例结束统一停。
 *  这不是测试脚手架 —— 真实宿主就是视图 setup,卸载即销毁。退避链是**定时器**,
 *  不销毁的实例会把定时器漏给下一个用例的新假时钟;更隐蔽的是:两个实例读同一份
 *  模块级 `failedAt`,同 eid 的旧实例会被新用例的失败**唤醒**并替它重取
 *  (计数凭空多一次,而断言看上去只是"多了个请求")。 */
let caseScope: ReturnType<typeof effectScope>
function surface(steps: Ref<any[]>, entries: Ref<any>) {
  return caseScope.run(() => useInjectableSurface(steps, entries))!
}

it('IS-1: dead 分两组 — step-oob/legacy 入 intrinsic,契约未定而 path-unresolvable 入 contractDependent', async () => {
  // 契约未回填(getFullEndpoint 挂起)→ pending=true
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise(() => {}) as any)
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-x' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 9, source: 'body', jsonpath: '$.z' }, value: 1, asserts: [] },      // step-oob → intrinsic
    { id: 'b', name: 'B', anchor: {}, asserts: [] },                                                            // legacy → intrinsic
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }, // 契约未定 → contractDependent
  ] as any)
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  const s = surface(steps, entries)
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
  // 两条条目故意都**靠声明面**才判得准:一条只在面里活(body 无 $.carry_x),
  // 一条谁都不认(面里也没有 $.nowhere)。⇒ 断言有了判别力:重取若把面闪掉
  // (在飞窗口里缓存被清 / 读口返 undefined),键就变、重算成 body 面,
  // 'alive' 当场判死 —— `['dead']` 立刻对不上。空跑的实现(body 面也判得对)
  // 则永远看不出差别,故**必须在在飞窗口里读一次**。
  const same = { id: 'ep-s', request: { declarations: [] }, declared_surface: ['$', '$.carry_x'] } as any
  let release!: (v: unknown) => void
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce(same)
    .mockReturnValueOnce(new Promise((res) => { release = res }) as any)  // 重取挂在在飞窗口里
  const project = vi.spyOn(assertionRegistry, 'injectablePathSetOf')
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-s' } } }])
  const entries = ref([
    { id: 'alive', name: 'A', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
    { id: 'dead', name: 'D', path: { stepIndex: 0, source: 'body', jsonpath: '$.nowhere' }, value: 1, asserts: [] },
  ] as any)
  const s = surface(steps, entries)
  s.ensure()
  await flushPromises()
  const first = s.pathsOfStep(0)
  expect(project).toHaveBeenCalledTimes(1)
  expect(s.deadIds.value).toEqual(['dead'])             // 面在 ⇒ 'alive' 活(不靠 body)、'dead' 死
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  s.ensure()
  // 重取**在飞**:读口不看 TTL ⇒ 面照旧被服务,判定与投影都原地不动(不闪空)
  expect(s.deadIds.value).toEqual(['dead'])
  expect(s.pathsOfStep(0)).toBe(first)
  expect(project).toHaveBeenCalledTimes(1)
  release({ ...same })                                  // 逐字相同、另一份对象 ⇒ 落定
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)                  // 到期重取了
  expect(s.surfaceChanged.value).toBe(false)            // 但面没变 ⇒ 不算换面
  expect(s.pathsOfStep(0)).toBe(first)                  // 命中同一份投影
  expect(project).toHaveBeenCalledTimes(1)              // 没白算一遍
  expect(s.deadIds.value).toEqual(['dead'])             // 落定后判定照旧
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
  const s = surface(steps, entries)
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

/* ── 降级重试通道(有界退避 + 失败态可见)────────────────────────────
 * 公共夹具:单步 + 单条**只被契约托着**的条目($.carry_field 在 body 里没有)
 * ⇒ 判定面全靠 /full 的声明面,取数失败即从严判死、条目不可勾选。 */

/** 声明面含 $.carry_field 的成功响应(退避重试恢复后的那一份)。 */
const FULL_WITH_CARRY = {
  id: 'ep-s',
  request: { declarations: [
    { name: 'carry_field', path: '$.carry_field', state: 'carry', required: true, description: '' }] },
  declared_surface: ['$', '$.carry_field'],
} as any

/** 降级夹具:单步 + 单条只被契约托着的条目(见上)。实例走用例作用域。 */
function surfaceOf(eid = 'ep-s') {
  const steps = ref([{ request: { body: {} }, api: { view_hints: { endpoint_id: eid } } }])
  const entries = ref([
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] },
  ] as any)
  return { s: surface(steps, entries), steps, entries }
}

it('IS-12: 降级后按 [10s,30s,60s] 自动重试三次 —— 试满即停(有界)', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const { s } = surfaceOf('ep-down')
  s.ensure()
  await flushPromises()
  expect(s.degraded.value).toBe(true)
  expect(spy).toHaveBeenCalledTimes(1)               // 此刻只有挂载那一次取数
  // 三档退避各试一次(下一档在上一档落定后才排 ⇒ 逐档推进 + 冲刷)
  for (const tier of [10_000, 30_000, 60_000]) {
    vi.advanceTimersByTime(tier)
    await flushPromises()
  }
  expect(spy).toHaveBeenCalledTimes(4)               // 1 首取 + 3 档退避各一次
  // **有界**:退避表试满即停 —— 再等十分钟也不会变成常驻轮询
  vi.advanceTimersByTime(600_000)
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(4)
})

it('IS-13: 退避重试成功 ⇒ 降级解除、条目由死转活(通道真的自愈)', async () => {
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockRejectedValueOnce(new Error('plate down'))  // 挂载首取失败
    .mockResolvedValue(FULL_WITH_CARRY)              // 退避那一档:plate 已恢复
  const { s } = surfaceOf()
  s.ensure()
  await flushPromises()
  expect(s.degraded.value).toBe(true)
  // 降级姿态的**可观测后果**:只被契约托着的条目被从严判死 ⇒ 不可勾选
  expect(s.dead.value.intrinsic).toEqual(['c'])
  expect(s.deadIds.value).toEqual(['c'])
  vi.advanceTimersByTime(10_000)                     // 退避第一档(与负缓存窗同宽)
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)               // ← 自动重试真的发了取数
  expect(s.degraded.value).toBe(false)               // 取回面 ⇒ 降级解除
  expect(s.dead.value.intrinsic).toEqual([])         // 条目由死转活(恢复可勾选)
  expect([...s.pathsOfStep(0)]).toContain('$.carry_field')
  // 解除即断链:再等十分钟不再重取
  vi.advanceTimersByTime(600_000)
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)
})

it('IS-16: 退避重试覆盖**全部**步骤端点 —— 无条目引用的那一步(画布侧)同时恢复', async () => {
  // 裁定 R29:画布与判定面读同一份缓存,但画布只靠预拉的覆盖面 —— 重试若只重取
  // 被条目引用那几个端点,画布当前步的声明树就整会话不自愈(降级成手写 JSON)。
  // 本用例两个端点挂载时都失败:步骤 0 **被条目引用**(降级的信号源),步骤 1
  // 无任何条目引用(画布那一侧)。一次退避必须把两个都取回来。
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockRejectedValueOnce(new Error('plate down'))   // ep-ref 挂载首取失败
    .mockRejectedValueOnce(new Error('plate down'))   // ep-canvas 挂载首取失败
    .mockResolvedValue(FULL_WITH_CARRY)               // 退避那一档:plate 已恢复
  const steps = ref([
    { request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-ref' } } },
    { request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-canvas' } } },
  ])
  const entries = ref([
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] },
  ] as any)
  const s = surface(steps, entries)
  s.ensure()
  await flushPromises()
  expect(s.degraded.value).toBe(true)
  expect(spy).toHaveBeenCalledTimes(2)               // 预拉:两个端点各一次
  expect(getEndpointFull('ep-canvas')).toBeUndefined()
  vi.advanceTimersByTime(10_000)
  await flushPromises()
  expect(new Set(spy.mock.calls.slice(2).map((c) => c[0])))
    .toEqual(new Set(['ep-ref', 'ep-canvas']))       // ← 覆盖的是全部步骤端点
  expect(getEndpointFull('ep-canvas')).toBeDefined()  // 画布那一侧一并恢复
  expect(s.degraded.value).toBe(false)
})

it('IS-17: 退避**每一档都不是空操作** —— 他处重取失败刷新了负缓存,退避照样真发', async () => {
  // 首档 10s 与负缓存窗 FAILED_RETRY_MS 同宽:退避若走「自发取数」那道闸,
  // 只要别的消费者(画布/另一宿主的手动重试)在第一档到期前刚失败过一次,
  // 窗口就被刷新到更近 ⇒ 这一档被静默吞掉,链子表面在跑、实际少试一次。
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const { s } = surfaceOf('ep-down')
  s.ensure()
  await flushPromises()
  expect(s.degraded.value).toBe(true)
  expect(spy).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(9_500)                      // 距第一档还有 0.5s
  await flushPromises()
  await ensureEndpointFull('ep-down', { force: true })   // 他处的显式重试:真发,且失败
  expect(spy).toHaveBeenCalledTimes(2)               // ⇒ 负缓存刷新到 t=9.5s
  vi.advanceTimersByTime(500)                        // t=10s:退避第一档到期
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(3)               // ← 第一档真发了(不是空操作)
})

it('IS-14: degraded 的宽定义 —— 含「续用旧面」那一格(刷新失败,旧面仍被服务)', async () => {
  // 裁定 R21:降级的判据是「本次取数失败」,**不**收窄成「没有可用面」——
  // 该重试的信号与旧面是否仍在服务无关。故这一格必须同时为真:
  // degraded=true,而 getEndpointFull/pathsOfStep 照旧供着那份旧面。
  vi.useFakeTimers()
  const spy = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce(FULL_WITH_CARRY)
    .mockRejectedValue(new Error('plate down'))      // 面 TTL 到期后的那次刷新失败
  const { s } = surfaceOf()
  s.ensure()
  await flushPromises()
  expect(s.degraded.value).toBe(false)
  expect([...s.pathsOfStep(0)]).toContain('$.carry_field')
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  s.ensure()
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(2)               // 面到期确实重取了
  expect(s.degraded.value).toBe(true)                // 刷新失败 ⇒ 降级(尽管旧面还在)
  // 反空转:这一格的「旧面仍在服务」是事实,不是靠把面清空换来的降级
  expect(getEndpointFull('ep-s')).toBeDefined()
  expect([...s.pathsOfStep(0)]).toContain('$.carry_field')
  expect(s.dead.value.intrinsic).toEqual([])         // 判定照旧(降级 ≠ 清面)
  expect(s.pending.value).toBe(false)                // 失败也是答案,不悬置(IS-3 同口径)
})

it('IS-15: 退避链随宿主作用域销毁而停 —— **待定**与**在飞**两条路径都不例外', async () => {
  vi.useFakeTimers()

  // ① 待定时的那一半:定时器已排上、还没到点 ⇒ 随作用域一起清掉
  const spy = vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const { s } = surfaceOf('ep-down')
  s.ensure()
  await flushPromises()
  // 反空转:链确实排上了(没排上的实现同样"不再重取",但那是空跑)
  expect(s.degraded.value).toBe(true)
  caseScope.stop()                                   // 宿主卸载 ⇒ 组合式同生共死
  vi.advanceTimersByTime(600_000)
  await flushPromises()
  expect(spy).toHaveBeenCalledTimes(1)

  // ② **在飞**的那一半(更隐蔽):某一档已经发出、plate 卡着不答时卸载 ——
  //    该档的尾部不得在销毁之后**重挂**下一档(它会在之后几十秒里继续取数,
  //    打向一个已死的视图)。只清待定定时器挡不住这一条。
  caseScope = effectScope()                            // 换一个新宿主
  _resetEndpointFullCacheForTest()                     // 新宿主从"未降级"起步(否则首次求值即为真,watch 不触发)
  let failInFlight!: (e: Error) => void
  const spy2 = vi.spyOn(api, 'getFullEndpoint')
    .mockRejectedValueOnce(new Error('plate down'))    // 挂载首取失败
    .mockReturnValueOnce(new Promise((_res, rej) => { failInFlight = rej }) as any)
  const s2 = surfaceOf('ep-down').s
  s2.ensure()
  await flushPromises()
  expect(s2.degraded.value).toBe(true)
  spy2.mockClear()
  vi.advanceTimersByTime(10_000)                       // 第一档发出
  await flushPromises()
  expect(spy2).toHaveBeenCalledTimes(1)                // 确实发了,且仍在飞
  caseScope.stop()                                     // 宿主卸载(plate 还卡着)
  failInFlight(new Error('plate down'))                // 这时请求才落定(失败)
  await flushPromises()
  vi.advanceTimersByTime(600_000)
  await flushPromises()
  expect(spy2).toHaveBeenCalledTimes(1)                // ← 没有重挂第二档
})
