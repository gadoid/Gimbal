/**
 * workbench/layout.ts — 工作台布局存档单元测试。
 * 契约:默认 = registry 序;add/remove/move/setSize 持久化;存档精确集合
 * (删掉的卡不复活);未知 id 读取时过滤;按用户分键;v1 旧存档(纯 id
 * 数组)迁移为 v2(order 继承,sizes 取 defaultSize)。
 *
 * 2026-09-22 起存档走 useUserPreference:localStorage 只是首帧镜像,服务端
 * user_prefs 才是真值 —— 所以这里同时钉三件事:镜像键内容(渲染依据)、
 * PUT 载荷(跨设备依据)、"值没变就不发写"(否则每次进页面都空写一发)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useWorkbenchLayout } from '@/components/workbench/layout'
import { workbenchRegistry } from '@/components/workbench/registry'
import {
  PREFERENCE_PUT_DEBOUNCE_MS, resetUserPreferencesForTest,
} from '@/composables/useUserPreferences'
import * as prefApi from '@/api/preferences'
import type { PrefValues } from '@/api/preferences'

vi.mock('@/api/preferences', () => ({
  getPreferences: vi.fn().mockResolvedValue({}),
  putPreference: vi.fn().mockResolvedValue({}),
}))

const USER = 'alice'
const OTHER = 'bob'
const V2_KEY = `workbench.layout.v2:${USER}`
const V1_KEY = `workbench.layout.v1:${USER}`

function ids(): string[] {
  return workbenchRegistry.map((d) => d.id)
}

function readV2(): { order: string[]; sizes: Record<string, string> } {
  return JSON.parse(localStorage.getItem(V2_KEY)!)
}

function asUser(username: string): void {
  useAuthStore().currentUser = {
    id: 1, username, display_name: username, is_admin: false, role: 'member',
  } as never
}

/** 持久化经 deep watch(flush: pre)—— 断言镜像前 flush 微任务即可 */
async function flushed() {
  await nextTick()
  await nextTick()
}

/** PUT 是防抖合并的 —— 断言上云载荷要额外等过合并窗口 */
async function putFlushed() {
  await flushed()
  await new Promise((r) => setTimeout(r, PREFERENCE_PUT_DEBOUNCE_MS + 30))
}

/** 同键全局单例:模拟"重新进页面"要先清实例(存档仍留在 localStorage)。 */
function reloadLayout() {
  resetUserPreferencesForTest()
  return useWorkbenchLayout()
}

function putCalls(key: string) {
  return vi.mocked(prefApi.putPreference).mock.calls.filter(([k]) => k === key)
}

/** 只取本键的载荷(putPreference 的入参是三键联合类型,按键筛完要收窄) */
function layoutPuts(): PrefValues['workbench.layout'][] {
  return putCalls('workbench.layout').map(([, v]) => v as PrefValues['workbench.layout'])
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  resetUserPreferencesForTest()
  vi.mocked(prefApi.getPreferences).mockResolvedValue({})
  vi.mocked(prefApi.putPreference).mockClear()
  asUser(USER)
})

