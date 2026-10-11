<template>
  <section class="slib">
    <PageHead icon="activity" title="适配中心" :subtitle="stepSubtitle">
      <template #right>
        <Button v-if="step > 1 && step < 4" variant="outline"
                data-testid="adapt-back" @click="step--">← 上一步</Button>
      </template>
    </PageHead>

    <!-- ── 步骤指示器 ── -->
    <div class="af-steps" data-testid="adapt-steps">
      <div v-for="(label, i) in stepLabels" :key="label"
           class="af-step" :class="{ active: step === i + 1, done: step > i + 1 }">
        <span class="af-step-num">{{ i + 1 }}</span>
        <span class="af-step-label">{{ label }}</span>
      </div>
    </div>

    <!-- ── Step 1：选择场景与目标 ── -->
    <div v-if="step === 1" class="c-card">
      <div class="c-card-head">
        <h3>选择场景与目标版本</h3>
        <p class="c-head-desc">输入场景 ID 或从陈旧清单选择（Release §5.2 两类适配）</p>
      </div>
      <div class="c-form">
        <div class="mf-item">
          <span class="mf-label">场景 ID</span>
          <Input v-model="scenarioId" placeholder="sc-..." data-testid="adapt-scenario-id" />
        </div>
        <div class="mf-item">
          <span class="mf-label">目标修订</span>
          <Input v-model="targetRevision" placeholder="1.0#3（或 working）"
                 data-testid="adapt-target-revision" />
        </div>
        <div v-if="staleScenarios.length" class="mf-item">
          <span class="mf-label">陈旧清单（点击填入）</span>
          <div class="stale-list">
            <button v-for="s in staleScenarios" :key="s.scenario_id"
                    class="stale-item" data-testid="stale-item"
                    @click="pickStale(s)">
              <span class="mono">{{ s.scenario_id }}</span>
              <span class="stale-name">{{ s.name }}</span>
              <span class="stale-reason">{{ s.reasons.join(' · ') }}</span>
            </button>
          </div>
        </div>
        <Button :disabled="!scenarioId || !targetRevision" data-testid="adapt-next-compare"
                @click="goCompare">比较差异 →</Button>
      </div>
    </div>

    <!-- ── Step 2：比较结果 ── -->
    <div v-if="step === 2" class="c-card">
      <div class="c-card-head">
        <h3>差异比较与影响</h3>
        <p class="c-head-desc" v-if="compareResult">
          {{ compareResult.system }}：{{ compareResult.from }} → {{ compareResult.to }}
        </p>
      </div>
      <div v-if="comparing" class="af-loading">比较中…</div>
      <template v-else-if="compareResult">
        <!-- 三组影响（§5.3） -->
        <div class="groups" data-testid="adapt-groups">
          <div class="group g-direct">
            <div class="g-head">直接切换（{{ compareResult.groups.direct.length }}）</div>
            <p class="g-desc">接口结构未变或仅 binding 变化——只更新版本声明</p>
            <div v-for="d in compareResult.groups.direct" :key="d.step"
                 class="diff-item">步骤 {{ d.step + 1 }} · <span class="mono">{{ d.endpoint }}</span></div>
          </div>
          <div class="group g-field">
            <div class="g-head">字段级适配（{{ compareResult.groups.field.length }}）</div>
            <p class="g-desc">请求/响应声明变化——提交时起草字段级 op</p>
            <div v-for="f in compareResult.groups.field" :key="f.step" class="diff-item warn">
              步骤 {{ f.step + 1 }} · <span class="mono">{{ f.endpoint }}</span>
              <span class="diff-parts">{{ fieldDiffSummary(f.endpoint) }}</span>
            </div>
          </div>
          <div class="group g-struct" v-if="compareResult.groups.structure.length">
            <div class="g-head">结构级改造（{{ compareResult.groups.structure.length }}）</div>
            <p class="g-desc">接口在目标修订中已删除——需结构级改造或放弃该场景</p>
            <div v-for="st in compareResult.groups.structure" :key="st.step" class="diff-item del">
              步骤 {{ st.step + 1 }} · <span class="mono">{{ st.endpoint }}</span>
            </div>
          </div>
        </div>
        <!-- 声明级字段差异明细（R7） -->
        <div v-if="fieldDiffEntries.length" class="mf-item">
          <span class="mf-label">字段差异明细</span>
          <div v-for="(fd, endpoint) in fieldDiffEntries" :key="endpoint" class="fd-block">
            <div class="mono fd-ep">{{ endpoint }}</div>
            <span v-for="a in fd.added" :key="a" class="fd-chip add">+ {{ a }}</span>
            <span v-for="r in fd.removed" :key="r" class="fd-chip del">− {{ r }}</span>
            <span v-for="(c, p) in fd.changed" :key="p" class="fd-chip chg">~ {{ p }}</span>
          </div>
        </div>
        <Button data-testid="adapt-next-check" @click="goSaveCheck">保存检查 →</Button>
      </template>
    </div>

    <!-- ── Step 3：保存检查 ── -->
    <div v-if="step === 3" class="c-card">
      <div class="c-card-head">
        <h3>保存检查</h3>
        <p class="c-head-desc">目标修订试算（阻断）· 引用检查 · 保存方式</p>
      </div>
      <div v-if="checking" class="af-loading">试算中…</div>
      <template v-else-if="checkResult">
        <!-- ① 阻断项 -->
        <div v-if="checkResult.blocking_issues.length" class="af-fail" data-testid="check-fail">
          <div v-for="(i, idx) in checkResult.blocking_issues" :key="idx" class="issue-line">
            ❌ {{ i.message }}
          </div>
          <p class="af-hint">阻断项须在编排页修正后重试（§5.6 试算是提交唯一依据）</p>
        </div>
        <div v-else-if="unconfirmedReview" class="af-warn" data-testid="check-review">
          <div class="g-head">R14 评审项（{{ checkResult.review_items.length }}）</div>
          <div v-for="(r, idx) in checkResult.review_items" :key="idx" class="issue-line">
            ⚠ {{ r.message }}
          </div>
          <label class="confirm-row">
            <input v-model="reviewConfirmed" type="checkbox" data-testid="review-confirm" />
            我确认这些响应/提取路径变更可以接受
          </label>
        </div>
        <div v-else class="af-ok" data-testid="check-ok">
          ✅ 试算通过——场景可以切换到 {{ checkResult.to }}
        </div>

        <!-- ② 引用检查 -->
        <div v-if="checkResult.references.own.length
                    || checkResult.references.others.length" class="mf-item">
          <span class="mf-label">引用检查</span>
          <div class="issue-line" v-for="r in checkResult.references.own" :key="`o-${r.id}`">
            自己的{{ r.type === 'suite' ? '用例集' : '集成任务' }}：{{ r.name }}
          </div>
          <div class="issue-line warn" v-for="r in checkResult.references.others"
               :key="`t-${r.id}`">
            他人的{{ r.type === 'suite' ? '用例集' : '集成任务' }}：{{ r.name }}（直接保存将通知其所有者）
          </div>
        </div>

        <!-- ③ 保存方式（推荐高亮） -->
        <div v-if="!checkResult.blocking_issues.length && (!unconfirmedReview || reviewConfirmed)"
             class="save-modes" data-testid="save-modes">
          <Button data-testid="adapt-save-direct"
                  :variant="checkResult.recommendation === 'direct' ? 'default' : 'outline'"
                  @click="doSubmit('direct')">
            直接保存{{ checkResult.recommendation === 'direct' ? '（推荐）' : '' }}
          </Button>
          <Button data-testid="adapt-save-copy"
                  :variant="checkResult.recommendation === 'copy' ? 'default' : 'outline'"
                  @click="doSubmit('copy')">
            保存为副本{{ checkResult.recommendation === 'copy' ? '（推荐）' : '' }}
          </Button>
        </div>
      </template>
    </div>

    <!-- ── Step 4：提交结果 ── -->
    <div v-if="step === 4 && submitResult" class="c-card">
      <div class="c-card-head"><h3>提交结果</h3></div>
      <div v-if="submitResult.success" class="af-ok" data-testid="submit-ok">
        ✅ {{ submitResult.save_mode === 'copy'
             ? `已保存为副本：${submitResult.new_scenario_id}`
             : `已直接保存到 ${submitResult.scenario_id}` }}
        <span class="mono batch-id">（批次 {{ submitResult.batch_id }}）</span>
      </div>
      <div v-else class="af-fail">❌ {{ submitResult.message || '提交失败' }}</div>
      <Button variant="outline" data-testid="adapt-restart" @click="reset">开始新适配</Button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  fetchStaleScenarios, compareScenario, saveCheck, submitAdaptation,
} from '@/api/adaptationFlow'
import type { CompareResult, SaveCheckResult, SubmitResult } from '@/api/adaptationFlow'

