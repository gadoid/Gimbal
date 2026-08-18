/**
 * plate /full 域路径 → gimbal 引擎 scratch 域路径。
 *
 * 引擎 scratch 顶层 key 由 `gimbal/strategy/builtin/call.py` 在 HTTP 响应后写入:
 * response_status / response_body / response_headers / duration_ms / ...
 * 策略(extract/assertion)的 JSONPath 导航以 scratch 为根。
 *
 * 映射规则(设计文档 2026-08-18-step-editor-io-cards-design.md §2.1):
 * - `$.status` → `$.response_status`(引擎独立 key,特判)
 * - `$` / `''`  → `$.response_body`(根 = 整个响应体)
 * - 其余        → `$.` 前缀替换为 `$.response_body.`,下标语法原样保留
 * - 已是 scratch 域(`$.response_body.` / `$.response_status`)的路径幂等返回
 */
export function toScratchPath(platePath: string): string {
  if (platePath === '$.status') return '$.response_status'
  if (platePath === '$' || platePath === '') return '$.response_body'
  if (platePath === '$.response_status') return platePath
  if (platePath.startsWith('$.response_body.')) return platePath
  return platePath.replace(/^\$\./, '$.response_body.')
}
