/**
 * router — 关键深链可达性(2026-11-05 前端评审 P1-1/P2-5 回归钉)。
 * 调试台路由曾在普通字符串里把 \\d+ 写成 \d+(\d 即字母 d),数字 id
 * 全部落空白页;这里断言数字 id 命中调试台、字母 id 不命中,并钉住
 * catch-all 404:坏链路落 NotFound 而不是无匹配。
 */
import { describe, it, expect } from 'vitest'
import router from '@/router'

const DEBUG_PATH = '/executions/:id(\\d+)/debug'
const CATCH_ALL = '/:pathMatch(.*)*'

describe('router — 深链可达性', () => {
  it('调试台:数字 id 命中,字母 id 不命中(评审 P1-1)', () => {
    expect(router.resolve('/executions/123/debug').matched.at(-1)?.path)
      .toBe(DEBUG_PATH)
    // 修复前 \d 被当成字母 d:这个地址反而能匹配调试台
    expect(router.resolve('/executions/ddd/debug').matched.at(-1)?.path)
      .toBe(CATCH_ALL)
  })

  it('catch-all 404:未知路径落 NotFound(评审 P2-5)', () => {
    expect(router.resolve('/definitely/not/a/page').matched.at(-1)?.path)
      .toBe(CATCH_ALL)
    // 已知深链不受兜底影响
    expect(router.resolve('/executions/7/events').matched.at(-1)?.path)
      .toBe('/executions/:id(\\d+)/events')
  })
})