const stepLabels = ['选择', '比较', '检查', '提交']

const step = ref(1)
const scenarioId = ref('')
const targetRevision = ref('')

const compareResult = ref<CompareResult | null>(null)
const checkResult = ref<SaveCheckResult | null>(null)
const submitResult = ref<SubmitResult | null>(null)
const reviewConfirmed = ref(false)

const comparing = ref(false)
const checking = ref(false)

const staleScenarios = ref<
  Array<{ scenario_id: string; name: string; reasons: string[] }>
>([])

const stepSubtitle = computed(() => {
  const labels = ['选择要适配的场景与目标版本', '查看定义差异与影响',
                  '验证能否直接切换', '完成适配']
  return `步骤 ${step.value}/4：${labels[step.value - 1]}`
})

const unconfirmedReview = computed(() =>
  !!checkResult.value?.review_items.length && !reviewConfirmed.value)

/** R7 字段差异明细:变更接口的 request 声明差异(响应差异随评审项走)。 */
const fieldDiffEntries = computed<Record<string, { added: string[];
  removed: string[]; changed: Record<string, unknown> }>>(() => {
  const out: Record<string, { added: string[]; removed: string[];
    changed: Record<string, unknown> }> = {}
  for (const [key, info] of Object.entries(compareResult.value?.diff.changed || {})) {
    const fd = (info.parts as Record<string, unknown> | undefined)?.request
    const diff = (fd as { field_diff?: { added: string[]; removed: string[];
      changed: Record<string, unknown> } } | undefined)?.field_diff
    if (diff && (diff.added.length || diff.removed.length
                 || Object.keys(diff.changed).length)) {
      out[key.replace('endpoint.', '')] = diff
    }
  }
  return out
})

