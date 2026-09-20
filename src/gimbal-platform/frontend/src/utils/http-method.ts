/**
 * http-method.ts — HTTP 方法 → 徽标配色档。
 * 画像是服务级、线索板是接口级,两处此前各写一份 hex 映射表。
 */
export function methodClass(method: string | null | undefined): 'get' | 'post' | 'put' | 'del' | 'other' {
  switch ((method || '').toUpperCase()) {
    case 'GET': return 'get'
    case 'POST': return 'post'
    case 'PUT': return 'put'
    case 'DELETE': return 'del'
    default: return 'other'
  }
}
