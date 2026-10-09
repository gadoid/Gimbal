<!-- SuiteRunPreflight.vue — 运行预检弹窗(原型 30,第 3 步接服务端)。
     摘要(单元数 · 预计 runs/上限 · 判定门数)+ 逐条预检:结论来自
     POST /suites/{id}/validate 的权威判定(执行器编译:环 / 输入无上游
     供给 / 同名歧义;逐成员 _precheck_one;认证别名按发起人;在途)。
     在途批次或运行 → 按钮变「查看」;超上限 → 禁用;带 units+action
     的警告可直达对应成员改选 / 改名。 -->
<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="pf-dialog" data-testid="suite-preflight">
      <DialogHeader>
        <DialogTitle>运行预检</DialogTitle>
      </DialogHeader>

      <div v-if="loading" class="pf-loading">检查中…</div>
      <template v-else-if="out">
        <p class="pf-summary" data-testid="suite-preflight-summary">
          {{ out.unitCount }} 个单元 · 预计 {{ out.estimatedRuns }} runs(上限 {{ out.runCap }})· 判定门 {{ out.gates }} 条
        </p>
        <p v-if="out.degraded" class="pf-degraded">
          执行器编译链路不可用,已降级为本地结构检查 —— 未校验变量
        </p>

        <ul class="pf-list">
          <li
            v-for="(it, i) in out.items"
            :key="i"
            class="pf-item"
            :class="it.level"
            :data-testid="`suite-preflight-item-${i}`"
          >
            <span class="pf-ico">{{ it.level === 'warn' ? '!' : it.level === 'error' ? '×' : '✓' }}</span>
            <span class="pf-msg">{{ it.message }}</span>
            <button
              v-if="it.units?.length && it.action"
              type="button"
              class="pf-go"
              :data-testid="`suite-preflight-go-${i}`"
              @click="$emit('locate', it.units![0])"
            >{{ it.action === 'map' ? '去改名' : '去改选' }}</button>
          </li>
        </ul>
      </template>
      <div v-else-if="failed" class="pf-loading">
        预检服务不可用 —— 可直接发起(运行侧仍有同口径校验)
      </div>

      <DialogFooter>
        <button type="button" class="btn-ghost" @click="$emit('update:open', false)">取消</button>
        <button
          v-if="inFlightBatch"
          type="button" class="btn-primary"
          data-testid="suite-preflight-view"
          @click="viewInFlight"
        >查看</button>
        <button
          v-else
          type="button" class="btn-primary"
          data-testid="suite-preflight-run"
          :disabled="!canRun || running"
          @click="$emit('run')"
        >{{ running ? '发起中…' : '开始运行' }}</button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { validateSuite, type ValidateOut } from '@/api/suites'

const props = defineProps<{
  open: boolean
  suiteId: number
  running?: boolean
  /** 外层已有最新 detail 时传入(仅用于打开时跳过重复拉取,不必须)。 */
  detail0?: unknown
}>()

defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'run'): void
  (e: 'locate', scenarioId: string): void
}>()

const loading = ref(false)
const failed = ref(false)
const out = ref<ValidateOut | null>(null)

const inFlightBatch = computed(() => out.value?.inFlight?.batchId ?? null)
/** 服务端结论 ok 才放行;预检服务本身不可用时不拦(运行侧仍有同口径校验)。 */
const canRun = computed(() =>
  out.value ? out.value.ok && !inFlightBatch.value : failed.value)

async function check(): Promise<void> {
  loading.value = true
  failed.value = false
  out.value = null
  try {
    out.value = await validateSuite(props.suiteId)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function viewInFlight(): void {
  const b = inFlightBatch.value
  if (b) window.location.assign(`/executions?batch_id=${encodeURIComponent(b)}`)
}

watch(() => props.open, (v) => { if (v) void check() })
</script>

<style scoped>
.pf-dialog { display: flex; flex-direction: column; gap: 12px; max-width: 540px; }
.pf-loading { padding: 18px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.pf-summary { margin: 0; font-size: 13px; }
.pf-degraded {
  margin: 0; font-size: 12px; color: #b45309;
  padding: 6px 10px; border-radius: 8px;
  background: rgb(245 158 11 / 8%); border: 1px solid rgb(245 158 11 / 35%);
}
.pf-list {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 6px;
  max-height: 320px; overflow-y: auto;
}
.pf-item {
  display: flex; align-items: center; gap: 8px; font-size: 12.5px;
  padding: 6px 10px; border-radius: 8px;
  border: 1px solid rgb(100 116 139 / 18%); background: rgb(100 116 139 / 4%);
}
.pf-item.ok { border-color: rgb(34 197 94 / 35%); background: rgb(34 197 94 / 6%); }
.pf-item.warn { border-color: rgb(245 158 11 / 40%); background: rgb(245 158 11 / 7%); }
.pf-item.error { border-color: rgb(220 38 38 / 35%); background: rgb(220 38 38 / 6%); }
.pf-ico { flex: none; width: 16px; text-align: center; font-weight: 700; }
.pf-item.ok .pf-ico { color: #15803d; }
.pf-item.warn .pf-ico { color: #b45309; }
.pf-item.error .pf-ico { color: #dc2626; }
.pf-msg { flex: 1; min-width: 0; }
.pf-go {
  flex: none; font-size: 11.5px; padding: 3px 9px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft); border: 1px solid var(--accent-soft-border);
}
.btn-ghost, .btn-primary {
  padding: 7px 16px; font-size: 13px; border-radius: 8px; cursor: pointer;
}
.btn-ghost { border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit; }
.btn-primary { font-weight: 600; border: none; color: #fff; background: #4338ca; }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
</style>
