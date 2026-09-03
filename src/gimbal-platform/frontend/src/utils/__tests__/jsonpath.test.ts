/**
 * jsonpath — get/set/prune/deepDefaults 行为。
 *
 * deepDefaults 只消费 IOFieldBinding 的 default(缺省 example);契约字段
 * (schema 有、binding 无)的 schema default 不再拷贝 — 该职责已移交 carry
 * 通道(platform 值表 + materialize 注入)。
 */
import { describe, it, expect } from 'vitest'
import { deepDefaults, getByPath, pruneByPath, setByPath } from '@/utils/jsonpath'

describe('deepDefaults — 绑定字段(既有行为)', () => {
  it('default 优先于 example;都缺省跳过', () => {
    const body = deepDefaults([
      { path: '$.a', default: 1, example: 9 },
      { path: '$.b', default: null, example: 'ex' },
      { path: '$.c', default: null, example: null },
    ])
    expect(body).toEqual({ a: 1, b: 'ex' })
  })

  it('嵌套路径按段写入', () => {
    const body = deepDefaults([{ path: '$.cfg.timeout', default: 30, example: null }])
    expect(body).toEqual({ cfg: { timeout: 30 } })
  })
})

describe('getByPath — bracket 寻址(D6)', () => {
  it('容器缺失/下标越界 → undefined 不炸', () => {
    expect(getByPath({}, 'supplier[0].order_id')).toBeUndefined()
  })

  it('bracket 下标后继续字段导航', () => {
    const body = { supplier: [null, { order_id: 'x' }] }
    expect(getByPath(body, 'supplier[1].order_id')).toBe('x')
  })
})

describe('setByPath — bracket 写(D6)', () => {
  it('自动建链 + pad null(对齐 gimbal _set_at)', () => {
    const body: any = {}
    setByPath(body, 'supplier[2].order_id', 'x')
    expect(body).toEqual({ supplier: [null, null, { order_id: 'x' }] })
  })
})

describe('deepDefaults — 深层默认不落库(D7)', () => {
  it('bracket 深层 path 跳过(default 只展示),平铺照常落库', () => {
    const body = deepDefaults([
      { path: '$.supplier[0].x', default: 'd', example: null },
      { path: '$.flat', default: 'f', example: null },
    ])
    expect(body).toEqual({ flat: 'f' })
  })
})

describe('pruneByPath — 容器级剪枝(D8)', () => {
  it('整树空 → 根键消失(恢复 carry 资格)', () => {
    const body: any = { supplier: [{ order_id: 'x' }] }
    pruneByPath(body, 'supplier[0].order_id')
    expect(body).toEqual({})
  })

  it('兄弟占容器 → 容器保留', () => {
    const body: any = { supplier: [{ a: 1, order_id: 'x' }] }
    pruneByPath(body, 'supplier[0].order_id')
    expect(body).toEqual({ supplier: [{ a: 1 }] })
  })

  it('中间空元素保留(索引不漂移,不 splice 洗位)', () => {
    const body: any = { supplier: [{ order_id: 'x' }, { b: 1 }] }
    pruneByPath(body, 'supplier[0].order_id')
    expect(body).toEqual({ supplier: [null, { b: 1 }] })
  })
})
