/**
 * errors.ts — Spec-2-11 unit tests.
 */
import { describe, it, expect } from 'vitest'
import axios from 'axios'
import { normalizeError, toUserMessage } from '@/utils/errors'

describe('normalizeError', () => {
  it('extracts status + message from AxiosError with string detail', () => {
    const err = axios.isAxiosError(new Error()) ? null : null
    void err
    const fake = {
      isAxiosError: true,
      message: 'Request failed',
      response: { status: 404, data: { detail: 'case not found: xyz' } },
    } as unknown
    // Cast to Error-shaped axios
    const ax = fake as Parameters<typeof normalizeError>[0]
    const n = normalizeError(ax)
    expect(n.status).toBe(404)
    expect(n.message).toBe('case not found: xyz')
  })

  it('extracts code + msg from object detail shape', () => {
    const fake = {
      isAxiosError: true,
      message: 'fallback',
      response: {
        status: 409,
        data: { detail: { code: 4091, msg: '不能删除自己' } },
      },
    } as unknown
    const n = normalizeError(fake as Parameters<typeof normalizeError>[0])
    expect(n.status).toBe(409)
    expect(n.code).toBe('4091')
    expect(n.message).toBe('不能删除自己')
  })

  it('returns plain Error message for non-axios', () => {
    const n = normalizeError(new Error('boom'))
    expect(n.status).toBeNull()
    expect(n.message).toBe('boom')
  })

  it('returns stringified value for unknown thrown objects', () => {
    const n = normalizeError('oops')
    expect(n.message).toBe('oops')
  })
})

describe('toUserMessage', () => {
  const mk = (status: number | null, message: string) => {
    if (status === null) {
      return new Error(message)
    }
    // Construct a real AxiosError so axios.isAxiosError(e) is true.
    const ax = new axios.AxiosError(
      message,
      String(status),
      undefined,
      undefined,
      {
        status,
        data: { detail: message },
        statusText: '',
        config: {} as never,
        headers: {},
      },
    )
    return ax
  }

  it('returns "请先登录" for 401', () => {
    expect(toUserMessage(mk(401, 'invalid token'))).toContain('登录')
  })

  it('returns 404-prefixed message', () => {
    expect(toUserMessage(mk(404, 'not found'))).toContain('未找到')
  })

  it('returns server-error message for 5xx', () => {
    expect(toUserMessage(mk(503, 'db down'))).toContain('服务器错误')
  })

  it('returns network error for non-axios with timeout-y message', () => {
    expect(toUserMessage(new Error('Request timeout'))).toContain('网络错误')
  })
})