/**
 * confirmAction.ts — 单一的 ElMessageBox.confirm 封装。
 *
 * 取消路径统一返回 false：'cancel'（取消按钮）、'close'（ESC / 右上角
 * 关闭 / 点击遮罩）都不是错误。此前 7 处调用点各自手写 try/catch，
 * 其中两处只吞 'cancel'，按 ESC 会误弹"删除失败"错误 toast。
 */
import { ElMessageBox } from 'element-plus'

export async function confirmAction(
  message: string,
  title: string,
  options: Parameters<typeof ElMessageBox.confirm>[2] = {},
): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, options)
    return true
  } catch {
    return false
  }
}

/**
 * prompt 变体：取消/关闭（'cancel' / 'close'）同样返回 null 而非
 * reject，确认则返回输入值（可能为空字符串，由调用方校验）。
 */
export async function promptAction(
  message: string,
  title: string,
  options: Parameters<typeof ElMessageBox.prompt>[2] = {},
): Promise<string | null> {
  try {
    const { value } = await ElMessageBox.prompt(message, title, options)
    return value
  } catch {
    return null
  }
}
