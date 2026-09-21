<!-- AdaptationBatchDetail —— 批次工作台(spec §6,admin-only):
     头部(版本/状态/回滚)→ ops 列表(预览 + 状态驱动操作组 + 合并勾选)
     → 构造对话框 → 快照折叠。member 直入 → 403「仅管理员」占位(§8);
     页内 isAdmin 只读分支保留作双保险。 -->
<template>
  <HubDetailPage v-if="detail" width="wide" :title="`批次 ${detail.batchId}`">
    <template #meta>
      <p class="mono m-0">{{ detail.endpointId }} · {{ detail.fromVersion }} → {{ detail.toVersion }}</p>
    </template>

    <template #actions>
      <span class="chip" :class="statusClass[detail.status] ?? 'bg-muted text-muted-foreground'">{{ detail.status }}</span>
      <template v-if="auth.hasRole('operator', 'admin')">
        <Button variant="outline" data-action="construct" @click="constructOpen = true">
          构造 op
        </Button>
        <Button
          variant="outline"
          data-action="merge"
          :disabled="!mergeReady"
          @click="startMerge"
        >合并为 renameField</Button>
        <Button
          v-if="detail.status === 'open' || detail.status === 'applying'"
          variant="destructive"
          data-action="rollback"
          @click="onRollback"
        >整批回滚</Button>
      </template>
    </template>

    <template #summary>
      <p class="m-0">
        <span
          v-for="(n, s) in detail.opCounts"
          :key="s"
          class="chip op-tag"
          :class="statusClass[String(s)] ?? 'bg-muted text-muted-foreground'"
        >{{ s }} {{ n }}</span>
      </p>
    </template>

    <Alert v-if="!auth.hasRole('operator', 'admin')" class="mb-3">
      <AlertTitle>owner 只读视图:仅查看 op 与快照,操作请联系管理员</AlertTitle>
    </Alert>

    <div class="ops">
      <div v-for="op in detail.ops" :key="op.id" class="op-row">
        <div class="op-head">
          <input
            v-if="auth.hasRole('operator', 'admin') && selectable(op)"
            type="checkbox"
            class="op-check"
            :data-testid="`op-check-${op.id}`"
            :checked="selectedIds.has(op.id)"
            @change="toggleSelect(op)"
          />
          <span class="chip mono bg-muted text-muted-foreground">{{ op.opType }}</span>
          <span class="chip" :class="statusClass[op.status] ?? 'bg-muted text-muted-foreground'">
            {{ op.status }}
          </span>
          <span v-if="op.appliedAt" class="hint">{{ op.appliedAt }}</span>
          <span v-if="op.note" class="hint note">{{ op.note }}</span>
          <span v-if="auth.hasRole('operator', 'admin') && op.status === 'pending'" class="op-actions">
            <Button
              size="sm"
              class="op-action"
              data-action="apply"
              @click="onApply(op)"
            >应用</Button>
            <Button
              size="sm"
              variant="outline"
              class="op-action"
              data-action="skip"
              @click="onSkip(op)"
            >跳过</Button>
            <Button
              size="sm"
              variant="outline"
              class="op-action"
              data-action="edit"
              @click="onEdit(op)"
            >编辑</Button>
          </span>
        </div>
        <OpPreview :op="op" />
      </div>
    </div>

    <details class="snapshots">
      <summary>快照({{ detail.snapshots.length }})</summary>
      <ul>
        <li v-for="(s, i) in detail.snapshots" :key="i" class="mono">
          {{ s.entityType }} · {{ s.entityId }}
        </li>
      </ul>
    </details>

    <OpConstructDialog
      v-model="constructOpen"
      :batch-id="detail.batchId"
      :merge-seed="activeSeed"
      @created="onCreated"
    />

    <Dialog :open="editOpen" @update:open="editOpen = $event">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>编辑 payload(JSON,仅 pending)</DialogTitle>
        </DialogHeader>
        <textarea
          v-model="editJson"
          rows="8"
          class="w-full rounded-field border border-input bg-transparent p-2 font-mono text-body"
          data-testid="edit-json"
        ></textarea>
        <p class="hint">mapValue 骨架在此补 map 值;保存即整包替换</p>
        <DialogFooter>
          <Button variant="outline" @click="editOpen = false">取消</Button>
          <Button @click="saveEdit">保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog :open="reportOpen" @update:open="reportOpen = $event">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>回滚报告</DialogTitle>
        </DialogHeader>
        <h4 class="m-0 mb-1 text-label font-semibold">已恢复</h4>
        <ul>
          <li v-for="(r, i) in rollbackReport?.restored ?? []" :key="i" class="mono">
            {{ r.entityType }} · {{ r.entityId }}
          </li>
        </ul>
        <h4 class="m-0 mb-1 mt-3 text-label font-semibold">冲突(跳过)</h4>
        <ul>
          <li v-for="(c, i) in rollbackReport?.conflicts ?? []" :key="i">
            <span class="mono">{{ c.entityType }} · {{ c.entityId }}</span>
            <span class="hint"> — {{ c.note }}</span>
          </li>
        </ul>
      </DialogContent>
    </Dialog>
  </HubDetailPage>
  <div v-else-if="adminOnly" class="mx-auto w-full max-w-[min(1480px,100%)] px-4 py-6">
    <div class="empty-state">
      <p>仅管理员:批次工作台为管理员专用</p>
      <router-link to="/adaptations" class="link">返回适配中心</router-link>
    </div>
  </div>
  <div v-else-if="loaded" class="mx-auto w-full max-w-[min(1480px,100%)] px-4 py-6">
    <div class="empty-state">
      <p>批次不存在或已清理</p>
      <router-link to="/adaptations" class="link">返回适配中心</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import HubDetailPage from '@/layouts/HubDetailPage.vue'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import * as api from '@/api/adaptations'
