/**
 * api/runs.ts —— 运行读面 client(S7.3 起:生效预览)。
 *
 * 契约对齐后端 app/routers/runs.py POST /runs/preview(S5 落地):
 * 本次执行将生效的 地址/槽位绑定/carry 逐值带来源,不含明文凭证;
 * 读闸同预检(不可读场景 404,不泄露存在性)。环境链与执行同源:
 * 显式 > 方案 > 项目默认 > 个人偏好 > 默认环境。
 */
import http from './http'

export interface PreviewRequest {
  scenarioId: string
  schemeId?: string
  environmentId?: number
  /** 服务键 → {alias}(S6 后唯一形态;url/authAlias 后端 422) */
  serviceBindings?: Record<string, { alias: string }>
}

/** 来源标签 → 中文(S7.3 生效预览展示;口径 = run_prepare.resolve_effective_config) */
export const PREVIEW_SOURCE_LABELS: Record<string, string> = {
  authored: '场景声明',
  deployment: '部署地址',
  explicit: '本次指定',
  scheme: '方案',
  project: '项目默认',
  preference: '我的偏好',
  default: '默认环境',
}

/** carry 来源形如 "{scope}:{scopeId}:base|alias"(scope = project/user;
 * scopeId 为公共项目 id 时即「全局层」)。拆层名供展示。 */
export function carrySourceLabel(source: string): string {
  const m = /^(project|user):(\d+):(base|alias)$/.exec(source)
  if (!m) return source
  const scope = m[1] === 'project' ? '项目层' : '个人层'
  return m[3] === 'alias' ? `${scope}·别名` : scope
}

export interface PreviewEnv {
  environmentId: number | null
  environmentSource: string | null
}

export interface PreviewService {
  url: string
  source: string
  alias?: string
}

export interface PreviewAuth {
  bindingId: number
  system: string
  envId: number | null
  isDefault: boolean
}

export interface PreviewCarryValue {
  value: unknown
  source: string
}

export interface EffectiveConfigPreview {
  env: PreviewEnv | null
  services: Record<string, PreviewService>
  auths: Record<string, PreviewAuth>
  missingAuths: string[]
  carry: Record<string, Record<string, PreviewCarryValue>>
  carryDefaults: Record<string, PreviewCarryValue>
}

export function previewEffectiveConfig(
  body: PreviewRequest,
): Promise<EffectiveConfigPreview> {
  return http.post<EffectiveConfigPreview>('/runs/preview', body)
    .then((r) => r.data)
}
