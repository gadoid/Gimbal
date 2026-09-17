/**
 * confirmAction.ts — 语义回归测试(重构方案 Phase 1 交叉切面)。
 *
 * 换栈(ElMessageBox → 新栈 Dialog 总线)必须保住的历史语义:
 * - 取消/ESC/遮罩/右上角关闭统一落 false(确认)/ null(prompt),
 *   都不是错误 —— 这是当年 7 处调用点收拢时的核心修复;
 * - prompt 确认返回输入值,**空字符串是合法返回值**(由调用方校验);
 * - 弹窗串行:前一条未决时后一条排队,不互相覆盖。
 * 渲染端 ConfirmHost 只是把 acceptDialog/cancelDialog 接到 Dialog
 * 事件上,行为真源在本模块,直接驱动总线即测。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  acceptDialog,
  cancelDialog,
  confirmAction,
  dialogState,
  promptAction,
} from '@/utils/confirmAction'

describe('confirmAction — 取消/关闭统一返 false', () => {
  beforeEach(() => {
    dialogState.current = null
    dialogState.inputValue = ''
  })

  it('确认 → true', async () => {
    const p = confirmAction('确认删除?', '删除', { type: 'warning', confirmButtonText: '删除' })
    expect(dialogState.current).toMatchObject({ kind: 'confirm', title: '删除' })
    acceptDialog()
    await expect(p).resolves.toBe(true)
  })

  it('取消按钮 → false', async () => {
    const p = confirmAction('x', 'y')
    cancelDialog()
    await expect(p).resolves.toBe(false)
  })

  it('ESC/遮罩/关闭(Host 走同一 cancelDialog)→ false,不 reject', async () => {
    const p = confirmAction('x', 'y')
    cancelDialog()
    await expect(p).resolves.toBe(false)
  })

  it('confirmButtonClass 含 danger → danger 兜底语义(批次 6 迁移容忍)', async () => {
    const p = confirmAction('x', 'y', { confirmButtonClass: 'el-button--danger' })
    expect(dialogState.current?.options.confirmButtonClass).toContain('danger')
    acceptDialog()
    await expect(p).resolves.toBe(true)
  })
})

describe('promptAction — 空串合法、取消 null', () => {
  beforeEach(() => {
    dialogState.current = null
    dialogState.inputValue = ''
  })

  it('确认 → 输入值;inputValue 预填生效(重命名场景)', async () => {
    const p = promptAction('方案名称', '重命名方案', { inputValue: '冒烟' })
    expect(dialogState.inputValue).toBe('冒烟')
    dialogState.inputValue = '冒烟 v2'
    acceptDialog()
    await expect(p).resolves.toBe('冒烟 v2')
  })

  it('确认时空字符串原样返回(由调用方校验非空)', async () => {
    const p = promptAction('方案名称', '重命名方案')
    dialogState.inputValue = ''
    acceptDialog()
    await expect(p).resolves.toBe('')
  })

  it('取消 → null', async () => {
    const p = promptAction('x', 'y', { inputValue: '草稿' })
    cancelDialog()
    await expect(p).resolves.toBeNull()
  })
})

describe('弹窗串行 — 前一条未决时排队', () => {
  beforeEach(() => {
    dialogState.current = null
    dialogState.inputValue = ''
  })

  it('第二条在第一条 resolve 后才激活,inputValue 换成新请求的预填', async () => {
    const first = confirmAction('第一问', 'A')
    const second = promptAction('第二问', 'B', { inputValue: 'pre' })

    expect(dialogState.current?.title).toBe('A')
    acceptDialog()
    await first

    expect(dialogState.current?.title).toBe('B')
    expect(dialogState.inputValue).toBe('pre')
    cancelDialog()
    await expect(second).resolves.toBeNull()
    expect(dialogState.current).toBeNull()
  })
})
