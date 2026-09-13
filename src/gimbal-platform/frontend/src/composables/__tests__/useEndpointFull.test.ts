/**
 * useEndpointFull — plate /full 结构契约的**唯一**会话级缓存。
 *
 * 契约:每 endpoint 一次取数(并发收敛为同一 Promise),面有 FULL_TTL_MS
 * 有效期 —— 到期重取(EF-TTL-1),到期前不重取(EF-TTL-2);**负缓存优先于
 * TTL**,刚失败的端点不因面到期就重发(EF-TTL-6)。**读 / 取各管一头**:
 * 读口 `getEndpointFull` 不看 TTL,重取失败时旧面继续服务(EF-TTL-3)。
 * 成功入缓存 —— 容器是 Vue 原生响应式,消费方**读缓存即建立依赖**
 * (手工版本号协议已退役,EF-6 钉住该性质);失败**负缓存** ——
 * FAILED_RETRY_MS 窗口内不再发起,窗口过后允许重试(EF-7)。
 * `surfaceVersion` 是面版本:首取记 1(EF-TTL-4),内容相同的重取不动(EF-TTL-5)。
 * 入缓存时一次入口消毒(Ruling C7):路径不可用条目剔除、children 提升
 * (DP-7)—— 画布递归 `buildNode → suffixOf` 因此不再收到真值非串 path。
 *
 * 抽取自 CaseComposerCanvas 与 useFieldDescriptions 里各自的一份同款实现。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed } from 'vue'

import * as api from '@/api/scenario-composer'
import {
  _resetEndpointFullCacheForTest,
  endpointFullState,
  ensureEndpointFull,
  FAILED_RETRY_MS,
  FULL_TTL_MS,
  getEndpointFull,
  surfaceVersion,
} from '@/composables/useEndpointFull'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

const FULL = { id: 'fin.order.add', request: { declarations: [] } } as any

/** 一份 /full,只改被测的那一维:**面**(后端随 /full 算好的声明面)。 */
function fullWith(paths: string[]) {
  return { id: 'ep-1', request: { declarations: paths.map((p) => ({ path: p })) } } as any
}

/** 一条形状完整(plate wire 形状)的声明条目 —— 便于只改被测轴。 */
function decl(over: Partial<Record<string, unknown>>): DeclarationEntryView {
  return {
    name: 'x', path: '$.x', type: 'string', required: false, description: '',
    ui_kind: 'text', source_kind: 'independent', assertable: false,
    ...over,
  } as unknown as DeclarationEntryView
}

