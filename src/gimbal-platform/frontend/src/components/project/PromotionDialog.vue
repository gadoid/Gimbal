<!-- PromotionDialog.vue — M2a S7.2「加入项目…」:析出分析 → 无冲突直通
     复制 / 有冲突提交申请。数据源:auth.projects(我所在的普通项目)。 -->
<template>
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="dialog" data-testid="promo-dialog">
      <header class="d-head">
        <h3>加入项目</h3>
        <button type="button" class="x" @click="$emit('close')">✕</button>
      </header>

      <p class="hint">
        {{ kind === 'scenario' ? '场景' : '用例集' }} <b>{{ sourceName }}</b>
        将复制进目标项目(原件保留在私有区,可继续使用)。
      </p>

      <label class="field">目标项目
        <select v-model="projectId" data-testid="promo-project" :disabled="busy">
          <option v-if="!memberProjects.length" value="" disabled>
            (没有可加入的项目 —— 须先是项目成员)
          </option>
          <option v-for="p in memberProjects" :key="p.id" :value="String(p.id)">
            {{ p.name }}({{ p.role === 'admin' ? '管理员' : '成员' }})
          </option>
        </select>
      </label>

      <template v-if="analysis">
        <div v-if="analysis.blockers.length" class="warn" data-testid="promo-blockers">
          <p><b>存在阻断项,不能发起:</b></p>
          <ul>
            <li v-for="b in analysis.blockers" :key="b.scenarioId">
              {{ b.scenarioId }} —
              {{ b.reason === 'missing' ? '成员场景已删除'
                : b.reason === 'in_other_project' ? '成员场景在其他项目'
                  : '不是你名下的场景' }}
            </li>
          </ul>
        </div>
        <template v-else>
          <div v-if="!analysis.conflicts.length" class="ok" data-testid="promo-clean">
            无冲突 —— 提交即复制进项目。
          </div>
          <template v-else>
            <p class="warn" data-testid="promo-conflicts">
              <b>{{ analysis.conflicts.length }} 项 carry 值在两区解析不同</b>
              —— 提交后转项目管理员审批:
            </p>
            <table class="tbl">
              <thead><tr><th>服务</th><th>路径</th><th>我的(私有区)</th><th>项目层</th></tr></thead>
              <tbody>
                <tr v-for="c in analysis.conflicts" :key="`${c.service}.${c.path}`">
                  <td>{{ c.service }}</td>
                  <td>{{ c.path }}</td>
                  <td>{{ c.sourceValue ?? '(未设)' }}</td>
                  <td>{{ c.projectValue ?? '(缺口)' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <p v-if="analysis.slots.length" class="muted">
            引用槽位:{{ analysis.slots.join('、') }}(凭证跟人走,进项目后成员各自绑定)
          </p>
        </template>
      </template>
      <p v-else-if="error" class="err" data-testid="promo-error">{{ error }}</p>

      <footer class="d-foot">
        <button type="button" class="btn" :disabled="busy" @click="$emit('close')">取消</button>
        <button
          type="button"
          class="btn primary"
          data-testid="promo-submit"
          :disabled="busy || !projectId || !analysis || analysis.blockers.length > 0"
          @click="submit"
        >{{ submitLabel }}</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  analyzePromotion, createPromotion, type PromotionAnalysis,
} from '@/api/project-promotions'
import { toast } from '@/utils/toast'

const props = defineProps<{
  open: boolean
  kind: 'scenario' | 'suite'
  sourceId: string
  sourceName: string
}>()
const emit = defineEmits<{ close: []; done: [] }>()

const auth = useAuthStore()
const projectId = ref('')
const analysis = ref<PromotionAnalysis | null>(null)
const busy = ref(false)
const error = ref('')

const memberProjects = computed(() =>
  (auth.projects ?? []).filter((p) => p.kind !== 'public'))

const submitLabel = computed(() => {
  if (!analysis.value) return '分析…'
  if (analysis.value.blockers.length) return '不可发起'
  return analysis.value.conflicts.length ? '提交申请' : '立即加入'
})

watch(() => props.open, async (open) => {
  projectId.value = memberProjects.value[0] ? String(memberProjects.value[0].id) : ''
  analysis.value = null
  error.value = ''
  if (open && memberProjects.value.length === 0) {
    error.value = '你还不是任何项目的成员 —— 请先让项目管理员把你加进项目'
  }
})

watch(projectId, async (pid) => {
  analysis.value = null
  error.value = ''
  if (!pid || !props.open) return
  busy.value = true
  try {
    analysis.value = await analyzePromotion(Number(pid), {
      kind: props.kind, sourceId: props.sourceId })
  } catch (e) {
    error.value = String((e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail?.message ?? (e as Error).message ?? e)
  } finally {
    busy.value = false
  }
})

async function submit(): Promise<void> {
  if (!projectId.value) return
  busy.value = true
  try {
    const out = await createPromotion(Number(projectId.value), {
      kind: props.kind, sourceId: props.sourceId })
    if (out.status === 'copied') {
      toast.success(`已复制进项目(副本:${out.copy?.scenarioId ?? out.copy?.suiteId})`)
    } else {
      toast.success('已提交加入申请,待项目管理员审批')
    }
    emit('done')
    emit('close')
  } catch (e) {
    error.value = String((e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail?.message ?? (e as Error).message ?? e)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgb(15 23 42 / 45%); display: flex; align-items: center; justify-content: center; z-index: 60; }
.dialog { background: #fff; border-radius: 10px; width: min(640px, 92vw); max-height: 84vh; overflow: auto; padding: 1rem 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }
.d-head { display: flex; align-items: center; justify-content: space-between; }
.d-head h3 { margin: 0; font-size: 1rem; }
.x { border: none; background: none; cursor: pointer; font-size: 0.9rem; color: #64748b; }
.hint { color: #475569; font-size: 0.85rem; margin: 0; }
.field { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; }
.field select { padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.tbl th, .tbl td { text-align: left; padding: 0.3rem 0.5rem; border-bottom: 1px solid #eef2f7; }
.ok { color: #15803d; font-size: 0.85rem; }
.warn { color: #b45309; font-size: 0.85rem; }
.warn ul { margin: 0.25rem 0 0 1rem; padding: 0; }
.err { color: #dc2626; font-size: 0.82rem; }
.muted { color: #94a3b8; font-size: 0.78rem; margin: 0; }
.d-foot { display: flex; justify-content: flex-end; gap: 0.5rem; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.35rem 0.9rem; background: #fff; cursor: pointer; font-size: 0.85rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn:disabled { opacity: 0.5; cursor: default; }
</style>