describe('useWorkbenchLayout — order(存档 = 镜像 + 服务端)', () => {
  it('无存档 → 默认 = registry 全量按注册序,sizes 取各卡 defaultSize(未声明才 M)', () => {
    const { orderedIds, sizeOf } = useWorkbenchLayout()
    expect(orderedIds.value).toEqual(ids())
    for (const d of workbenchRegistry) expect(sizeOf(d.id)).toBe(d.defaultSize ?? 'M')
    // 用户管理只出两个计数,列表不是 glance 信息 —— 唯一刻意 S 起步的卡
    expect(sizeOf('users')).toBe('S')
  })

  it('给 eligibleIds → 默认板只含可见集(adminOnly 卡不塞给 member)', () => {
    const allow = ref(workbenchRegistry.filter((d) => !d.adminOnly).map((d) => d.id))
    const { orderedIds } = useWorkbenchLayout(allow)
    expect(orderedIds.value).toEqual(allow.value)
    // 注册表里确有 adminOnly 卡,否则这条断言是空的
    expect(allow.value.length).toBeLessThan(ids().length)
  })

  it('remove → 集合收缩并持久化(含 sizes 键清理);重载不复活', async () => {
    const { remove } = useWorkbenchLayout()
    remove(ids()[0])
    await flushed()
    const stored = readV2()
    expect(stored.order).toEqual(ids().slice(1))
    expect(stored.sizes[ids()[0]]).toBeUndefined()   // 残骸清理

    expect(reloadLayout().orderedIds.value).toEqual(ids().slice(1))
  })

  it('改动同时上云:PUT 收到 workbench.layout + 当前整份布局', async () => {
    const { remove } = useWorkbenchLayout()
    remove(ids()[0])
    await putFlushed()
    expect(putCalls('workbench.layout')).toHaveLength(1)
    expect(layoutPuts()[0]!.order).toEqual(ids().slice(1))
  })

  it('值没变就不发写(服务端回读套进 ref 不该再 PUT 一次自己)', async () => {
    const { setSize } = useWorkbenchLayout()
    setSize(ids()[0], 'L')
    await putFlushed()
    const before = putCalls('workbench.layout').length
    setSize(ids()[0], 'L')                 // 同值幂等
    await putFlushed()
    expect(putCalls('workbench.layout')).toHaveLength(before)
  })

  it('add → 追加到尾部(size 取 defaultSize);重复 add 幂等;未知 id 拒收', async () => {
    const { remove, add, setSize } = useWorkbenchLayout()
    remove(ids()[0])
    await flushed()
    // 加回前把别卡调成 L — 验证 add 不覆盖既有尺寸
    setSize(ids()[1], 'L')
    add(ids()[0])
    await flushed()
    const afterAdd = readV2()
    expect([...afterAdd.order].sort()).toEqual([...ids()].sort())
    expect(afterAdd.order[afterAdd.order.length - 1]).toBe(ids()[0])
    expect(afterAdd.sizes[ids()[0]]).toBe('M')       // defaultSize
    expect(afterAdd.sizes[ids()[1]]).toBe('L')       // 不受影响
    add(ids()[0])                          // 已在场 — 幂等
    add('not-a-card')                      // 未知 — 拒收
    await flushed()
    expect(readV2().order).toHaveLength(ids().length)
  })

  it('move → 换序持久化(拖拽落点的纯函数面)', async () => {
    const { move } = useWorkbenchLayout()
    move(0, 2)   // [a,b,c] → [b,c,a]
    await flushed()
    const expect_ = [...ids()]
    const [first] = expect_.splice(0, 1)
    expect_.splice(2, 0, first)
    expect(readV2().order).toEqual(expect_)
    move(-1, 0)                            // 越界拒收(不变)
    move(0, 99)
    await flushed()
    expect(readV2().order).toEqual(expect_)
  })

  it('存档含未知 id / 非法尺寸 → 读取时静默过滤回默认;损坏存档回默认', () => {
    localStorage.setItem(V2_KEY, JSON.stringify({
      order: [ids()[0], 'gone'],
      sizes: { [ids()[0]]: 'XL', [ids()[1]]: 'L' },
    }))
    const { orderedIds, sizeOf } = reloadLayout()
    expect(orderedIds.value).toEqual([ids()[0]])
    expect(sizeOf(ids()[0])).toBe('M')               // 'XL' 非法 → defaultSize

    localStorage.setItem(V2_KEY, '{broken json')
    expect(reloadLayout().orderedIds.value).toEqual(ids())
  })

  it('按用户分键:另一账号的存档互不串台;身份切换自动重载', async () => {
    localStorage.setItem(`workbench.layout.v2:${OTHER}`, JSON.stringify({
      order: [ids()[1]],
      sizes: { [ids()[1]]: 'S' },
    }))
    const { orderedIds } = useWorkbenchLayout()
    expect(orderedIds.value).toEqual(ids())          // alice 无存档 → 默认

    asUser(OTHER)
    await flushed()
    expect(orderedIds.value).toEqual([ids()[1]])     // 切到 bob → 读 bob 的存档
  })

  it('reset → 回默认序 + 默认尺寸', async () => {
    const { move, remove, setSize, reset } = useWorkbenchLayout()
    move(0, 2)
    setSize(ids()[0], 'S')
    remove(ids()[2])
    reset()
    await flushed()
    const stored = readV2()
    expect(stored.order).toEqual(ids())
    expect(stored.sizes[ids()[0]]).toBe('M')
  })
})

