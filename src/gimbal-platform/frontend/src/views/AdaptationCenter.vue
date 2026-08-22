<!-- AdaptationCenter —— P5 适配中心总览(spec §3/§5)。
     admin:未索引警示 + 待适配卡片(C12 异常卡不可开批次)+ 全量批次表;
     member:自动只读 owner 视图(仅批次表,scope=mine,无详情列 ——
     批次工作台为 admin-only,member 直入得 403)。 -->
<template>
  <section class="adaptation-center">
    <header class="page-header">
      <div>
        <h2>适配中心</h2>
        <p>{{ auth.isAdmin ? '目录变更检测与批次适配' : '仅显示触碰你场景的批次(只读)' }}</p>
      </div>
      <el-button
        v-if="auth.isAdmin"
        :loading="adaptations.refreshing"
        @click="refreshAll"
      >检查更新</el-button>
    </header>

    <template v-if="auth.isAdmin">
      <UnindexedAlert :steps="unindexed" />

      <h3>待适配</h3>
      <el-alert
        v-if="adaptations.lastError"
        type="error"
        :title="adaptations.lastError"
        :closable="false"
      />
      <el-empty
        v-else-if="pendingCards.length === 0 && anomalies.length === 0"
        description="目录无待适配变更"
      />
      <div v-else class="cards">
        <div
          v-for="a in anomalies"
          :key="a.endpointId"
          class="card anomaly"
        >
          <b class="mono">{{ a.endpointId }}</b>
          <el-tag type="warning" size="small">异常</el-tag>
          <p class="detail">{{ a.detail }}</p>
          <p class="hint">版本未动不会自动适配 —— 请在 plate 侧确认是否忘 bump</p>
        </div>
        <div
          v-for="p in pendingCards"
          :key="p.endpointId"
          class="card pending"
          data-testid="pending-card"
          @click="openDrawer(p)"
        >
          <b class="mono">{{ p.endpointId }}</b>
          <span class="ver">{{ p.fromVersion }} → {{ p.toVersion }}</span>
          <p class="hint">点击查看影响清单</p>
        </div>
      </div>

      <ImpactDrawer
        v-model="drawerOpen"
        :endpoint-id="drawerEndpointId"
        :from-version="drawerFrom"
        :to-version="drawerTo"
        @open-batch="onOpenBatch"
      />
    </template>

    <h3>批次</h3>
    <p v-if="!auth.isAdmin" class="hint mine-hint">仅显示触碰你场景的批次</p>
    <el-table v-loading="batchesLoading" :data="batchRows">
      <el-table-column prop="batchId" label="批次" min-width="140" />
      <el-table-column prop="endpointId" label="Endpoint" min-width="180" />
      <el-table-column label="版本" min-width="130">
        <template #default="{ row }">
          {{ row.fromVersion }} → {{ row.toVersion }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="ops" min-width="200">
        <template #default="{ row }">
          <el-tag
            v-for="(n, s) in row.opCounts"
            :key="s"
            size="small"
            :type="opTagType(String(s))"
            class="op-tag"
          >{{ s }} {{ n }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" min-width="170" />
      <!-- 详情入口仅 admin:GET /batches/{id} 为 admin-only,
           member 点击只会得 403(死链),故整列不渲染。 -->
      <el-table-column v-if="auth.isAdmin" label="操作" width="80">
        <template #default="{ row }">
          <router-link
            :to="`/adaptations/batches/${row.batchId}`"
            class="link"
          >详情</router-link>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '@/api/adaptations'
import type { BatchOut, PendingChange, UnindexedStep } from '@/api/adaptations'
import { useAuthStore } from '@/stores/auth'
import { useAdaptationsStore } from '@/stores/adaptations'
import UnindexedAlert from '@/components/adaptations/UnindexedAlert.vue'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'

const auth = useAuthStore()
const adaptations = useAdaptationsStore()
const router = useRouter()

const unindexed = ref<UnindexedStep[]>([])
const batchRows = ref<BatchOut[]>([])
const batchesLoading = ref(false)

const drawerOpen = ref(false)
const drawerEndpointId = ref('')
const drawerFrom = ref('')
const drawerTo = ref('')

const pendingCards = computed<PendingChange[]>(
  () => adaptations.diffReport?.pending ?? [])
const anomalies = computed(() => adaptations.diffReport?.anomalies ?? [])

function opTagType(status: string): 'success' | 'info' | 'danger' | 'warning' {
  if (status === 'applied') return 'success'
  if (status === 'conflict') return 'danger'
  if (status === 'skipped') return 'info'
  return 'warning' // pending
}

async function loadBatches(scope?: 'mine'): Promise<void> {
  batchesLoading.value = true
  try {
    batchRows.value = await api.listBatches(scope)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '批次列表加载失败'))
    batchRows.value = []
  } finally {
    batchesLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await adaptations.refreshDiff(true)   // D3:打开/手动检查 → 强制刷新
  try {
    unindexed.value = await api.unindexedSteps()
  } catch {
    unindexed.value = []
  }
  await loadBatches()
}

function openDrawer(p: PendingChange): void {
  drawerEndpointId.value = p.endpointId
  drawerFrom.value = p.fromVersion
  drawerTo.value = p.toVersion
  drawerOpen.value = true
}

async function onOpenBatch(): Promise<void> {
  try {
    const detail = await api.openBatch(drawerEndpointId.value)
    drawerOpen.value = false
    await router.push(`/adaptations/batches/${detail.batchId}`)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '开批次失败(no_pending_change 等),请刷新后重试'))
  }
}

onMounted(() => {
  if (auth.isAdmin) void refreshAll()
  else void loadBatches('mine')
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header p { margin: 4px 0 0; color: #909399; font-size: 13px; }
h3 { margin: 22px 0 10px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; }
.card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px 16px;
  min-width: 260px;
}
.card.pending { cursor: pointer; border-color: #409eff; }
.card.anomaly { border-color: #e6a23c; background: #fdf6ec; }
.card .ver { margin-left: 8px; color: #909399; }
.card .detail { margin: 8px 0 0; font-size: 13px; }
.hint { margin: 4px 0 0; color: #909399; font-size: 12px; }
.mine-hint { color: #909399; font-size: 13px; }
.op-tag { margin-right: 4px; }
.link { color: #409eff; }
.mono { font-family: monospace; }
</style>
