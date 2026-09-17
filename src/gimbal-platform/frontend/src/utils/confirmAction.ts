/**
 * confirmAction.ts — 确认/输入弹窗单一真源(重构方案 Phase 1 交叉切面)。
 *
 * 接口签名与语义不变,内部实现从 ElMessageBox 换为新栈 Dialog
 * (ConfirmHost 渲染,App.vue 挂载):
 *
 * - confirmAction:确认 → true;取消('cancel')、关闭(ESC / 右上角 /
 *   点击遮罩,'close')统一返回 false,都不是错误。此前 7 处调用点各自
 *   手写 try/catch,其中两处只吞 'cancel',按 ESC 会误弹"删除失败"
 *   错误 toast —— 收拢后由本模块统一兜住,替换时语义不得丢失。
 * - promptAction:确认 → 输入值(可能为空字符串,由调用方校验);
 *   取消/关闭 → null。
 *
 * 测试 mock 本模块(vi.mock('@/utils/confirmAction')),不再 mock
 * element-plus 的 ElMessageBox。
 */
import { reactive } from 'vue'

export interface ConfirmOptions {
  /** 图标语义:'warning' 警示,'info' 提示(默认)。 */
  type?: 'info' | 'warning'
  confirmButtonText?: string
  cancelButtonText?: string
  /** 危险操作:主按钮用 destructive 色。 */
  danger?: boolean
  /** @deprecated 迁移容忍:'el-button--danger' 等同 danger:true;批次 6 起调用方改传 danger。 */
  confirmButtonClass?: string
}

export interface PromptOptions {
  /** 输入框预填值(重命名场景)。 */
  inputValue?: string
  placeholder?: string
}

export interface DialogRequest {
  kind: 'confirm' | 'prompt'
  title: string
  message: string
  options: ConfirmOptions & PromptOptions
}

/** ConfirmHost 消费的总线状态;current 非空即有弹窗在场。 */
export const dialogState = reactive({
  current: null as DialogRequest | null,
  /** prompt 模式下输入框的绑定值(open 时用 inputValue 预填)。 */
  inputValue: '',
})

const queue: Array<{ req: DialogRequest; resolve: (v: boolean | string) => void }> = []

function activate(req: DialogRequest, resolve: (v: boolean | string) => void) {
  queue.push({ req, resolve })
  if (!dialogState.current) shift()
}

function shift() {
  const next = queue.shift()
  if (!next) return
  dialogState.current = next.req
  dialogState.inputValue = next.req.options.inputValue ?? ''
  pendingResolve = next.resolve
}

let pendingResolve: ((v: boolean | string) => void) | null = null

/** 由 ConfirmHost 调用:确认(confirm → true;prompt → 输入值)。 */
export function acceptDialog(): void {
  if (!dialogState.current || !pendingResolve) return
  const resolve = pendingResolve
  const kind = dialogState.current.kind
  // 先取值再 close:close 会激活队列中下一条弹窗并重置 inputValue
  const value = kind === 'prompt' ? dialogState.inputValue : true
  close()
  resolve(value)
}

/** 由 ConfirmHost 调用:取消/ESC/遮罩/右上角关闭 —— confirm 落 false,
 *  prompt 落 null,均不视作错误。 */
export function cancelDialog(): void {
  if (!dialogState.current || !pendingResolve) return
  const resolve = pendingResolve
  close()
  resolve(false)
}

function close() {
  pendingResolve = null
  dialogState.current = null
  shift()
}

function openDialog(req: DialogRequest): Promise<boolean | string> {
  return new Promise((resolve) => activate(req, resolve))
}

export async function confirmAction(
  message: string,
  title: string,
  options: ConfirmOptions = {},
): Promise<boolean> {
  return (await openDialog({ kind: 'confirm', title, message, options })) === true
}

export async function promptAction(
  message: string,
  title: string,
  options: PromptOptions = {},
): Promise<string | null> {
  const v = await openDialog({ kind: 'prompt', title, message, options })
  return typeof v === 'string' ? v : null
}
