/**
 * useInsertTarget — DOM 焦点跟踪插入目标。
 * F1: 跟踪 text/textarea,忽略 number/checkbox/radio/file/select;
 * F2: 断连目标 appendValue 返回 false 并清引用;
 * F3: appendValue 值尾追加 + 派发原生 input 事件。
 */
import { describe, it, expect, vi } from 'vitest'
import { useInsertTarget } from '@/composables/useInsertTarget'

function focus(el: Element): void {
  el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
}

describe('useInsertTarget', () => {
  it('F1: 跟踪文本可编辑元素,忽略 number/checkbox/radio/file/select', () => {
    document.body.innerHTML = `
      <div id="root">
        <input id="t1" type="text" />
        <input id="n1" type="number" />
        <input id="c1" type="checkbox" />
        <input id="r1" type="radio" />
        <input id="f1" type="file" />
        <select id="s1"><option>a</option></select>
        <textarea id="ta1"></textarea>
      </div>`
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)

    focus(document.getElementById('t1')!)
    expect(api.lastTarget.value?.id).toBe('t1')
    for (const id of ['n1', 'c1', 'r1', 'f1', 's1']) {
      focus(document.getElementById(id)!)
      expect(api.lastTarget.value?.id).toBe('t1') // 非文本目标不更新
    }
    focus(document.getElementById('ta1')!)
    expect(api.lastTarget.value?.id).toBe('ta1')
    api.stop()
    document.body.innerHTML = ''
  })

  it('F2: 目标已断连 — appendValue 返回 false 并清空引用', () => {
    document.body.innerHTML =
      '<div id="root"><input id="gone" type="text" value="x" /></div>'
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)
    focus(document.getElementById('gone')!)
    document.getElementById('gone')!.remove()
    expect(api.appendValue('Y')).toBe(false)
    expect(api.lastTarget.value).toBeNull()
    api.stop()
    document.body.innerHTML = ''
  })

  it('F3: appendValue 值尾追加 + 派发原生 input 事件', () => {
    document.body.innerHTML =
      '<div id="root"><input id="t" type="text" value="abc" /></div>'
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)
    const input = document.getElementById('t') as HTMLInputElement
    focus(input)
    const spy = vi.fn()
    input.addEventListener('input', spy)
    expect(api.appendValue('-tail')).toBe(true)
    expect(input.value).toBe('abc-tail')
    expect(spy).toHaveBeenCalledTimes(1)
    api.stop()
    document.body.innerHTML = ''
  })
})
