import { describe, expect, it } from 'vitest'
import { toScratchPath } from '../scratch-path'

describe('toScratchPath', () => {
  it('特判 $.status → $.call.response.status', () => {
    expect(toScratchPath('$.status')).toBe('$.call.response.status')
  })

  it('常规字段加 response_body 前缀', () => {
    expect(toScratchPath('$.data.orderId')).toBe('$.call.response.body.data.orderId')
  })

  it('下标语法原样保留', () => {
    expect(toScratchPath('$.data.container[0].id')).toBe('$.call.response.body.data.container[0].id')
  })

  it('根路径 $ → $.call.response.body', () => {
    expect(toScratchPath('$')).toBe('$.call.response.body')
  })

  it('空串 → $.call.response.body', () => {
    expect(toScratchPath('')).toBe('$.call.response.body')
  })

  it('已是 scratch 域的路径不重复加前缀', () => {
    expect(toScratchPath('$.call.response.body.data.id')).toBe('$.call.response.body.data.id')
    expect(toScratchPath('$.call.response.status')).toBe('$.call.response.status')
  })

  it('根 list 形态: $[0].sku → $.call.response.body[0].sku(前缀直拼无点,修轮 R2)', () => {
    expect(toScratchPath('$[0].sku')).toBe('$.call.response.body[0].sku')
    expect(toScratchPath('$[1].items[0].n')).toBe('$.call.response.body[1].items[0].n')
  })
})
