/** NotesCard — 存量下划线键读入归一(2026-11-05 修复轮评审 N3)。
 * 修复前落库的条目是 created_at / done_at,GET 原样返回;不归一的话
 * toggle 追加 doneAt 后两种键并存,后端 extra=forbid 整卡 422。归一后
 * PUT 载荷只剩 NoteItemDTO 的五个驼峰键。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import NotesCard from '@/components/workbench/cards/NotesCard.vue'
import * as prefs from '@/api/preferences'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('NotesCard — 存量下划线键归一', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(prefs, 'getPreferences').mockResolvedValue({
      notes: { items: [
        { id: 'old1', text: '修复前的便签', done: false,
          created_at: '2026-11-01T00:00:00Z', done_at: null },
      ] },
    } as never)
    vi.spyOn(prefs, 'putPreference').mockResolvedValue({} as never)
  })

  it('勾选完成:PUT 载荷只有驼峰键,createdAt 取自 created_at', async () => {
    const w = mount(NotesCard)
    await flushPromises()
    await w.find('input[type="checkbox"]').trigger('change')
    await flushPromises()
    expect(prefs.putPreference).toHaveBeenCalledTimes(1)
    const [key, value] = vi.mocked(prefs.putPreference).mock.calls[0]!
    expect(key).toBe('notes')
    const item = (value as prefs.PrefValues['notes']).items[0]!
    expect(Object.keys(item).sort()).toEqual(['createdAt', 'done', 'doneAt', 'id', 'text'])
    expect(item.createdAt).toBe('2026-11-01T00:00:00Z')
    expect(item.done).toBe(true)
    expect(typeof item.doneAt).toBe('string')
    w.unmount()
  })
})
