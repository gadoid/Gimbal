/** M2a S1.8:zone store —— 区选择持久化与列表参数投影。 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useZoneStore } from '@/stores/zone'

describe('stores/zone', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('默认私有区;私有区不加任何列表参数', () => {
    const zone = useZoneStore()
    expect(zone.zone).toBe('private')
    expect(zone.listParams).toEqual({})
  })

  it('公共区 → visibility=public;项目区 → projectId', () => {
    const zone = useZoneStore()
    zone.set('public')
    expect(zone.listParams).toEqual({ visibility: 'public' })
    zone.set(42)
    expect(zone.listParams).toEqual({ projectId: 42 })
  })

  it('选择持久化到 localStorage(刷新恢复)', () => {
    const zone = useZoneStore()
    zone.set(7)
    expect(localStorage.getItem('gimbal-zone')).toBe('7')
    const second = useZoneStore()
    expect(second.zone).toBe(7)
  })

  it('非法持久化值回落私有区', () => {
    localStorage.setItem('gimbal-zone', 'nonsense')
    const zone = useZoneStore()
    expect(zone.zone).toBe('private')
  })
})
