/** useServerList 查询词清空链路:q: "FC" → '' 必须触发防抖重拉,
 *  且请求不再带 q(signature 剔除 undefined 的回归钉子)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { useServerList } from '@/composables/useServerList'

describe('useServerList q 清空链路', () => {
  beforeEach(() => vi.clearAllMocks())

  it('q: "FC" → "" 触发重拉且请求不带 q', async () => {
    const fetch = vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 })
    const q = ref('')
    const list = useServerList({
      fetch,
      params: () => ({ q: q.value || undefined }),
    })

    q.value = 'FC'
    await new Promise((r) => setTimeout(r, 400))
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch.mock.lastCall?.[0]).toMatchObject({ q: 'FC', page: 1 })

    q.value = ''
    await new Promise((r) => setTimeout(r, 400))
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.lastCall?.[0]).toMatchObject({ page: 1 })
    expect(fetch.mock.lastCall?.[0].q).toBeUndefined()
    expect(list.total.value).toBe(0)
  })
})
