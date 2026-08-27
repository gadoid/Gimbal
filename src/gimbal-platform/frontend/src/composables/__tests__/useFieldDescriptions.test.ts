/** useFieldDescriptions.test.ts — IOFieldBinding.description 拉取与 columnKey 索引 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import * as api from '@/api/scenario-composer'
import {
  _resetFullCacheForTest,
  useFieldDescriptions,
} from '@/composables/useFieldDescriptions'

const FULL_A = {
  id: 'fin.order.add',
  request: {
    fields: [
      { name: 'amount', description: '订单金额(分)', required: true, default: null, example: null, enum: null, ui_kind: 'number', source_kind: 'literal' },
      { name: 'customer_id', description: '客户编号', required: true, default: null, example: null, enum: null, ui_kind: 'text', source_kind: 'literal' },
    ],
  },
}

const FULL_B = {
  id: 'fin.order.query',
  request: {
    fields: [
      { name: 'page', description: '页码', required: false, default: 1, example: null, enum: null, ui_kind: 'number', source_kind: 'literal' },
    ],
  },
}

const DRAFT = {
  definition: {
    steps: [
      {
        api: { view_hints: { endpoint_id: 'fin.order.add' } },
        request: { body: { amount: '${var.amount}', customer_id: '261' } },
      },
      {
        api: { view_hints: { endpoint_id: 'fin.order.query' } },
        request: {},
      },
    ],
  },
}

describe('useFieldDescriptions', () => {
  beforeEach(() => {
    _resetFullCacheForTest()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('从每个 step 的 endpoint_id 拉 /full,按 columnKey 索引 description', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint')
    // 同一 endpoint 不重复拉
    spy.mockResolvedValueOnce(FULL_A as any)
      .mockResolvedValueOnce(FULL_B as any)

    const draft = ref<{ definition: { steps?: any[] } } | null>(DRAFT as any)
    const { descriptionByColumnKey } = useFieldDescriptions(draft)

    // 给 microtask 几次 tick 让 fetch 完成
    await new Promise((r) => setTimeout(r, 10))
    await new Promise((r) => setTimeout(r, 10))

    expect(spy).toHaveBeenCalledWith('fin.order.add')
    expect(spy).toHaveBeenCalledWith('fin.order.query')
    expect(spy).toHaveBeenCalledTimes(2)  // 无重复

    expect(descriptionByColumnKey.value.get('0:body:amount')).toBe('订单金额(分)')
    expect(descriptionByColumnKey.value.get('0:body:customer_id')).toBe('客户编号')
    // step 2 的 body 是空对象 → 没有 columnKey
    expect(descriptionByColumnKey.value.has('1:body:page')).toBe(false)
  })

  it('endpoint 不在 /full 中存在 → 该 step 的所有 columnKey 缺失(无错误)', async () => {
    vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
      id: 'x', request: { fields: [] },
    } as any)

    const draft = ref({
      definition: {
        steps: [{
          api: { view_hints: { endpoint_id: 'unknown.ep' } },
          request: { body: { foo: '${var.foo}' } },
        }],
      },
    })
    const { descriptionByColumnKey } = useFieldDescriptions(draft)
    await new Promise((r) => setTimeout(r, 10))

    expect(descriptionByColumnKey.value.size).toBe(0)
  })

  it('字段在 scenario body 中存在但 endpoint 的 fields 中没有 → 该 columnKey 缺失', async () => {
    vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL_A as any)
    const draft = ref({
      definition: {
        steps: [{
          api: { view_hints: { endpoint_id: 'fin.order.add' } },
          request: { body: { amount: '${var.amount}', ghost_field: 'x' } },
        }],
      },
    })
    const { descriptionByColumnKey } = useFieldDescriptions(draft)
    await new Promise((r) => setTimeout(r, 10))

    expect(descriptionByColumnKey.value.get('0:body:amount')).toBe('订单金额(分)')
    expect(descriptionByColumnKey.value.has('0:body:ghost_field')).toBe(false)
  })

  it('endpoint_id 缺失的 step → 跳过(没有 columnKey)', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL_A as any)
    const draft = ref({
      definition: {
        steps: [
          { api: {}, request: { body: { amount: '100' } } },   // 无 endpoint_id
          { api: { view_hints: { endpoint_id: 'fin.order.add' } }, request: { body: { amount: '100' } } },
        ],
      },
    })
    const { descriptionByColumnKey } = useFieldDescriptions(draft)
    await new Promise((r) => setTimeout(r, 10))

    // 只拉了 1 个 endpoint
    expect(spy).toHaveBeenCalledTimes(1)
    expect(descriptionByColumnKey.value.get('1:body:amount')).toBe('订单金额(分)')
    expect(descriptionByColumnKey.value.has('0:body:amount')).toBe(false)
  })
})