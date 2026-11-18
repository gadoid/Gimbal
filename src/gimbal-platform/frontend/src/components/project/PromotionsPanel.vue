<!-- PromotionsPanel.vue — M2a S7.2 项目详情「加入申请」页签:
     项目管理员裁决(批准 = 逐项选 采纳原件值/保留项目层值,以批准那一刻
     的原件内容复制;驳回须理由);申请人可撤回自己的 pending。
     2026-11-16 重塑:表格落 .slib-table + 状态徽章令牌化;裁决/驳回自绘
     overlay → ui/Dialog;撤回走 confirmAction。
     2026-11-18 按 stitch 原型 _4 重排:状态筛选 Tab(全部/待审批/已
     通过/已驳回/已撤回,客户端过滤)+ 卡片式审批流(类型/来源/冲突数/
     状态徽章/提交时间/驳回理由/操作)。注意:本面板是「场景/用例集加入
     项目」的内容审批 —— 原型画的「人员申请加入项目(工号/部门/角色/
     批量通过/转派/审计流)」是另一套模型,后端不存在,排期见
     docs/project-detail-stitch-plan.md。 -->
<template>
  <div class="panel" data-testid="prj-promotions">
    <!-- ══ 原型 _4 · 说明头(语义:内容审批,不是人员加入申请)════ -->
    <header class="promo-head" data-testid="promo-head">
      <span class="ph-icon" aria-hidden="true">✓</span>
      <div class="ph-main">
        <div class="ph-title">项目内容协同审批</div>
        <p>
          私有场景 / 用例集加入本项目需管理员审批:批准按<b>当前原件内容</b>
          复制进项目,冲突项逐条裁决;申请人可在本页撤回自己的待审批申请。
        </p>
      </div>
    </header>

    <!-- ══ 原型 _4 · 状态筛选 Tab ══════════════════════════════ -->
    <div class="promo-toolbar">
      <div class="status-tabs" data-testid="promo-status-tabs">
        <button
          v-for="s in statusFilters"
          :key="s.key"
          type="button"
          class="stab"
          :class="{ on: statusFilter === s.key }"
          :data-testid="`promo-filter-${s.key || 'all'}`"
          @click="statusFilter = s.key"
        >{{ s.label }}<span class="stn" :class="{ alert: s.key === 'pending' && statusCount('pending') }">{{ statusCount(s.key) }}</span></button>
      </div>
    </div>

    <p v-if="loading" class="muted">加载中…</p>
    <div v-else-if="shownItems.length" class="promo-list">
      <article
        v-for="p in shownItems" :key="p.id" class="promo-card"
        :data-testid="`promo-row-${p.id}`"
      >
        <header class="pc-head">
          <span class="kind-chip">{{ p.kind === 'scenario' ? '场景' : '用例集' }}</span>
          <span class="src mono" :title="p.sourceId">{{ p.sourceId }}</span>
          <span class="status-badge" :class="p.status">{{ STATUS_LABEL[p.status] }}</span>
        </header>
        <div class="pc-meta">
          <span>冲突 <b class="mono" :class="{ 'conflict-n': p.conflicts.length }">{{ p.conflicts.length || '—' }}</b> 项</span>
          <span v-if="p.createdAt">提交于 {{ shortDateTime(p.createdAt) }}</span>
          <span v-if="p.resolution?.decidedAt">处理于 {{ shortDateTime(p.resolution.decidedAt) }}</span>
        </div>
        <p v-if="p.status === 'pending' && p.sourceChangedSinceApplication" class="changed">
          ⚠ 原件在申请后有过修改 —— 批准将按当前内容复制
        </p>
        <p v-if="p.status === 'rejected' && p.note" class="reject-note">驳回理由:{{ p.note }}</p>
        <footer v-if="p.status === 'pending'" class="pc-ops">
          <template v-if="canManage">
            <button type="button" class="act-btn primary"
                    :data-testid="`promo-approve-${p.id}`"
                    @click="openApprove(p)">✓ 通过 (裁决)…</button>
            <button type="button" class="act-btn danger"
                    :data-testid="`promo-reject-${p.id}`"
                    @click="openReject(p)">✕ 驳回</button>
          </template>
          <button v-else-if="p.applicantId === auth.currentUser?.id"
                  type="button" class="act-btn"
                  :data-testid="`promo-withdraw-${p.id}`"
                  @click="withdraw(p)">撤回</button>
          <span v-else class="muted">待管理员审批</span>
        </footer>
      </article>
    </div>
    <div v-else class="empty-cta">
      <p>{{ statusFilter
        ? '该状态下没有申请 —— 换个状态筛选看看'
        : '暂无加入申请 —— 在私有场景 / 用例集的「⋯」菜单里发起「加入项目」。' }}</p>
    </div>

    <!-- 裁决对话框:逐项选 采纳原件值(写入项目层)/ 保留项目层值 -->
    <Dialog :open="approving !== null" @update:open="approving = $event ? approving : null">
      <DialogContent class="max-w-[42.5rem]">
        <DialogHeader>
          <DialogTitle>裁决加入申请</DialogTitle>
        </DialogHeader>
        <p class="muted note">
          批准将以<b>当前原件内容</b>复制进项目;「采纳原件值」会把该路径写入项目层 carry。
        </p>
        <div class="lib-card conflict-card">
          <table class="slib-table">
            <thead><tr><th>服务</th><th>路径</th><th>原件值</th><th>项目层</th><th style="width:9.375rem">裁决</th></tr></thead>
            <tbody>
              <tr v-for="c in approving?.conflicts ?? []" :key="`${c.service}.${c.path}`">
                <td><span class="mono">{{ c.service }}</span></td>
                <td><span class="mono">{{ c.path }}</span></td>
                <td><span class="muted">{{ c.sourceValue ?? '(未设)' }}</span></td>
                <td><span class="muted">{{ c.projectValue ?? '(缺口)' }}</span></td>
                <td>
                  <select v-model="decisions[`${c.service}.${c.path}`]" class="field-select w-full">
                    <option value="source">采纳原件值</option>
                    <option value="project">保留项目层值</option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="approving = null">取消</Button>
          <Button data-testid="promo-approve-confirm" :disabled="busy" @click="approve">
            批准并复制
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 驳回对话框 -->
    <Dialog :open="rejecting !== null" @update:open="rejecting = $event ? rejecting : null">
      <DialogContent class="max-w-[26.25rem]">
        <DialogHeader>
          <DialogTitle>驳回加入申请</DialogTitle>
        </DialogHeader>
        <label class="field">
          <span class="field-label">理由(申请人可见)<span class="req">*</span></span>
          <textarea v-model="rejectReason" rows="3" class="field-area"
                    data-testid="promo-reject-reason" />
        </label>
        <DialogFooter>
          <Button variant="outline" @click="rejecting = null">取消</Button>
          <Button variant="destructive" data-testid="promo-reject-confirm"
                  :disabled="busy || !rejectReason.trim()" @click="reject">
            驳回
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  listPromotions, getPromotion, approvePromotion, rejectPromotion,
  withdrawPromotion, type PromotionOut,
} from '@/api/project-promotions'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { shortDateTime } from '@/utils/datetime'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{ projectId: number; canManage: boolean }>()
const auth = useAuthStore()

