<!-- ScenarioEditorMeta.vue — 场景编辑 · ① 基本信息
     4 步流程第 1 步：基本信息 + systems + 模块 / 优先级 / tags
     进入时: 新建场景 → 默认 draft / 编辑已有场景 → 加载 + 回填
     保存：跳到 ② 步骤编排
-->
<template>
  <section class="editor">
    <header class="page-header">
      <div>
        <h2>📚 场景编辑</h2>
        <p>{{ draft.meta.name || draft.meta.scenarioId || '新场景' }} · ① 基本信息</p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push('/scenarios')">← 返回场景库</el-button>
        <el-button type="primary" @click="saveAndNext">保存并下一步 →</el-button>
      </div>
    </header>

    <HeadStepper :steps="STEPS" :active-index="0" />

    <div class="body">
      <!-- 左侧主表单 -->
      <el-form
        ref="formRef"
        :model="draft.meta"
        :rules="rules"
        label-position="top"
        class="main-card"
      >
        <h3>基本信息</h3>
        <el-form-item label="scenarioId" prop="scenarioId">
          <el-input
            v-model="draft.meta.scenarioId"
            :disabled="!!scenarioId"
            placeholder="sc-order-create"
          />
        </el-form-item>
        <el-form-item label="场景名称" prop="name">
          <el-input v-model="draft.meta.name" placeholder="订单创建" />
        </el-form-item>
        <el-form-item label="业务模块" prop="module">
          <el-input v-model="draft.meta.module" placeholder="订单" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="draft.meta.description"
            type="textarea"
            :rows="3"
            placeholder="覆盖订单创建主链路：选品 → 校验 → 落库 → 回调"
          />
        </el-form-item>

        <h3>归属信息</h3>
        <div class="grid-2">
          <el-form-item label="作者" prop="author">
            <el-input v-model="draft.meta.author" placeholder="王" />
          </el-form-item>
          <el-form-item label="维护人" prop="owner">
            <el-input v-model="draft.meta.owner" placeholder="王" />
          </el-form-item>
          <el-form-item label="优先级" prop="priority">
            <el-select v-model.number="draft.meta.priority" placeholder="选择优先级">
              <el-option v-for="p in [0,1,2,3]" :key="p" :value="p" :label="`P${p}`" />
            </el-select>
          </el-form-item>
          <el-form-item label="版本号">
            <el-input v-model="draft.meta.version" placeholder="v1.0.0" />
          </el-form-item>
        </div>

        <el-form-item label="Tags">
          <TagInput v-model="draft.meta.tags" placeholder="按 Enter 添加 tag" />
        </el-form-item>

        <el-form-item label="过期标志">
          <el-switch v-model="draft.meta.expire" />
        </el-form-item>
      </el-form>

      <!-- 右侧 SideCard：systems 多选 -->
      <aside class="side-card">
        <h3>归属被测系统 (V3.2: list[str])</h3>
        <p class="hint">支持多选 · 选 <code>common</code> 表示通用</p>
        <div class="sys-grid">
          <label
            v-for="s in SYS_OPTIONS"
            :key="s"
            class="sys-tile"
            :class="{ active: draft.meta.system.includes(s) }"
          >
            <input
              type="checkbox"
              :checked="draft.meta.system.includes(s)"
              @change="toggleSystem(s)"
            />
            <SystemChip :sys="s" />
          </label>
        </div>

        <h3 style="margin-top: 24px;">预览</h3>
        <pre class="preview">{{ JSON.stringify(draft.meta, null, 2) }}</pre>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import HeadStepper from '@/components/HeadStepper.vue'
import SystemChip from '@/components/SystemChip.vue'
import TagInput from '@/components/TagInput.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import type { ScenarioDraft } from '@/types/scenario-composer'

const SYS_OPTIONS = ['fin', 'logi', 'wms', 'mall', 'common']
const STEPS = [
  { key: 'meta',   label: '① 基本信息', to: '' as RouteLocationRaw },
  { key: 'steps',  label: '② 步骤编排', to: '' as RouteLocationRaw },
  { key: 'cases',  label: '③ 用例管理', to: '' as RouteLocationRaw },
  { key: 'data',   label: '④ 数据集',   to: '' as RouteLocationRaw },
]

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()

