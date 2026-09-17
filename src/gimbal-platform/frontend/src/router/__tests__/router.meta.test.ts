/**
 * router — chromeMode 路由表标注(评审补充的测试缺口)。
 * 钉住两条约束:编辑流页(编排器/方案工作台/断言注册表/常量池)必须是
 * collapsed;其余认证页不得误标(误标会让侧栏整页消失)。默认落地 /home。
 */
import { describe, it, expect } from 'vitest'
import router from '@/router'

const COLLAPSED_PATHS = [
  '/composer/:scenarioId',
  '/scenarios/:scenarioId/schemes',
  '/scenarios/:scenarioId/assertions',
  '/constants',
]

describe('router — chromeMode 标注', () => {
  const routes = router.getRoutes()

  it('编辑流页 = collapsed,且恰好这四条', () => {
    const collapsed = routes
      .filter((r) => r.meta.chromeMode === 'collapsed')
      .map((r) => r.path)
      .sort()
    expect(collapsed).toEqual([...COLLAPSED_PATHS].sort())
  })

  it('认证页其余全部缺省 full(不显式写,走 App 默认)', () => {
    const fullOrUndefined = routes
      .filter((r) => !COLLAPSED_PATHS.includes(r.path))
      .every((r) => r.meta.chromeMode === undefined)
    expect(fullOrUndefined).toBe(true)
  })

  it('默认落地:/ → /home,/home requiresAuth(F-sitemap v2)', () => {
    const root = router.options.routes.find((r) => r.path === '/')
    expect(root?.redirect).toBe('/home')
    const home = routes.find((r) => r.path === '/home')
    expect(home?.meta.requiresAuth).toBe(true)
  })

  it('D1 退役数据集路由兜底:两条旧深链 redirect 到方案工作台(不白屏)', () => {
    const retired = [
      '/scenarios/:scenarioId/data-sets',
      '/scenarios/:scenarioId/data-sets/:datasetId',
    ].map((path) => router.options.routes.find((r) => r.path === path))
    expect(retired.every(Boolean)).toBe(true)
    for (const rec of retired) {
      const redirect = (rec as unknown as { redirect: (to: unknown) => string }).redirect
      expect(redirect).toBeTypeOf('function')
      // 含空格的 id 也要编码正确(路由段语义)
      expect(
        redirect({ params: { scenarioId: 'sc x' } }),
      ).toBe('/scenarios/sc%20x/schemes')
    }
  })
})
