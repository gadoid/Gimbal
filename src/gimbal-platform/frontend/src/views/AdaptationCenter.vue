<!-- AdaptationCenter —— RS4a（Release v4.4 §5.1/§5.10）重做。
     主体 = 新适配流程（R22 全员）；下方两栏：批次表 + carry 漂移（admin）。 -->
<template>
  <section class="slib">
    <PageHead
      icon="activity"
      title="变更适配"
      subtitle="场景版本适配 · 比较 → 检查 → 提交"
    />

    <!-- ── 新适配流程（主体卡片）──────────────────────────────────── -->
    <div class="ac-main-card">
      <AdaptationFlow />
    </div>

    <!-- ── 下方两栏：批次 + carry ────────────────────────────────── -->
    <div class="ac-bottom">

      <!-- 左栏：批次表 -->
      <div class="ac-panel">
        <div class="ac-panel-head">
          <h3 class="ac-panel-title">批次</h3>
          <span v-if="batchTotal" class="ac-panel-count mono">{{ batchTotal }}</span>
          <select
            v-model="batchStatus"
            class="ac-select"
            data-testid="batch-status"
            @change="setBatchStatus(batchStatus)"
          >
            <option v-for="opt in BATCH_STATUS_OPTS" :key="opt.value"
                    :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>

        <div v-if="batchesLoading" class="ac-empty">加载中…</div>
        <div v-else-if="batchRows.length === 0" class="ac-empty">
          {{ auth.isAdmin ? '暂无批次' : '暂无触碰你场景的批次' }}
        </div>
        <table v-else class="ac-table">
          <thead>
            <tr>
              <th>batchId</th>
              <th>kind</th>
              <th>状态</th>
              <th>操作人</th>
              <th>时间</th>
              <th v-if="auth.isAdmin"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in batchRows" :key="b.batchId" data-testid="batch-row">
              <td class="mono ac-ellipsis" :title="b.batchId">{{ b.batchId.slice(0, 10) }}…</td>
              <td><span class="ac-chip ac-chip-kind">{{ (b as any).kind || 'carry' }}</span></td>
              <td>
                <span class="ac-chip" :class="batchStatusClass[b.status] ?? ''">{{ b.status }}</span>
              </td>
              <td class="ac-nowrap">{{ (b as any).operatorName || '—' }}</td>
              <td class="mono ac-nowrap">{{ formatDate(b.createdAt) }}</td>
              <td v-if="auth.isAdmin" class="ac-center">
                <router-link :to="`/adaptations/batches/${b.batchId}`" class="ac-link">详情</router-link>
              </td>
            </tr>
          </tbody>
        </table>
        <Pagination
          v-if="batchPageCount > 1"
          v-model:page="batchPage"
          :total="batchTotal"
          :page-size="batchPageSize"
        />
      </div>

      <!-- 右栏：carry 漂移（admin-only；member 隐藏整栏） -->
      <div v-if="auth.isAdmin" class="ac-panel">
        <div class="ac-panel-head">
          <h3 class="ac-panel-title">carry 漂移</h3>
          <span v-if="carryDrift.length" class="ac-panel-count mono">{{ carryDriftTotal }}</span>
          <span class="ac-panel-actions">
            <Button variant="outline" size="sm"
                    :disabled="carryDriftLoading"
                    @click="loadCarryDrift"
            >{{ carryDriftLoading ? '刷新中…' : '刷新' }}</Button>
            <Button size="sm" data-action="carry-generate"
                    :disabled="!canGenerate"
                    @click="openCarryBatchFromDrift"
            >{{ carryGenerating ? '生成中…' : `生成批(${carryChecked.length})` }}</Button>
          </span>
        </div>

        <Alert v-if="!carryPlateReachable" class="ac-mt" data-testid="drift-unreachable">
          <AlertTitle>plate 目录不可达</AlertTitle>
          <AlertDescription>漂移数据可能失真,已禁用勾选与批生成</AlertDescription>
        </Alert>
        <div v-else-if="carryDrift.length === 0" class="ac-empty">
          {{ carryLoadFailed ? '加载失败,请刷新' : '暂无 carry 数据' }}
        </div>
        <div v-else class="ac-drift-list">
          <div v-for="s in carryDrift" :key="s.service" class="ac-drift-svc" data-testid="drift-svc">
            <div class="ac-drift-name mono">{{ s.service }}</div>
            <p v-if="!hasCarryDrift(s)" class="ac-drift-ok">✓ 无漂移</p>
            <div v-else class="ac-drift-checks">
              <label v-for="opt in driftCheckOptions(s)" :key="opt.key" class="ac-drift-check">
                <input v-model="carryChecked" type="checkbox" :value="opt.key" />
                {{ opt.text }}
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import AdaptationFlow from '@/views/AdaptationFlow.vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/adaptations'
import type { BatchOut } from '@/api/adaptations'
import { getDrift, type ServiceDrift } from '@/api/carry'
import {
  canGenerateCarryBatch, checkedServices, driftCheckOptions,
  hasCarryDrift, parseCarryChecked,
} from '@/utils/carry-drift'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Pagination } from '@/components/ui/pagination'
import { usePagerSize } from '@/composables/usePagerSize'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const auth = useAuthStore()
const router = useRouter()

