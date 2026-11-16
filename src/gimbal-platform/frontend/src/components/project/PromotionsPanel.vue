<!-- PromotionsPanel.vue — M2a S7.2 项目详情「加入申请」页签:
     项目管理员裁决(批准 = 逐项选 采纳原件值/保留项目层值,以批准那一刻
     的原件内容复制;驳回须理由);申请人可撤回自己的 pending。
     2026-11-16 重塑:表格落 .slib-table + 状态徽章令牌化;裁决/驳回自绘
     overlay → ui/Dialog;撤回走 confirmAction。 -->
<template>
  <div class="panel" data-testid="prj-promotions">
    <p v-if="loading" class="muted">加载中…</p>
    <div v-else-if="items.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:4.375rem">类型</th>
            <th>来源</th>
            <th style="width:5rem" class="c-center">冲突</th>
            <th style="width:5.625rem">状态</th>
            <th style="width:11.25rem">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in items" :key="p.id" :data-testid="`promo-row-${p.id}`">
            <td><span class="kind-chip">{{ p.kind === 'scenario' ? '场景' : '用例集' }}</span></td>
            <td>
              <div class="src mono">{{ p.sourceId }}</div>
              <div v-if="p.status === 'pending' && p.sourceChangedSinceApplication"
                   class="changed">⚠ 原件在申请后有过修改 —— 批准将按当前内容复制</div>
              <div v-if="p.status === 'rejected'" class="muted">理由:{{ p.note }}</div>
            </td>
            <td class="c-center"><span v-if="p.conflicts.length" class="mono conflict-n">{{ p.conflicts.length }}</span><span v-else class="muted">—</span></td>
            <td><span class="status-badge" :class="p.status">{{ STATUS_LABEL[p.status] }}</span></td>
            <td>
              <template v-if="p.status === 'pending'">
                <template v-if="canManage">
                  <button type="button" class="act-btn primary"
                          :data-testid="`promo-approve-${p.id}`"
                          @click="openApprove(p)">裁决…</button>
                  <button type="button" class="act-btn danger"
                          :data-testid="`promo-reject-${p.id}`"
                          @click="openReject(p)">驳回</button>
                </template>
                <button v-else-if="p.applicantId === auth.currentUser?.id"
                        type="button" class="act-btn"
                        :data-testid="`promo-withdraw-${p.id}`"
                        @click="withdraw(p)">撤回</button>
                <span v-else class="muted">待管理员审批</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-cta">
      <p>暂无加入申请 —— 在私有场景 / 用例集的「⋯」菜单里发起「加入项目」。</p>
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
import { onMounted, ref } from 'vue'
import {
  listPromotions, getPromotion, approvePromotion, rejectPromotion,
  withdrawPromotion, type PromotionOut,
} from '@/api/project-promotions'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{ projectId: number; canManage: boolean }>()
const auth = useAuthStore()

const STATUS_LABEL: Record<string, string> = {
  pending: '待审批', approved: '已批准', rejected: '已驳回', withdrawn: '已撤回',
}

const items = ref<PromotionOut[]>([])
const loading = ref(true)
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
.panel { display: flex; flex-direction: column; gap: 0.625rem; }
.muted { color: var(--sl-ink-3); font-size: 0.78125rem; }
.mono { font-family: var(--font-mono, monospace); }
.c-center { text-align: center !important; }

.src { font-weight: 600; font-size: 0.78125rem; color: var(--sl-ink); }
.changed { color: var(--sl-warn); font-size: 0.71875rem; }
.kind-chip {
  font-size: 0.6875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--soft-neutral-bg);
  color: var(--color-text-strong);
  border: 1px solid var(--sl-line);
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
