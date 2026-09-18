/**
 * workbench/layout.ts — 布局组装状态单元测试(v2:order + sizes)。
 * 契约:默认 = registry 序;add/remove/move/setSize 持久化 localStorage;
 * 存档精确集合(删掉的卡不复活);未知 id 读取时过滤;按用户分键;
 * v1 旧存档(纯 id 数组)迁移为 v2(order 继承,sizes 取 defaultSize)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useWorkbenchLayout } from '@/components/workbench/layout'
import { workbenchRegistry } from '@/components/workbench/registry'

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

beforeEach(() => {
  localStorage.clear()
})

/** 持久化经 deep watch(flush: pre)— 断言前 flush 微任务 */
async function flushed() {
  await nextTick()
  await nextTick()
}

describe('useWorkbenchLayout — order(v2 沿用 v1 契约)', () => {
  it('无存档 → 默认 = registry 全量按注册序,sizes 全 defaultSize(缺省 M)', () => {
    const { orderedIds, sizeOf } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual(ids())
    for (const id of ids()) expect(sizeOf(id)).toBe('M')
  })

  it('remove → 集合收缩并持久化(含 sizes 键清理);重载不复活', async () => {
    const { remove } = useWorkbenchLayout(ref(USER))
    remove(ids()[0])
    await flushed()
    const stored = readV2()
    expect(stored.order).toEqual(ids().slice(1))
    expect(stored.sizes[ids()[0]]).toBeUndefined()   // 残骸清理

    const again = useWorkbenchLayout(ref(USER))
    expect(again.orderedIds.value).toEqual(ids().slice(1))
  })

  it('add → 追加到尾部(size 取 defaultSize);重复 add 幂等;未知 id 拒收', async () => {
    const { remove, add, setSize } = useWorkbenchLayout(ref(USER))
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
    add(ids()[0])                        // 已在场 — 幂等
    add('not-a-card')                    // 未知 — 拒收
    await flushed()
    expect(readV2().order).toHaveLength(ids().length)
  })

  it('move → 换序持久化(拖拽落点的纯函数面)', async () => {
    const { move } = useWorkbenchLayout(ref(USER))
    move(0, 2)   // [a,b,c] → [b,c,a]
    await flushed()
    const expect_ = [...ids()]
    const [first] = expect_.splice(0, 1)
    expect_.splice(2, 0, first)
    expect(readV2().order).toEqual(expect_)
    move(-1, 0)                          // 越界拒收(不变)
    move(0, 99)
    await flushed()
    expect(readV2().order).toEqual(expect_)
  })

  it('存档含未知 id / 非法尺寸 → 读取时静默过滤回默认;损坏存档回默认', () => {
    localStorage.setItem(V2_KEY, JSON.stringify({
      order: [ids()[0], 'gone'],
      sizes: { [ids()[0]]: 'XL', [ids()[1]]: 'L' },
    }))
    const { orderedIds, sizeOf } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual([ids()[0]])
    expect(sizeOf(ids()[0])).toBe('M')               // 'XL' 非法 → defaultSize

    localStorage.setItem(V2_KEY, '{broken json')
    const again = useWorkbenchLayout(ref(USER))
    expect(again.orderedIds.value).toEqual(ids())
  })

  it('按用户分键:另一账号的存档互不串台;username 切换自动重载', async () => {
    localStorage.setItem(`workbench.layout.v2:${OTHER}`, JSON.stringify({
      order: [ids()[1]],
      sizes: { [ids()[1]]: 'S' },
    }))
    const name = ref(USER)
    const { orderedIds } = useWorkbenchLayout(name)
    expect(orderedIds.value).toEqual(ids())          // alice 无存档 → 默认

    name.value = OTHER
    await nextTick()
    expect(orderedIds.value).toEqual([ids()[1]])     // 切到 bob → 读 bob 的存档
  })

  it('reset → 回默认序 + 默认尺寸', async () => {
    const { move, remove, setSize, reset } = useWorkbenchLayout(ref(USER))
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
  it('v1 存档(纯 id 数组)→ 迁移读取;v2 键落盘,v1 键保留', async () => {
    const v1Order = [ids()[2], ids()[0]]             // 删了 1 张 + 换序
    localStorage.setItem(V1_KEY, JSON.stringify(v1Order))
    const { orderedIds, sizeOf } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual(v1Order)        // order 精确继承
    expect(sizeOf(ids()[2])).toBe('M')

    // 迁移结果落 v2
    await flushed()
    const stored = readV2()
    expect(stored.order).toEqual(v1Order)
    expect(stored.sizes).toEqual({ [ids()[2]]: 'M', [ids()[0]]: 'M' })
    // v1 键保留(回滚友好)
    expect(localStorage.getItem(V1_KEY)).toBe(JSON.stringify(v1Order))
  })

  it('v2 存档优先于 v1(迁移不覆盖新档)', () => {
    localStorage.setItem(V1_KEY, JSON.stringify([ids()[0]]))
    localStorage.setItem(V2_KEY, JSON.stringify({
      order: [ids()[1], ids()[2]],
      sizes: { [ids()[1]]: 'L', [ids()[2]]: 'S' },
    }))
    const { orderedIds, sizeOf } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual([ids()[1], ids()[2]])
    expect(sizeOf(ids()[1])).toBe('L')
    expect(sizeOf(ids()[2])).toBe('S')
  })
})

describe('useWorkbenchLayout — sizes(v3 尺寸系统)', () => {
  it('setSize → 持久化;sizeOf 无记录取 defaultSize;不在场的卡拒收', async () => {
    const { setSize, sizeOf, remove } = useWorkbenchLayout(ref(USER))
    setSize(ids()[0], 'L')
    setSize(ids()[1], 'S')
    await flushed()
    expect(readV2().sizes).toEqual({
      [ids()[0]]: 'L',
      [ids()[1]]: 'S',
      // 其余未碰的卡一律取注册表 defaultSize(缺省 M)
      ...Object.fromEntries(ids().slice(2).map((id) => [id, 'M'])),
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