const scenarioId = (route.params.scenarioId as string) || null
const formRef = ref<FormInstance>()

function emptyDraft(): ScenarioDraft {
  return {
    meta: {
      scenarioId: scenarioId ?? '',
      name: '',
      description: '',
      module: '',
      priority: 2,
      author: '',
      owner: '',
      tags: [],
      // 默认选中 common,避免空 system 触发后端 422 (ScenarioMeta.system: min_length=1)
      system: ['common'],
    },
    steps: [],
  }
}

const draft = reactive<ScenarioDraft>(emptyDraft())

const rules: FormRules = {
  scenarioId: [{ required: true, pattern: /^sc-[a-z0-9-]+$/, message: '前缀 sc- 小写', trigger: 'blur' }],
  name:        [{ required: true, message: '请输入场景名', trigger: 'blur' }],
  module:      [{ required: true, message: '请输入模块', trigger: 'blur' }],
  description: [{ required: true, message: '请输入描述', trigger: 'blur' }],
  author:      [{ required: true, message: '请输入作者', trigger: 'blur' }],
  owner:       [{ required: true, message: '请输入维护人', trigger: 'blur' }],
  priority:    [{ required: true, message: '请选择优先级', trigger: 'change' }],
}

onMounted(async () => {
  if (!scenarioId || scenarioId === 'new') return
  try {
    const sc = store.scenarioById(scenarioId)
    if (sc) {
      Object.assign(draft.meta, sc.meta)
      draft.steps = sc.steps
    } else {
      await store.fetchScenarios()
      const sc2 = store.scenarioById(scenarioId)
      if (sc2) Object.assign(draft.meta, sc2.meta)
    }
    // 跳转目标拼装
    STEPS[1].to = `/scenarios/${scenarioId}/steps`
    STEPS[2].to = `/scenarios/${scenarioId}/cases`
    STEPS[3].to = `/scenarios/${scenarioId}/data-sets`
  } catch (e) {
    showError('加载场景', undefined, (e as Error).message)
  }
})

function toggleSystem(s: string) {
  const idx = draft.meta.system.indexOf(s)
  if (idx >= 0) draft.meta.system.splice(idx, 1)
  else draft.meta.system.push(s)
}

async function saveAndNext() {
  if (!formRef.value) return
  await formRef.value.validate(async (ok) => {
    if (!ok) return
    // 后端 ScenarioMeta.system 要求至少 1 个 tag
    if (!draft.meta.system || draft.meta.system.length === 0) {
      ElMessage.error('请至少选择一个被测系统 (system)')
      return
    }
    try {
      const saved = await store.saveScenario(
        scenarioId === 'new' ? null : scenarioId,
        draft,
      )
      ElMessage.success('已保存基本信息')
      router.push(`/scenarios/${saved.meta.scenarioId}/steps`)
    } catch (e) {
      showError('保存', undefined, (e as Error).message)
    }
  })
}
</script>

<style scoped>
.editor {
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
.page-header h2 { margin: 0; font-size: 22px; line-height: 1.25; color: var(--color-text-primary); }
.page-header p  { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }

.header-actions { display: flex; gap: 8px; }

.body {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  margin-top: 16px;
}

.main-card, .side-card {
  padding: 22px 24px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.main-card h3, .side-card h3 {
  margin: 18px 0 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-primary);
}
.main-card h3:first-child, .side-card h3:first-child { margin-top: 0; }

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.side-card .hint {
  margin: 0 0 10px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.side-card code {
  padding: 1px 4px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: #f1f5f9;
  border-radius: 3px;
}

.sys-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.sys-tile {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  cursor: pointer;
}
.sys-tile.active { border-color: var(--accent); background: var(--accent-soft); }
.sys-tile input { accent-color: var(--accent); }

.preview {
  padding: 12px;
  margin: 0;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.55;
  color: #cbd5e1;
  background: #0f172a;
  border-radius: 6px;
  max-height: 280px;
}

@media (max-width: 1100px) {
  .body { grid-template-columns: 1fr; }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
