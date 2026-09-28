/**
 * plate /full 域路径 → gimbal 引擎 call 信封域路径。
 *
 * 引擎 scratch 根 = call 信封(`gimbal/strategy/builtin/call.py` 在调用后
 * 写入 `$.call.*`:response.body / response.status / response.meta.headers /
 * elapsed_ms / request.body …),策略(extract/assertion/assign)的 JSONPath
 * 导航以 call 信封为根(api→call 清理:旧 `$.response_body` scratch 域退役,
 * 前端直产 call 域,不再依赖 plate convert 的路径重写)。
 *
 * 映射规则(设计文档 2026-08-18-step-editor-io-cards-design.md §2.1,域随
 * 2026-09-28 api→call 清理切换):
 * - `$.status` → `$.call.response.status`(引擎独立 key,特判)
 * - `$` / `''`  → `$.call.response.body`(根 = 整个响应体)
 * - 其余        → `$.` 前缀替换为 `$.call.response.body.`,下标语法原样保留;
 *   根 list 形态(修轮 R2)`$[0].sku` 剥 `$`(无点)后 rel 以 `[` 开头 →
 *   前缀直拼无点(`$.call.response.body[0].sku`,与 requestBodyTargetOf 同式分流)
 * - 已是 call 域(`$.call.response.body.` / `$.call.response.status`)的路径幂等返回
 */
export function toScratchPath(platePath: string): string {
  if (platePath === '$.status') return '$.call.response.status'
  if (platePath === '$' || platePath === '') return '$.call.response.body'
  if (platePath === '$.call.response.status') return platePath
  if (platePath.startsWith('$.call.response.body.')) return platePath
  const rel = platePath.replace(/^\$\.?/, '')
  return `$.call.response.body${rel.startsWith('[') ? '' : '.'}${rel}`
}
