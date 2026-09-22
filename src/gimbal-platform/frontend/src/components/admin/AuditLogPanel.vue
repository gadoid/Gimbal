<!--
  AuditLogPanel.vue — 特权写审计面板(从 UsersAdmin 审计 tab 抽出,2026-09-22)。
  抽组件顺带修两处:
  * 懒加载判据原来是「rows 为空才拉」— 首次落在空结果(无日志/筛选无
    命中)后切走再切回永不重拉;改为面板挂载即拉(reka TabsContent 非激
    活即卸载,每次进 tab 都是新鲜挂载)+ 显式「刷新」按钮。
  * 时间列原用 toISOString(UTC),+8 时区早上会显示成前一天下午;
    统一走 mediumDateTime(本地时区)。
  对象列 = resourceType + resourceId(原来丢 resourceType,只剩裸 id)。
-->
<template>
  <div class="lib-card p-4">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <span class="text-body font-semibold">特权写审计</span>
      <span class="text-caption text-slate-500">角色变更 / 删号 / 重置密码 / 公告 / carry / 适配 / 别名</span>
      <span class="flex-1"></span>
      <button
        v-for="a in actions"
        :key="a"
        type="button"
        class="audit-chip"
        :class="{ active: action === a }"
        :data-testid="`audit-chip-${a}`"
        @click="setAction(action === a ? '' : a)"
      >{{ a }}</button>
      <button
        type="button"
        class="audit-refresh"
        data-testid="audit-refresh"
        :disabled="loading"
        title="重新拉取审计日志"
        @click="load"
      >{{ loading ? '加载中…' : '↻ 刷新' }}</button>
    </div>

    <Table v-if="rows.length">
      <TableHeader>
        <TableRow>
          <TableHead class="w-[160px]">时间</TableHead>
          <TableHead class="w-[140px]">操作者</TableHead>
          <TableHead class="w-[200px]">动作</TableHead>
          <TableHead class="w-[200px]">对象</TableHead>
          <TableHead>详情</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in rows" :key="row.id" :data-testid="`audit-row-${row.id}`">
          <TableCell class="muted">{{ mediumDateTime(row.createdAt) }}</TableCell>
          <TableCell>{{ row.actorName || (row.actorId ? `#${row.actorId}` : '系统') }}</TableCell>
          <TableCell><span class="audit-chip static">{{ row.action }}</span></TableCell>
          <TableCell class="mono">
            <template v-if="row.resourceType || row.resourceId">{{ row.resourceType ?? '' }}{{ row.resourceType && row.resourceId ? ':' : '' }}{{ row.resourceId ?? '' }}</template>
            <template v-else>—</template>
          </TableCell>
          <TableCell class="mono audit-detail">{{ JSON.stringify(row.detail) }}</TableCell>
        </TableRow>
      </TableBody>
    </Table>
    <p v-else-if="!loading" class="py-6 text-center text-body text-slate-500">暂无审计记录</p>
    <Pagination
      v-if="pageCount > 1"
      v-model:page="page"
      :total="total"
      :page-size="PAGE_SIZE"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listAuditLogs, type AuditLogRow } from '@/api/admin'
import { mediumDateTime } from '@/utils/datetime'
import { Pagination } from '@/components/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const PAGE_SIZE = 20

const rows = ref<AuditLogRow[]>([])
const total = ref(0)
const page = ref(1)
const action = ref('')
const loading = ref(false)
const actions = ref<string[]>([])

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load(): Promise<void> {
  loading.value = true
  try {
    const env = await listAuditLogs({
      action: action.value || undefined,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    rows.value = env.items
    total.value = env.total
    actions.value = env.actions
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function setAction(a: string): void {
  action.value = a
  page.value = 1
  void load()
}

defineExpose({ load })

onMounted(() => { void load() })
</script>

<style scoped>
.audit-chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid var(--color-border-tertiary, #e1e5eb);
  background: transparent;
}
.audit-chip.active {
  color: #2f6fed;
  border-color: #2f6fed;
  background: #e7efff;
}
.audit-chip.static { cursor: default; background: #f1f5f9; }
.audit-refresh {
  padding: 2px 10px;
  border: 1px solid var(--color-border-tertiary, #e1e5eb);
  border-radius: 6px;
  background: #fff;
  font-size: 11.5px;
  color: #5a6273;
  cursor: pointer;
}
.audit-refresh:hover:not(:disabled) { color: #2f6fed; border-color: #2f6fed; }
.audit-refresh:disabled { color: #c4c9d2; cursor: default; }
.audit-detail { font-size: 11px; color: #64748b; word-break: break-all; }
.muted { color: #64748b; }
.mono { font-family: ui-monospace, monospace; font-size: 11.5px; }
</style>
