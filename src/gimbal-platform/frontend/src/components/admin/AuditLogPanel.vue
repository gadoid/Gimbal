<!--
  AuditLogPanel.vue — 特权写审计面板(从 UsersAdmin 审计 tab 抽出,2026-09-22)。
  抽组件顺带修两处:
  * 懒加载判据原来是「rows 为空才拉」— 首次落在空结果(无日志/筛选无
    命中)后切走再切回永不重拉;改为面板挂载即拉(reka TabsContent 非激
    活即卸载,每次进 tab 都是新鲜挂载)+ 显式「刷新」按钮。
  * 时间列原用 toISOString(UTC),+8 时区早上会显示成前一天下午;
    统一走 mediumDateTime(本地时区)。
  对象列 = resourceType + resourceId(原来丢 resourceType,只剩裸 id)。
  2026-10-14 可读性收口:动作/对象/详情三列人话化 —— 动作走
  auditText 中文标签表;对象优先 resource_name 快照(无名称老记录回落
  type:id);详情按动作渲染中文模板,原始 JSON 收进 <details> 展开区。
  2026-10-20 分页修复批次:
  * 分页失灵根因:page 只是 Pagination 的 v-model,没有任何 watcher →
    点页码只改本地状态不重拉。补 watch(page) → load,并加越界页回退
    (行数变更/记录被清后停在空页 → 回末页重取,与 NotificationsCenter
    同口径)。
  * 动作筛选从逐动作 chip 行(20+ 个动作后已横向挤爆)改为单个下拉,
    按域 optgroup 分组(auditActionGroups),词表再长也只占一行。
  * 每页行数接入 usePagerSize('audit-logs') → 服务端偏好键 pager.sizes
    (与其他列表页同一套:镜像管首帧、PUT 防抖落库)。
-->
<template>
  <div class="lib-card p-4">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <span class="text-body font-semibold">特权写审计</span>
      <span class="text-caption text-slate-500">特权写操作全量流水(用户 / 公告 / carry / 适配 / 场景 / 套件 / 分享 / 集成凭证…)</span>
      <span class="flex-1"></span>
      <select
        class="audit-filter"
        data-testid="audit-action-filter"
        :disabled="loading"
        title="按动作筛选审计记录"
        :value="action"
        @change="setAction(($event.target as HTMLSelectElement).value)"
      >
        <option value="">全部动作</option>
        <optgroup
          v-for="g in actionGroups"
          :key="g.domain"
          :label="g.label"
          :data-testid="`audit-group-${g.domain}`"
        >
          <option v-for="a in g.items" :key="a" :value="a">{{ auditActionLabel(a) }}</option>
        </optgroup>
      </select>
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
          <TableHead class="w-[130px]">动作</TableHead>
          <TableHead class="w-[200px]">对象</TableHead>
          <TableHead>详情</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in rows" :key="row.id" :data-testid="`audit-row-${row.id}`">
          <TableCell class="muted">{{ mediumDateTime(row.createdAt) }}</TableCell>
          <TableCell>{{ row.actorName || (row.actorId ? `#${row.actorId}` : '系统') }}</TableCell>
          <TableCell><span class="audit-chip" :title="row.action">{{ auditActionLabel(row.action) }}</span></TableCell>
          <TableCell>
            <template v-if="row.resourceType || row.resourceId">
              <span :class="{ mono: !auditResourceName(row) }">{{ auditResourceText(row) }}</span>
            </template>
            <template v-else>—</template>
          </TableCell>
          <TableCell>
            <div class="audit-detail-text">{{ describeAuditDetail(row) }}</div>
            <details v-if="Object.keys(row.detail ?? {}).length" class="audit-raw" :data-testid="`audit-raw-${row.id}`">
              <summary>原始数据</summary>
              <pre>{{ JSON.stringify(row.detail, null, 2) }}</pre>
            </details>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
    <p v-else-if="!loading" class="py-6 text-center text-body text-slate-500">暂无审计记录</p>
    <Pagination
      v-if="pageCount > 1 || total > 0"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      :disabled="loading"
      show-page-size
      show-jump
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { listAuditLogs, type AuditLogRow } from '@/api/admin'
import { usePagerSize } from '@/composables/usePagerSize'
import { mediumDateTime } from '@/utils/datetime'
import {
  auditActionGroups, auditActionLabel, auditResourceName, auditResourceText, describeAuditDetail,
} from './auditText'
import { Pagination } from '@/components/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const { pageSize } = usePagerSize('audit-logs', 20)

const rows = ref<AuditLogRow[]>([])
const total = ref(0)
const page = ref(1)
const action = ref('')
const loading = ref(false)
const actions = ref<string[]>([])

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const actionGroups = computed(() => auditActionGroups(actions.value))

async function load(): Promise<void> {
  loading.value = true
  try {
    const env = await listAuditLogs({
      action: action.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = env.items
    total.value = env.total
    actions.value = env.actions
    // 越界页回退:记录被清/行数变大后停在空页 → 回末页(page watcher 重拉)
    const back = Math.max(1, Math.ceil(env.total / pageSize.value))
    if (env.items.length === 0 && page.value > back) page.value = back
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function setAction(a: string): void {
  action.value = a
  // page 已是 1 → 显式拉;否则先归 1,交给 page watcher 拉(避免双拉)
  if (page.value === 1) void load()
  else page.value = 1
}

watch(page, () => { void load() })
watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
  else void load()
})

defineExpose({ load })

onMounted(() => { void load() })
</script>

<style scoped>
.audit-chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid var(--color-border-tertiary, #e1e5eb);
  background: #f1f5f9;
}
.audit-filter {
  height: 26px;
  max-width: 220px;
  padding: 0 6px;
  border: 1px solid var(--color-border-tertiary, #e1e5eb);
  border-radius: 6px;
  background: #fff;
  font-size: 11.5px;
  color: #5a6273;
  cursor: pointer;
}
.audit-filter:hover:not(:disabled) { color: #2f6fed; border-color: #2f6fed; }
.audit-filter:disabled { color: #c4c9d2; cursor: default; }
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
.audit-detail-text { font-size: 12px; color: #334155; }
.audit-raw { margin-top: 4px; }
.audit-raw summary {
  cursor: pointer;
  font-size: 11px;
  color: #94a3b8;
  user-select: none;
}
.audit-raw summary:hover { color: #2f6fed; }
.audit-raw pre {
  margin: 4px 0 0;
  padding: 6px 8px;
  background: #f8fafc;
  border-radius: 6px;
  font-family: ui-monospace, monospace;
  font-size: 10.5px;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-all;
}
.muted { color: #64748b; }
.mono { font-family: ui-monospace, monospace; font-size: 11.5px; }
</style>
