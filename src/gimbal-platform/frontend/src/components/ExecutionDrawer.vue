<!-- ExecutionDrawer.vue — Spec-2 §4.5 E 快速执行抽屉 v2
     - Header: case 元数据条（name / id / 模块 / 作者 / tags chips）
     - Body: 分段（执行控制 / 凭证注入 / 环境）+ 快捷预设（N×parallel）
     - Footer: 取消 / ▶ 开始执行

     设计要点：左侧栏用竖向 accent 强调，分组标题用 caps + emoji 提高扫读速度。
-->
<template>
  <el-drawer
    :model-value="modelValue"
    direction="rtl"
    size="520px"
    :close-on-click-modal="false"
    :with-header="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <section class="exdraw">
      <!-- ─── Header ──────────────────────────────────────── -->
      <header class="exdraw-head">
        <div class="exdraw-head-bar" aria-hidden="true"></div>
        <div class="exdraw-head-body">
          <div class="exdraw-head-eyebrow">
            <span class="exdraw-head-eyebrow-dot"></span>
            用例执行 · {{ caseSummary?.module || '未分类' }}
          </div>
          <h3 class="exdraw-head-title">{{ caseName }}</h3>
          <div class="exdraw-head-meta">
            <code class="exdraw-case-id">{{ caseId }}</code>
            <span class="exdraw-head-author">
              <span class="exdraw-head-author-label">作者</span>
              <strong>{{ authorLabel }}</strong>
            </span>
            <span v-if="caseSummary?.priority" class="priority-pill" :class="`priority-${caseSummary.priority}`">
              P{{ caseSummary.priority }}
            </span>
          </div>
          <div v-if="caseTags.length" class="exdraw-tags">
            <TagPill v-for="t in caseTags" :key="t" :label="t" tone="accent" />
          </div>
        </div>
        <button class="exdraw-close" type="button" aria-label="关闭" @click="close">
          ×
        </button>
      </header>

      <!-- ─── Body ───────────────────────────────────────── -->
      <el-form
        ref="formRef"
        class="exdraw-form"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent
      >
        <!-- ▸ Preset chips -->
        <div class="exdraw-presets">
          <span class="exdraw-presets-label">快速预设</span>
          <div class="exdraw-presets-chips">
            <button
              v-for="p in PRESETS"
              :key="p.id"
              type="button"
              class="exdraw-chip"
              :class="{ active: activePreset === p.id }"
              @click="applyPreset(p.id)"
            >{{ p.label }}</button>
          </div>
        </div>

        <!-- ▸ 执行控制 -->
        <section class="exdraw-section">
          <h4 class="exdraw-section-title">
            <span class="exdraw-section-bullet" aria-hidden="true">⚡</span>
            执行控制
          </h4>
          <div class="exdraw-grid-2">
            <el-form-item label="执行次数" prop="n_runs">
              <el-input-number v-model="form.n_runs" :min="1" :max="1000" style="width:100%" />
            </el-form-item>
            <el-form-item label="并发度" prop="parallel">
              <el-input-number v-model="form.parallel" :min="1" :max="200" style="width:100%" />
            </el-form-item>
          </div>
        </section>

        <!-- ▸ 凭证注入 -->
        <section class="exdraw-section">
          <h4 class="exdraw-section-title">
            <span class="exdraw-section-bullet" aria-hidden="true">🔐</span>
            凭证注入
          </h4>
          <el-form-item label="合并策略" prop="merge_policy">
            <el-radio-group v-model="form.merge_policy" class="exdraw-merge">
              <el-radio-button value="origin">origin · 不注入</el-radio-button>
              <el-radio-button value="override">override · 替换</el-radio-button>
              <el-radio-button value="merge">merge · 合并</el-radio-button>
              <el-radio-button value="append">append · 追加</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="执行用认证" prop="exec_auth_alias">
            <el-select
              v-model="form.exec_auth_alias"
              multiple
              collapse-tags
              collapse-tags-tooltip
              :disabled="form.merge_policy === 'origin'"
              :placeholder="
                form.merge_policy === 'origin'
                  ? 'origin 模式下不注入凭证，使用 yaml 默认 Config.users'
                  : authsLoading
                    ? '正在从认证管理加载…'
                    : authsList.length
                      ? '选择 auth session（注入到 Config.users）'
                      : '尚无认证，请前往 「认证管理」 创建'
              "
              style="width:100%"
              :loading="authsLoading"
              :no-data-text="
                authsLoading
                  ? '加载中…'
                  : '尚无认证 · 前往 认证管理 创建'
              "
            >
              <el-option
                v-for="a in authsList"
                :key="a.id"
                :value="a.alias"
                :label="`${a.alias} · ${a.username} · ${a.token_type}`"
              />
            </el-select>

            <div
              v-if="form.merge_policy !== 'origin' && !authsLoading && authsList.length === 0"
              class="exdraw-auths-empty"
            >
              <div class="exdraw-auths-empty-body">
                <span class="exdraw-auths-empty-icon" aria-hidden="true">🔐</span>
                <div class="exdraw-auths-empty-text">
                  <strong>还没有认证</strong>
                  <span>认证来自「认证管理」页面 · 你自己的凭证池</span>
                </div>
                <el-button
                  type="primary"
                  size="small"
                  class="exdraw-auths-empty-cta"
                  @click="goToAuths"
                >
                  前往认证管理 →
                </el-button>
              </div>
            </div>

            <div
              v-else-if="form.merge_policy !== 'origin' && authsList.length > 0"
              class="exdraw-auths-hint"
            >
              <span class="exdraw-auths-hint-dot" aria-hidden="true"></span>
              共 {{ authsList.length }} 条认证从 <code>认证管理</code> 自动加载
            </div>
          </el-form-item>
        </section>

        <!-- ▸ 环境 -->
        <section class="exdraw-section">
          <h4 class="exdraw-section-title">
            <span class="exdraw-section-bullet" aria-hidden="true">🌱</span>
            环境
          </h4>
          <div class="exdraw-grid-2">
            <el-form-item label="环境" prop="env">
              <el-select v-model="form.env" style="width:100%">
                <el-option label="dev" value="dev" />
                <el-option label="prod" value="prod" />
              </el-select>
            </el-form-item>
            <el-form-item label="提单号前缀" prop="prefix">
              <el-input
                v-model="form.prefix"
                placeholder="例 BIZ2024（留空不注入）"
              />
            </el-form-item>
          </div>
        </section>

        <!-- ▸ 步骤选框 (gimbal run show + --step-to) -->
        <section class="exdraw-section">
          <h4 class="exdraw-section-title">
            <span class="exdraw-section-bullet" aria-hidden="true">🛑</span>
            步骤选框
          </h4>

          <el-form-item label="执行范围" prop="step_to">
            <el-popover
              v-model:visible="pickerOpen"
              placement="bottom-start"
              :width="420"
              trigger="click"
              popper-class="exdraw-step-popover"
            >
              <template #reference>
                <el-button
                  class="exdraw-step-trigger"
                  :disabled="!showData || showLoading"
                >
                  <span class="exdraw-step-trigger-icon" aria-hidden="true">{{ form.step_to === null ? '◯' : '●' }}</span>
                  <span class="exdraw-step-trigger-label">{{ stepTriggerLabel }}</span>
                  <span class="exdraw-step-trigger-count" v-if="showData">· {{ stepCountText }} 步</span>
                  <span class="exdraw-step-trigger-caret" aria-hidden="true">▾</span>
                </el-button>
              </template>

              <div v-loading="showLoading" class="exdraw-step-popover-body">
                <button
                  type="button"
                  class="exdraw-step-row exdraw-step-row-all"
                  :class="{ active: form.step_to === null }"
                  @click="pickStep(null)"
                >
                  <span class="exdraw-step-row-radio" aria-hidden="true">{{ form.step_to === null ? '●' : '○' }}</span>
                  <span class="exdraw-step-row-idx">all</span>
                  <span class="exdraw-step-row-desc">全部执行（{{ stepCountText }} 步）</span>
                </button>
                <div class="exdraw-step-divider"></div>
                <div class="exdraw-step-scroll">
                  <button
                    v-for="s in showData?.steps ?? []"
                    :key="s.index"
                    type="button"
                    class="exdraw-step-row"
                    :class="{ active: form.step_to === s.index }"
                    :title="`#${s.index} · ${s.api?.method ?? ''} ${s.api?.path ?? ''}`"
                    @click="pickStep(s.index)"
                  >
                    <span class="exdraw-step-row-radio" aria-hidden="true">{{ form.step_to === s.index ? '●' : '○' }}</span>
                    <span class="exdraw-step-row-idx">{{ s.index }}</span>
                    <span class="exdraw-step-row-desc">{{ s.description || '—' }}</span>
                  </button>
                </div>
              </div>
            </el-popover>

            <div class="exdraw-step-hint">
              <span v-if="form.step_to === null">不限步数（按用例默认执行）</span>
              <span v-else>执行到第 {{ form.step_to + 1 }} 步后停止（halt <code>--step-to {{ form.step_to }}</code>）</span>
            </div>
            <div class="exdraw-step-meta">
              共 {{ stepCountText }} 步（0-based）。<code>--step-from</code> 暂未暴露（gimbal 阶段 2 引入 StepResolver 后生效）。
            </div>
          </el-form-item>
        </section>

        <!-- ▸ 命令行覆盖（仅 admin 可见） -->
        <section v-if="isAdmin" class="exdraw-section exdraw-section-admin">
          <h4 class="exdraw-section-title">
            <span class="exdraw-section-bullet" aria-hidden="true">$_</span>
            执行命令（admin 可编辑）
            <el-tag
              v-if="commandLineDirty"
              type="warning"
              size="small"
              class="exdraw-section-tag"
            >已修改</el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
              class="exdraw-section-tag"
            >默认</el-tag>
          </h4>
          <p class="exdraw-cmd-hint">
            一行一项 argv；留空走默认命令（<code>gimbal run launch &lt;yaml&gt; [--step-to N]</code>），
            输入任何内容即视为覆盖并原样下发。
            admin 自定义 argv 时后端 <b>不会</b>自动追加 <code>--step-to</code> —
            如需请在 textarea 内手动添加。
          </p>
          <el-input
            v-model="commandLineText"
            type="textarea"
            :autosize="{ minRows: 5, maxRows: 10 }"
            placeholder="留空走默认命令；输入任意内容即覆盖 argv（每行一项）"
            spellcheck="false"
            class="exdraw-cmd-textarea"
            @input="onCommandLineEdit"
          />
          <div class="exdraw-cmd-actions">
            <el-button link size="small" @click="resetCommandLine">
              重置为默认
            </el-button>
          </div>
        </section>
      </el-form>

      <!-- ─── Footer ─────────────────────────────────────── -->
      <footer class="exdraw-foot">
        <span class="exdraw-foot-hint">
          <span class="exdraw-foot-hint-dot" aria-hidden="true"></span>
          将创建 {{ form.n_runs }} 个 run · 最大并发 {{ form.parallel }}
        </span>
        <div class="exdraw-foot-buttons">
          <el-button @click="close">取消</el-button>
          <el-button
            type="primary"
            :loading="submitting"
            class="exdraw-launch"
            @click="submit"
          >
            <span class="exdraw-launch-icon" aria-hidden="true">▶</span>
            开始执行
          </el-button>
        </div>
      </footer>
    </section>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useExecutionsStore } from '@/stores/executions'