const STATUS_LABEL: Record<string, string> = {
  pending: '待审批', approved: '已批准', rejected: '已驳回', withdrawn: '已撤回',
}

const items = ref<PromotionOut[]>([])
const loading = ref(true)

// ── 原型 _4:状态筛选 Tab(客户端过滤,列表一次拉全)─────────────
const statusFilter = ref('')
const statusFilters = [
  { key: '', label: '全部申请' },
  { key: 'pending', label: '待审批' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已驳回' },
  { key: 'withdrawn', label: '已撤回' },
]
function statusCount(key: string): number {
  if (!key) return items.value.length
  return items.value.filter((p) => p.status === key).length
}
const shownItems = computed(() =>
  (statusFilter.value
    ? items.value.filter((p) => p.status === statusFilter.value)
    : items.value))
const busy = ref(false)
const approving = ref<PromotionOut | null>(null)
const decisions = ref<Record<string, 'source' | 'project'>>({})
const rejecting = ref<PromotionOut | null>(null)
const rejectReason = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = (await listPromotions(props.projectId)).items
    // pending 行拉详情补 sourceChangedSinceApplication
    await Promise.all(items.value
      .filter((p) => p.status === 'pending')
      .map(async (p) => {
        try {
          const d = await getPromotion(p.id)
          p.sourceChangedSinceApplication = d.sourceChangedSinceApplication
        } catch { /* 详情失败不阻塞列表 */ }
      }))
  } finally {
    loading.value = false
  }
}

function openApprove(p: PromotionOut): void {
  approving.value = p
  decisions.value = Object.fromEntries(
    p.conflicts.map((c) => [`${c.service}.${c.path}`, 'source' as const]))
}

async function approve(): Promise<void> {
  if (!approving.value) return
  busy.value = true
  try {
    const p = approving.value
    await approvePromotion(p.id, p.conflicts.map((c) => ({
      service: c.service, path: c.path,
      use: decisions.value[`${c.service}.${c.path}`] ?? 'source',
      sourceValue: c.sourceValue,
    })))
    toast.success('已批准并复制进项目')
    approving.value = null
    await load()
  } catch (e) {
    toast.error(String((e as Error).message ?? e))
  } finally {
    busy.value = false
  }
}

