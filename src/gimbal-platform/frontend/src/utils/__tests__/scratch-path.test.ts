import { describe, expect, it } from 'vitest'
import { toScratchPath } from '../scratch-path'

describe('toScratchPath', () => {
  it('特判 $.status → $.response_status', () => {
    expect(toScratchPath('$.status')).toBe('$.response_status')
  })

  it('常规字段加 response_body 前缀', () => {
    expect(toScratchPath('$.data.orderId')).toBe('$.response_body.data.orderId')
  })

  it('下标语法原样保留', () => {
    expect(toScratchPath('$.data.container[0].id')).toBe('$.response_body.data.container[0].id')
  })

  it('根路径 $ → $.response_body', () => {
    expect(toScratchPath('$')).toBe('$.response_body')
  })

  it('空串 → $.response_body', () => {
    expect(toScratchPath('')).toBe('$.response_body')
  })

  it('已是 scratch 域的路径不重复加前缀', () => {
    expect(toScratchPath('$.response_body.data.id')).toBe('$.response_body.data.id')
    expect(toScratchPath('$.response_status')).toBe('$.response_status')
  })
})
