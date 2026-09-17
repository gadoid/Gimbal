<!-- AdaptationCenter —— P5 适配中心总览(spec §3/§5 + §7 carry 职能)。
     批次 3 迁移新栈:shadcn Table/Button/Alert;tag → Signal chip;
     勾选清单 → 原生 checkbox(label.drift-check)。
     admin:未索引警示 + 待适配卡片(C12 异常卡不可开批次)+ 全量批次表
       + carry 漂移面板(T16:三类勾选 → 生成值表批,plateReachable 先判);
     member:自动只读 owner 视图(仅批次表,scope=mine,无详情列 ——
       批次工作台为 admin-only,member 直入得 403)。 -->
<template>
  <section class="adaptation-center mx-auto max-w-[1480px] px-8 pb-12 pt-7">
    <header class="page-header">
      <div class="header-text">
        <h2 class="m-0 text-display text-signal-ink">适配中心</h2>
        <p class="mt-1 mb-0 text-caption text-muted-foreground">
          {{ auth.isAdmin ? '目录变更检测与批次适配' : '仅显示触碰你场景的批次(只读)' }}
        </p>
      </div>
      <Button
        v-if="auth.isAdmin"
        :disabled="adaptations.refreshing"
        data-testid="refresh-all"
        @click="refreshAll"
      >{{ adaptations.refreshing ? '检查中…' : '检查更新' }}</Button>
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
      <Alert v-if="adaptations.lastError" variant="destructive" data-testid="diff-error">
        <AlertTitle>{{ adaptations.lastError }}</AlertTitle>
      </Alert>
      <div v-else-if="pendingCards.length === 0 && anomalies.length === 0" class="empty-note">
        目录无待适配变更
      </div>
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
            <span class="chip bg-amber-50 text-amber-800">异常</span>
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
    <div v-if="batchesLoading" class="py-6 text-center text-body text-muted-foreground">批次加载中…</div>
    <Table v-else class="rounded-field border border-signal-line bg-signal-card">
      <TableHeader>
        <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
          <TableHead class="text-caption font-semibold text-muted-foreground">批次</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">Endpoint</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">版本</TableHead>
          <TableHead class="w-[110px] text-caption font-semibold text-muted-foreground">状态</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">ops</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">创建时间</TableHead>
          <!-- 详情入口仅 admin:GET /batches/{id} 为 admin-only,
               member 点击只会得 403(死链),故整列不渲染。 -->
          <TableHead v-if="auth.isAdmin" class="w-[70px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in batchRows" :key="row.batchId">
          <TableCell><span class="mono">{{ row.batchId }}</span></TableCell>
          <TableCell><span class="mono endpoint-cell">{{ row.endpointId }}</span></TableCell>
          <TableCell>
            <span class="ver-chip from">{{ row.fromVersion }}</span>
            <span class="ver-arrow">→</span>
            <span class="ver-chip to">{{ row.toVersion }}</span>
          </TableCell>
          <TableCell>
            <span class="chip" :class="batchStatusClass[row.status] ?? 'bg-muted text-muted-foreground'">
              {{ row.status }}
            </span>
          </TableCell>
          <TableCell>
            <span
              v-for="(n, s) in row.opCounts"
              :key="s"
              class="chip op-tag"
              :class="opStatusClass[String(s)] ?? 'bg-muted text-muted-foreground'"
            >{{ s }} {{ n }}</span>
          </TableCell>
          <TableCell class="text-caption text-muted-foreground">{{ row.createdAt }}</TableCell>
          <TableCell v-if="auth.isAdmin">
            <router-link
              :to="`/adaptations/batches/${row.batchId}`"
              class="link"
            >详情</router-link>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

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
          <Button
            variant="outline"
            size="sm"
            :disabled="carryDriftLoading"
            @click="loadCarryDrift"
          >{{ carryDriftLoading ? '刷新中…' : '刷新' }}</Button>
          <Button
            size="sm"
            data-action="carry-generate"
            :disabled="!canGenerate"
            @click="openCarryBatchFromDrift"
          >{{ carryGenerating ? '生成中…' : `勾选生成批(${carryChecked.length})` }}</Button>
        </span>
      </div>

      <Alert v-if="!carryPlateReachable" class="mt-2" data-testid="drift-unreachable">
        <AlertTitle>plate 目录不可达:漂移数据可能失真(绑定可能被误报为孤儿),已禁用勾选与批生成</AlertTitle>
        <AlertDescription>清单已停止渲染,请先恢复 plate 目录后点刷新重查</AlertDescription>
      </Alert>
      <div v-else-if="carryDrift.length === 0" class="empty-note">
        {{ carryLoadFailed ? '加载失败,请刷新' : '暂无服务 carry 数据(无绑定且 plate 面为空)' }}
      </div>
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
          <div v-else class="drift-checks">
            <label v-for="opt in driftCheckOptions(s)" :key="opt.key" class="drift-check">
              <input v-model="carryChecked" type="checkbox" :value="opt.key" />
              {{ opt.text }}
            </label>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
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
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

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

