/**
 * utils/ansi — ESC 序列剥除(结构化日志设计 AD8 层 4:治愈存量文件)。
 *
 * 历史执行的 server-engine.log 含 ANSI 色码(早期 loguru/uvicorn/reporter
 * 汇总行);入库面已零 ANSI,本 util 只服务**工件查看器**的展示面:默认
 * 剥除显示纯文本,「显示原始」开关保留原样。
 *
 * 注:正则以字符串构造(ESC/BEL 是控制字符,字面量正则在多轮编辑/heredoc
 * 传递中转义层次易错;字符串拼接的源只有一层含义)。
 */

const ESC = String.fromCharCode(27)   // \x1b
const BEL = String.fromCharCode(7)    // \x07

const ANSI_RE = new RegExp(
  ESC + String.raw`\[[0-9;]*[A-HJKSTfhlmnsu]`      // CSI(SGR/光标/擦除)
  + '|' + ESC + String.raw`\][^` + BEL + ESC + String.raw`]*(?:` + BEL
    + '|' + ESC + String.raw`\\)`                    // OSC(BEL 或 ESC\ 收尾)
  + '|' + ESC + '[=>]',
  'g',
)

/** 剥除 ANSI/OSC 转义序列;无转义时原样返回(零拷贝路径)。 */
export function stripAnsi(text: string): string {
  return ANSI_RE.test(text) ? text.replace(ANSI_RE, '') : text
}

/** 是否含 ANSI(查看器决定默认视图与开关态)。 */
export function hasAnsi(text: string): boolean {
  ANSI_RE.lastIndex = 0
  return ANSI_RE.test(text)
}
