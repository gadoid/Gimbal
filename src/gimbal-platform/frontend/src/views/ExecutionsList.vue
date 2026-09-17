<!-- ExecutionsList.vue — 列出当前用户的所有 execution。批次 4 迁移新栈:
     shadcn Table/Button/Alert;状态色统一 Signal(status-colors.css)。
     原型修订项(v2.2):失败数字红色可点 → 直达详情并自动展开行级表格
     (失败用例清单即行级表);时间列已含日期(YYYY-MM-DD HH:MM:SS)。 -->
<template>
  <section class="executions-list mx-auto max-w-[1480px] px-8 pb-12 pt-7">
    <header class="page-header">
      <div>
        <h2 class="m-0 text-display text-signal-ink">执行历史</h2>
        <p class="mt-1 mb-0 text-caption text-muted-foreground">{{ store.list.length }} 条记录 · 实时状态每 1s 刷新（详情页）</p>
      </div>
    </header>

    <div v-if="store.loading" class="mt-3.5 py-8 text-center text-body text-muted-foreground">加载中…</div>
    <Table v-else-if="store.list.length > 0" class="exec-table mt-3.5 rounded-field border border-signal-line bg-signal-card">
      <TableHeader>
        <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
          <TableHead class="w-[54px] text-caption font-semibold text-muted-foreground">#</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">scenario_id</TableHead>
          <TableHead class="w-[110px] text-caption font-semibold text-muted-foreground">状态</TableHead>
          <TableHead class="w-[150px] text-caption font-semibold text-muted-foreground">通过 / 失败 / 总</TableHead>
          <TableHead class="w-[160px] text-caption font-semibold text-muted-foreground">开始时间</TableHead>
          <TableHead class="w-[150px] text-center text-caption font-semibold text-muted-foreground">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in store.list" :key="row.id" :data-testid="`exec-list-row-${row.id}`">
          <TableCell class="mono">{{ row.id }}</TableCell>
          <TableCell><code class="mono">{{ row.scenario_id }}</code></TableCell>
          <TableCell>
            <span :class="['status-tag', `status-${row.status}`]">
              {{ executionStatusText(row.status) }}
            </span>
          </TableCell>
          <TableCell>
            <span class="mono">
              {{ row.passed }} /
              <!-- 原型修订:失败数字红色可点 → 详情自动展开行级表(失败用例清单) -->
              <button
                v-if="row.failed > 0"
                type="button"
                class="fail-link"
                :data-testid="`exec-failed-${row.id}`"
                title="查看失败用例"
                @click="open(row.id, true)"
              >{{ row.failed }}</button>
              <template v-else>{{ row.failed }}</template>
              / {{ row.total_runs }}
            </span>
          </TableCell>
          <TableCell>
            <span class="mono dim">{{ row.started_at?.slice(0, 19).replace('T', ' ') || '—' }}</span>
          </TableCell>
          <TableCell class="text-center">
            <div class="flex items-center justify-center gap-0.5">
              <Button variant="link" size="sm" class="h-7 px-2" @click="open(row.id)">详情</Button>
              <Button
                v-if="row.status === 'queued' || row.status === 'running'"
                variant="link"
                size="sm"
                class="h-7 px-2 text-amber-700"
                @click="cancel(row.id)"
              >取消</Button>
              <Button variant="link" size="sm" class="h-7 px-2 text-signal-failed" @click="remove(row.id)">删除</Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <Alert v-else-if="store.lastError" variant="destructive" class="mt-3.5">
      <AlertTitle>加载执行历史失败：{{ store.lastError }}</AlertTitle>
    </Alert>
    <div v-else class="empty-note">
      <p>暂无执行记录 — 在场景编排页点击「运行」发起执行</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { useExecutionsStore } from '@/stores/executions'
import { cancelExecution } from '@/api/executions'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl } from '@/utils/links'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertTitle } from '@/components/ui/alert'

const router = useRouter()
const store = useExecutionsStore()

/** focusFailed:失败数字入口 → 详情页带 ?rows=failed 自动展开行级表。 */
function open(id: number, focusFailed = false) {
  router.push(focusFailed ? `${executionUrl(id)}?rows=failed` : executionUrl(id))
}

async function remove(id: number) {
  await removeExecution(id, (i) => store.remove(i))
}

/** P4 协作式取消:queued/running 行可见(running 由在飞 fanout 行边界
 * 消费;无在飞 task 的都是重启僵尸,后端 inline 终态化)。
 * 409 = 点击时单子已终态(竞态)。 */
async function cancel(id: number) {
  try {
    await cancelExecution(id)
    toast.success('已请求取消')
  } catch (e) {
    if ((e as { status?: number }).status === 409) {
      // 终态竞态:刷新让取消按钮消失即可,不算失败。
      toast.info('该执行已结束,无法取消')
    } else {
      showError('取消', e)
      return
    }
  }
  await store.fetchList().catch(() => undefined)
}

let handle: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await store.fetchList().catch(() => undefined)
  // Refresh list every 3s while on the page (cheap; list is small).
  // fetchList rethrows — swallow here so a down backend / expired
  // session doesn't emit an unhandled rejection every tick.
  handle = setInterval(() => store.fetchList().catch(() => undefined), 3000)
})

onUnmounted(() => {
  if (handle !== null) clearInterval(handle)
})
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

/* 失败数字:红 + 可点(原型修订 v2.2) */
.fail-link {
  padding: 0;
  border: none;
  background: none;
  color: #dc2626;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.empty-note {
  margin-top: 14px;
  padding: 40px 16px;
  text-align: center;
  font-size: 12.5px;
  color: #94a3b8;
  border: 1px dashed #e1e5eb;
  border-radius: 8px;
}

.empty-note p { margin: 0; }

.mono { font-family: var(--font-mono); }
.dim { color: var(--color-text-tertiary); }
</style>

<style src="@/styles/status-colors.css"></style>
