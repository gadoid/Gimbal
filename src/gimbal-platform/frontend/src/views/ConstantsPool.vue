<!--
  ConstantsPool.vue — 常量池管理页(/constants)

  上半: 生成器模板目录(只读,plate 代理;kind 可折叠卡片: 说明/参数表/
  示例 JSON 复制)。下半: 我的常量池(el-table CRUD;新增/编辑共享弹框 —
  字面量四型值控件 / 生成器目录驱动动态参数表单 + 实时 spec 预览)。
  降级: 目录不可用 → 模板区降级条 + 生成器类型禁用;字面量 CRUD 不受影响。
-->
<template>
  <div class="constants-page">
    <header class="page-head">
      <h1>常量池</h1>
      <p class="muted">常用字面值与生成器声明 — 编排页右栏「常量池」面板可直接复制/插入</p>
    </header>

    <!-- ── 生成器模板目录 ── -->
    <section class="card catalog">
      <div class="section-head">
        <h2>生成器模板目录</h2>
        <span v-if="constantsStore.catalogError" class="degraded">
          {{ constantsStore.catalogError }} — 目录暂不可用,字面量条目不受影响
        </span>
      </div>
      <div v-for="k in constantsStore.catalog" :key="k.kind" class="kind-card" :data-kind="k.kind">
        <button class="kind-head" @click="toggleKind(k.kind)">
          <span class="chevron" :class="{ open: openKinds.has(k.kind) }">▸</span>
          <code class="kind-name">{{ k.kind }}</code>
          <span class="kind-summary">{{ k.summary }}</span>
        </button>
        <div v-if="openKinds.has(k.kind)" class="kind-body">
          <template v-if="fulls[k.kind]">
            <p class="kind-desc">{{ fulls[k.kind]!.description }}</p>
            <table v-if="fulls[k.kind]!.params.length" class="params-table">
              <thead>
                <tr><th>参数</th><th>类型</th><th>必填</th><th>默认</th><th>可选值/范围</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in fulls[k.kind]!.params" :key="p.name" :data-param="p.name">
                  <td><code>{{ p.name }}</code></td>
                  <td>{{ p.type }}</td>
                  <td>{{ p.required ? '是' : '否' }}</td>
                  <td>{{ p.default === null || p.default === undefined ? '—' : JSON.stringify(p.default) }}</td>
                  <td>{{ paramRange(p) }}</td>
                  <td>{{ p.description }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="muted">无参数</p>
            <div class="example-row">
              <pre class="example-json">{{ JSON.stringify(fulls[k.kind]!.example, null, 2) }}</pre>
              <button class="ghost-btn" @click="copyExample(fulls[k.kind]!)">复制 JSON</button>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- ── 我的常量池 ── -->
    <section class="card entries">
      <div class="section-head">
        <h2>我的常量池</h2>
        <button class="primary-btn" data-action="pool-create" @click="openCreate">新增</button>
      </div>
      <el-table :data="constantsStore.entries" data-testid="entries-table">
        <el-table-column prop="name" label="名称" width="180">
          <template #default="{ row }"><code>{{ row.name }}</code></template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.entry_kind === 'generator' ? 'warning' : 'info'" size="small">
              {{ row.entry_kind === 'generator' ? '生成器' : '常量' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容">
          <template #default="{ row }">
            <code class="entry-value">{{ entryValueText(row) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" width="200" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <button class="ghost-btn" data-action="edit" @click="openEdit(row)">编辑</button>
            <button class="ghost-btn danger" data-action="delete" @click="onDelete(row)">删除</button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- ── 新增/编辑弹框 ── -->
    <el-dialog
      v-model="dialogOpen"
      :title="editing ? '编辑常量' : '新增常量'"
      width="560px"
      data-testid="entry-dialog"
    >
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" data-field="name" placeholder="A-Z a-z 0-9 _,1-64 字符" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" data-field="description" placeholder="可选" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.entry_kind" :disabled="editing" data-field="entry_kind">
            <el-radio-button value="literal">常量(字面值)</el-radio-button>
            <el-radio-button value="generator" :disabled="!!constantsStore.catalogError">
              生成器
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.entry_kind === 'literal'">
          <el-form-item label="值类型">
            <el-select v-model="form.valueType" data-field="valueType">
              <el-option label="字符串" value="string" />
              <el-option label="整数" value="integer" />
              <el-option label="小数" value="decimal" />
              <el-option label="布尔" value="boolean" />
            </el-select>
          </el-form-item>
          <el-form-item label="值" required>
            <el-switch
              v-if="form.valueType === 'boolean'"
              v-model="form.valueBool"
              data-field="valueBool"
            />
            <el-input-number
              v-else-if="form.valueType !== 'string'"
              v-model="form.valueNum"
              data-field="valueNum"
            />
            <el-input v-else v-model="form.valueStr" data-field="valueStr" placeholder="字面值文本" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="生成器" required>
            <div class="kind-chips">
              <button
                v-for="k in constantsStore.catalog"
                :key="k.kind"
                type="button"
                class="kind-chip"
                :class="{ active: form.genKind === k.kind }"
                :data-kind="k.kind"
                :title="k.summary"
                @click="selectGenKind(k.kind)"
              >{{ k.kind }}</button>
            </div>
          </el-form-item>
          <p v-if="constantsStore.catalogError" class="muted">目录不可用,无法配置生成器条目</p>
          <el-form-item
            v-for="p in genParams"
            :key="p.name"
            :label="p.name"
            :required="p.required"
          >
            <el-select
              v-if="p.enum"
              :model-value="form.genParams[p.name]"
              :data-field="`param-${p.name}`"
              @update:model-value="(v: unknown) => setParam(p.name, v)"
            >
              <el-option v-for="v in p.enum" :key="String(v)" :value="v" :label="String(v)" />
            </el-select>
            <el-switch
              v-else-if="p.type === 'boolean'"
              :model-value="form.genParams[p.name] === true"
              :data-field="`param-${p.name}`"
              @change="(v: unknown) => setParam(p.name, v === true)"
            />
            <el-input-number
              v-else-if="p.type === 'integer' || p.type === 'number'"
              :model-value="form.genParams[p.name] as number | undefined"
              :min="p.min ?? undefined"
              :max="p.max ?? undefined"
              :data-field="`param-${p.name}`"
              @update:model-value="(v: unknown) => setParam(p.name, v)"
            />
            <el-input
              v-else
              :model-value="String(form.genParams[p.name] ?? '')"
              :data-field="`param-${p.name}`"
              @update:model-value="(v: unknown) => setParam(p.name, v)"
            />
            <span class="muted param-hint">{{ p.description }}</span>
          </el-form-item>
          <el-form-item label="spec 预览">
            <div class="spec-preview">
              <pre data-testid="spec-preview">{{ specPreview }}</pre>
              <button class="ghost-btn" data-action="copy-spec" @click="copySpec">复制</button>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <button class="ghost-btn" @click="dialogOpen = false">取消</button>
        <button class="primary-btn" data-action="submit" :disabled="!canSubmit" @click="onSubmit">
          保存
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useConstantsStore } from '@/stores/constants'
import { getGeneratorKindFull } from '@/api/generator_catalog'
import { copyText } from '@/utils/clipboard'
import type {
  ConstantEntry,
  GeneratorKindDetailView,
  GeneratorParamDesc,
} from '@/types/constants'

const constantsStore = useConstantsStore()

onMounted(() => {
  void constantsStore.ensureEntries().catch(() => ElMessage.error('常量池加载失败'))
  void constantsStore.ensureCatalog()
})

// ── 目录(展开时拉 full,缓存) ──
const openKinds = ref(new Set<string>())
const fulls = ref<Record<string, GeneratorKindDetailView>>({})

async function toggleKind(kind: string): Promise<void> {
  const next = new Set(openKinds.value)
  if (next.has(kind)) {
    next.delete(kind)
  } else {
    next.add(kind)
    if (!fulls.value[kind]) await ensureFull(kind)
  }
  openKinds.value = next
}

async function ensureFull(kind: string): Promise<void> {
  if (fulls.value[kind]) return
  try {
    fulls.value = { ...fulls.value, [kind]: await getGeneratorKindFull(kind) }
  } catch {
    ElMessage.error(`加载 ${kind} 说明失败`)
  }
}

function paramRange(p: GeneratorParamDesc): string {
  if (p.enum) return p.enum.map(String).join(' / ')
  if (p.min !== null && p.max !== null) return `${p.min} ~ ${p.max}`
  if (p.min !== null) return `≥ ${p.min}`
  if (p.max !== null) return `≤ ${p.max}`
  return '—'
}

function copyExample(full: GeneratorKindDetailView): void {
  void copyText(JSON.stringify(full.example)).then((ok) => {
    if (ok) ElMessage.success('已复制示例 JSON')
  })
}

// ── 条目表 ──
function entryValueText(row: ConstantEntry): string {
  return row.entry_kind === 'generator' ? JSON.stringify(row.spec) : String(row.value)
}

async function onDelete(row: ConstantEntry): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除常量「${row.name}」?`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await constantsStore.removeEntry(row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 新增/编辑弹框 ──
const dialogOpen = ref(false)
const editing = ref<ConstantEntry | null>(null)

interface EntryForm {
  name: string
  description: string
  entry_kind: 'literal' | 'generator'
  valueType: 'string' | 'integer' | 'decimal' | 'boolean'
  valueStr: string
  valueNum: number
  valueBool: boolean
  genKind: string
  genParams: Record<string, unknown>
}

const EMPTY_FORM: EntryForm = {
  name: '',
  description: '',
  entry_kind: 'literal',
  valueType: 'string',
  valueStr: '',
  valueNum: 0,
  valueBool: false,
  genKind: '',
  genParams: {},
}
const form = reactive<EntryForm>({ ...EMPTY_FORM })

const genFull = computed(() => fulls.value[form.genKind] ?? null)
const genParams = computed<GeneratorParamDesc[]>(() => genFull.value?.params ?? [])

const NAME_RE = /^[A-Za-z0-9_]{1,64}$/
const canSubmit = computed(() => {
  if (!NAME_RE.test(form.name)) return false
  if (
    constantsStore.entries.some((e) => e.name === form.name && e.id !== editing.value?.id)
  ) {
    return false
  }
  if (form.entry_kind === 'literal') {
    return form.valueType === 'string' ? form.valueStr.trim().length > 0 : true
  }
  return !!form.genKind
})

const specPreview = computed(() => JSON.stringify(buildSpec()))

function setParam(name: string, v: unknown): void {
  form.genParams[name] = v
}

function buildSpec(): Record<string, unknown> | null {
  if (form.entry_kind !== 'generator' || !form.genKind) return null
  const spec: Record<string, unknown> = { kind: form.genKind }
  // 并集: 目录 full 拉取失败时 genParams 为空,只遍历描述符会丢已存参数(降级编辑)
  const names = new Set([...genParams.value.map((p) => p.name), ...Object.keys(form.genParams)])
  for (const name of names) {
    const v = form.genParams[name]
    if (v !== undefined && v !== null && v !== '') spec[name] = v
  }
  return spec
}

/** 新建流程选 kind: 拉 full + 默认值预填(编辑流程的预填在 openEdit,不走此 watch)。 */
watch(
  () => form.genKind,
  async (kind) => {
    if (!kind || editing.value) return
    await ensureFull(kind)
    const defaults: Record<string, unknown> = {}
    for (const p of fulls.value[kind]?.params ?? []) {
      if (p.default !== null && p.default !== undefined) defaults[p.name] = p.default
    }
    form.genParams = defaults
  },
)

function selectGenKind(kind: string): void {
  form.genKind = kind
}

function openCreate(): void {
  editing.value = null
  Object.assign(form, EMPTY_FORM, { genParams: {} })
  dialogOpen.value = true
}

function openEdit(row: ConstantEntry): void {
  editing.value = row
  Object.assign(form, EMPTY_FORM, {
    name: row.name,
    description: row.description,
    entry_kind: row.entry_kind,
  })
  if (row.entry_kind === 'literal') {
    const v = row.value
    if (typeof v === 'boolean') form.valueType = 'boolean'
    else if (typeof v === 'number') {
      form.valueType = Number.isInteger(v) ? 'integer' : 'decimal'
    } else form.valueType = 'string'
    form.valueStr = typeof v === 'string' ? v : String(v ?? '')
    form.valueNum = typeof v === 'number' ? v : 0
    form.valueBool = v === true
  } else {
    const spec = row.spec ?? {}
    form.genKind = String(spec.kind ?? '')
    const params: Record<string, unknown> = { ...spec }
    delete params.kind
    form.genParams = params
    void ensureFull(form.genKind)
  }
  dialogOpen.value = true
}

function literalValueFromForm(): unknown {
  switch (form.valueType) {
    case 'boolean':
      return form.valueBool
    case 'integer':
      return Math.trunc(form.valueNum)
    case 'decimal':
      return form.valueNum
    default:
      return form.valueStr
  }
}

async function onSubmit(): Promise<void> {
  try {
    if (editing.value) {
      const payload: Record<string, unknown> = { description: form.description }
      if (form.entry_kind === 'literal') payload.value = literalValueFromForm()
      else payload.spec = buildSpec()
      await constantsStore.patchEntry(editing.value.id, payload)
      ElMessage.success('已保存')
    } else if (form.entry_kind === 'literal') {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'literal',
        value: literalValueFromForm(),
      })
      ElMessage.success('已新增')
    } else {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'generator',
        spec: buildSpec() ?? undefined,
      })
      ElMessage.success('已新增')
    }
    dialogOpen.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

function copySpec(): void {
  const spec = buildSpec()
  if (!spec) return
  void copyText(JSON.stringify(spec)).then((ok) => {
    if (ok) ElMessage.success('已复制 spec')
  })
}
</script>

<style scoped>
.constants-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-head h1 { font-size: 18px; margin-bottom: 4px; }
.muted { color: var(--c-text-tertiary); font-size: 12px; }
.card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 14px 16px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.section-head h2 { font-size: 14px; }
.degraded { color: #b45309; font-size: 12px; }
.kind-card { border: 1px solid var(--c-border); border-radius: 8px; margin-bottom: 8px; }
.kind-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12.5px;
  text-align: left;
}
.chevron { display: inline-block; transition: transform 0.15s ease; color: var(--c-text-tertiary); }
.chevron.open { transform: rotate(90deg); }
.kind-name { font-family: var(--font-mono); font-weight: 600; }
.kind-summary { color: var(--c-text-secondary, #64748b); }
.kind-body { padding: 0 12px 10px; }
.kind-desc { font-size: 12px; margin: 4px 0 8px; }
.params-table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
.params-table th,
.params-table td { border: 1px solid var(--c-border); padding: 3px 8px; text-align: left; }
.params-table th { background: var(--c-bg-secondary); font-weight: 600; }
.example-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.example-json {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
}
.entry-value {
  font-family: var(--font-mono);
  font-size: 11.5px;
  word-break: break-all;
}
.kind-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.kind-chip {
  border: 1px solid var(--c-border);
  background: var(--c-bg-secondary);
  border-radius: 12px;
  padding: 2px 10px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  cursor: pointer;
}
.kind-chip.active {
  background: #ede9fe;
  border-color: #7c3aed;
  color: #4c1d95;
}
.param-hint { display: block; margin-top: 2px; }
.spec-preview { display: flex; align-items: center; gap: 8px; width: 100%; }
.spec-preview pre {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border: none; border-radius: 8px;
  padding: 8px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.2);
}
.primary-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.ghost-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.ghost-btn:hover { background: #f5f6fa; color: #1a1d24; }
.ghost-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.ghost-btn.danger { color: #dc2626; }
</style>