import type { OpOut, RollbackReport } from '@/api/adaptations'
import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import OpPreview from '@/components/adaptations/OpPreview.vue'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import { mergeSeedFrom } from '@/utils/adaptation-merge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Alert, AlertTitle } from '@/components/ui/alert'

const auth = useAuthStore()
const route = useRoute()

const detail = ref<api.BatchDetail | null>(null)
const loaded = ref(false)
const adminOnly = ref(false)
const selectedOps = ref<OpOut[]>([])
const constructOpen = ref(false)
const activeSeed = ref<api.MergeSeed | null>(null)
// F2:onCreated 是否已消费合并种子 —— 关闭对话框时的清理据此避让,
// 防止清掉正在被 onCreated 串联 skip 消费的 seed/勾选。
let seedConsumed = false
const editOpen = ref(false)
const editJson = ref('')
const editingOp = ref<OpOut | null>(null)
const reportOpen = ref(false)
const rollbackReport = ref<RollbackReport | null>(null)

const selectedIds = computed(
  () => new Set(selectedOps.value.map((o) => o.id)))
const mergeReady = computed(() => mergeSeedFrom(selectedOps.value) !== null)

function selectable(op: OpOut): boolean {
  return op.status === 'pending'
    && (op.opType === 'removeField' || op.opType === 'addField')
}

function toggleSelect(op: OpOut): void {
  const idx = selectedOps.value.findIndex((o) => o.id === op.id)
  if (idx >= 0) selectedOps.value.splice(idx, 1)
  else selectedOps.value.push(op)
}

/** op 状态 → Signal chip 色(el-tag type 语义迁移) */
const statusClass: Record<string, string> = {
  applied: 'bg-signal-done/10 text-signal-done',
  conflict: 'bg-signal-failed/10 text-signal-failed',
  skipped: 'bg-muted text-muted-foreground',
  pending: 'bg-amber-50 text-amber-800',
}

// F1:member 直入本页 → GET /batches/{id} 为 admin-only,403 detail 含
// admin_only(http.ts 归一后 status=403)→ 渲染 §8「仅管理员」占位而非误报 404。
function isAdminOnly(e: unknown): boolean {
  return e instanceof ApiError
    && (e.status === 403 || e.message.includes('admin_only'))
}

async function reload(): Promise<void> {
  try {
    detail.value = await api.getBatch(String(route.params.batchId))
  } catch (e) {
    if (isAdminOnly(e)) adminOnly.value = true
    else toast.error(api.errMsg(e, '批次加载失败'))
  } finally {
    loaded.value = true
  }
}

