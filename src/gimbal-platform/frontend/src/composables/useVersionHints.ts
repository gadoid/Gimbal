/**
 * RS3（Release v4.4 §2.3）：场景版本提示计算。
 *
 * 从 meta.plate 声明 + plate 版本线数据 → 提示列表。
 * 纯函数：数据由调用方传入（场景列表 / 详情 / 编排页均可复用）。
 */
import type { VersionHint } from '@/components/scenario-lib/VersionHints.vue'
import type { PlateLineInfo } from '@/api/plate'

export interface PlateMetaInfo {
  /** meta.plate：{系统: "<line>#<n>" | "working"} */
  plate: Record<string, string>
  /** 各系统当前版本线列表（调 fetchSystemLines 预取） */
  systemLines: Record<string, PlateLineInfo[]>
}

export function computeVersionHints(info: PlateMetaInfo): VersionHint[] {
  const hints: VersionHint[] = []
  const { plate, systemLines } = info

  for (const [system, ref] of Object.entries(plate)) {
    const lines = systemLines[system] || []

    // 1. 仍为预览（working）
    if (ref === 'working' || !ref) {
      if (lines.length > 0) {
        hints.push({
          key: `preview:${system}`,
          level: 'warn',
          text: `${system}: 仍为预览（working）——已有版本线可用，不计入入库标准`,
          action: 'adapt',
        })
      }
      continue
    }

    // 解析 "<line>#<n>"
    const hashIdx = ref.lastIndexOf('#')
    if (hashIdx < 0) continue
    const declaredLine = ref.substring(0, hashIdx)

    // 2. 有新版本线（declaredLine 之后存在新的线）
    const declaredIdx = lines.findIndex(l => l.line === declaredLine)
    if (declaredIdx >= 0 && declaredIdx < lines.length - 1) {
      const latest = lines[lines.length - 1]
      hints.push({
        key: `new-line:${system}`,
        level: 'info',
        text: `${system}: 有新版本线 ${latest.line}（当前 ${declaredLine}）`,
        action: 'adapt',
      })
    }

    // 3. 定义已修正（declared revision 不在该线的最新修订上——
    //    真正的判定需要调 plate resolve；此处用简化口径：最新修订号 > 声明号）
    const declaredRev = parseInt(ref.substring(hashIdx + 1), 10)
    const lineInfo = lines.find(l => l.line === declaredLine)
    if (lineInfo) {
      const latestRev = parseInt(
        lineInfo.latest.substring(lineInfo.latest.lastIndexOf('#') + 1), 10)
      if (latestRev > declaredRev) {
        hints.push({
          key: `corrected:${system}`,
          level: 'warn',
          text: `${system}: 定义已修正（${declaredLine}#${declaredRev} → #${latestRev}）`,
          action: 'adapt',
        })
      }
    }
  }

  return hints
}
