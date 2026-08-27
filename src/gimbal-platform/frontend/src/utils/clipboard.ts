/**
 * clipboard.ts — 剪贴板双通道(clipboard API 主 + execCommand 回退)。
 * 从 stores/scenario-draft.ts copyJson 抽出(常量池 Panel/管理页复用)。
 * jsdom 与非安全上下文(内网 http)下 navigator.clipboard 可能缺失/被拒 —
 * 回退保命。
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      /* 落到 execCommand 回退 */
    }
  }
  const ta = document.createElement('textarea')
  ta.value = text
  document.body.appendChild(ta)
  ta.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  return ok
}