import { useCasesStore } from '@/stores/cases'
import TagPill from '@/components/TagPill.vue'
import type { CaseShow, CaseSummary } from '@/api/cases'

const props = defineProps<{
  modelValue: boolean
  caseId: string
  caseName: string
  caseSummary?: CaseSummary | null
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  submitted: [executionId: number]
}>()

const router = useRouter()
const userAuthStore = useAuthStore()
const authStore = useAuthSessionsStore()
const execStore = useExecutionsStore()
const casesStore = useCasesStore()

const isAdmin = computed(() => userAuthStore.isAdmin)

const formRef = ref<FormInstance | null>(null)
const submitting = ref(false)
const authsLoading = ref(false)
const activePreset = ref<string | null>(null)

// ── gimbal run show (step picker) ─────────────────────────────
const showData = ref<CaseShow | null>(null)
const showLoading = ref(false)
const pickerOpen = ref(false)
const stepTriggerLabel = computed(() => {
  if (form.step_to === null) return '全部执行'
  return `执行到第 ${form.step_to + 1} 步`
})
const stepCountText = computed(() => showData.value?.step_count ?? 0)

async function loadShow() {
  // 缓存命中时 store 直接返回,无网络开销 —— 这里只判 showData 即可
  // (避免 in-flight 锁造成重新打开抽屉不刷新)。
  if (showData.value) return
  showLoading.value = true
  try {
    const data = await casesStore.fetchShow(props.caseId)
    showData.value = data
  } catch {
    // Non-fatal: the drawer still submits without step_to.  Errors are
    // surfaced via casesStore.showError for callers that want to render
    // them; we just disable the picker in the meantime.
    showData.value = null
  } finally {
    showLoading.value = false
  }
}

