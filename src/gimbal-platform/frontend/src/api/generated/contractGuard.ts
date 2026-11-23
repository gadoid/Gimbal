/**
 * contractGuard.ts — B5 治本切片 1:手写类型 ↔ 生成契约的编译期对账。
 *
 * 生成的 openapi.ts 是后端契约快照的直译(Any 字段 → unknown,比手写
 * 宽);手写类型是前端消费面(更窄、带语义注释)。本文件用 assignability
 * 断言钉住「手写声明的每个形状都存在于生成形状」—— 后端改字段名/
 * 可空性而前端手写类型没跟上时,这里在 vue-tsc 编译期变红(而非运行
 * 时 undefined 静默漂移)。
 *
 * 断言方向:`const _x: GeneratedOut = handwrittenValue`(手写 ⊆ 生成)。
 * 手写比生成**多**的字段(前端自加的投影/计算面)不检查 —— 那是合法
 * 的客户端扩展;手写比生成**窄**的类型(union 收窄、null 收紧)是合法
 * 子类型,放行。
 *
 * 逐域接入:本文件先挂 executions 域(示范位);其余域按批次追加
 * 断言块(登记册 B5 切片 2+)。生成物勿手改 —— 重跑
 * `python scripts/gen_frontend_contract.py`。
 */
import type {
  Execution,
  ExecutionListEnvelope,
  ExecutionListItem,
  ExecutionRow,
  ExecutionsSummary,
} from '@/api/executions'
import type {
  ExecutionListItemOut,
  ExecutionListOut,
  ExecutionOut,
  ExecutionRowOut,
  ExecutionSummaryOut,
} from './openapi'

// ── executions 域 ──────────────────────────────────────────────
declare const _execution: Execution
const _g1: ExecutionOut = _execution

declare const _listItem: ExecutionListItem
const _g2: ExecutionListItemOut = _listItem

declare const _envelope: ExecutionListEnvelope
const _g3: ExecutionListOut = _envelope

declare const _row: ExecutionRow
const _g4: ExecutionRowOut = _row

declare const _summary: ExecutionsSummary
const _g5: ExecutionSummaryOut = _summary

// 编译期防未使用告警(guards 是纯类型层,无运行时产物)
export const CONTRACT_GUARD_DOMAINS = ['executions'] as const
void [_g1, _g2, _g3, _g4, _g5]
