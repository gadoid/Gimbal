/**
 * errorFallback.ts — single source of truth for "operation failed"
 * toast messages.  Replaces 14+ scattered inline `store.lastError || 'xxx失败'`
 * ternaries across 7 views.
 *
 * Usage:
 *   import { showError } from '@/utils/errorFallback'
 *   showError('保存', e)
 *   // → "保存失败: <server msg>" or just "保存失败" if no detail
 *
 * 第二参数 `err` 直接传 unknown,从 ErrorLike (msg/message) 抽详情。
 * 旧式三参 `showError(op, undefined, store.lastError)` 已废弃,store 层错误请
 * 直接 `throw` 出来,让 catch 块捕到再丢给 showError。
 */
import { ElMessage } from 'element-plus'

/** 常用操作标签(仅文档作用;``op`` 实际接受任意短标签,
 *  传时**不带**"失败"后缀 —— 后缀由 showError 拼接)。 */
export type OpKind =
  | '保存'
  | '加载'
  | '删除'
  | '修改'
  | '上传'
  | '提交'
  | '执行'
  | '重命名'
  | '另存为'
  | '复制'
  | '发布'
  | '收藏'
  | '操作'
  | (string & {})

export interface ErrorLike {
  message?: string
  msg?: string
}

/**
 * Show a toast: ``<op>失败: <server detail>`` when the error carries
 * a useful message, just ``<op>失败`` otherwise.  Falls back to the
 * optional ``storeLastError`` string when no detail is present.
 */
export function showError(
  op: OpKind,
  err?: unknown,
  storeLastError: string | null = '',
): void {
  const detail =
    (err as ErrorLike | null | undefined)?.msg ||
    (err as ErrorLike | null | undefined)?.message ||
    storeLastError ||
    ''
  ElMessage.error(detail ? `${op}失败: ${detail}` : `${op}失败`)
}