function pickStep(idx: number | null) {
  form.step_to = idx
  pickerOpen.value = false
}

// Admin-only: editable view of the subprocess argv.  When the textarea
// is empty, the backend's default argv is used (gimbal run launch
// <yaml> [--step-to N]); once the admin types anything the textarea
// is sent verbatim as the override.
//
// We deliberately do NOT pre-populate the textarea with a placeholder
// path (e.g. "src/.../exec_<executionId>_<idx>.yaml") — that path is
// a *runtime* path the backend fills in.  A non-empty textarea is
// the explicit signal that the operator wants full control.
const commandLineText = ref('')
const commandLineDirty = ref(false)

function onCommandLineEdit() {
  // The textarea is "dirty" iff it has any non-whitespace content.
  commandLineDirty.value = commandLineText.value.trim().length > 0
}

function resetCommandLine() {
  commandLineText.value = ''
  commandLineDirty.value = false
}

const form = reactive({
  prefix: '',
  n_runs: 1,
  parallel: 1,
  // ``origin`` 是 UI 概念,提交时翻译成 ``inject_credentials: false``。
  // 后端 schema 里 ``MergePolicy`` 不含 'origin',所以前端在本地拓宽联合。
  merge_policy: 'origin' as 'override' | 'merge' | 'append' | 'origin',
  exec_auth_alias: [] as string[],
  env: 'dev',
  // 0-based inclusive halt index for ``gimbal run launch --step-to <N>``.
  // ``null`` = "run all steps" (legacy / default).  Submitted to backend
  // as ``step_to`` in ExecutionCreateIn.
  step_to: null as number | null,
})

