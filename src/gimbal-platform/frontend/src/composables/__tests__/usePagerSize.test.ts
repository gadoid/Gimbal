/**
 * usePagerSize — 列表页「每页行数」偏好(2026-09-23 分页批次)。
 * 钉住:fallback、镜像首帧、服务端采纳、用户改动防抖 PUT(pager.sizes
 * 整值,只含改动页 + 既有键)、非法值钳到 fallback。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { usePagerSize } from '@/composables/usePagerSize'
import {
  PREFERENCE_PUT_DEBOUNCE_MS, resetUserPreferencesForTest,
} from '@/composables/useUserPreferences'
import { useAuthStore } from '@/stores/auth'
import * as prefApi from '@/api/preferences'

vi.mock('@/api/preferences', () => ({
  getPreferences: vi.fn().mockResolvedValue({}),
  putPreference: vi.fn().mockResolvedValue({}),
}))

const as = (username: string) => {
  useAuthStore().currentUser = {
    id: 1, username, display_name: username, is_admin: false,
  } as never
}

async function settled() {
  await nextTick()
  await nextTick()
}

async function putLanded() {
  await new Promise((r) => setTimeout(r, PREFERENCE_PUT_DEBOUNCE_MS + 60))
}

describe('usePagerSize — 每页行数偏好', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    resetUserPreferencesForTest()
    vi.mocked(prefApi.getPreferences).mockResolvedValue({})
    vi.mocked(prefApi.putPreference).mockClear()
    as('alice')
  })

  it('无存档 → fallback;用户改行数 → 防抖 PUT 整值只含本页', async () => {
    const { pageSize } = usePagerSize('auths', 50)
    expect(pageSize.value).toBe(50)

    pageSize.value = 100
    await settled()
    expect(prefApi.putPreference).not.toHaveBeenCalled() // 防抖窗口内未发
    await putLanded()
    expect(prefApi.putPreference).toHaveBeenCalledWith(
      'pager.sizes', { sizes: { auths: 100 } })
  })

  it('镜像有存档 → 首帧即得(不等网络)', async () => {
    localStorage.setItem('pager-sizes:alice', JSON.stringify({ auths: 100 }))
    const { pageSize } = usePagerSize('auths', 50)
    expect(pageSize.value).toBe(100)
    await settled()
    expect(prefApi.putPreference).not.toHaveBeenCalled() // 回读相等不空写
  })

  it('服务端有存档(新设备)→ 回读采纳并重拉到该行数', async () => {
    vi.mocked(prefApi.getPreferences).mockResolvedValue(
      { 'pager.sizes': { sizes: { auths: 100 } } } as never)
    const { pageSize } = usePagerSize('auths', 50)
    expect(pageSize.value).toBe(50) // 首帧 fallback
    await settled()
    expect(pageSize.value).toBe(100) // 服务端为准
    expect(localStorage.getItem('pager-sizes:alice'))
      .toBe(JSON.stringify({ auths: 100 })) // 回填镜像
    expect(prefApi.putPreference).not.toHaveBeenCalled()
  })

  it('多页共享一个实例:后到的页读到先到的页写下的键', async () => {
    const a = usePagerSize('auths', 50)
    a.pageSize.value = 100
    await settled()
    const b = usePagerSize('executions', 20)
    expect(b.pageSize.value).toBe(20) // 本页无存档 → 自己的 fallback
    await putLanded()
    expect(prefApi.putPreference).toHaveBeenCalledWith(
      'pager.sizes', { sizes: { auths: 100 } })

    // 第二页再改 → 整值合并(不丢第一页)
    b.pageSize.value = 10
    await settled()
    await putLanded()
    expect(prefApi.putPreference).toHaveBeenLastCalledWith(
      'pager.sizes', { sizes: { auths: 100, executions: 10 } })
  })

  it('存档里的非法值(越界/非数)→ 钳回 fallback', async () => {
    localStorage.setItem('pager-sizes:alice',
      JSON.stringify({ auths: 9999, executions: 'x' }))
    expect(usePagerSize('auths', 50).pageSize.value).toBe(50)
    expect(usePagerSize('executions', 20).pageSize.value).toBe(20)
  })
})
