/**
 * useInsertTarget — DOM 焦点跟踪的"插入目标"(常量池 Panel 插入到字段)。
 *
 * focusin 捕获挂在 composer 根,记录最后获焦的文本可编辑元素;插入 =
 * 值尾追加 + 派发原生 input 事件,兼容 FieldForm 原生 @input→setValue
 * (JSONPath)、el-input v-model、原生 textarea 三链。跳过
 * number/checkbox/radio/file/select —— 这些控件追加文本无意义。
 *
 * 通过 provide/inject 共享: CaseComposer 根 provideInsertTarget(),
 * rail Panel(步骤 0-2)与 Canvas col-info Panel(步骤 3)inject 同一实例。
 */
import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

const TEXT_SELECTOR =
  'input[type="text"], input:not([type]), input[type="search"], textarea, [contenteditable="true"]'

export interface InsertTargetApi {
  lastTarget: Ref<HTMLElement | null>
  start: (root: HTMLElement) => void
  stop: () => void
  /** 值尾追加 text 并派发原生 input;无有效目标返回 false。 */
  appendValue: (text: string) => boolean
}

export function useInsertTarget(): InsertTargetApi {
  const lastTarget = ref<HTMLElement | null>(null)
  let boundRoot: HTMLElement | null = null

  function isTextEditable(el: EventTarget | null): el is HTMLElement {
    if (!(el instanceof HTMLElement)) return false
    if (el.hasAttribute('disabled') || el.hasAttribute('readonly')) return false
    return el.matches(TEXT_SELECTOR)
  }

  function onFocusIn(e: FocusEvent): void {
    if (isTextEditable(e.target)) lastTarget.value = e.target
  }

  function start(root: HTMLElement): void {
    stop()
    boundRoot = root
    root.addEventListener('focusin', onFocusIn, true)
  }

  function stop(): void {
    if (boundRoot) boundRoot.removeEventListener('focusin', onFocusIn, true)
    boundRoot = null
    lastTarget.value = null
  }

  function appendValue(text: string): boolean {
    const el = lastTarget.value
    if (!el || !el.isConnected) {
      lastTarget.value = null
      return false
    }
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
      el.value = el.value + text
      el.dispatchEvent(new Event('input', { bubbles: true }))
    } else {
      el.appendChild(document.createTextNode(text))
      el.dispatchEvent(new InputEvent('input', { bubbles: true }))
    }
    return true
  }

  return { lastTarget, start, stop, appendValue }
}

export const INSERT_TARGET_KEY: InjectionKey<InsertTargetApi> = Symbol('insert-target')

export function provideInsertTarget(api: InsertTargetApi): void {
  provide(INSERT_TARGET_KEY, api)
}

/** Panel 侧取共享实例;CaseComposer 根提供。 */
export function useSharedInsertTarget(): InsertTargetApi {
  const api = inject(INSERT_TARGET_KEY)
  if (!api) {
    throw new Error(
      'useSharedInsertTarget: 未 provide INSERT_TARGET_KEY(应由 CaseComposer 根提供)',
    )
  }
  return api
}
