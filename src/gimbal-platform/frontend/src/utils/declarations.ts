/**
 * declarations.ts —— plate /full 统一声明清单的前端投影工具。
 *
 * plate 侧 declarations 为唯一承重存储(旧 fields/carry/assertable_fields
 * 线上键已清除);IOFieldBinding 仍是字段元信息的 UI 形状(FieldForm/
 * Catalog 字段表),本文件把声明条目按通道投影回该形状 —— 前端唯一的
 * 投影入口,各消费点(Canvas/Catalog/useFieldDescriptions)不再自行展开。
 */
import type { DeclarationEntryView, IOFieldBinding } from '@/types/plate'

/**
 * D12 祖先判定(字符串前缀,归一化形态下可靠):
 * `$.a` 是 `$.a.b` / `$.a[0].c` 的祖先;`$.ab` 不是 `$.a` 的后代
 * (前缀后必须紧跟 `.` 或 `[`,不吃假前缀)。
 */
function isAncestor(anc: string, desc: string): boolean {
  if (anc === desc || !desc.startsWith(anc)) return false
  const next = desc[anc.length]
  return next === '.' || next === '['
}

/**
 * D12:最长已声明祖先(无 → null);parentChannel 随源条目。
 * 扫描跨通道 — carry 容器是 binding 深字段的合法上级(值表打底语义)。
 * O(n²),声明清单量级无忧。
 */
function deriveParent(
  e: DeclarationEntryView,
  all: DeclarationEntryView[],
): { parentPath: string | null; parentChannel: DeclarationEntryView['channel'] | null } {
  let best: DeclarationEntryView | null = null
  for (const o of all) {
    if (o.path !== e.path && isAncestor(o.path, e.path) &&
        (best === null || o.path.length > best.path.length)) best = o
  }
  return best
    ? { parentPath: best.path, parentChannel: best.channel }
    : { parentPath: null, parentChannel: null }
}

/** 声明条目 → IOFieldBinding 形状(掐掉 channel/type/assertable 三个声明轴,派生 parent 投影) */
function toFieldBinding(e: DeclarationEntryView, all: DeclarationEntryView[]): IOFieldBinding {
  const { parentPath, parentChannel } = deriveParent(e, all)
  return {
    name: e.name,
    path: e.path,
    required: e.required,
    default: e.default ?? null,
    example: e.example ?? null,
    description: e.description,
    enum: e.enum ?? null,
    ui_kind: e.ui_kind,
    source_kind: e.source_kind,
    parentPath,
    parentChannel,
  }
}

/** 表单/展示字段面:binding(请求)或 view_only(响应)通道条目按序投影(parent 派生吃全量清单) */
export function channelFields(
  decls: DeclarationEntryView[] | undefined | null,
  channel: 'binding' | 'view_only',
): IOFieldBinding[] {
  const all = decls ?? []
  return all.filter((e) => e.channel === channel).map((e) => toFieldBinding(e, all))
}

/** 传递字段面:carry 通道条目的 path 集(carry 徽章 / Type C 过滤用) */
export function carryPaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'carry').map((e) => e.path)
}

/** 断言候选面:view_only 且 assertable=True 的 paths(响应契约 ✓ 标 / 策略候选) */
export function assertablePaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'view_only' && e.assertable).map((e) => e.path)
}
