<!-- ExecutionsList.vue — 列出当前用户的所有 execution. -->
<template>
  <section class="executions-list">
    <header class="page-header">
      <div>
        <h2>执行历史</h2>
        <p>{{ store.list.length }} 条记录 · 实时状态每 1s 刷新（详情页）</p>
      </div>
    </header>

    <el-table
      v-if="store.list.length > 0"
      v-loading="store.loading"
      :data="store.list"
      class="exec-table"
    >
      <el-table-column label="#" prop="id" width="60" />
      <el-table-column label="scenario_id" min-width="180">
        <template #default="{ row }">
          <code class="mono">{{ row.scenario_id }}</code>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <span :class="['status-tag', `status-${row.status}`]">
            {{ executionStatusText(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="通过 / 失败 / 总" width="160">
        <template #default="{ row }">
          <span class="mono">{{ row.passed }} / {{ row.failed }} / {{ row.total_runs }}</span>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">
          <span class="mono dim">{{ row.started_at?.slice(0, 19).replace('T', ' ') || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row.id)">详情</el-button>
          <el-button
            v-if="row.status === 'queued' || row.status === 'running'"
            link
            type="warning"
            @click="cancel(row.id)"
            >取消</el-button
          >
          <el-button link type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-alert
      v-else-if="store.lastError"
      :title="`加载执行历史失败：${store.lastError}`"
      type="error"
      :closable="false"
      show-icon
      class="load-error"
    />
    <el-empty
      v-else-if="!store.loading"
      description="暂无执行记录 — 在场景编排页点击「运行」发起执行"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useExecutionsStore } from '@/stores/executions'
import { cancelExecution } from '@/api/executions'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl } from '@/utils/links'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'

const router = useRouter()
const store = useExecutionsStore()

function open(id: number) {
  router.push(executionUrl(id))
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
    ElMessage.success('已请求取消')
  } catch (e) {
    if ((e as { status?: number }).status === 409) {
      // 终态竞态:刷新让取消按钮消失即可,不算失败。
      ElMessage.info('该执行已结束,无法取消')
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
.executions-list {
  max-width: 1480px;
  padding: 28px 32px 48px;
  margin: 0 auto;
}

.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
}

.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.exec-table {
  width: 100%;
  margin-top: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.load-error {
  margin-top: 14px;
}

.status-tag {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

/* 状态配色统一在 @/styles/status-colors.css（见文件末尾引入） */
</style>

<style src="@/styles/status-colors.css"></style>