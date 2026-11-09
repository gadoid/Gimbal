<!-- EffectivePreviewDialog.vue — S7.3 生效预览(S5 resolve_effective_config
     的展示面):本次执行将生效的 环境/服务地址/槽位绑定/carry 逐值带来源。
     双宿主:项目配置页签(选场景)与运行配置面板(场景/方案/环境已定,
     透传上下文)。不含明文凭证(后端契约)。 -->
<template>
  <div v-if="open" class="overlay" @click.self="$emit('close')">
    <div class="dialog wide" data-testid="preview-dialog">
      <header class="d-head">
        <h3>生效预览</h3>
        <button type="button" class="x" @click="$emit('close')">✕</button>
      </header>

      <div class="body">
        <div v-if="pickable" class="field">
          <label>场景
            <select v-model="pickedId" data-testid="preview-scenario" @change="run">
              <option value="" disabled>选择场景…</option>
              <option v-for="s in scenarios" :key="s.id" :value="s.id">
                {{ s.name }}({{ s.id }})
              </option>
            </select>
          </label>
        </div>
        <p v-else class="ctx muted">
          场景 <b>{{ scenarioId }}</b><template v-if="schemeId"> · 方案 {{ schemeId }}</template>
        </p>

        <p v-if="error" class="err" data-testid="preview-error">{{ error }}</p>
        <p v-else-if="loading" class="muted" data-testid="preview-loading">解析中…</p>

        <template v-else-if="cfg">
          <!-- 环境:来源 = 链路哪一环(explicit>scheme>project>preference>default) -->
          <section>
            <h4>执行环境</h4>
            <p v-if="cfg.env" data-testid="preview-env">
              <b>{{ envName(cfg.env.environmentId) }}</b>
              <span class="src">{{ envSourceLabel(cfg.env.environmentSource) }}</span>
            </p>
            <p v-else class="muted" data-testid="preview-env-none">未选定环境(地址走场景声明/别名旧链)</p>
          </section>

          <!-- 缺槽:执行会被拒(S5 预检失败即中止)— 置顶提示 -->
          <p v-if="cfg.missingAuths.length" class="warn" data-testid="preview-missing">
            <b>缺槽位绑定:</b>{{ cfg.missingAuths.join('、') }} —— 执行将被拒绝,请先在「认证管理」绑定
          </p>

          <!-- 服务地址:②场景声明 vs ③部署地址 -->
          <section v-if="Object.keys(cfg.services).length">
            <h4>服务地址</h4>
            <table class="tbl" data-testid="preview-services">
              <thead><tr><th>服务</th><th>地址</th><th style="width:130px">来源</th></tr></thead>
              <tbody>
                <tr v-for="(svc, key) in cfg.services" :key="key">
                  <td>{{ key }}<span v-if="svc.alias" class="muted"> · {{ svc.alias }}</span></td>
                  <td class="mono">{{ svc.url || '—' }}</td>
                  <td><span class="src">{{ PREVIEW_SOURCE_LABELS[svc.source] ?? svc.source }}</span></td>
                </tr>
              </tbody>
            </table>
          </section>

          <!-- 槽位绑定:解析到哪条绑定(id/系统/环境/默认) -->
          <section v-if="Object.keys(cfg.auths).length">
            <h4>槽位绑定</h4>
            <table class="tbl" data-testid="preview-auths">
              <thead><tr><th>槽位</th><th style="width:80px">绑定 #</th><th>系统</th><th style="width:90px">环境</th><th style="width:70px">默认</th></tr></thead>
              <tbody>
                <tr v-for="(a, slot) in cfg.auths" :key="slot">
                  <td>{{ slot }}</td>
                  <td>#{{ a.bindingId }}</td>
                  <td>{{ a.system || '—' }}</td>
                  <td>{{ a.envId != null ? envName(a.envId) : '不限' }}</td>
                  <td>{{ a.isDefault ? '是' : '否' }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <!-- carry 逐值:服务键 → path → {value, source(层·键)} -->
          <section v-if="carryRows.length">
            <h4>carry 注入值</h4>
            <table class="tbl" data-testid="preview-carry">
              <thead><tr><th>服务</th><th>字段路径</th><th>值</th><th style="width:120px">来源</th></tr></thead>
              <tbody>
                <tr v-for="r in carryRows" :key="`${r.service}.${r.path}`">
                  <td>{{ r.service }}</td>
                  <td class="mono">{{ r.path }}</td>
                  <td class="mono">{{ fmt(r.value) }}</td>
                  <td><span class="src">{{ carrySourceLabel(r.source) }}</span></td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="Object.keys(cfg.carryDefaults).length">
            <h4>carry 默认值(未命中服务/别名键的兜底)</h4>
            <table class="tbl" data-testid="preview-carry-defaults">
              <thead><tr><th>字段路径</th><th>值</th><th style="width:120px">来源</th></tr></thead>
              <tbody>
                <tr v-for="(d, path) in cfg.carryDefaults" :key="path">
                  <td class="mono">{{ path }}</td>
                  <td class="mono">{{ fmt(d.value) }}</td>
                  <td><span class="src">{{ carrySourceLabel(d.source) }}</span></td>
                </tr>
              </tbody>
            </table>
          </section>

          <p v-if="!hasContent" class="muted" data-testid="preview-empty">
            该场景无服务地址 / 槽位 / carry 注入。
          </p>
        </template>
      </div>

      <footer class="d-foot">
        <button type="button" class="btn" data-testid="preview-rerun" :disabled="loading" @click="run">重新解析</button>
        <button type="button" class="btn primary" @click="$emit('close')">关闭</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * EffectivePreviewDialog —— S7.3 生效预览。
 * 数据面 = api/runs previewEffectiveConfig(POST /runs/preview)。
 * pickable = 未固定场景Id 时由内部选(父级传 scenarios 列表);
 * 固定形态(运行面板)透传 schemeId/environmentId/serviceBindings。
 */
import { computed, ref, watch } from 'vue'
import {
  previewEffectiveConfig, carrySourceLabel, PREVIEW_SOURCE_LABELS,
  type EffectiveConfigPreview,
} from '@/api/runs'

const props = defineProps<{
  open: boolean
  /** 固定场景(run 面板形态);缺省 = pickable(项目配置页形态) */
  scenarioId?: string
  scenarios?: Array<{ id: string; name: string }>
  schemeId?: string
  environmentId?: number | null
  serviceBindings?: Record<string, { alias: string }>
  /** 环境名映射(父级已拉过环境列表时透传,避免重复请求) */
  envNames?: Record<number, string>
}>()

defineEmits<{ close: [] }>()

const pickable = computed(() => !props.scenarioId)
const pickedId = ref('')
const loading = ref(false)
const error = ref('')
const cfg = ref<EffectiveConfigPreview | null>(null)

const carryRows = computed(() => {
  if (!cfg.value) return []
  const out: Array<{ service: string; path: string; value: unknown; source: string }> = []
  for (const [svc, paths] of Object.entries(cfg.value.carry)) {
    for (const [path, v] of Object.entries(paths)) {
      out.push({ service: svc, path, value: v.value, source: v.source })
    }
  }
  return out
})

const hasContent = computed(() => {
  const c = cfg.value
  return !!c && (
    Object.keys(c.services).length > 0
    || Object.keys(c.auths).length > 0
    || carryRows.value.length > 0
    || Object.keys(c.carryDefaults).length > 0)
})

function envName(id: number | null): string {
  if (id == null) return '—'
  return props.envNames?.[id] ?? `环境 #${id}`
}

function envSourceLabel(source: string | null): string {
  if (!source) return ''
  return PREVIEW_SOURCE_LABELS[source] ?? source
}

function fmt(v: unknown): string {
  if (v == null) return 'null'
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}

async function run(): Promise<void> {
  const sid = props.scenarioId ?? pickedId.value
  if (!sid) return
  loading.value = true
  error.value = ''
  try {
    cfg.value = await previewEffectiveConfig({
      scenarioId: sid,
      schemeId: props.schemeId,
      environmentId: props.environmentId ?? undefined,
      serviceBindings: props.serviceBindings,
    })
  } catch (e) {
    cfg.value = null
    error.value = String((e as Error)?.message ?? e)
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (o) => {
  if (o) {
    // 固定场景 → 直接解析;选场景形态 → 等用户选
    if (props.scenarioId) void run()
  } else {
    cfg.value = null
    error.value = ''
  }
})
watch(() => props.scenarioId, (sid) => {
  if (props.open && sid) void run()
})
</script>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgb(15 23 42 / 45%); display: flex; align-items: center; justify-content: center; z-index: 60; }
.dialog { background: var(--color-bg, #fff); border-radius: 10px; width: min(560px, calc(100vw - 2rem)); max-height: min(80vh, 720px); display: flex; flex-direction: column; box-shadow: 0 20px 50px rgb(15 23 42 / 25%); }
.dialog.wide { width: min(720px, calc(100vw - 2rem)); }
.d-head { display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1.1rem; border-bottom: 1px solid #e2e8f0; }
.d-head h3 { margin: 0; font-size: 1rem; }
.x { border: none; background: none; cursor: pointer; color: #64748b; font-size: 1rem; }
.body { padding: 0.9rem 1.1rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.9rem; }
.d-foot { display: flex; justify-content: flex-end; gap: 0.5rem; padding: 0.7rem 1.1rem; border-top: 1px solid #e2e8f0; }
.field label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.85rem; color: #475569; }
select { padding: 6px 8px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); background: transparent; }
.ctx { font-size: 0.85rem; }
section h4 { margin: 0 0 0.4rem; font-size: 0.85rem; color: #334155; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.tbl th, .tbl td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid #eef2f7; }
.tbl th { color: #64748b; font-weight: 500; }
.mono { font-family: ui-monospace, monospace; font-size: 0.78rem; }
.muted { color: #94a3b8; font-size: 0.82rem; }
.src { display: inline-block; margin-left: 6px; font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.warn { background: rgb(245 158 11 / 10%); border: 1px solid rgb(245 158 11 / 40%); color: #92400e; border-radius: 8px; padding: 0.5rem 0.7rem; font-size: 0.82rem; margin: 0; }
.err { color: #dc2626; font-size: 0.82rem; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.35rem 0.9rem; background: #fff; cursor: pointer; font-size: 0.85rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
