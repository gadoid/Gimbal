/**
 * dataset-palette.ts — 列描述类型(纯类型,零 IO)
 *
 * 历史上的列派生器(deriveBaselineColumns / fieldsOf / varNameOf /
 * renderTemplate)已随 DataSetEditor 基线区退场删除(2026-09-11):
 * 列宇宙 = config.vars,由 dataset-segments 的引用扫描派生。本文件
 * 只剩 BaselineColumn — 网格(dataset-grid)与 CSV 链(csv-dataset)
 * 共用的最小列形状。
 */

/** 网格 / CSV 链的最小列描述 */
export interface BaselineColumn {
  stepIndex: number
  source: 'body' | 'headers'
  field: string
  /** var = 步骤值含 ${var.NAME}(可被数据集行覆盖);direct = 直填(CSV 链兜底过滤用) */
  kind: 'var' | 'direct'
  varName: string | null
  /** 基线展示值:var 列 = config.vars 基线;direct 列 = 字面值 */
  baseline: string
}
