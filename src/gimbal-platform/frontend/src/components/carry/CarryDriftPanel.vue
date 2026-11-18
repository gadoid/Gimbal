<!-- CarryDriftPanel.vue — M2a S7.6:分层 carry 漂移面板(项目配置页 /
     我的配置复用)。数据 = getDrift(target);勾选生成作用域化的 carry 批
     (openCarryBatch(service, target)),跳批次详情页应用。分权后端同
     carry 写面:项目层 = 项目管理员,个人层 = 本人。
     §8.9:instanceEnvId 非空的行 = 实例档(系统×环境)diff —— 只读
     呈现,不进适配批(实例键适配 op 为后续缺口)。 -->
<template>
  <div class="cdp" :data-testid="`carry-drift-${tid}`">
    <div class="head">
      <span class="label">{{ title }}</span>
      <span v-if="drift.length" class="count mono">{{ total }}</span>
      <span class="actions">
        <button
          type="button" class="btn" :disabled="loading"
          data-action="drift-refresh" @click="load"
        >{{ loading ? '刷新中…' : '刷新' }}</button>
        <button
          type="button" class="btn primary" data-action="drift-generate"
          :disabled="!canGenerate || generating"
          @click="generate"
        >{{ generating ? '生成中…' : `生成批(${checked.length})` }}</button>
      </span>
    </div>

    <p v-if="!plateReachable" class="warn" data-testid="drift-unreachable">
      plate 目录不可达,漂移数据可能失真 —— 已禁用勾选与批生成
    </p>
    <p v-else-if="loading" class="hint">加载中…</p>
    <p v-else-if="loadFailed" class="hint">加载失败,请刷新</p>
    <p v-else-if="drift.length === 0" class="hint">暂无 carry 数据</p>
    <div v-else class="list">
      <div v-for="s in drift" :key="s.instanceEnvId ? `${s.service}#${s.instanceEnvId}` : s.service"
           class="svc" data-testid="drift-svc">
        <div class="name mono">
          {{ s.service }}<template v-if="s.instanceEnvId"> · 实例#{{ s.instanceEnvId }}</template>
        </div>
        <template v-if="s.instanceEnvId">
          <!-- §8.9 实例档行:只读呈现(实例键暂不进适配批,维护在
               服务注册的实例抽屉「carry 默认值(实例)」) -->
          <p v-if="!hasCarryDrift(s)" class="ok">✓ 无漂移</p>
          <div v-else class="checks">
            <p v-if="s.orphaned.length" class="check">面外字段:{{ s.orphaned.join('、') }}</p>
            <p v-if="s.uncovered.length" class="check">未覆盖:{{ s.uncovered.join('、') }}</p>
            <p class="hint">实例档(系统 × 环境)维护在服务注册的实例配置,不进适配批</p>
          </div>
        </template>
        <template v-else>
          <p v-if="!hasCarryDrift(s)" class="ok">✓ 无漂移</p>
          <div v-else class="checks">
            <label v-for="opt in driftCheckOptions(s)" :key="opt.key" class="check">
              <input v-model="checked" type="checkbox" :value="opt.key" :disabled="!plateReachable" />
              {{ opt.text }}
            </label>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CarryDriftPanel —— S7.6 分层漂移面板。
 * 复用 AdaptationCenter 的 carry-drift 纯函数(勾选/回读/plateReachable
 * 硬契约);批生成 = 逐服务 openCarryBatch(service, target) + createOp,
 * 成功后路由到批次详情页(/adaptations/batches/:id,成员可达自己的层批)。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDrift, type ScopeTarget, type ServiceDrift } from '@/api/carry'
import * as api from '@/api/adaptations'
import {
  canGenerateCarryBatch, checkedServices, driftCheckOptions,
  hasCarryDrift, parseCarryChecked,
} from '@/utils/carry-drift'
import { toast } from '@/utils/toast'

const props = defineProps<{
  title: string
  target: ScopeTarget
  tid: string
}>()

const router = useRouter()
const drift = ref<ServiceDrift[]>([])
const plateReachable = ref(true)
const loading = ref(false)
const loadFailed = ref(false)
const generating = ref(false)
const checked = ref<string[]>([])

const total = computed(() =>
  drift.value.reduce((n, s) =>
    n + s.orphaned.length + s.uncovered.length + s.renamedSuggestions.length, 0))
const canGenerate = computed(() =>
  canGenerateCarryBatch(plateReachable.value, checked.value.length))

async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    const report = await getDrift(props.target)
    plateReachable.value = report.plateReachable
    drift.value = report.services
    checked.value = []
  } catch (e) {
    loadFailed.value = true
    toast.error(api.errMsg(e, 'carry 漂移拉取失败'))
  } finally {
    loading.value = false
  }
}

async function generate(): Promise<void> {
  const items = parseCarryChecked(checked.value)
  if (!canGenerateCarryBatch(plateReachable.value, items.length)) return
  generating.value = true
  try {
    let lastBatchId = ''
    for (const svc of checkedServices(items)) {
      const detail = await api.openCarryBatch(svc, props.target)
      lastBatchId = detail.batchId
      for (const item of items) {
        if (item.service !== svc) continue
        await api.createOp(detail.batchId, {
          opType: item.opType, payload: item.payload,
        })
      }
    }
    checked.value = []
    toast.success('carry 批已生成')
    await router.push(`/adaptations/batches/${lastBatchId}`)
  } catch (e) {
    toast.error(api.errMsg(e, 'carry 批生成失败'))
  } finally {
    generating.value = false
  }
}

onMounted(() => { void load() })
</script>

<style scoped>
.cdp { display: flex; flex-direction: column; gap: 0.5rem; }
.head { display: flex; align-items: center; gap: 0.5rem; }
.label { font-size: 0.85rem; font-weight: 600; color: #334155; }
.count { font-size: 0.6875rem; color: var(--color-text-secondary); background: var(--soft-neutral-bg); border-radius: 0.25rem; padding: 0.0625rem 0.375rem; }
.actions { margin-left: auto; display: flex; gap: 0.25rem; }
.hint { margin: 0; color: var(--color-text-secondary); font-size: 0.8rem; }
.warn { margin: 0; color: var(--sl-warn); font-size: 0.8rem; background: rgb(245 158 11 / 10%); border: 1px solid rgb(245 158 11 / 40%); border-radius: 0.375rem; padding: 0.375rem 0.625rem; }
.list { display: flex; flex-direction: column; gap: 0.6rem; }
.svc { border: 1px solid var(--color-border-tertiary); border-radius: 0.5rem; padding: 0.5rem 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
.name { font-size: 0.8rem; font-weight: 600; color: #1e293b; }
.ok { margin: 0; color: var(--sl-ok); font-size: 0.8rem; }
.checks { display: flex; flex-direction: column; gap: 0.125rem; }
.check { font-size: 0.8rem; color: #334155; display: flex; align-items: center; gap: 0.375rem; }
.btn { border: 1px solid var(--color-border-secondary); border-radius: 0.375rem; padding: 0.3rem 0.8rem; background: var(--c-surface); cursor: pointer; font-size: 0.8rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.mono { font-family: var(--font-mono, monospace); }
</style>