const rules = {
  n_runs: [{ required: true, message: '执行次数必填', trigger: 'blur' }],
  parallel: [{ required: true, message: '并发度必填', trigger: 'blur' }],
  step_to: [
    {
      validator: (_rule: unknown, value: unknown, callback: (err?: Error) => void) => {
        if (value === null || value === undefined) return callback()
        const max = (showData.value?.step_count ?? 0) - 1
        if (typeof value !== 'number' || value < 0 || value > max) {
          return callback(new Error(`step_to 必须在 0..${max} 之间`))
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const PRESETS = [
  { id: 'smoke', label: '🔥 烟囱 · 1/1', n: 1, p: 1 },
  { id: 'mini', label: '🌤 小批量 · 5/3', n: 5, p: 3 },
  { id: 'load', label: '📈 压测 · 50/10', n: 50, p: 10 },
]

function applyPreset(id: string) {
  const p = PRESETS.find((x) => x.id === id)
  if (!p) return
  form.n_runs = p.n
  form.parallel = p.p
  activePreset.value = id
}

watch(
  () => [form.n_runs, form.parallel],
  ([n, p]) => {
    const hit = PRESETS.find((x) => x.n === n && x.p === p)
    activePreset.value = hit ? hit.id : null
  },
)

// Re-prime the textarea every time the drawer opens so the default
// reflects the latest form (env, …) edits.  Resetting `Dirty` here
// covers the edge case where user opens, edits env, but never edits
// the command line.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    commandLineText.value = ''
    commandLineDirty.value = false
    // 重置 step_to —— 每次重新打开抽屉都从 "全部执行" 起步,
    // 避免上次会话遗留的状态污染本次提交。
    form.step_to = null
  },
)
// The textarea is the source of truth once the operator has typed
// anything.  Re-priming it on env/step_to changes would clobber their
// in-flight override, so the watchers below only clear the flag
// (visually reflecting "still using default") without touching the
// textarea content.

// 切到 origin 时清空 alias,避免"已勾选凭证但策略是不注入"的不一致状态。
// 切回 override/merge/append 时 alias 仍为空,需要用户重新选 —— 这是
// origin 语义的正确表现(不注入 = 不需要凭证)。
watch(
  () => form.merge_policy,
  (p) => {
    if (p === 'origin' && form.exec_auth_alias.length > 0) {
      form.exec_auth_alias = []
    }
  },
)

const authsList = computed(() => authStore.list)
const caseTags = computed<string[]>(() => props.caseSummary?.tags ?? [])
const authorLabel = computed(() => {
  const a = props.caseSummary?.author
  return a || '—'
})

watch(
  () => props.modelValue,
  async (open) => {
    if (open) await loadDrawerData()
  },
)

/**
 * First-open bootstrap.  Idempotent: skipping on cached auths / cached
 * show data avoids the network roundtrip on re-opens.  Called from
 * both the ``modelValue`` watcher (subsequent opens) and ``onMounted``
 * (first mount, where modelValue may already be true).
 */
async function loadDrawerData() {
  if (authsList.value.length === 0) {
    authsLoading.value = true
    try {
      await authStore.fetchAll()
    } finally {
      authsLoading.value = false
    }
  }
  // 拉步骤描述(用于步骤选框)。已缓存时 fetchShow 立即返回。
  await loadShow()
}

function close() {
  emit('update:modelValue', false)
}

function goToAuths() {
  close()
  router.push('/auths')
}

async function submit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    // 4-option radio 的 'origin' 在后端拆成 inject_credentials=false;
    // 其余 3 个选项同时设置 inject_credentials=true + merge_policy=<value>。
    const isOrigin = form.merge_policy === 'origin'
    const ex = await execStore.create({
      case_id: props.caseId,
      n_runs: form.n_runs,
      parallel: form.parallel,
      env: form.env,
      prefix: form.prefix || undefined,
      exec_auth_alias: isOrigin ? [] : form.exec_auth_alias,
      merge_policy: isOrigin
        ? undefined
        : (form.merge_policy as 'override' | 'merge' | 'append'),
      inject_credentials: !isOrigin,
      // Admin-only override.  We send `undefined` when the textarea
      // matches the default so the executor builds the standard argv
      // server-side; sending it raw (including extra env flags the user
      // added) replaces the entire subprocess argv.
      command_line:
        isAdmin.value && commandLineDirty.value
          ? commandLineText.value
              .split('\n')
              .map((s) => s.trim())
              .filter((s) => s.length > 0)
          : undefined,
      // step_to is null when user picked "全部执行"; backend serializes
      // it as the literal null in ExecutionCreateIn → config_json omits
      // the key (legacy payload path).  Backend validates step_to <
      // step_count so the user can't sneak an out-of-range value past
      // the rules.validator.
      step_to: form.step_to,
    })
    ElMessage.success(`执行已创建 #${ex.id}`)
    emit('submitted', ex.id)
    close()
    router.push(`/executions/${ex.id}`)
  } catch {
    ElMessage.error(execStore.lastError || '创建失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  // 抽屉首次挂载时如果 modelValue 已经为 true（典型情况：父组件
  // 用 v-model 控制显示），watch 的回调只在 prop 变化时触发，所以
  // 这里也要主动拉一次。loadDrawerData 是幂等的，重复调用无副作用。
  if (props.modelValue) {
    await loadDrawerData()
  }
})
</script>

<style scoped>
.exdraw {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(180deg, #faf9ff 0%, #ffffff 80px);
}

/* ─── Header ─────────────────────────────────────────────── */
.exdraw-head {
  position: relative;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 22px 24px 18px 24px;
  background: #ffffff;
  border-bottom: 1px solid var(--color-border-tertiary);
}

.exdraw-head-bar {
  position: absolute;
  top: 14px;
  bottom: 14px;
  left: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--accent) 0%, #818cf8 100%);
  border-radius: 0 4px 4px 0;
}

.exdraw-head-body {
  flex: 1;
  min-width: 0;
}

.exdraw-head-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.exdraw-head-eyebrow-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--accent-soft);
}

