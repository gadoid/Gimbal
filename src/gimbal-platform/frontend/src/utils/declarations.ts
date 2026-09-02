/**
 * declarations.ts —— plate /full 统一声明清单的前端投影工具。
 *
 * plate 侧 declarations 为唯一承重存储(旧 fields/carry/assertable_fields
 * 线上键已清除);IOFieldBinding 仍是字段元信息的 UI 形状(FieldForm/
 * Catalog 字段表),本文件把声明条目按通道投影回该形状 —— 前端唯一的
 * 投影入口,各消费点(Canvas/Catalog/useFieldDescriptions)不再自行展开。
 */
import type { DeclarationEntryView, IOFieldBinding } from '@/types/plate'

/** 声明条目 → IOFieldBinding 形状(掐掉 channel/type/assertable 三个声明轴) */
function toFieldBinding(e: DeclarationEntryView): IOFieldBinding {
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
  }
}

/** 表单/展示字段面:binding(请求)或 view_only(响应)通道条目按序投影 */
export function channelFields(
  decls: DeclarationEntryView[] | undefined | null,
  channel: 'binding' | 'view_only',
): IOFieldBinding[] {
  return (decls ?? []).filter((e) => e.channel === channel).map(toFieldBinding)
}

/** 传递字段面:carry 通道条目的 path 集(carry 徽章 / Type C 过滤用) */
export function carryPaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'carry').map((e) => e.path)
}

/** 断言候选面:view_only 且 assertable=True 的 paths(响应契约 ✓ 标 / 策略候选) */
export function assertablePaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'view_only' && e.assertable).map((e) => e.path)
}
