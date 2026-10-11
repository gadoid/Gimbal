<template>
  <section class="slib">
    <PageHead
      icon="activity"
      title="适配中心"
      :subtitle="stepSubtitle"
    >
      <template #right>
        <Button
          v-if="step > 1"
          variant="outline"
          data-testid="adapt-back"
          @click="step--"
        >← 上一步</Button>
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
        <p class="c-head-desc">输入场景 ID 或从陈旧清单选择</p>
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
                    @click="scenarioId = s.scenario_id">
              <span class="mono">{{ s.scenario_id }}</span>
              <span class="stale-name">{{ s.name }}</span>
              <span class="stale-reason">{{ s.reasons.join(' · ') }}</span>
            </button>
          </div>
        </div>
        <Button
          :disabled="!scenarioId || !targetRevision"
          data-testid="adapt-next-compare"
          @click="goCompare"
        >比较差异 →</Button>
      </div>
    </div>

    <!-- ── Step 2：比较结果 ── -->
    <div v-if="step === 2" class="c-card">
      <div class="c-card-head">
        <h3>差异比较</h3>
        <p class="c-head-desc">{{ systemId }}: {{ targetRevision }} 与当前定义的差异</p>
      </div>
      <div v-if="comparing" class="af-loading">比较中…</div>
      <div v-else-if="diffResult" class="diff-result">
        <div v-if="diffResult.changed && Object.keys(diffResult.changed).length">
          <div class="mf-label">变更对象（{{ Object.keys(diffResult.changed).length }}）</div>
          <div v-for="(info, key) in diffResult.changed" :key="key" class="diff-item">
            <span class="mono">{{ key }}</span>
            <span v-if="info.parts" class="diff-parts">
              {{ Object.keys(info.parts).join(', ') }}
            </span>
          </div>
        </div>
        <div v-if="diffResult.added?.length">
          <div class="mf-label">新增（{{ diffResult.added.length }}）</div>
          <div v-for="a in diffResult.added" :key="a" class="diff-item add">
            <span class="mono">{{ a }}</span>
          </div>
        </div>
        <div v-if="diffResult.removed?.length">
          <div class="mf-label">移除（{{ diffResult.removed.length }}）</div>
          <div v-for="r in diffResult.removed" :key="r" class="diff-item del">
            <span class="mono">{{ r }}</span>
          </div>
        </div>
        <div v-if="!diffResult.changed?.length && !diffResult.added?.length
                    && !diffResult.removed?.length"
             class="af-empty">无差异——定义已与目标修订一致</div>
      </div>
      <Button
        v-if="diffResult && (diffResult.changed?.length || diffResult.added?.length)"
        data-testid="adapt-next-check"
        @click="goSaveCheck"
      >保存检查 →</Button>
    </div>

    <!-- ── Step 3：保存检查 ── -->
    <div v-if="step === 3" class="c-card">
      <div class="c-card-head">
        <h3>保存检查</h3>
        <p class="c-head-desc">目标修订试算——校验场景能否直接切换</p>
      </div>
      <div v-if="checking" class="af-loading">试算中…</div>
      <template v-else-if="checkResult">
        <div v-if="checkResult.ok" class="af-ok" data-testid="check-ok">
          ✅ 试算通过——场景可以直接切换到目标修订
        </div>
        <div v-else class="af-fail" data-testid="check-fail">
          ❌ 试算失败：{{ checkResult.error }}
        </div>
        <div v-if="checkResult.ok" class="save-modes">
          <Button data-testid="adapt-save-direct" @click="doSubmit('direct')">
            直接保存
          </Button>
          <Button variant="outline" data-testid="adapt-save-copy" @click="doSubmit('copy')">
            保存为副本
          </Button>
        </div>
        <div v-else class="af-hint">
          试算失败时：请在编排页手动修正后重试，或保存为副本后手动适配
        </div>
      </template>
    </div>

    <!-- ── Step 4：提交结果 ── -->
    <div v-if="step === 4 && submitResult" class="c-card">
      <div class="c-card-head">
        <h3>提交结果</h3>
      </div>
      <div v-if="submitResult.success" class="af-ok">
        ✅ {{ submitResult.save_mode === 'copy'
             ? `已保存为副本：${submitResult.new_scenario_id}`
             : `已直接保存到 ${submitResult.scenario_id}` }}
      </div>
      <div v-else class="af-fail">
        ❌ {{ submitResult.message || '提交失败' }}
      </div>
      <Button variant="outline" data-testid="adapt-restart" @click="reset">开始新适配</Button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  fetchStaleScenarios, compareRevisions, saveCheck, submitAdaptation,
} from '@/api/adaptationFlow'
import type { DiffResult, SaveCheckResult, SubmitResult } from '@/api/adaptationFlow'