.exdraw-head-title {
  margin: 6px 0 8px;
  color: var(--color-text-primary);
  font-size: 19px;
  font-weight: 700;
  line-height: 1.3;
}

.exdraw-head-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
}

.exdraw-case-id {
  padding: 2px 7px;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
  background: #f1f5f9;
  border-radius: 4px;
}

.exdraw-head-author {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-text-tertiary);
}

.exdraw-head-author-label {
  color: var(--color-text-tertiary);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.exdraw-head-author strong {
  color: var(--color-text-primary);
  font-weight: 600;
}

.priority-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 31px;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  border-radius: 10px;
}
.priority-1 { color: #991b1b; background: #fee2e2; }
.priority-2 { color: #9a3412; background: #ffedd5; }
.priority-3 { color: #5b21b6; background: #ede9fe; }

.exdraw-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 10px;
}

.exdraw-close {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-size: 22px;
  line-height: 1;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
}
.exdraw-close:hover,
.exdraw-close:focus-visible {
  color: var(--color-text-primary);
  background: var(--accent-soft);
  outline: none;
}

/* ─── Form / Sections ────────────────────────────────────── */
.exdraw-form {
  flex: 1;
  padding: 16px 24px 8px;
  overflow: auto;
}

.exdraw-presets {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 14px;
  background: #fff;
  border: 1px dashed var(--color-border-tertiary);
  border-radius: 8px;
}

.exdraw-presets-label {
  color: var(--color-text-secondary);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.exdraw-presets-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.exdraw-chip {
  padding: 4px 10px;
  color: var(--color-text-primary);
  font: inherit;
  font-size: 11.5px;
  background: var(--accent-soft);
  border: 1px solid transparent;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.exdraw-chip:hover {
  background: #dbe5ff;
}
.exdraw-chip.active {
  color: white;
  background: var(--accent);
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.exdraw-section {
  padding: 14px 14px 4px;
  margin-bottom: 10px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}

.exdraw-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.exdraw-section-bullet {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 4px;
}

.exdraw-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.exdraw-grid-2 :deep(.el-form-item) {
  margin-bottom: 12px;
}

.exdraw-section :deep(.el-form-item) {
  margin-bottom: 12px;
}

.exdraw-merge :deep(.el-radio-button__inner) {
  padding: 6px 12px;
  font-size: 12px;
}

.exdraw-auths-empty {
  margin-top: 8px;
  padding: 12px;
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
  border: 1px dashed #fed7aa;
  border-radius: 8px;
}

.exdraw-auths-empty-body {
  display: flex;
  gap: 10px;
  align-items: center;
}

.exdraw-auths-empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 16px;
  background: #ffedd5;
  border-radius: 50%;
  flex-shrink: 0;
}

.exdraw-auths-empty-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  min-width: 0;
  color: var(--color-text-primary);
  font-size: 12px;
}

.exdraw-auths-empty-text strong {
  color: #9a3412;
  font-size: 12.5px;
}

.exdraw-auths-empty-text span {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.exdraw-auths-empty-cta {
  flex-shrink: 0;
}

.exdraw-auths-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.exdraw-auths-hint-dot {
  width: 5px;
  height: 5px;
  background: var(--green);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.16);
}

.exdraw-auths-hint code {
  padding: 1px 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: var(--accent-soft);
  border-radius: 3px;
}

/* ─── Footer ─────────────────────────────────────────────── */
.exdraw-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 16px;
  background: #fafbff;
  border-top: 1px solid var(--color-border-tertiary);
}

.exdraw-foot-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 11.5px;
}

.exdraw-foot-hint-dot {
  width: 6px;
  height: 6px;
  background: var(--green);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.exdraw-foot-buttons {
  display: flex;
  gap: 8px;
}

.exdraw-launch {
  font-weight: 600;
}

.exdraw-launch-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-right: 4px;
  font-size: 9px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 999px;
}

:deep(.el-drawer__body) {
  padding: 0;
}

/* ─── Admin command-line override ────────────────────────── */
.exdraw-section-admin {
  background: #fff7ed;
  border-color: #fed7aa;
}

.exdraw-section-tag {
  margin-left: 8px;
}

.exdraw-cmd-hint {
  margin: 0 0 6px;
  color: var(--color-text-secondary);
  font-size: 11.5px;
  line-height: 1.45;
}
.exdraw-cmd-hint code {
  padding: 1px 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 3px;
}

.exdraw-cmd-textarea :deep(.el-textarea__inner) {
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--color-text-primary);
  background: #ffffff;
  border: 1px solid #fed7aa;
  border-radius: 6px;
}
.exdraw-cmd-textarea :deep(.el-textarea__inner:focus) {
  border-color: var(--accent);
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.exdraw-cmd-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

/* ── 步骤选框 (gimbal run show) ────────────────────────────── */
.exdraw-step-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  color: var(--color-text-primary);
  font: inherit;
  font-size: 12.5px;
  text-align: left;
  background: #ffffff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.exdraw-step-trigger:hover:not(:disabled),
.exdraw-step-trigger:focus-visible:not(:disabled) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  outline: none;
}
.exdraw-step-trigger:disabled {
  cursor: not-allowed;
  background: #f8fafc;
  color: var(--color-text-tertiary);
}
.exdraw-step-trigger-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--accent);
  font-size: 14px;
  flex-shrink: 0;
}
.exdraw-step-trigger-label {
  flex: 1;
  min-width: 0;
  font-weight: 500;
}
.exdraw-step-trigger-count {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
  flex-shrink: 0;
}
.exdraw-step-trigger-caret {
  color: var(--color-text-tertiary);
  font-size: 10px;
  flex-shrink: 0;
}

