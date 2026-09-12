/**
 * useEndpointFull — plate /full 结构契约的**唯一**会话级缓存。
 *
 * 契约:每 endpoint 一个会话内恰好一次请求(并发收敛为同一 Promise);
 * 成功入缓存 —— 容器是 Vue 原生响应式,消费方**读缓存即建立依赖**
 * (手工版本号协议已退役,EF-6 钉住该性质);失败**负缓存** ——
 * FAILED_RETRY_MS 窗口内不再发起,窗口过后允许重试(EF-7)。
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
  getEndpointFull,
} from '@/composables/useEndpointFull'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

const FULL = { id: 'fin.order.add', request: { declarations: [] } } as any

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

  it('EF-1: 首次拉取后入缓存,再次 ensure 不再发请求', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    expect(getEndpointFull('fin.order.add')).toBeUndefined()

    const first = await ensureEndpointFull('fin.order.add')
    expect(first).toBe(FULL)
    expect(getEndpointFull('fin.order.add')).toBe(FULL)

    const second = await ensureEndpointFull('fin.order.add')
    expect(second).toBe(FULL)
    expect(spy).toHaveBeenCalledTimes(1)
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
})
