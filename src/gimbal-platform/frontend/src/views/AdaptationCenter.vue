<!-- AdaptationCenter —— P5 适配中心总览(spec §3/§5 + §7 carry 职能)。
     admin:未索引警示 + 待适配卡片(C12 异常卡不可开批次)+ 全量批次表
       + carry 漂移面板(T16:三类勾选 → 生成值表批,plateReachable 先判);
     member:自动只读 owner 视图(仅批次表,scope=mine,无详情列 ——
     批次工作台为 admin-only,member 直入得 403)。 -->
<template>
  <section class="adaptation-center">
    <header class="page-header">
      <div class="header-text">
        <h2>适配中心</h2>
        <p>{{ auth.isAdmin ? '目录变更检测与批次适配' : '仅显示触碰你场景的批次(只读)' }}</p>
      </div>
      <el-button
        v-if="auth.isAdmin"
        type="primary"
        :loading="adaptations.refreshing"
        @click="refreshAll"
      >检查更新</el-button>
    </header>

    <template v-if="auth.isAdmin">
      <UnindexedAlert :steps="unindexed" />

      <div class="section-head">
        <span class="section-title">待适配</span>
        <span
          v-if="pendingCards.length + anomalies.length > 0"
          class="section-count"
        >{{ pendingCards.length + anomalies.length }} 个端点</span>
      </div>
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
          data-testid="anomaly-card"
        >
          <div class="card-top">
            <span class="dot" />
            <b class="mono endpoint">{{ a.endpointId }}</b>
            <el-tag type="warning" size="small" effect="plain">异常</el-tag>
          </div>
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
          <div class="card-top">
            <span class="dot" />
            <b class="mono endpoint">{{ p.endpointId }}</b>
          </div>
          <div class="card-bottom">
            <span class="ver-chip from">{{ p.fromVersion }}</span>
            <span class="ver-arrow">→</span>
            <span class="ver-chip to">{{ p.toVersion }}</span>
            <span class="view">查看影响 →</span>
          </div>
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

    <div class="section-head">
      <span class="section-title">批次</span>
    </div>
    <p v-if="!auth.isAdmin" class="hint mine-hint">仅显示触碰你场景的批次</p>
    <el-table v-loading="batchesLoading" :data="batchRows">
      <el-table-column prop="batchId" label="批次" min-width="140">
        <template #default="{ row }">
          <span class="mono">{{ row.batchId }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="endpointId" label="Endpoint" min-width="180">
        <template #default="{ row }">
          <span class="mono endpoint-cell">{{ row.endpointId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="版本" min-width="130">
        <template #default="{ row }">
          <span class="ver-chip from">{{ row.fromVersion }}</span>
          <span class="ver-arrow">→</span>
          <span class="ver-chip to">{{ row.toVersion }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="batchTagType(row.status)">{{ row.status }}</el-tag>
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
            effect="plain"
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

    <!-- carry 漂移(T16,admin-only:后端 drift 为 AdminUser,member 403)。
         plateReachable=False → 不渲染清单 + 显式警示 + 禁批生成(T11 硬性
         契约:plate 挂时 drift 会把全表绑定误报孤儿,防管理员误清空)。 -->
    <template v-if="auth.isAdmin">
      <div class="section-head">
        <span class="section-title">carry 漂移(值表 vs plate 面)</span>
        <span v-if="carryDrift.length" class="section-count">
          {{ carryDriftTotal }} 项漂移 · {{ carryDrift.length }} 服务
        </span>
        <span class="section-actions">
          <el-button
            size="small"
            :loading="carryDriftLoading"
            @click="loadCarryDrift"
          >刷新</el-button>
          <el-button
            size="small"
            type="primary"
            data-action="carry-generate"
            :disabled="!canGenerate"
            :loading="carryGenerating"
            @click="openCarryBatchFromDrift"
          >勾选生成批({{ carryChecked.length }})</el-button>
        </span>
      </div>

      <el-alert
        v-if="!carryPlateReachable"
        type="warning"
        :closable="false"
        class="drift-alert"
        title="plate 目录不可达:漂移数据可能失真(绑定可能被误报为孤儿),已禁用勾选与批生成"
        description="清单已停止渲染,请先恢复 plate 目录后点刷新重查"
      />
      <el-empty
        v-else-if="carryDrift.length === 0"
        description="暂无服务 carry 数据(无绑定且 plate 面为空)"
      />
      <div v-else class="drift-list">
        <div
          v-for="s in carryDrift"
          :key="s.service"
          class="drift-svc"
          data-testid="drift-svc"
        >
          <h4 class="mono">{{ s.service }}</h4>
          <!-- 对齐服务(三列表全空)正向确认,不渲染空壳(T11 评审契约) -->
          <p v-if="!hasCarryDrift(s)" class="hint drift-ok">已检查,无漂移</p>
          <el-checkbox-group
            v-else
            v-model="carryChecked"
            class="drift-checks"
          >
            <el-checkbox
              v-for="opt in driftCheckOptions(s)"
              :key="opt.key"
              :value="opt.key"
            >{{ opt.text }}</el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '@/api/adaptations'
import type { BatchOut, PendingChange, UnindexedStep } from '@/api/adaptations'
import { getDrift, type ServiceDrift } from '@/api/carry'
import {
  canGenerateCarryBatch,
  checkedServices,
  driftCheckOptions,
  hasCarryDrift,
  parseCarryChecked,
} from '@/utils/carry-drift'
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

function batchTagType(
  status: string
): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'applying') return 'primary'
  if (status === 'open') return 'warning'
  return 'info' // rolled_back
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

// ── carry 漂移面板(T16,spec §7):发现 → 勾选 → 生成值表批 ─────────────
// plateReachable 先判(T11 契约):False 时清单不渲染、勾选与生成禁用。
const carryDrift = ref<ServiceDrift[]>([])
const carryPlateReachable = ref(true)
const carryDriftLoading = ref(false)
const carryGenerating = ref(false)
const carryChecked = ref<string[]>([])

const carryDriftTotal = computed(() =>
  carryDrift.value.reduce((n, s) =>
    n + s.orphaned.length + s.uncovered.length + s.renamedSuggestions.length,
    0))
const canGenerate = computed(
  () => canGenerateCarryBatch(carryPlateReachable.value, carryChecked.value.length))

async function loadCarryDrift(): Promise<void> {
  carryDriftLoading.value = true
  try {
    const report = await getDrift()
    carryPlateReachable.value = report.plateReachable
    carryDrift.value = report.services
    carryChecked.value = []
  } catch (e) {
    ElMessage.error(api.errMsg(e, 'carry 漂移拉取失败'))
  } finally {
    carryDriftLoading.value = false
  }
}

/** 勾选 → 按服务分批(ops 保勾选序逐条 createOp,详情页按序逐条应用),
 *  完成跳到最后一个批;carry op 请求体不带 scenarioId(后端 D1 免场景)。 */
async function openCarryBatchFromDrift(): Promise<void> {
  const items = parseCarryChecked(carryChecked.value)
  if (!canGenerateCarryBatch(carryPlateReachable.value, items.length)) return
  carryGenerating.value = true
  try {
    let lastBatchId = ''
    for (const svc of checkedServices(items)) {
      const detail = await api.openCarryBatch(svc)
      lastBatchId = detail.batchId
      for (const item of items) {
        if (item.service !== svc) continue
        await api.createOp(detail.batchId, {
          opType: item.opType,
          payload: item.payload,
        })
      }
    }
    carryChecked.value = []
    ElMessage.success('carry 批已生成,请在批次详情页按序逐条应用')
    await loadBatches()
    await router.push(`/adaptations/batches/${lastBatchId}`)
  } catch (e) {
    ElMessage.error(api.errMsg(e, 'carry 批生成失败'))
    await loadBatches()   // 中途失败也可能已建批:刷新让列表反映真实
  } finally {
    carryGenerating.value = false
  }
}

onMounted(() => {
  if (auth.isAdmin) {
    void refreshAll()
    void loadCarryDrift()
  } else {
    void loadBatches('mine')
  }
})
</script>

<style scoped>
/* 页面容器:对齐 CaseDataSetsList 的页面规范(居中 + 大边距)。 */
.adaptation-center {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

/* ── 页头 ── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.header-text p { margin: 6px 0 0; color: #909399; font-size: 13px; }

/* ── 小节头:标签 + 计数,与内容拉开层级 ── */
.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 26px 0 12px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: #606266;
}
.section-count { font-size: 12px; color: #909399; }

/* ── 待适配卡片网格 ── */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 14px 16px;
  transition: border-color 0.2s, background-color 0.2s;
}
.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
}
.card.anomaly .dot { background: #e6a23c; }
.endpoint {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.card-bottom {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
}
.card.pending { cursor: pointer; }
.card.pending:hover {
  border-color: #409eff;
  background: #f5faff;
}
.card.anomaly {
  border-color: #f3d19e;
  background: #fdf6ec;
}
.card .detail { margin: 0; font-size: 13px; color: #606266; }
.hint { margin: 0; color: #909399; font-size: 12px; }
.view { margin-left: auto; font-size: 12px; color: #909399; }

/* ── 版本 chip(卡片与批次表共用) ── */
.ver-chip {
  display: inline-block;
  font-family: monospace;
  font-size: 12px;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 4px;
}
.ver-chip.from { background: #f4f4f5; color: #909399; }
.ver-chip.to { background: #ecf5ff; color: #409eff; }
.ver-arrow { color: #c0c4cc; font-size: 12px; }

/* ── 批次表 ── */
.endpoint-cell { font-size: 13px; color: #303133; }
.mine-hint { margin: 0 0 10px; }
.op-tag { margin-right: 4px; }
.link { color: #409eff; }
.mono { font-family: monospace; }

/* ── carry 漂移(T16)── */
.section-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.drift-alert { margin: 0 0 12px; }
.drift-svc {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 10px;
}
.drift-svc h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.drift-checks { display: block; }
.drift-checks :deep(.el-checkbox) {
  height: auto;
  min-height: 24px;
  align-items: flex-start;
  white-space: normal;
  margin-right: 0;
}
.drift-ok { margin: 0; color: #67c23a; }
</style>