// ── 批次表 ──────────────────────────────────────────────────────
const batchRows = ref<BatchOut[]>([])
const batchTotal = ref(0)
const batchStatus = ref('')
const batchPage = ref(1)
const { pageSize: batchPageSize } = usePagerSize('adaptation-batches', 20)
const batchPageCount = computed(() =>
  Math.max(1, Math.ceil(batchTotal.value / batchPageSize.value)))
const batchesLoading = ref(false)

watch(batchPage, () => void loadBatches(auth.isAdmin ? undefined : 'mine'))
watch(batchPageSize, () => {
  if (batchPage.value !== 1) batchPage.value = 1
  else void loadBatches(auth.isAdmin ? undefined : 'mine')
})

const BATCH_STATUS_OPTS = [
  { value: '', label: '全部' },
  { value: 'open', label: 'open' },
  { value: 'applying', label: 'applying' },
  { value: 'completed', label: 'completed' },
  { value: 'rolled_back', label: 'rolled_back' },
] as const

function setBatchStatus(v: string): void {
  if (batchStatus.value === v) return
  batchStatus.value = v
  if (batchPage.value !== 1) batchPage.value = 1
  else void loadBatches(auth.isAdmin ? undefined : 'mine')
}

const batchStatusClass: Record<string, string> = {
  completed: 'ac-chip-done',
  applying: 'ac-chip-active',
  open: 'ac-chip-open',
  rolled_back: 'ac-chip-muted',
}

async function loadBatches(scope?: 'mine'): Promise<void> {
  batchesLoading.value = true
  try {
    const env = await api.listBatches({
      scope, status: batchStatus.value || undefined,
      page: batchPage.value, page_size: batchPageSize.value,
    })
    batchRows.value = env.items
    batchTotal.value = env.total
    if (env.items.length === 0 && batchPage.value > 1) {
      batchPage.value = Math.max(1, Math.ceil(env.total / batchPageSize.value))
      return
    }
  } catch (e) {
    toast.error(api.errMsg(e, '批次列表加载失败'))
    batchRows.value = []
    batchTotal.value = 0
  } finally {
    batchesLoading.value = false
  }
}

function formatDate(iso: string): string {
  try { return new Date(iso).toLocaleDateString() } catch { return iso }
}

// ── carry 漂移面板 ──────────────────────────────────────────────
const carryDrift = ref<ServiceDrift[]>([])
const carryPlateReachable = ref(true)
const carryDriftLoading = ref(false)
const carryGenerating = ref(false)
const carryChecked = ref<string[]>([])
const carryLoadFailed = ref(false)

const carryDriftTotal = computed(() =>
  carryDrift.value.reduce((n, s) =>
    n + s.orphaned.length + s.uncovered.length + s.renamedSuggestions.length, 0))