.exdraw-step-popover :deep(.el-popover__content) {
  padding: 8px !important;
}
.exdraw-step-popover-body {
  display: flex;
  flex-direction: column;
}
.exdraw-step-divider {
  height: 1px;
  margin: 4px 8px;
  background: var(--color-border-tertiary);
}
.exdraw-step-scroll {
  max-height: 320px;
  overflow-y: auto;
}
.exdraw-step-row {
  display: grid;
  grid-template-columns: 24px 50px 1fr;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px 10px;
  color: var(--color-text-primary);
  font: inherit;
  font-size: 12px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
}
.exdraw-step-row:hover {
  background: var(--accent-soft);
}
.exdraw-step-row.active {
  background: var(--accent-soft);
}
.exdraw-step-row-all {
  font-weight: 500;
  color: var(--color-text-secondary);
}
.exdraw-step-row-all.active {
  color: var(--accent);
}
.exdraw-step-row-radio {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  font-size: 12px;
  color: var(--accent);
}
.exdraw-step-row.active .exdraw-step-row-radio {
  color: var(--accent);
}
.exdraw-step-row:not(.active) .exdraw-step-row-radio {
  color: var(--color-text-tertiary);
}
.exdraw-step-row-idx {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-align: right;
}
.exdraw-step-row.active .exdraw-step-row-idx {
  color: var(--accent);
  font-weight: 600;
}
.exdraw-step-row-desc {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exdraw-step-hint {
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 11.5px;
}
.exdraw-step-hint code {
  padding: 1px 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: var(--accent-soft);
  border-radius: 3px;
}
.exdraw-step-meta {
  margin-top: 4px;
  color: var(--color-text-tertiary);
  font-size: 10.5px;
}
.exdraw-step-meta code {
  font-family: var(--font-mono);
}
</style>
