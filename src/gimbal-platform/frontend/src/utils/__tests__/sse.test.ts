/**
 * utils/sse — 共享 SSE 解析器单测(结构化日志批 2/AD7)。
 *
 * 关键回归面:真 `\n\n` 分帧 + chunk 边界任意(网络分片不保证行对齐)
 * + 注释/心跳帧忽略 + done 帧返回 false 停读。历史缺陷(后端字面量 \n
 * 发帧 → 前端永远切不出帧)由后端帧结构测试把守,本面把守前端解析。
 */
import { describe, it, expect } from 'vitest'
import { parseSseFrame, parseSseText, readSseStream } from '@/utils/sse'

function respOf(chunks: string[]): Response {
  const enc = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch))
      c.close()
    },
  })
  return { ok: true, status: 200, body: stream } as unknown as Response
}

describe('parseSseFrame / parseSseText', () => {
  it('解析 id/event/data 三字段(真换行)', () => {
    const f = parseSseFrame('id: 42\nevent: log\ndata: {"a":1}')
    expect(f).toEqual({ id: '42', event: 'log', data: '{"a":1}' })
  })

  it('注释/心跳帧与空块返回 null', () => {
    expect(parseSseFrame(': ping')).toBeNull()
    expect(parseSseFrame('')).toBeNull()
  })

  it('CRLF 行尾兼容', () => {
    const f = parseSseFrame('id: 7\r\nevent: ev\r\n')
    expect(f).toEqual({ id: '7', event: 'ev' })
  })

  it('parseSseText 按 \\n\\n 分帧且丢弃注释帧', () => {
    const frames = parseSseText(
      'id: 1\nevent: ev\ndata: {}\n\n: ping\n\nid: 2\nevent: done\ndata: {"status":"done"}\n\n',
    )
    expect(frames.map((f) => f.id)).toEqual(['1', '2'])
    expect(frames[1]!.event).toBe('done')
  })
})

describe('readSseStream', () => {
  it('chunk 边界任意切分仍完整成帧(半行分片)', async () => {
    const chunks = [
      'id: 1\nev', 'ent: log\ndata: {"m":"a"}\n', '\nid: 2\nevent: log\ndata: {"m":"b"}\n\n',
    ]
    const got: unknown[] = []
    await readSseStream(respOf(chunks), (f) => { got.push(f) })
    expect(got).toHaveLength(2)
    expect((got[0] as { data?: string }).data).toContain('"a"')
    expect((got[1] as { data?: string }).data).toContain('"b"')
  })

  it('onFrame 返回 false 停读(done 帧后不再消费)', async () => {
    const chunks = [
      'id: 1\nevent: ev\ndata: {}\n\n',
      'id: 2\nevent: done\ndata: {}\n\n',
      'id: 3\nevent: ev\ndata: {}\n\n',
    ]
    const ids: (string | undefined)[] = []
    await readSseStream(respOf(chunks), (f) => {
      ids.push(f.id)
      return f.event !== 'done'
    })
    expect(ids).toEqual(['1', '2'])
  })

  it('无 body 直接返回', async () => {
    await readSseStream({ body: null } as unknown as Response, () => {})
  })
})