/** 状态 → Signal chip 色(el-tag type 的语义迁移) */
const opStatusClass: Record<string, string> = {
  applied: 'bg-signal-done/10 text-signal-done',
  conflict: 'bg-signal-failed/10 text-signal-failed',
  skipped: 'bg-muted text-muted-foreground',
  pending: 'bg-amber-50 text-amber-800',
}

const batchStatusClass: Record<string, string> = {
  completed: 'bg-signal-done/10 text-signal-done',
  applying: 'bg-signal-soft text-signal',
  open: 'bg-amber-50 text-amber-800',
  rolled_back: 'bg-muted text-muted-foreground',
}

async function loadBatches(scope?: 'mine'): Promise<void> {
  batchesLoading.value = true
  try {
    batchRows.value = await api.listBatches(scope)
  } catch (e) {
    toast.error(api.errMsg(e, '批次列表加载失败'))
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
    toast.error(api.errMsg(e, '开批次失败(no_pending_change 等),请刷新后重试'))
  }
}

// ── carry 漂移面板(T16,spec §7):发现 → 勾选 → 生成值表批 ─────────────
// plateReachable 先判(T11 契约):False 时清单不渲染、勾选与生成禁用。
const carryDrift = ref<ServiceDrift[]>([])
const carryPlateReachable = ref(true)
const carryDriftLoading = ref(false)
const carryGenerating = ref(false)
const carryChecked = ref<string[]>([])
/** 拉取失败标志:失败时空态须说"加载失败"而非误导性的"暂无数据"。 */
const carryLoadFailed = ref(false)

const carryDriftTotal = computed(() =>
  carryDrift.value.reduce((n, s) =>
    n + s.orphaned.length + s.uncovered.length + s.renamedSuggestions.length,
  0))
const canGenerate = computed(
  () => canGenerateCarryBatch(carryPlateReachable.value, carryChecked.value.length))

async function loadCarryDrift(): Promise<void> {
  carryDriftLoading.value = true
  carryLoadFailed.value = false
  try {
    const report = await getDrift()
    carryPlateReachable.value = report.plateReachable
    carryDrift.value = report.services
    carryChecked.value = []
  } catch (e) {
    carryLoadFailed.value = true
    toast.error(api.errMsg(e, 'carry 漂移拉取失败'))
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
    toast.success('carry 批已生成,请在批次详情页按序逐条应用')
    await loadBatches()
    await router.push(`/adaptations/batches/${lastBatchId}`)
  } catch (e) {
    toast.error(api.errMsg(e, 'carry 批生成失败'))
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
/* ── 页头 ── */
.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

/* ── 分节标题 ── */
.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 22px 0 10px;
}
.section-title {
  font-size: 14px;
  font-weight: 700;
  color: #10151c;
  padding-left: 10px;
  border-left: 3px solid #2f6fed;
}
.section-count {
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 3px;
}
.section-actions { margin-left: auto; display: flex; gap: 8px; }

/* ── 待适配卡片 ── */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}
.card {
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 8px;
  padding: 10px 14px;
}
.card.anomaly { border-color: #fde68a; background: #fffbeb; }
.card.pending { cursor: pointer; transition: border-color 0.15s ease, box-shadow 0.15s ease; }
.card.pending:hover { border-color: #2f6fed; box-shadow: 0 1px 6px rgba(47, 111, 237, 0.12); }
.card-top { display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #2f6fed; flex-shrink: 0; }
.card.anomaly .dot { background: #eab308; }
.endpoint { font-size: 13px; }
.detail { margin: 6px 0 2px; font-size: 12px; color: #334155; }
.card-bottom { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.view { margin-left: auto; font-size: 12px; color: #2f6fed; }

/* ── 版本 chip ── */
.ver-chip {
  padding: 1px 8px;
  font-family: monospace;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}
.ver-chip.from { color: #64748b; background: #f1f5f9; }
.ver-chip.to { color: #2f6fed; background: #e7efff; }
.ver-arrow { color: #94a3b8; font-size: 11px; }

/* ── 通用 chip(状态/ops)── */
.chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}
.op-tag { margin-right: 4px; }
.endpoint-cell { font-size: 12px; }

/* ── 空态/提示 ── */
.empty-note {
  padding: 18px 16px;
  text-align: center;
  font-size: 12.5px;
  color: #94a3b8;
  border: 1px dashed #e1e5eb;
  border-radius: 8px;
}
.hint { font-size: 11.5px; color: #94a3b8; margin: 2px 0 0; }
.mine-hint { margin: -4px 0 10px; }

/* ── drift 清单 ── */
.drift-list { display: flex; flex-direction: column; gap: 10px; }
.drift-svc {
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 8px;
  padding: 10px 14px;
}
.drift-svc h4 { margin: 0 0 6px; font-size: 13px; }
.drift-ok { color: #15803d; }
.drift-checks { display: flex; flex-direction: column; gap: 4px; }
.drift-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  cursor: pointer;
}
.drift-check input { accent-color: #2f6fed; }

.mono { font-family: monospace; }
.link { color: #2f6fed; }
</style>
