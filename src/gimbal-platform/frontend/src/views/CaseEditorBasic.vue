<!-- CaseEditorBasic.vue — 用例编辑 · 基础信息
     1:1 绑定场景 → 携带值覆盖（env / auth / retry / dataSetIds）
     底部调用 Plate /convert 预校验 → 显示校验状态徽章
-->
<template>
  <section class="case-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><Tickets /></el-icon>用例编辑</h2>
        <p>{{ caseId === 'new' ? '新建用例' : caseId }}</p>
      </div>
      <div class="header-actions">
        <el-button :icon="ArrowBack" @click="router.back()">返回</el-button>
        <el-button :loading="validating" plain :icon="Search" @click="onValidate">预校验 Scenario 草稿</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </div>
    </header>

    <!-- 场景绑定 banner -->
    <div v-if="scenario" class="bind-banner">
      <span class="lbl">绑定场景 (1:1)</span>
      <button class="scenario-link" @click="router.push(`/scenarios/${scenario.meta.scenarioId}/edit`)">
        {{ scenario.meta.name || scenario.meta.scenarioId }}
      </button>
      <span class="sid">{{ scenario.meta.scenarioId }}</span>
      <div class="sys-list">
        <SystemChip v-for="s in scenario.meta.system" :key="s" :sys="s" />
      </div>
    </div>

    <div class="body">
      <el-form :model="form" label-position="top" class="main">
        <h3>用例基础信息</h3>
        <el-form-item label="用例名">
          <el-input v-model="form.name" placeholder="order_create_正常路径" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <h3>执行覆盖（相对于场景）</h3>
        <div class="grid-2">
          <el-form-item label="执行环境">
            <el-input v-model="form.env" placeholder="test-env-A" />
          </el-form-item>
          <el-form-item label="认证会话">
            <el-input v-model="form.authName" placeholder="admin@fin" />
          </el-form-item>
          <el-form-item label="认证类型">
            <el-select v-model="form.authType">
              <el-option value="bearer"  label="bearer" />
              <el-option value="cookie"  label="cookie" />
              <el-option value="oauth2"  label="oauth2" />
              <el-option value="apikey"  label="apikey" />
            </el-select>
          </el-form-item>
          <el-form-item label="重试次数">
            <el-input-number v-model="form.retryMaxAttempts" :min="0" :max="10" />
          </el-form-item>
          <el-form-item label="重试间隔(ms)">
            <el-input-number v-model="form.retryIntervalMs" :min="100" :step="100" />
          </el-form-item>
        </div>

        <el-form-item label="绑定数据集 (1:N · 留空表示不跑)">
          <el-select v-model="form.dataSetIds" multiple placeholder="选择数据集">
            <el-option
              v-for="d in scenarioDataSets"
              :key="d.datasetId"
              :value="d.datasetId"
              :label="`${d.name} (${d.rowCount} 条)`"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 右侧校验状态 -->
      <aside class="side">
        <h3>校验状态</h3>
        <div v-if="!validationResult" class="valid-empty">
          点击右上角 <code>预校验 Scenario 草稿</code> 调用 Plate /convert
        </div>
        <div v-else class="valid-result" :class="validationResult.ok ? 'ok' : 'fail'">
          <div class="valid-head">
            <StatusBadge :status="validationResult.ok ? 'PASS' : 'FAIL'" />
            <span class="v-title">{{ validationResult.ok ? '草稿可通过 /convert' : '草稿未通过 /convert' }}</span>
          </div>
          <div v-if="validationResult.errors?.length" class="valid-errors">
            <div v-for="(err, i) in validationResult.errors" :key="i" class="err">
              <code>{{ err.path }}</code>
              <span>{{ err.message }}</span>
            </div>
          </div>
        </div>

        <h3 style="margin-top: 24px;">草稿预览</h3>
        <pre class="preview">{{ JSON.stringify(draftPreview, null, 2) }}</pre>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowBack, Search, Tickets } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SystemChip from '@/components/SystemChip.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { createCase } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()

const caseId = (route.params.caseId as string) || 'new'
const queryScenarioId = (route.query.scenarioId as string) || ''

const saving = ref(false)
const validating = ref(false)
const validationResult = ref<{ ok: boolean; errors?: any[] } | null>(null)

const form = reactive({
  name: '',
  description: '',
  env: 'test-env-A',
  authName: 'admin@fin',
  authType: 'bearer' as 'bearer' | 'cookie' | 'oauth2' | 'apikey',
  retryMaxAttempts: 0,
  retryIntervalMs: 500,
  dataSetIds: [] as string[],
})

const scenarioId = computed(() => {
  const c = store.caseById(caseId)
  return c?.scenarioId || queryScenarioId
})

const scenario = computed(() => store.scenarioById(scenarioId.value))
const scenarioDataSets = computed(() =>
  store.dataSets.filter((d) => {
    const c = store.caseById(caseId)
    return c && d.caseId === c.caseId
  }),
)

const draftPreview = computed(() => ({
  scenarioId: scenarioId.value,
  case: {
    caseId,
    name: form.name,
    env: form.env,
    auth: { name: form.authName, type: form.authType },
    retry: { maxAttempts: form.retryMaxAttempts, intervalMs: form.retryIntervalMs },
    dataSetIds: form.dataSetIds,
  },
}))

onMounted(async () => {
  try {
    if (!store.scenarios.length) await store.fetchScenarios()
    if (!store.cases.length)      await store.fetchCases()
    await store.fetchDataSets()

    if (caseId !== 'new') {
      const c = store.caseById(caseId)
      if (c) {
        form.name = c.name
        form.description = c.description ?? ''
        form.env = c.env
        form.authName = c.auth.name
        form.authType = c.auth.type
        form.retryMaxAttempts = c.retry?.maxAttempts ?? 0
        form.retryIntervalMs  = c.retry?.intervalMs ?? 500
        form.dataSetIds = [...c.dataSetIds]
      }
    }
  } catch (e) {
    showError('加载', undefined, (e as Error).message)
  }
})

