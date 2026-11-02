<!--
  InboundActivityPanel.vue — 别名详情页「入站与回调」区块的排查面
  (收尾评审 2026-11-02 G3):经由本别名的最近执行 + 最近回调投递。

  平台模式执行的 owner 是系统用户,不出现在任何人的「我的执行」里;
  别名属主想查「回调为什么没收到」,这里是界面上唯一入口。两张表只读,
  投递行上的「补发」(G5)对 failed / delivered 行开放。可见性与管理面
  同一谓词(admin ∨ 别名属主),父级按 canManage 决定是否渲染。
-->
<template>
  <div class="flex flex-col gap-4" data-testid="inbound-activity">
    <div class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">经由本别名的执行</span>
        <span class="svc-panel-desc">最近 {{ LIMIT }} 条(平台模式 + 经本别名注册的个人模式)</span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" data-testid="activity-reload" @click="reload">刷新</Button>
      </div>
      <table v-if="executions.length" class="w-full text-caption" data-testid="alias-executions">
        <thead>
          <tr class="muted text-left">
            <th class="py-1 pr-2">#</th>
            <th class="py-1 pr-2">场景</th>
            <th class="py-1 pr-2">状态</th>
            <th class="py-1 pr-2">开始</th>
            <th class="py-1 pr-2">结束</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in executions" :key="e.id" class="border-t border-border/60">
            <td class="py-1 pr-2 mono">
              <a href="#" class="underline" :data-testid="`exec-link-${e.id}`"
                 @click.prevent="router.push(`/executions/${e.id}`)">{{ e.id }}</a>
            </td>
            <td class="py-1 pr-2">{{ e.scenario_display_name || e.scenario_id }}</td>
            <td class="py-1 pr-2">
              <span class="svc-flag" :class="statusTone(e.status)">{{ executionStatusText(e.status) }}</span>
            </td>
            <td class="py-1 pr-2">{{ fmt(e.started_at) }}</td>
            <td class="py-1 pr-2">{{ fmt(e.finished_at) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted text-caption">尚无经由本别名的执行</p>
    </div>

    <div class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">回调投递记录</span>
        <span class="svc-panel-desc">
          最近 {{ LIMIT }} 条;达到最大重试次数置「失败」后可补发
          (新建一条投递,原记录保留)
        </span>
      </div>
      <table v-if="deliveries.length" class="w-full text-caption" data-testid="alias-deliveries">
        <thead>
          <tr class="muted text-left">
            <th class="py-1 pr-2">#</th>
            <th class="py-1 pr-2">事件</th>
            <th class="py-1 pr-2">执行</th>
            <th class="py-1 pr-2">状态</th>
            <th class="py-1 pr-2">重试</th>
            <th class="py-1 pr-2">最后错误</th>
            <th class="py-1 pr-2">创建于</th>
            <th class="py-1" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in deliveries" :key="d.id" class="border-t border-border/60">
            <td class="py-1 pr-2 mono">{{ d.id }}</td>
            <td class="py-1 pr-2 mono">{{ d.eventType }}</td>
            <td class="py-1 pr-2 mono">{{ d.executionId ?? '—' }}</td>
            <td class="py-1 pr-2">
              <span class="svc-flag" :class="deliveryTone(d.status)">{{ deliveryStatusText(d.status) }}</span>
            </td>
            <td class="py-1 pr-2">{{ d.attempts }}</td>
            <td class="py-1 pr-2 max-w-xs truncate" :title="d.lastError ?? ''">{{ d.lastError || '—' }}</td>
            <td class="py-1 pr-2">{{ fmt(d.createdAt) }}</td>
            <td class="py-1 text-right">
              <Button v-if="d.status !== 'pending'" variant="outline" size="sm"
                      :disabled="busy === d.id" :data-testid="`redeliver-${d.id}`"
                      @click="redeliver(d.id)">补发</Button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted text-caption">尚无回调投递记录</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listExecutions, type ExecutionListItem } from '@/api/executions'
import {
  listWebhookDeliveries, redeliverWebhook,
  type DeliveryStatus, type WebhookDeliveryRow,
} from '@/api/webhook-deliveries'
import { executionStatusText } from '@/utils/executionStatus'
import { showError } from '@/utils/errorFallback'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/button'

const props = defineProps<{ aliasName: string }>()

const LIMIT = 20
const router = useRouter()
const executions = ref<ExecutionListItem[]>([])
const deliveries = ref<WebhookDeliveryRow[]>([])
const busy = ref<number | null>(null)

const DELIVERY_STATUS_LABELS: Record<DeliveryStatus, string> = {
  pending: '待投递',
  delivered: '已送达',
  failed: '失败',
}

function deliveryStatusText(s: DeliveryStatus): string {
  return DELIVERY_STATUS_LABELS[s] ?? s
}

function deliveryTone(s: DeliveryStatus): string {
  return s === 'delivered' ? 'green' : s === 'failed' ? 'red' : 'amber'
}

function statusTone(s: string): string {
  return s === 'done' ? 'green' : s === 'failed' ? 'red'
    : s === 'canceled' ? '' : 'blue'
}

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

async function reload(): Promise<void> {
  try {
    const [ex, ds] = await Promise.all([
      listExecutions({ callerAlias: props.aliasName, limit: LIMIT }),
      listWebhookDeliveries({ aliasName: props.aliasName, limit: LIMIT }),
    ])
    executions.value = ex.items
    deliveries.value = ds
  } catch (e) {
    showError('加载入站执行与投递', e)
  }
}

onMounted(reload)

async function redeliver(id: number): Promise<void> {
  busy.value = id
  try {
    const out = await redeliverWebhook(id)
    toast.success(`已补发为投递 #${out.id}`)
    await reload()
  } catch (e) {
    showError('补发回调', e)
  } finally {
    busy.value = null
  }
}
</script>
