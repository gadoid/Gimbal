/**
 * router — 关键深链可达性(2026-11-05 前端评审 P1-1/P2-5 回归钉)。
 * 调试台路由曾在普通字符串里把 \\d+ 写成 \d+(\d 即字母 d),数字 id
 * 全部落空白页;这里断言数字 id 命中调试台、字母 id 不命中,并钉住
 * catch-all 404:坏链路落 NotFound 而不是无匹配。
 */
import { describe, it, expect, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import router, { routes } from '@/router'

const DEBUG_PATH = '/executions/:id(\\d+)/debug'
const CATCH_ALL = '/:pathMatch(.*)*'
const COMPOSE_PATH = '/suites/:id(\\d+)/compose'

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

describe('router — 新建画布别名', () => {
  it('/suites/new 命中画布别名:id 为字面量 new,且与 /suites/:id/compose 同一记录', () => {
    const r = router.resolve('/suites/new')
    const hit = r.matched.at(-1)
    expect(hit?.path).toBe('/suites/:id(new)')
    expect(r.params.id).toBe('new')
    // 同一记录:别名 → 原路由换 URL 是记录内更新,画布实例不重挂
    expect(hit?.aliasOf?.path).toBe(COMPOSE_PATH)
    // 别名的 id 只吃字面量 new:其余仍由 \d+ 原路由或 catch-all 承接
    expect(router.resolve('/suites/abc').matched.at(-1)?.path).toBe(CATCH_ALL)
  })

  it('生产路由表建表零 vue-router 别名参数告警(静态别名 /suites/new 缺 :id 曾 warn)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // mockRestore 会连带清空 mock.calls —— 取数必须在 restore 之前
    const aliasWarns = () => warn.mock.calls
      .map((c) => String(c[0]))
      .filter((m) => m.includes('exact same param')).length
    try {
      // 对照:同一截取方式对缺参别名必然抓到 1 条(防本断言空转)
      createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/probe/:id(\\d+)', alias: '/probe/new', component: {} }],
      })
      expect(aliasWarns()).toBe(1)
      createRouter({ history: createMemoryHistory(), routes })
      expect(aliasWarns()).toBe(1)
    } finally {
      warn.mockRestore()
    }
  })
})