async function onApply(op: OpOut): Promise<void> {
  try {
    await api.applyOp(op.id)
    await reload()
  } catch (e) {
    toast.error(api.errMsg(e, '应用失败'))
  }
}

async function onSkip(op: OpOut): Promise<void> {
  try {
    await api.skipOp(op.id)
    await reload()
  } catch (e) {
    toast.error(api.errMsg(e, '跳过失败'))
  }
}

function onEdit(op: OpOut): void {
  editingOp.value = op
  editJson.value = JSON.stringify(op.payload, null, 2)
  editOpen.value = true
}

async function saveEdit(): Promise<void> {
  if (!editingOp.value) return
  try {
    const payload = JSON.parse(editJson.value) as Record<string, unknown>
    await api.patchOp(editingOp.value.id, payload)
    editOpen.value = false
    await reload()
  } catch (e) {
    toast.error(e instanceof SyntaxError
      ? 'JSON 解析失败' : api.errMsg(e, '保存失败(可能已非 pending)'))
  }
}

function startMerge(): void {
  const seed = mergeSeedFrom(selectedOps.value)
  if (!seed) {
    toast.warning('需勾选同一 step 的一删一增两条 pending 草案')
    return
  }
  activeSeed.value = seed
  constructOpen.value = true
}

// F2:构造对话框关闭且并非「创建成功」收尾 → 合并被取消,清种子与勾选,
// 否则下一次普通构造仍被 mergeSeed 锁类型/预填,并静默 skip 两条源 op。
// seedConsumed 在 onCreated 入口同步置位(v-model 关闭 emit 发生在其后,
// watch 默认 pre-flush 异步执行),清理不会抢跑创建流。
watch(constructOpen, (open) => {
  if (open) return
  if (!seedConsumed) {
    activeSeed.value = null
    selectedOps.value = []
  }
  seedConsumed = false
})

async function onCreated(op: OpOut): Promise<void> {
  seedConsumed = true
  const seed = activeSeed.value
  try {
    // 合并流:构造成功后跳过两条源 op(前端串联,§6.3)
    if (seed) {
      for (const src of selectedOps.value) {
        await api.skipOp(src.id)
      }
    }
  } catch (e) {
    // F3:skip 串联失败 → 报错兜底,下方 finally 重载以真实状态示人
    toast.error(api.errMsg(e, '跳过原草案失败'))
  } finally {
    if (seed) {
      selectedOps.value = []
      activeSeed.value = null
    }
    void op
    await reload()
  }
}

async function onRollback(): Promise<void> {
  const ok = await confirmAction(
    '整批回滚将恢复快照 before 像(冲突实体跳过不盲写),确认?',
    '回滚确认',
    { type: 'warning', danger: true, confirmButtonText: '回滚', cancelButtonText: '取消' },
  )
  if (!ok) return   // 用户取消
  try {
    rollbackReport.value = await api.rollbackBatch(
      String(route.params.batchId))
    reportOpen.value = true
    await reload()
  } catch (e) {
    toast.error(api.errMsg(e, '回滚失败(批次可能尚未 completed)'))
  }
}

defineExpose({ selectedOps, startMerge })

onMounted(reload)
</script>

<style scoped>
/* 配色对齐服务区域基座令牌(此前残留 Element-Plus 蓝 #409eff 与灰阶) */
.hint { @apply text-label font-normal; color: var(--sl-ink-3); }
.op-tag { margin-right: 4px; }
.chip {
  @apply text-micro font-semibold;
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 4px;
}
.op-check { accent-color: var(--sl-accent); flex: none; }
.snapshots summary {
  @apply text-body font-semibold;
  cursor: pointer;
  color: var(--sl-ink);
  margin: 18px 0 8px;
}
.snapshots ul { margin: 8px 0; padding-left: 18px; }
.snapshots li { @apply text-label font-normal; }
.op-row {
  border: 1px solid var(--sl-line);
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 10px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.04);
}
.op-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.op-actions { margin-left: auto; }
.note { max-width: 340px; overflow: hidden; text-overflow: ellipsis; }
.snapshots { margin-top: 18px; }
.snapshots ul { padding-left: 18px; }
.link { color: var(--sl-accent); }
.mono { font-family: var(--font-mono, monospace); }
</style>