function fieldDiffSummary(endpoint: string): string {
  const fd = fieldDiffEntries.value[endpoint]
  if (!fd) return ''
  const parts: string[] = []
  if (fd.added.length) parts.push(`+${fd.added.length}`)
  if (fd.removed.length) parts.push(`−${fd.removed.length}`)
  if (Object.keys(fd.changed).length) parts.push(`~${Object.keys(fd.changed).length}`)
  return parts.join(' ')
}

function pickStale(s: { scenario_id: string }): void {
  scenarioId.value = s.scenario_id
}

onMounted(async () => {
  try {
    staleScenarios.value = await fetchStaleScenarios()
  } catch { /* 静默降级:plate 不可达时清单空,手输场景 ID 仍可用 */ }
})

async function goCompare() {
  step.value = 2
  comparing.value = true
  compareResult.value = null
  try {
    compareResult.value = await compareScenario(
      scenarioId.value, targetRevision.value)
  } finally {
    comparing.value = false
  }
}

async function goSaveCheck() {
  step.value = 3
  checking.value = true
  checkResult.value = null
  reviewConfirmed.value = false
  try {
    checkResult.value = await saveCheck(
      scenarioId.value, targetRevision.value)
  } finally {
    checking.value = false
  }
}

async function doSubmit(mode: 'direct' | 'copy') {
  try {
    submitResult.value = await submitAdaptation(
      scenarioId.value, [], targetRevision.value, mode,
      reviewConfirmed.value)
  } catch (e) {
    submitResult.value = {
      success: false, save_mode: mode, message: String(e),
    }
  }
  step.value = 4
}

