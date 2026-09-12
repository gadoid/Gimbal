/**
 * api/scenario-composer.getFullEndpoint — **出口消毒**(裁定 C8b)单测。
 *
 * `/full` 是不可信来源。消毒在 `getFullEndpoint` **出口**一次做掉,让**每一个**
 * 消费方按构造拿到干净声明树 —— 含**不经**共享缓存的 `CaseComposerCatalog`
 * 浏览面板(它按设计直连本 API)。范围 = `request` + **每个 response**(裁定 C9)。
 *
 * 纪律与 `iterFlat` 逐字同:不可用路径条目**自身剔除、children 提升**到原位置,
 * **绝不整棵剪枝**。守卫是**双层**的:本出口层 + declarations.ts 内 S1 的逐处
 * 守卫(`iterFlat` 等)。本文件的用例打的是真出口;组件测试里大量
 * `vi.spyOn(api, 'getFullEndpoint')` **mock 掉了出口消毒**,那条路径上的保护
 * 来自 S1 的守卫层 —— 两层都在,不可声称"光靠出口消毒就够"。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/http'
import { getFullEndpoint } from '@/api/scenario-composer'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

/** 一条形状完整(plate wire 形状)的声明条目 —— 便于只改被测轴。 */
function decl(over: Partial<Record<string, unknown>>): DeclarationEntryView {
  return {
    name: 'x', path: '$.x', type: 'string', required: false, description: '',
    ui_kind: 'text', source_kind: 'independent', assertable: false,
    ...over,
  } as unknown as DeclarationEntryView
}

/** 合法容器 `$.order` 下挂 `path: 7` 的子条目,该畸形条目自身带一层子孙。 */
function payloadWithMalformedRequest() {
  const malformed = decl({
    name: 'bad', path: 7, type: 'object',
    children: [decl({ name: 'deep', path: '$.order.deep' })],
  })
  return {
    id: 'ep-req', request: {
      declarations: [decl({
        name: 'order', path: '$.order', type: 'object',
        children: [malformed, decl({ name: 'ok', path: '$.order.ok' })],
      })],
    },
  }
}

/** 响应侧同形畸形:`responses["200"].declarations` 里的容器下挂 `path: 7`。 */
function payloadWithMalformedResponse() {
  const malformed = decl({
    name: 'rbad', path: 7, type: 'object',
    children: [decl({ name: 'rdeep', path: '$.data.rdeep' })],
  })
  return {
    id: 'ep-res', request: { declarations: [] },
    responses: {
      '200': {
        status: 200, description: 'ok',
        declarations: [decl({
          name: 'data', path: '$.data', type: 'object',
          children: [malformed, decl({ name: 'rok', path: '$.data.rok' })],
        })],
      },
    },
  }
}

describe('getFullEndpoint — 出口消毒(C8b/C9)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('FE-1: request 侧 — 不可用 path 子条目剔除、其子孙提升;画布递归不硬抛', async () => {
    const payload = payloadWithMalformedRequest()
    vi.spyOn(http, 'get').mockResolvedValue({ data: payload } as any)

    const full = await getFullEndpoint('ep-req')
    const decls = full.request!.declarations

    // ① 不抛(出口已消毒 ⇒ 画布 buildNode → suffixOf 不再收到 path:7)
    expect(() => buildTree(decls)).not.toThrow()
    // ② 合法容器仍在
    expect(decls.map((d) => d.path)).toEqual(['$.order'])
    // ③ 畸形子条目剔除、其**子孙提升**到原位置;合法兄弟原位保留
    expect(decls[0].children!.map((c) => c.path)).toEqual(['$.order.deep', '$.order.ok'])
    // 树形自证
    const tree = buildTree(decls)
    expect(tree[0].kind === 'object' && tree[0].children.map((n) => n.templatePath))
      .toEqual(['$.order.deep', '$.order.ok'])
  })

  it('FE-2(C9): 响应侧 — 每个 response 的 declarations 同样在出口消毒', async () => {
    const payload = payloadWithMalformedResponse()
    vi.spyOn(http, 'get').mockResolvedValue({ data: payload } as any)

    const full = await getFullEndpoint('ep-res')
    const decls = full.responses['200'].declarations

    expect(decls.map((d) => d.path)).toEqual(['$.data'])
    expect(decls[0].children!.map((c) => c.path)).toEqual(['$.data.rdeep', '$.data.rok'])
    // 响应面消费方(assertablePaths / responseBindings)也吃这份已消毒数据
    expect(() => buildTree(decls)).not.toThrow()
  })

  it('FE-3: 干净响应零扰动 — 原对象原样返回(身份保持不变)', async () => {
    const payload = {
      id: 'ep-clean', request: { declarations: [decl({ path: '$.a' })] },
      responses: { '200': { status: 200, description: 'ok', declarations: [decl({ path: '$.b' })] } },
    }
    vi.spyOn(http, 'get').mockResolvedValue({ data: payload } as any)

    const full = await getFullEndpoint('ep-clean')
    expect(full).toBe(payload)
    expect(full.request!.declarations).toBe(payload.request.declarations)
    expect(full.responses['200'].declarations).toBe(payload.responses['200'].declarations)
  })
})
