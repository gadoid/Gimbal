/**
 * ConfirmHost — 渲染端 DOM 行为(评审补充的测试缺口)。
 *
 * confirmAction 总线逻辑已有单测;这里验证 Host 把 Dialog 事件正确接到
 * acceptDialog/cancelDialog 上:确认/取消按钮、ESC、X 关闭、prompt 的
 * 预填与 Enter、以及焦点策略(danger/warning → 取消;良性 → 确定明确;
 * prompt → 输入框)。
 *
 * 注意:shadcn Input 的 useVModel 走 Vue 调度器(pre-flush),模拟输入后
 * 需 nextTick 再点确认——真实用户操作天然满足这个时序。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ConfirmHost from '@/components/chrome/ConfirmHost.vue'
import { DialogContent } from '@/components/ui/dialog'
import {
  acceptDialog,
  cancelDialog,
  confirmAction,
  dialogState,
  promptAction,
} from '@/utils/confirmAction'

let w: ReturnType<typeof mount> | null = null

function bodyButtons(): HTMLButtonElement[] {
  return [...document.body.querySelectorAll('button')] as HTMLButtonElement[]
}

function findBodyButton(text: string): HTMLButtonElement | undefined {
  return bodyButtons().find((b) => b.textContent?.trim() === text)
}

async function openHost() {
  w = mount(ConfirmHost)
  await flushPromises()
  return w
}

beforeEach(() => {
  document.body.innerHTML = ''
  dialogState.current = null
  dialogState.inputValue = ''
})

afterEach(() => {
  // 断言失败也要拆掉 Host:它与下一个用例共享模块级总线
  w?.unmount()
  w = null
  document.body.innerHTML = ''
  dialogState.current = null
  dialogState.inputValue = ''
})

describe('ConfirmHost — confirm 模式', () => {
  it('确认按钮 → resolve true;文案与按钮字透传', async () => {
    await openHost()
    const p = confirmAction('确认删除?', '删除场景', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await flushPromises()

    expect(document.body.textContent).toContain('删除场景')
    expect(document.body.textContent).toContain('确认删除?')
    findBodyButton('删除')!.click()
    await expect(p).resolves.toBe(true)
  })

  it('取消按钮 → false;ESC 事件 → false(语义单点 cancelDialog)', async () => {
    await openHost()
    const p = confirmAction('x', 'y')
    await flushPromises()
    findBodyButton('取消')!.click()
    await expect(p).resolves.toBe(false)

    const p2 = confirmAction('x2', 'y2')
    await flushPromises()
    // reka-ui 侧发的事件名;Host 上 .prevent + cancelDialog 是我们的绑定
    w!.findComponent(DialogContent).vm.$emit('escapeKeyDown', new Event('escape'))
    await expect(p2).resolves.toBe(false)
  })

  it('焦点策略:warning → 初始焦点在取消(Enter 不误触破坏性操作)', async () => {
    await openHost()
    const p = confirmAction('确认?', '删除', { type: 'warning' })
    await flushPromises()
    expect(document.activeElement?.textContent?.trim()).toBe('取消')
    cancelDialog()
    await expect(p).resolves.toBe(false)
  })

  it('焦点策略:良性确认 → 初始焦点在主按钮(Enter=确认,对齐 ElMessageBox)', async () => {
    await openHost()
    const p = confirmAction('复制?', '复制场景', { type: 'info' })
    await flushPromises()
    expect(document.activeElement?.textContent?.trim()).toBe('确定')
    acceptDialog()
    await expect(p).resolves.toBe(true)
  })
})

describe('ConfirmHost — prompt 模式', () => {
  it('inputValue 预填回显;确认返回输入值;空串合法', async () => {
    await openHost()
    const p = promptAction('方案名称', '重命名方案', { inputValue: '冒烟' })
    await flushPromises()
    const input = document.body.querySelector('input')!
    expect(input.value).toBe('冒烟')

    input.value = '冒烟 v2'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick() // useVModel 经调度器 emit,非同步
    findBodyButton('确定')!.click()
    await expect(p).resolves.toBe('冒烟 v2')

    // 空串:确认后原样返回
    const p2 = promptAction('方案名称', '重命名方案')
    await flushPromises()
    findBodyButton('确定')!.click()
    await expect(p2).resolves.toBe('')
  })

  it('输入框 Enter=确认;取消/X 关闭 → null;焦点在输入框', async () => {
    await openHost()
    const p = promptAction('方案名称', '重命名方案')
    await flushPromises()
    const input = document.body.querySelector('input')!
    expect(document.activeElement).toBe(input)

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await expect(p).resolves.toBe('')

    const p2 = promptAction('x', 'y', { inputValue: '草稿' })
    await flushPromises()
    // 右上角 X(DialogClose)在场,点击 = cancel 语义
    const x = bodyButtons().find((b) => b.textContent?.includes('Close'))
    expect(x).toBeTruthy()
    x!.click()
    await expect(p2).resolves.toBeNull()
  })
})
