/**
 * carry-drift.ts — 适配中心 carry 漂移面板数据组装的纯核心(T16,spec §7)。
 *
 * 输入:后端 GET /api/carry/drift 的 ServiceDrift(值表绑定 vs plate 面
 * 三类 diff);输出:漂移勾选项(checkbox 值 = 请求形状的 JSON 串)与
 * 勾选回读(生成批时按服务分组、保序)。
 *
 * 契约钉死(T11 评审):
 * - plateReachable=False → 面板禁用勾选与批生成(plate 不可达时 drift 会把
 *   全表绑定误报 orphaned,防管理员误清空)—— canGenerateCarryBatch 单点;
 * - 对齐服务(三列表全空)同样入报告 → hasCarryDrift=False 渲染正向确认,
 *   不是空壳。
 *
 * op 语义对齐后端 _apply_carry_op:service 缺省 = 全局默认表;drift 面板
 * 只产服务绑定层 op(payload.service 恒有值)。
 *
 * 纯函数:单测不挂 Vue(模式同 carry-hint.ts / carry-entries.ts)。
 */
import type { ServiceDrift } from '@/api/carry'

/** 勾选项解析形状:checkbox 值(JSON 串) ↔ 生成批时的请求件。 */
export interface CarryCheckItem {
  service: string
  opType: string
  payload: Record<string, unknown>
}

/** 单条漂移勾选:key 为 checkbox 值(JSON 串,键序固定),text 为显示文案。 */
export interface DriftCheckOption {
  key: string
  item: CarryCheckItem
  text: string
}

/** 单服务是否存有漂移(三列表全空 = 对齐服务 → 面板正向确认)。 */
export function hasCarryDrift(s: ServiceDrift): boolean {
  return s.orphaned.length > 0
    || s.uncovered.length > 0
    || s.renamedSuggestions.length > 0
}

/** checkbox 值:JSON 串(键序 service→opType→payload 固定,作唯一 key)。 */
export function carryCheckKey(item: CarryCheckItem): string {
  return JSON.stringify({
    service: item.service,
    opType: item.opType,
    payload: item.payload,
  })
}

/**
 * ServiceDrift → 勾选项清单(三类固定序:孤儿移除 → 未绑定补绑 → 改名)。
 * uncovered 补绑初值 ''(空串是合法值,行建起来后可在配置页细化)。
 */
export function driftCheckOptions(s: ServiceDrift): DriftCheckOption[] {
  const out: DriftCheckOption[] = []
  const push = (item: CarryCheckItem, text: string): void => {
    out.push({ key: carryCheckKey(item), item, text })
  }
  for (const path of s.orphaned) {
    push({
      service: s.service, opType: 'removeCarryBinding',
      payload: { service: s.service, path },
    }, `孤儿绑定 ${path} → 移除`)
  }
  for (const path of s.uncovered) {
    push({
      service: s.service, opType: 'addCarryBinding',
      payload: { service: s.service, path, value: '' },
    }, `未绑定面字段 ${path} → 补绑定`)
  }
  for (const r of s.renamedSuggestions) {
    push({
      service: s.service, opType: 'renameCarryPath',
      payload: { service: s.service, from: r.from, to: r.to },
    }, `改名建议 ${r.from} → ${r.to}`)
  }
  return out
}

/** 勾选值回读(生成批入口);坏串防御性剔除而非整页失败。 */
export function parseCarryChecked(raws: readonly string[]): CarryCheckItem[] {
  const out: CarryCheckItem[] = []
  for (const raw of raws) {
    try {
      const v = JSON.parse(raw) as Partial<CarryCheckItem>
      if (typeof v.service === 'string'
        && typeof v.opType === 'string' && v.payload) {
        out.push({
          service: v.service,
          opType: v.opType,
          payload: v.payload as Record<string, unknown>,
        })
      }
    } catch { /* 坏串跳过 */ }
  }
  return out
}

/** 勾选项 → 去重服务清单(首见保序:批生成顺序可预期)。 */
export function checkedServices(items: readonly CarryCheckItem[]): string[] {
  return [...new Set(items.map((i) => i.service))]
}

/** 批生成入口放开条件:plate 可达(漂移可信)且已有勾选 —— T11 硬性契约。 */
export function canGenerateCarryBatch(
  plateReachable: boolean, checkedCount: number,
): boolean {
  return plateReachable && checkedCount > 0
}