const canGenerate = computed(() =>
  canGenerateCarryBatch(carryPlateReachable.value, carryChecked.value.length))

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
          opType: item.opType, payload: item.payload,
        })
      }
    }
    carryChecked.value = []
    toast.success('carry 批已生成')
    await loadBatches()
    await router.push(`/adaptations/batches/${lastBatchId}`)
  } catch (e) {
    toast.error(api.errMsg(e, 'carry 批生成失败'))
    await loadBatches()
  } finally {
    carryGenerating.value = false
  }
}

onMounted(() => {
  void loadBatches(auth.isAdmin ? undefined : 'mine')
  if (auth.isAdmin) void loadCarryDrift()
})
</script>

<style scoped>
/* 主体卡片 */
.ac-main-card {
  background: #fff;
  border: 1px solid var(--sl-line, #e1e5eb);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}

/* 下方两栏 */
.ac-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 960px) {
  .ac-bottom { grid-template-columns: 1fr; }
}

/* 面板 */
.ac-panel {
  background: #fff;
  border: 1px solid var(--sl-line, #e1e5eb);
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.ac-panel-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 12px;
}
.ac-panel-title {
  font-size: 14px; font-weight: 700;
  color: var(--sl-ink, #10151c); margin: 0;
}
.ac-panel-count {
  font-size: 11px; color: var(--sl-ink-soft, #64748b);
  background: var(--sl-line, #f1f5f9); border-radius: 4px; padding: 1px 6px;
}
.ac-panel-actions { margin-left: auto; display: flex; gap: 4px; }

/* 状态筛选 */
.ac-select {
  margin-left: auto; height: 26px; padding: 0 6px;
  font-size: 12px; color: var(--sl-ink, #10151c);
  background: #fff; border: 1px solid var(--sl-line, #e1e5eb);
  border-radius: 4px; outline: none;
}
.ac-panel-actions + .ac-select { margin-left: 0; }

/* 批次表 */
.ac-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ac-table th {
  text-align: left; font-size: 11px; font-weight: 600;
  color: var(--sl-ink-soft, #64748b);
  padding: 6px 8px; border-bottom: 1px solid var(--sl-line, #e1e5eb);
  white-space: nowrap;
}
.ac-table td {
  padding: 7px 8px;
  border-bottom: 1px solid var(--sl-line, #f1f5f9);
  color: var(--sl-ink, #374151);
}
.ac-table tbody tr:hover { background: #f8fafc; }

/* chip */
.ac-chip {
  display: inline-block; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 600;
  white-space: nowrap;
}
.ac-chip-kind { background: #f1f5f9; color: #475569; }
.ac-chip-done { background: #f0fdf4; color: #16a34a; }
.ac-chip-active { background: #eff6ff; color: #2563eb; }
.ac-chip-open { background: #fffbeb; color: #d97706; }
.ac-chip-muted { background: #f9fafb; color: #9ca3af; }

/* carry 漂移 */
.ac-drift-list { display: flex; flex-direction: column; gap: 6px; }
.ac-drift-svc {
  border: 1px solid var(--sl-line, #f1f5f9); border-radius: 8px;
  padding: 8px 12px;
}
.ac-drift-name {
  font-size: 12px; font-weight: 600;
  color: var(--sl-ink, #10151c); margin-bottom: 4px;
}
.ac-drift-ok { font-size: 12px; color: #10b981; margin: 0; }
.ac-drift-checks { display: flex; flex-direction: column; gap: 3px; }
.ac-drift-check {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--sl-ink, #374151); cursor: pointer;
}

/* 通用 */
.ac-empty { text-align: center; padding: 20px; color: var(--sl-ink-soft, #94a3b8); font-size: 13px; }
.ac-link { color: var(--sl-accent, #2f6fed); font-size: 12px; text-decoration: none; }
.ac-link:hover { text-decoration: underline; }
.ac-center { text-align: center; }
.ac-nowrap { white-space: nowrap; }
.ac-ellipsis { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ac-mt { margin-top: 8px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
</style>