function openReject(p: PromotionOut): void {
  rejecting.value = p
  rejectReason.value = ''
}

async function reject(): Promise<void> {
  if (!rejecting.value) return
  busy.value = true
  try {
    await rejectPromotion(rejecting.value.id, rejectReason.value.trim())
    toast.success('已驳回')
    rejecting.value = null
    await load()
  } catch (e) {
    toast.error(String((e as Error).message ?? e))
  } finally {
    busy.value = false
  }
}

async function withdraw(p: PromotionOut): Promise<void> {
  const ok = await confirmAction(
    `撤回「${p.sourceId}」的加入申请?`,
    '撤回申请',
    { confirmButtonText: '撤回' },
  )
  if (!ok) return
  busy.value = true
  try {
    await withdrawPromotion(p.id)
    toast.success('已撤回申请')
    await load()
  } catch (e) {
    toast.error(String((e as Error).message ?? e))
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 0.75rem; }
.muted { color: var(--sl-ink-3); font-size: 0.78125rem; }
.mono { font-family: var(--font-mono, monospace); }

/* ── 原型 _4 · 说明头 ─────────────────────────────────────────── */
.promo-head {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.ph-icon {
  flex: none;
  width: 2.25rem; height: 2.25rem;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
  color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border-radius: 0.5rem;
}
.ph-title { font-size: 0.9375rem; font-weight: 600; color: var(--sl-ink); }
.ph-main p { margin: 0.125rem 0 0; font-size: 0.75rem; color: var(--sl-ink-3); line-height: 1.5; }
.ph-main b { color: var(--sl-ink-2); }

/* ── 状态筛选 Tab(原型 _4)────────────────────────────────────── */
.promo-toolbar { display: flex; align-items: center; gap: 0.625rem; }
.status-tabs {
  display: flex;
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  overflow: hidden;
  flex-wrap: wrap;
}
.stab {
  padding: 0.375rem 0.6875rem;
  font-size: 0.78125rem;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--sl-ink-2);
  border-right: 1px solid var(--sl-line);
  white-space: nowrap;
}
.stab:last-child { border-right: none; }
.stab:hover { color: var(--sl-ink); }
.stab.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }
.stn {
  margin-left: 0.25rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
  font-variant-numeric: tabular-nums;
}
.stab.on .stn { color: var(--sl-accent); }
.stn.alert { color: var(--sl-bad); font-weight: 700; }

/* ── 审批卡片流(原型 _4)──────────────────────────────────────── */
.promo-list { display: flex; flex-direction: column; gap: 0.625rem; }
.promo-card {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.75rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.pc-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.src {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  font-size: 0.78125rem;
  color: var(--sl-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-meta {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
  font-variant-numeric: tabular-nums;
}
.changed { margin: 0; color: var(--sl-warn); font-size: 0.71875rem; }
.reject-note { margin: 0; color: var(--sl-bad); font-size: 0.71875rem; }
.pc-ops { display: flex; align-items: center; gap: 0.375rem; margin-top: 0.25rem; }

.kind-chip {
  font-size: 0.6875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--soft-neutral-bg);
  color: var(--color-text-strong);
  border: 1px solid var(--sl-line);
  white-space: nowrap;
}
.conflict-n { font-weight: 700; color: var(--sl-warn); }

.status-badge {
  font-size: 0.71875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--soft-neutral-bg);
  color: var(--sl-ink-2);
}
.status-badge.pending { background: var(--sl-warn-soft); color: var(--sl-warn); }
.status-badge.approved { background: var(--sl-ok-soft); color: var(--sl-ok); }
.status-badge.rejected { background: var(--sl-bad-soft); color: var(--sl-bad); }

.act-btn {
  height: 1.6875rem;
  padding: 0 0.625rem;
  margin-right: 0.375rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.act-btn:hover { border-color: var(--sl-accent); color: var(--sl-accent); }
.act-btn.primary { color: var(--sl-accent); border-color: var(--sl-accent); }
.act-btn.primary:hover { background: var(--sl-accent-soft); }
.act-btn.danger { color: var(--sl-bad); border-color: var(--sv-bad-line, var(--sl-bad)); }
.act-btn.danger:hover { background: var(--sl-bad-soft); }

.note { margin: 0 0 0.375rem; }
.conflict-card { --lib-card-max: 16.25rem; }

.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-select {
  height: 2rem;
  padding: 0 0.5rem;
  font-size: 0.78125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  outline: none;
}
.field-area {
  padding: 0.4375rem 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
  resize: none;
}
.field-area:focus { border-color: var(--sl-accent); }
</style>
