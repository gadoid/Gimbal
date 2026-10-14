/**
 * utils/sse — fetch-SSE 共享解析器(结构化日志设计 AD7)。
 *
 * EventSource 不支持 Authorization 头,平台两路 SSE(事件流/日志流)都走
 * fetch 流式读 + 本解析器。帧规范(设计 §7):真 `\n\n` 分帧,行前缀
 * id:/event:/data:,`: ping` 为注释帧忽略。
 *
 * 历史注记:后端曾以字面量 `\n` 两字符发帧(批 1 前缺陷),前端真换行
 * 切帧永远失败、页面更新静默退化为兜底轮询 —— 解析逻辑收敛到本 util
 * 单点维护,事件流与日志流共用。
 */

export interface SseFrame {
  id?: string
  event?: string
  data?: string
}

/** 解析单个帧块(不含 `\n\n` 分隔):返回 null 表示注释/空帧。 */
export function parseSseFrame(block: string): SseFrame | null {
  const out: SseFrame = {}
  for (const raw of block.split('\n')) {
    const line = raw.replace(/\r$/, '')
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('id:')) out.id = line.slice(3).trim()
    else if (line.startsWith('event:')) out.event = line.slice(6).trim()
    else if (line.startsWith('data:')) out.data = line.slice(5).trim()
  }
  return out.id !== undefined || out.event !== undefined || out.data !== undefined
    ? out
    : null
}

/** 整段文本 → 帧列表(测试/一次性解析用)。 */
export function parseSseText(text: string): SseFrame[] {
  return text.split('\n\n')
    .map(parseSseFrame)
    .filter((f): f is SseFrame => f !== null)
}

/**
 * 逐帧消费 fetch 响应体。chunk 边界任意(网络分片不保证行对齐),内部
 * 缓冲按 `\n\n` 切帧;流结束收尾。
 *
 * @param onFrame 每帧回调;返回 false 提前停止读取(如收到 done 帧)。
 */
export async function readSseStream(
  resp: Response,
  onFrame: (frame: SseFrame) => boolean | void,
): Promise<void> {
  if (!resp.body) return
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let sep = buf.indexOf('\n\n')
    while (sep >= 0) {
      const frame = parseSseFrame(buf.slice(0, sep))
      buf = buf.slice(sep + 2)
      sep = buf.indexOf('\n\n')
      if (frame && onFrame(frame) === false) return
    }
  }
  // 尾部残帧(无空行结尾的非规范收尾)尽力解析
  if (buf.trim()) {
    const frame = parseSseFrame(buf)
    if (frame) onFrame(frame)
  }
}
