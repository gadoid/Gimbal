/**
 * workbench/layout.ts — 布局组装状态单元测试。
 * 契约:默认 = registry 序;add/remove/move 持久化 localStorage;
 * 存档精确集合(删掉的卡不复活);未知 id 读取时过滤;按用户分键。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useWorkbenchLayout } from '@/components/workbench/layout'
import { workbenchRegistry } from '@/components/workbench/registry'

const USER = 'alice'
const OTHER = 'bob'

function ids(): string[] {
  return workbenchRegistry.map((d) => d.id)
}

beforeEach(() => {
  localStorage.clear()
})

/** 持久化经 deep watch(flush: pre)— 断言前 flush 微任务 */
async function flushed() {
  await nextTick()
  await nextTick()
}

describe('useWorkbenchLayout', () => {
  it('无存档 → 默认 = registry 全量按注册序', () => {
    const { orderedIds } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual(ids())
  })

  it('remove → 集合收缩并持久化;重载(新挂载)不复活', async () => {
    const { remove } = useWorkbenchLayout(ref(USER))
    remove(ids()[0])
    await flushed()
    expect(localStorage.getItem('workbench.layout.v1:alice')).toBe(JSON.stringify(ids().slice(1)))

    // 新挂载读取同一存档
    const again = useWorkbenchLayout(ref(USER))
    expect(again.orderedIds.value).toEqual(ids().slice(1))
  })

  it('add → 追加到尾部;重复 add 幂等;未知 id 拒收', async () => {
    const { remove, add } = useWorkbenchLayout(ref(USER))
    remove(ids()[0])
    add(ids()[0])
    await flushed()
    // add 追加到尾部(非回原位)— 契约 = 集合恢复,顺序 = 追加序
    const afterAdd = JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)
    expect([...afterAdd].sort()).toEqual([...ids()].sort())
    expect(afterAdd[afterAdd.length - 1]).toBe(ids()[0])
    add(ids()[0])                        // 已在场 — 幂等
    add('not-a-card')                    // 未知 — 拒收
    await flushed()
    const final = JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)
    expect([...final].sort()).toEqual([...ids()].sort())
    expect(final[final.length - 1]).toBe(ids()[0])   // 未重复追加
  })

  it('move → 换序持久化(拖拽落点的纯函数面)', async () => {
    const { move } = useWorkbenchLayout(ref(USER))
    move(0, 2)   // [a,b,c] → [b,c,a]
    await flushed()
    const expect_ = [...ids()]
    const [first] = expect_.splice(0, 1)
    expect_.splice(2, 0, first)
    expect(JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)).toEqual(expect_)
    // 越界拒收(不变)
    move(-1, 0)
    move(0, 99)
    await flushed()
    expect(JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)).toEqual(expect_)
  })

  it('存档含未知 id → 读取时静默过滤;损坏存档 → 回默认', () => {
    localStorage.setItem(`workbench.layout.v1:${USER}`, JSON.stringify([ids()[0], 'gone']))
    const { orderedIds } = useWorkbenchLayout(ref(USER))
    expect(orderedIds.value).toEqual([ids()[0]])

    localStorage.setItem(`workbench.layout.v1:${USER}`, '{broken json')
    const again = useWorkbenchLayout(ref(USER))
    expect(again.orderedIds.value).toEqual(ids())
  })

  it('按用户分键:另一账号的存档互不串台;username 切换自动重载', async () => {
    localStorage.setItem(`workbench.layout.v1:${OTHER}`, JSON.stringify([ids()[1]]))
    const name = ref(USER)
    const { orderedIds } = useWorkbenchLayout(name)
    expect(orderedIds.value).toEqual(ids())        // alice 无存档 → 默认

    name.value = OTHER
    await nextTick()
    expect(orderedIds.value).toEqual([ids()[1]])   // 切到 bob → 读 bob 的存档
  })

  it('reset → 回默认序', async () => {
    const { move, remove, reset } = useWorkbenchLayout(ref(USER))
    move(0, 2)
    remove(ids()[2])
    reset()
    await flushed()
    expect(JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)).toEqual(ids())
  })
})