describe('useWorkbenchLayout — v1 迁移(order 继承,sizes 补 defaultSize)', () => {
  it('v1 存档(纯 id 数组)→ 迁移读取;v2 键落盘并播种上云,v1 键保留', async () => {
    const v1Order = [ids()[2], ids()[0]]             // 删了 1 张 + 换序
    localStorage.setItem(V1_KEY, JSON.stringify(v1Order))
    const { orderedIds, sizeOf } = useWorkbenchLayout()
    expect(orderedIds.value).toEqual(v1Order)        // order 精确继承
    expect(sizeOf(ids()[2])).toBe('M')

    await putFlushed()
    const stored = readV2()
    expect(stored.order).toEqual(v1Order)
    expect(stored.sizes).toEqual({ [ids()[2]]: 'M', [ids()[0]]: 'M' })
    // v1 键保留(回滚友好)
    expect(localStorage.getItem(V1_KEY)).toBe(JSON.stringify(v1Order))
    // 迁移结果同时播种到服务端 —— 换设备不再依赖这台机器的旧键
    expect(layoutPuts().some((v) => v.order.join() === v1Order.join())).toBe(true)
  })

  it('v2 存档优先于 v1(迁移不覆盖新档)', () => {
    localStorage.setItem(V1_KEY, JSON.stringify([ids()[0]]))
    localStorage.setItem(V2_KEY, JSON.stringify({
      order: [ids()[1], ids()[2]],
      sizes: { [ids()[1]]: 'L', [ids()[2]]: 'S' },
    }))
    const { orderedIds, sizeOf } = reloadLayout()
    expect(orderedIds.value).toEqual([ids()[1], ids()[2]])
    expect(sizeOf(ids()[1])).toBe('L')
    expect(sizeOf(ids()[2])).toBe('S')
  })
})

describe('useWorkbenchLayout — 服务端为准(镜像只管首帧)', () => {
  it('服务端有值 → 首帧仍按镜像,到位后覆盖并回填镜像', async () => {
    localStorage.setItem(V2_KEY, JSON.stringify({ order: [ids()[0]], sizes: {} }))
    vi.mocked(prefApi.getPreferences).mockResolvedValue({
      'workbench.layout': { order: [ids()[1], ids()[0]], sizes: { [ids()[1]]: 'L' } },
    })
    const { orderedIds, sizeOf } = useWorkbenchLayout()
    expect(orderedIds.value).toEqual([ids()[0]])     // 首帧不闪

    await putFlushed()
    expect(orderedIds.value).toEqual([ids()[1], ids()[0]])   // 服务端为准
    expect(sizeOf(ids()[1])).toBe('L')
    expect(readV2().order).toEqual([ids()[1], ids()[0]])     // 回填镜像
    // 回声写必须是 0:回读值套进 ref 会触发 deep watch,若守卫缺失这里
    // 就多出一次"把自己 PUT 回去"的空写。
    expect(putCalls('workbench.layout')).toHaveLength(0)
  })

  it('服务端没这个键而镜像有 → 播种上云,不改本机值', async () => {
    localStorage.setItem(V2_KEY, JSON.stringify({ order: [ids()[1]], sizes: {} }))
    const { orderedIds } = useWorkbenchLayout()
    await putFlushed()
    expect(orderedIds.value).toEqual([ids()[1]])
    expect(putCalls('workbench.layout')).toHaveLength(1)
  })

  it('GET 失败 → 镜像值继续用,不炸不闪', async () => {
    localStorage.setItem(V2_KEY, JSON.stringify({ order: [ids()[2]], sizes: {} }))
    vi.mocked(prefApi.getPreferences).mockRejectedValueOnce(new Error('502'))
    const { orderedIds } = useWorkbenchLayout()
    await putFlushed()
    expect(orderedIds.value).toEqual([ids()[2]])
  })
})

describe('useWorkbenchLayout — sizes(尺寸系统)', () => {
  it('setSize → 持久化;sizeOf 无记录取 defaultSize;不在场的卡拒收', async () => {
    const { setSize, sizeOf, remove } = useWorkbenchLayout()
    setSize(ids()[0], 'L')
    setSize(ids()[1], 'S')
    await flushed()
    expect(readV2().sizes).toEqual({
      [ids()[0]]: 'L',
      [ids()[1]]: 'S',
      // 其余未碰的卡一律取注册表 defaultSize(未声明才 M)
      ...Object.fromEntries(workbenchRegistry.slice(2).map((d) => [d.id, d.defaultSize ?? 'M'])),
    })
    expect(sizeOf(ids()[0])).toBe('L')

    // 同值幂等(不触发写)
    setSize(ids()[0], 'L')
    // 不在场拒收
    remove(ids()[2])
    await flushed()
    setSize(ids()[2], 'L')
    await flushed()
    expect(readV2().sizes[ids()[2]]).toBeUndefined()
  })
})
