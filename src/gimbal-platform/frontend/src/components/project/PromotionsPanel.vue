<!-- PromotionsPanel.vue — M2a S7.2 项目详情「加入申请」页签:
     项目管理员裁决(批准 = 逐项选 采纳原件值/保留项目层值,以批准那一刻
     的原件内容复制;驳回须理由);申请人可撤回自己的 pending。 -->
<template>
  <div class="panel" data-testid="prj-promotions">
    <div v-if="loading" class="muted">加载中…</div>
    <table v-else-if="items.length" class="tbl">
      <thead>
        <tr>
          <th style="width:70px">类型</th>
          <th>来源</th>
          <th style="width:80px" class="c-center">冲突</th>
          <th style="width:90px">状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in items" :key="p.id" :data-testid="`promo-row-${p.id}`">
          <td>{{ p.kind === 'scenario' ? '场景' : '用例集' }}</td>
          <td>
            <div class="src">{{ p.sourceId }}</div>
            <div v-if="p.status === 'pending' && p.sourceChangedSinceApplication"
                 class="changed">⚠ 原件在申请后有过修改 —— 批准将按当前内容复制</div>
            <div v-if="p.status === 'rejected'" class="muted">理由:{{ p.note }}</div>
          </td>
          <td class="c-center">{{ p.conflicts.length || '—' }}</td>
          <td><span class="badge" :class="p.status">{{ STATUS_LABEL[p.status] }}</span></td>
          <td>
            <template v-if="p.status === 'pending'">
              <template v-if="canManage">
                <button type="button" class="btn sm primary"
                        :data-testid="`promo-approve-${p.id}`"
                        @click="openApprove(p)">裁决…</button>
                <button type="button" class="btn sm danger"
                        :data-testid="`promo-reject-${p.id}`"
                        @click="openReject(p)">驳回</button>
              </template>
              <button v-else-if="p.applicantId === auth.currentUser?.id"
                      type="button" class="btn sm"
                      :data-testid="`promo-withdraw-${p.id}`"
                      @click="withdraw(p)">撤回</button>
              <span v-else class="muted">待管理员审批</span>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="muted">暂无加入申请 —— 在私有场景 / 用例集的「⋯」菜单里发起「加入项目」。</p>

    <!-- 裁决对话框:逐项选 采纳原件值(写入项目层)/ 保留项目层值 -->
    <div v-if="approving" class="overlay" @click.self="approving = null">
      <div class="dialog" data-testid="promo-approve-dialog">
        <h3>裁决加入申请</h3>
        <p class="muted">
          批准将以<b>当前原件内容</b>复制进项目;「采纳原件值」会把该路径写入项目层 carry。
        </p>
        <table class="tbl">
          <thead><tr><th>服务</th><th>路径</th><th>原件值</th><th>项目层</th><th style="width:150px">裁决</th></tr></thead>
          <tbody>
            <tr v-for="c in approving.conflicts" :key="`${c.service}.${c.path}`">
              <td>{{ c.service }}</td>
              <td>{{ c.path }}</td>
              <td>{{ c.sourceValue ?? '(未设)' }}</td>
              <td>{{ c.projectValue ?? '(缺口)' }}</td>
              <td>
                <select v-model="decisions[`${c.service}.${c.path}`]">
                  <option value="source">采纳原件值</option>
                  <option value="project">保留项目层值</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
        <footer class="foot">
          <button type="button" class="btn" @click="approving = null">取消</button>
          <button type="button" class="btn primary" data-testid="promo-approve-confirm"
                  :disabled="busy" @click="approve">批准并复制</button>
        </footer>
      </div>
    </div>

    <!-- 驳回对话框 -->
    <div v-if="rejecting" class="overlay" @click.self="rejecting = null">
      <div class="dialog" data-testid="promo-reject-dialog">
        <h3>驳回加入申请</h3>
        <label class="field">理由(申请人可见)
          <textarea v-model="rejectReason" rows="3" data-testid="promo-reject-reason" />
        </label>
        <footer class="foot">
          <button type="button" class="btn" @click="rejecting = null">取消</button>
          <button type="button" class="btn danger" data-testid="promo-reject-confirm"
                  :disabled="busy || !rejectReason.trim()" @click="reject">驳回</button>
        </footer>
      </div>
    </div>
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
    toast.error(String((e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail?.message ?? (e as Error).message ?? e))
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
.panel { display: flex; flex-direction: column; gap: 0.5rem; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.tbl th, .tbl td { text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.tbl th { background: #f8fafc; color: #64748b; font-weight: 500; }
.c-center { text-align: center !important; }
.src { font-weight: 500; }
.changed { color: #b45309; font-size: 0.74rem; }
.muted { color: #94a3b8; font-size: 0.8rem; }
.badge { font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; background: #f1f5f9; color: #475569; }
.badge.pending { background: rgb(245 158 11 / 12%); color: #b45309; }
.badge.approved { background: rgb(34 197 94 / 12%); color: #15803d; }
.badge.rejected { background: rgb(239 68 68 / 10%); color: #dc2626; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.danger { color: #dc2626; border-color: #fca5a5; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.btn:disabled { opacity: 0.5; }
.overlay { position: fixed; inset: 0; background: rgb(15 23 42 / 45%); display: flex; align-items: center; justify-content: center; z-index: 60; }
.dialog { background: #fff; border-radius: 10px; width: min(680px, 92vw); max-height: 84vh; overflow: auto; padding: 1rem 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }
.dialog h3 { margin: 0; font-size: 1rem; }
.field { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; }
.field textarea { padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.foot { display: flex; justify-content: flex-end; gap: 0.5rem; }
</style>
