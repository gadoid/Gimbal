/**
 * api/webhook-deliveries.ts — 回调投递排查面(webhook 设计 v3 P2-6)+
 * 人工补发(收尾评审 2026-11-02 G5)。
 *
 * 列表按 executionId / instanceId / tokenId 之一过滤(webhook v4);可见性在后端
 * (admin 全量;JWT = 目标执行/实例 owner 或 caller 别名属主;不可见 404)。
 * 补发 = 服务端新建一行 pending(新 id,接收端按 X-Gimbal-Delivery 去重,
 * 同 id 重发会被当重复丢弃),原行保留为历史。
 */
import http from '@/api/http'

export type DeliveryStatus = 'pending' | 'delivered' | 'failed'

export interface WebhookDeliveryRow {
  id: number
  tokenId: number | null
  tokenName: string
  eventType: string
  executionId: number | null
  instanceId: number | null
  url: string
  status: DeliveryStatus
  attempts: number
  lastError: string | null
  nextRetryAt: string | null
  deliveredAt: string | null
  createdAt: string
  body: string
}

export function listWebhookDeliveries(params: {
  executionId?: number
  instanceId?: number
  tokenId?: number
  limit?: number
}): Promise<WebhookDeliveryRow[]> {
  return http
    .get<{ items: WebhookDeliveryRow[] }>('/webhook-deliveries', { params })
    .then((r) => r.data.items)
}

/** 补发:返回新建的 pending 行(带 redeliveredFrom = 原行 id)。 */
export function redeliverWebhook(
  id: number,
): Promise<WebhookDeliveryRow & { redeliveredFrom: number }> {
  return http
    .post<WebhookDeliveryRow & { redeliveredFrom: number }>(
      `/webhook-deliveries/${id}/redeliver`)
    .then((r) => r.data)
}
