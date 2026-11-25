import { beforeEach, describe, expect, it, vi } from 'vitest'
import http from '@/api/http'
import { fetchQueryViewRows } from '@/api/query-views'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn() },
}))

const mocked = vi.mocked(http, { partial: true }) as unknown as {
  get: ReturnType<typeof vi.fn>
}

describe('api/query-views', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('credentialSource 按契约序列化,不推断查询身份', async () => {
    mocked.get.mockResolvedValue({ data: { rows: [] } })
    await fetchQueryViewRows('v 1', {
      scenarioId: 'sc-1', stepIndex: 0, schemeId: 'rs-1',
      credentialSource: 'project', service: 'svc',
    })
    expect(mocked.get).toHaveBeenCalledWith('/query-views/v%201/rows', {
      params: {
        refresh: 0, scenarioId: 'sc-1', stepIndex: 0, schemeId: 'rs-1',
        service: 'svc', credentialSource: 'project',
      },
    })
  })

  it('未选择凭证池时省略 credentialSource', async () => {
    mocked.get.mockResolvedValue({ data: { rows: [] } })
    await fetchQueryViewRows('v1', { serviceUrl: 'http://sut' })
    expect(mocked.get.mock.calls[0][1].params).not.toHaveProperty('credentialSource')
  })
})
