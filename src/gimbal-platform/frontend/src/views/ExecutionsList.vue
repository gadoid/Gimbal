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
      <el-table-column label="case_id" min-width="180">
        <template #default="{ row }">
          <code class="mono">{{ row.case_id }}</code>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <span :class="['status-tag', `status-${row.status}`]">
            {{ statusText(row.status) }}
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
      <el-table-column label="操作" width="120" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row.id)">详情</el-button>
          <el-button link type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else-if="!store.loading"
      description="暂无执行记录 — 从用例页点击 ⋯ → 执行"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useExecutionsStore } from '@/stores/executions'

const router = useRouter()
const store = useExecutionsStore()

function statusText(s: string): string {
  return ({ queued: '排队', running: '运行中', done: '完成', failed: '失败' } as Record<string, string>)[s] ?? s
}

function open(id: number) {
  router.push(`/executions/${id}`)
}

async function remove(id: number) {
  await store.remove(id)
  ElMessage.success('已删除')
}

let handle: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await store.fetchList()
  // Refresh list every 3s while on the page (cheap; list is small)
  handle = setInterval(() => store.fetchList(), 3000)
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

.mono {
  font-family: var(--font-mono);
}

.dim {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.status-tag {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

.status-queued {
  color: #4338ca;
  background: #eef2ff;
}

.status-running {
  color: #854d0e;
  background: #fef9c3;
}

.status-done {
  color: #166534;
  background: #dcfce7;
}

.status-failed {
  color: #991b1b;
  background: #fee2e2;
}
</style>