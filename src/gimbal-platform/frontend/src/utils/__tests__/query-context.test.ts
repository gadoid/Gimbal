/** query-context — 数据集单变量面板取数上下文解析(修订 10/11 语义纯函数钉)。 */
import { describe, expect, it } from 'vitest'
import { headerAuthTagOf, resolveQueryCtx } from '../query-context'

const CONFIG = {
  services: { fin: 'http://fin.example.com:8000', ops: 'http://ops.example.com' },
  users: {
    fin_admin: { url: 'http://fin.example.com:8000/login' },
    fin_b: { url: 'http://fin.example.com:8000/login' },
    ops_admin: { url: 'http://ops.example.com/login' },
  },
}

describe('headerAuthTagOf — headers auth 引用首命中(修订 11)', () => {
  it('headers 含 `${auth.<tag>.token}` → 首命中 tag', () => {
    const step = { headers: { Accept: 'application/json', Authorization: 'Bearer ${auth.fin_b.token}' } }
    expect(headerAuthTagOf(step)).toBe('fin_b')
  })

  it('无 auth 引用 → null(交由域内首键 fallback)', () => {
    expect(headerAuthTagOf({ headers: { Authorization: 'Bearer literal' } })).toBeNull()
    expect(headerAuthTagOf({ headers: {} })).toBeNull()
    expect(headerAuthTagOf({})).toBeNull()
  })
})

describe('resolveQueryCtx — serviceUrl + queryAlias', () => {
  it('服务声明命中 → serviceUrl;别名 = 同域 users 首键(修订 10 域内首键)', () => {
    const r = resolveQueryCtx({ service: 'fin', headers: {} }, CONFIG)
    expect(r.serviceUrl).toBe('http://fin.example.com:8000')
    // fin 域两个用户,键序首命中 fin_admin
    expect(r.queryAlias).toBe('fin_admin')
  })

  it('headers auth 引用优先于域内首键(修订 11:查询身份 = 执行身份)', () => {
    const r = resolveQueryCtx(
      { service: 'fin', headers: { Authorization: 'Bearer ${auth.fin_b.token}' } },
      CONFIG,
    )
    expect(r.queryAlias).toBe('fin_b')
  })

  it('服务域无用户 → null 诚实 422(不回退异域首键)', () => {
    const r = resolveQueryCtx({ service: 'ops' }, {
      services: { ops: 'http://elsewhere.example.com' },
      users: CONFIG.users,
    })
    expect(r.serviceUrl).toBe('http://elsewhere.example.com')
    expect(r.queryAlias).toBeNull()
  })

  it('服务未声明(URL 未知)→ serviceUrl undefined;别名回退全表首键', () => {
    const r = resolveQueryCtx({ service: '', headers: {} }, CONFIG)
    expect(r.serviceUrl).toBeUndefined()
    expect(r.queryAlias).toBe('fin_admin')
  })

  it('无 users → alias null;未声明服务 → services 表不命中', () => {
    expect(resolveQueryCtx({ service: 'fin' }, { services: CONFIG.services }).queryAlias).toBeNull()
    expect(resolveQueryCtx({ service: 'nope' }, CONFIG).serviceUrl).toBeUndefined()
  })
})