describe('useEndpointFull — /full 会话级缓存', () => {
  beforeEach(() => {
    vi.useRealTimers()          // 隔离上一条用例的 setSystemTime
    _resetEndpointFullCacheForTest()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('EF-1: 首次拉取后入缓存,面 TTL 内再次 ensure 不再发请求', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    expect(getEndpointFull('fin.order.add')).toBeUndefined()

    const first = await ensureEndpointFull('fin.order.add')
    expect(first).toBe(FULL)
    expect(getEndpointFull('fin.order.add')).toBe(FULL)

    const second = await ensureEndpointFull('fin.order.add')
    expect(second).toBe(FULL)
    expect(spy).toHaveBeenCalledTimes(1)     // 未过 TTL ⇒ 不重取(到期后必重取由 EF-TTL-1 钉)
  })

  it('EF-2: 并发 ensure 同一 endpoint → 收敛为一次请求,结果同一份', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    const [a, b] = await Promise.all([
      ensureEndpointFull('fin.order.add'),
      ensureEndpointFull('fin.order.add'),
    ])
    expect(a).toBe(FULL)
    expect(b).toBe(FULL)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('EF-3: 失败 → undefined 且 state=failed;失败不入缓存,窗口过后可重试成功', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(FULL)

    expect(await ensureEndpointFull('fin.order.add')).toBeUndefined()
    expect(getEndpointFull('fin.order.add')).toBeUndefined()
    expect(endpointFullState('fin.order.add')).toBe('failed')

    // 越过负缓存窗口 → 转缓存态(窗口内的「不重发」由 EF-7 钉住)
    vi.setSystemTime(Date.now() + 11_000)
    expect(await ensureEndpointFull('fin.order.add')).toBe(FULL)
    expect(endpointFullState('fin.order.add')).toBe('')
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('EF-4: state — 已缓存 = ""、失败 = failed、未拉过 = loading、无 id = ""', () => {
    expect(endpointFullState(undefined)).toBe('')
    expect(endpointFullState('never.requested')).toBe('loading')
  })

  it('EF-6(新): 响应式 — computed 读 getEndpointFull 会在回填后自动重算', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    const seen = computed(() => getEndpointFull('ep-r') === undefined ? 'none' : 'have')
    expect(seen.value).toBe('none')
    await ensureEndpointFull('ep-r')
    expect(seen.value).toBe('have')          // 无需任何手工 bump
  })

  it('EF-7(新): 失败负缓存 — 窗口内不重发,窗口过后允许重试', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('boom'))
    expect(await ensureEndpointFull('ep-f')).toBeUndefined()
    expect(await ensureEndpointFull('ep-f')).toBeUndefined()
    expect(spy).toHaveBeenCalledTimes(1)                     // 窗口内不重发
    vi.setSystemTime(Date.now() + 11_000)                    // 越过 FAILED_RETRY_MS
    expect(await ensureEndpointFull('ep-f')).toBeUndefined()
    expect(spy).toHaveBeenCalledTimes(2)                     // 窗口后允许重试
  })

  it('EF-8(新): 失败侧响应式 — computed 读 endpointFullState 在失败后**自己**转 failed', async () => {
    vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('boom'))
    // 画布 currentFullState 同形:computed 只读状态,失败后不得靠任何命令式重算
    const seen = computed(() => endpointFullState('ep-fs'))
    expect(seen.value).toBe('loading')
    await ensureEndpointFull('ep-fs')
    expect(seen.value).toBe('failed')        // 无手工 bump、无重新调用
  })

  it('DP-7(C7): 入口消毒 — 合法容器下挂 path:7 的子条目 → 剔除自身、子孙提升,画布递归不硬抛', async () => {
    // 畸形子条目自身不可用,但它带着一层**子孙**(提升纪律:绝不整棵剪枝)
    const malformed = decl({
      name: 'bad', path: 7, type: 'object',
      children: [decl({ name: 'deep', path: '$.root.deep' })],
    })
    const decls = [
      decl({
        name: 'root', path: '$.root', type: 'object',
        children: [malformed, decl({ name: 'ok', path: '$.root.ok' })],
      }),
    ]
    vi.spyOn(api, 'getFullEndpoint')
      .mockResolvedValue({ id: 'ep-dp7', request: { declarations: decls } } as any)

    const full = await ensureEndpointFull('ep-dp7')
    const clean = full!.request!.declarations

    // ① 不抛:画布递归入口(buildNode → suffixOf 的 `childPath.startsWith`)不再收到 path:7
    expect(() => buildTree(clean)).not.toThrow()
    // ② 合法容器仍在
    expect(clean.map((d) => d.path)).toEqual(['$.root'])
    // ③ 畸形子条目剔除、其**子孙提升**到原位置;合法兄弟原位保留
    expect(clean[0].children!.map((c) => c.path)).toEqual(['$.root.deep', '$.root.ok'])
    // 树形自证:容器仍在、提升的子孙成了它的子节点
    const tree = buildTree(clean)
    expect(tree.map((n) => n.templatePath)).toEqual(['$.root'])
    expect(tree[0].kind === 'object' && tree[0].children.map((n) => n.templatePath))
      .toEqual(['$.root.deep', '$.root.ok'])
  })

  it('EF-TTL-1: 到期后重取,且面版本自增', async () => {
    vi.useFakeTimers()
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockResolvedValueOnce(fullWith(['$.a']))
      .mockResolvedValueOnce(fullWith(['$.b']))
    await ensureEndpointFull('ep-1')
    const v0 = surfaceVersion('ep-1')
    vi.advanceTimersByTime(FULL_TTL_MS + 1)
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(2)
    expect(surfaceVersion('ep-1')).toBeGreaterThan(v0)
    vi.useRealTimers()
  })

  it('EF-TTL-2: 到期前不重取', async () => {
    vi.useFakeTimers()
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(fullWith(['$.a']))
    await ensureEndpointFull('ep-1')
    vi.advanceTimersByTime(FULL_TTL_MS - 1)
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('EF-TTL-3: 过期但重取失败时,getEndpointFull 仍返回旧面(不闪空)', async () => {
    vi.useFakeTimers()
    const first = fullWith(['$.a'])
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockResolvedValueOnce(first)
      .mockRejectedValueOnce(new Error('plate down'))
    await ensureEndpointFull('ep-1')
    const v = surfaceVersion('ep-1')
    vi.advanceTimersByTime(FULL_TTL_MS + 1)
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(2)               // 确实重取过、且失败了
    expect(getEndpointFull('ep-1')).toBe(first)        // 旧面仍在(fail-open-to-old),不闪空
    expect(surfaceVersion('ep-1')).toBe(v)             // 面没换 ⇒ 判定不重算
    expect(endpointFullState('ep-1')).toBe('failed')   // 但状态如实报失败 —— 降级可见
    vi.useRealTimers()
  })

  it('EF-TTL-4: 首取即计一版(0 → 1)—— 记忆化键要跟着「从无面到有面」变', async () => {
    vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(fullWith(['$.a']))
    expect(surfaceVersion('ep-1')).toBe(0)             // 尚无面
    await ensureEndpointFull('ep-1')
    expect(surfaceVersion('ep-1')).toBe(1)
  })

  it('EF-TTL-5: 内容相同的重取不动版本,且沿用旧那份本体', async () => {
    vi.useFakeTimers()
    const first = fullWith(['$.a'])
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce({ ...first })             // 逐字相同、另一份对象(真重取回来就是新对象)
    await ensureEndpointFull('ep-1')
    const v = surfaceVersion('ep-1')
    vi.advanceTimersByTime(FULL_TTL_MS + 1)
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(2)               // 确实重取了
    expect(surfaceVersion('ep-1')).toBe(v)             // 面没变 ⇒ 版本不动(记忆化投影不被无谓作废)
    expect(getEndpointFull('ep-1')).toBe(first)        // 且沿用旧本体(消费方响应依赖不被惊动)
    vi.useRealTimers()
  })

  it('EF-TTL-6: 负缓存优先于 TTL —— 刚失败的端点不因面到期就重发(无重取风暴)', async () => {
    vi.useFakeTimers()
    const spy = vi.spyOn(api, 'getFullEndpoint')
      .mockResolvedValueOnce(fullWith(['$.a']))       // 首取成功
      .mockRejectedValue(new Error('plate down'))     // 之后一律失败
    await ensureEndpointFull('ep-1')
    vi.advanceTimersByTime(FULL_TTL_MS + 1)            // 面到期
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(2)               // 到期重取一次
    vi.advanceTimersByTime(FAILED_RETRY_MS - 1)        // 仍在负缓存窗口内
    await ensureEndpointFull('ep-1')
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(2)               // 一次都不发(读多少次都不发)
    vi.advanceTimersByTime(2)                          // 越过负缓存窗口
    await ensureEndpointFull('ep-1')
    expect(spy).toHaveBeenCalledTimes(3)               // 才允许重试
    vi.useRealTimers()
  })
})