const router = useRouter()
const stepLabels = ['选择', '比较', '检查', '提交']

const step = ref(1)
const scenarioId = ref('')
const targetRevision = ref('')
const systemId = computed(() => scenarioId.value.split('-')[0] || '')

const diffResult = ref<DiffResult | null>(null)
const checkResult = ref<SaveCheckResult | null>(null)
const submitResult = ref<SubmitResult | null>(null)

const comparing = ref(false)
const checking = ref(false)

const staleScenarios = ref<
  Array<{ scenario_id: string; name: string; reasons: string[] }>
>([])

const stepSubtitle = computed(() => {
  const labels = ['选择要适配的场景与目标版本', '查看定义差异',
                  '验证能否直接切换', '完成适配']
  return `步骤 ${step.value}/4：${labels[step.value - 1]}`
})

onMounted(async () => {
  try {
    staleScenarios.value = await fetchStaleScenarios()
  } catch { /* 静默降级 */ }
})

async function goCompare() {
  step.value = 2
  comparing.value = true
  diffResult.value = null
  try {
    diffResult.value = await compareRevisions(
      systemId.value, 'working', targetRevision.value)
  } catch (e) {
    console.warn('[AdaptationFlow] compare failed:', e)
    diffResult.value = { from: 'working', to: targetRevision.value,
                          added: [], removed: [], changed: {} }
  } finally {
    comparing.value = false
  }
}

async function goSaveCheck() {
  step.value = 3
  checking.value = true
  checkResult.value = null
  try {
    checkResult.value = await saveCheck(
      scenarioId.value, targetRevision.value)
  } catch (e) {
    checkResult.value = { ok: false, error: String(e), code: 'network' }
  } finally {
    checking.value = false
  }
}

async function doSubmit(mode: 'direct' | 'copy') {
  try {
    submitResult.value = await submitAdaptation(
      scenarioId.value, [], targetRevision.value, mode)
    step.value = 4
  } catch (e) {
    submitResult.value = {
      success: false, save_mode: mode, message: String(e),
    }
    step.value = 4
  }
}

function reset() {
  step.value = 1
  scenarioId.value = ''
  targetRevision.value = ''
  diffResult.value = null
  checkResult.value = null
  submitResult.value = null
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
  font-size: 11px; font-weight: 600;
  border: 1px solid currentColor;
}
.af-step.active .af-step-num { background: #2f6fed; color: #fff; }
.af-step.done .af-step-num { background: #10b981; color: #fff; }

.af-loading { padding: 24px; text-align: center; color: #94a3b8; font-size: 13px; }
.af-empty { padding: 24px; text-align: center; color: #10b981; }
.af-ok { padding: 12px 16px; color: #10b981; font-size: 14px; }
.af-fail { padding: 12px 16px; color: #ef4444; font-size: 13px; }
.af-hint { padding: 8px 16px; color: #94a3b8; font-size: 12px; }

.diff-result { padding: 0 16px 12px; }
.diff-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px; margin: 2px 0;
  font-size: 12.5px; border-radius: 4px; background: #f8fafc;
}
.diff-item.add { background: #f0fdf4; }
.diff-item.del { background: #fef2f2; text-decoration: line-through; }
.diff-parts { color: #64748b; font-size: 11px; }

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

.mf-label {
  display: block; font-size: 11px; font-weight: 600;
  color: var(--color-text-secondary, #64748b); margin: 8px 0 4px;
}
.mf-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.mono { font-family: ui-monospace, monospace; }
</style>