async function onSave() {
  if (caseId === 'new') {
    if (!scenarioId.value) {
      ElMessage.warning('缺少 scenarioId — 请从场景的「③ 用例管理」进入新建用例')
      return
    }
    if (!form.name.trim()) {
      ElMessage.warning('请填写用例名')
      return
    }
    saving.value = true
    try {
      // P0 修复：新建用例此前是死表单（仅弹提示不落库）。
      // 后端 createCase (POST /cases) 已存在，此处直接接通。
      // 注意两点：
      // 1. caseId 必须带 `case-` 前缀 — 后端 v3_case_id 路由转换器的
      //    regex 是 (?:case|sc)-[a-z0-9-]+，无前缀的 id 创建后无法
      //    再被 GET/PATCH/DELETE 命中（会落到 legacy 路由 404）。
      // 2. updatedAt 不能传空字符串 — 后端 updated_at: datetime|None
      //    校验会 422。createdBy 由服务端无条件覆盖，传空串无害。
      const slug = form.name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '') || 'case'
      const suffix = Date.now().toString(36).slice(-4)
      const created = await createCase({
        caseId: `case-${slug}-${suffix}`,
        scenarioId: scenarioId.value,
        name: form.name.trim(),
        description: form.description,
        env: form.env,
        auth: { name: form.authName, type: form.authType },
        retry: { maxAttempts: form.retryMaxAttempts, intervalMs: form.retryIntervalMs },
        dataSetIds: form.dataSetIds,
        createdBy: '',
        updatedAt: undefined as unknown as string,
      })
      ElMessage.success(`已创建：${created.caseId}`)
      await store.fetchCases()
      // router.replace 到同路由不同参数不会重挂载本组件（caseId 常量
      // 会停留在 'new'，再次点保存会重复创建）— 整页跳转强制重挂载。
      window.location.assign(`/cases/${created.caseId}/edit`)
    } catch (e) {
      showError('创建用例', undefined, (e as Error).message)
    } finally {
      saving.value = false
    }
    return
  }
  saving.value = true
  try {
    await store.saveCase(caseId, {
      name: form.name,
      description: form.description,
      env: form.env,
      auth: { name: form.authName, type: form.authType },
      retry: { maxAttempts: form.retryMaxAttempts, intervalMs: form.retryIntervalMs },
      dataSetIds: form.dataSetIds,
    })
    ElMessage.success('已保存')
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onValidate() {
  validating.value = true
  try {
    validationResult.value = await store.previewPlate({
      meta: scenario.value?.meta ?? {
        scenarioId: scenarioId.value, name: '', description: '', module: '',
        priority: 2, author: '', owner: '', tags: [], system: [],
      },
      steps: scenario.value?.steps ?? [],
      caseMeta: {
        env: form.env,
        auth: { name: form.authName, type: form.authType },
        dataSetIds: form.dataSetIds,
      },
    })
    if (validationResult.value.ok) ElMessage.success('预校验通过')
  } catch (e) {
    validationResult.value = { ok: false, errors: [{ path: '*', message: (e as Error).message }] }
  } finally {
    validating.value = false
  }
}
</script>

<style scoped>
.case-editor {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p  { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.header-actions { display: flex; gap: 8px; }

.bind-banner {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
  border-radius: 8px;
}
.bind-banner .lbl {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: var(--accent);
  text-transform: uppercase;
}
.scenario-link {
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  background: #fff;
  border: 1px solid var(--accent-soft-border);
  border-radius: 6px;
  cursor: pointer;
}
.scenario-link:hover { border-color: var(--accent); }
.sid {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-text-secondary);
}
.sys-list { display: flex; gap: 4px; margin-left: auto; }

.body {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
}
.main, .side {
  padding: 22px 24px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.main h3, .side h3 {
  margin: 18px 0 12px;
  font-size: 13px;
  font-weight: 700;
}
.main h3:first-child, .side h3:first-child { margin-top: 0; }
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.valid-empty {
  padding: 16px;
  font-size: 11px;
  color: var(--color-text-secondary);
  background: #f8fafc;
  border: 1px dashed var(--color-border-tertiary);
  border-radius: 6px;
}
.valid-empty code {
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: #fff;
  padding: 1px 4px;
  border-radius: 3px;
}

.valid-result { padding: 12px 14px; border-radius: 8px; }
.valid-result.ok   { background: #f0fdf4; border: 1px solid #bbf7d0; }
.valid-result.fail { background: #fef2f2; border: 1px solid #fecaca; }

.valid-head {
  display: flex;
  gap: 8px;
  align-items: center;
}
.v-title {
  font-size: 12px;
  font-weight: 600;
}
.valid-result.ok .v-title   { color: #15803d; }
.valid-result.fail .v-title { color: #b91c1c; }

.valid-errors { margin-top: 10px; }
.err {
  display: flex;
  gap: 6px;
  align-items: baseline;
  padding: 4px 6px;
  margin-bottom: 4px;
  font-size: 11px;
  background: #fff;
  border-radius: 4px;
}
.err code {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: #b91c1c;
}

.preview {
  padding: 12px;
  margin: 0;
  max-height: 320px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.55;
  color: #cbd5e1;
  background: #0f172a;
  border-radius: 6px;
}

@media (max-width: 1100px) {
  .body { grid-template-columns: 1fr; }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