function reset() {
  step.value = 1
  scenarioId.value = ''
  targetRevision.value = ''
  compareResult.value = null
  checkResult.value = null
  submitResult.value = null
  reviewConfirmed.value = false
}
</script>

<style scoped>
.af-steps { display: flex; gap: 0; margin: 12px 0 16px; }
.af-step {
  flex: 1; display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; font-size: 12px; color: #94a3b8;
  border-bottom: 2px solid #e1e5eb;
}
.af-step.active { color: #2f6fed; border-bottom-color: #2f6fed; font-weight: 600; }
.af-step.done { color: #10b981; border-bottom-color: #10b981; }
.af-step-num {
  width: 20px; height: 20px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; border: 1px solid currentColor;
}
.af-step.active .af-step-num { background: #2f6fed; color: #fff; }
.af-step.done .af-step-num { background: #10b981; color: #fff; }

.af-loading { padding: 24px; text-align: center; color: #94a3b8; font-size: 13px; }
.af-empty { padding: 24px; text-align: center; color: #10b981; }
.af-ok { padding: 12px 16px; color: #10b981; font-size: 14px; }
.af-fail { padding: 12px 16px; color: #ef4444; font-size: 13px; }
.af-warn { padding: 12px 16px; color: #b45309; font-size: 13px;
           background: #fffbeb; border-radius: 6px; }
.af-hint { padding: 8px 16px; color: #94a3b8; font-size: 12px; }
.issue-line { padding: 2px 0; }
.issue-line.warn { color: #b45309; }
.confirm-row { display: flex; align-items: center; gap: 8px;
               padding: 8px 0 0; font-size: 13px; cursor: pointer; }

.groups { display: flex; flex-wrap: wrap; gap: 10px; padding: 0 16px 8px; }
.group { flex: 1 1 240px; border: 1px solid #e1e5eb; border-radius: 8px;
         padding: 10px 12px; }
.g-direct { border-color: #a7f3d0; }
.g-field { border-color: #fde68a; }
.g-struct { border-color: #fecaca; }
.g-head { font-size: 13px; font-weight: 600; margin-bottom: 2px; }
.g-desc { font-size: 11px; color: #94a3b8; margin: 0 0 6px; }

.diff-result { padding: 0 16px 12px; }
.diff-item {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 4px 8px; margin: 2px 0;
  font-size: 12.5px; border-radius: 4px; background: #f8fafc;
}
.diff-item.add { background: #f0fdf4; }
.diff-item.del { background: #fef2f2; }
.diff-item.warn { background: #fffbeb; }
.diff-parts { color: #64748b; font-size: 11px; }

.fd-block { padding: 4px 0; }
.fd-ep { font-size: 12px; font-weight: 600; margin-bottom: 2px; }
.fd-chip { display: inline-block; margin: 2px 4px 2px 0; padding: 1px 8px;
           border-radius: 10px; font-size: 11px; font-family: ui-monospace, monospace; }
.fd-chip.add { background: #f0fdf4; color: #15803d; }
.fd-chip.del { background: #fef2f2; color: #b91c1c; }
.fd-chip.chg { background: #eff6ff; color: #1d4ed8; }

.stale-list { display: flex; flex-direction: column; gap: 4px; }
.stale-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border: 1px solid #e1e5eb; border-radius: 6px;
  background: #fff; cursor: pointer; font-size: 12px;
  text-align: left; width: 100%;
}
.stale-item:hover { border-color: #2f6fed; }
.stale-name { color: #374151; font-weight: 500; }
.stale-reason { color: #f59e0b; font-size: 11px; }

.save-modes { display: flex; gap: 8px; padding: 8px 16px; }
.batch-id { font-size: 11px; color: #94a3b8; }

.mf-label {
  display: block; font-size: 11px; font-weight: 600;
  color: var(--color-text-secondary, #64748b); margin: 8px 0 4px;
}
.mf-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.mono { font-family: ui-monospace, monospace; }
</style>
