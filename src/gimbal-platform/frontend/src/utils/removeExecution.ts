/**
 * removeExecution.ts — 删除 execution 的统一确认 → 删除 → 提示流程。
 *
 * Executions.vue(详情页)与 ExecutionsList.vue(列表页)曾各自维护一份
 * 拷贝(文案/按钮/错误提示已漂移过一次),收敛到此处。
 *
 * Returns true when the row was actually deleted (caller may navigate).
 */
import { ElMessage } from 'element-plus'
import { confirmAction } from './confirmAction'
import { showError } from './errorFallback'

export async function removeExecution(
  id: number,
  remove: (id: number) => Promise<unknown>,
): Promise<boolean> {
  const ok = await confirmAction(
    `确认删除 execution #${id}？删除后不可撤销。`,
    '删除 execution',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  if (!ok) return false
  try {
    await remove(id)
  } catch (e) {
    showError('删除', e)
    return false
  }
  ElMessage.success('已删除')
  return true
}
