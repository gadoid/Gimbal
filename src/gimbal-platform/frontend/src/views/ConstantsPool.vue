<!--
  ConstantsPool.vue — 常量池管理页(/constants)。批次 3 迁移新栈:
  shadcn Table/Dialog/Select/Switch/Input;弹框保持 reactive form +
  canSubmit 门控(动态控制面板,非简单校验表单 — 不套 vee-validate);
  删除确认换新栈 confirmAction。

  上半: 生成器模板目录(只读,plate 代理;kind 可折叠卡片: 说明/参数表/
  示例 JSON 复制)。下半: 我的常量池(表格 CRUD;新增/编辑共享弹框 —
  字面量四型值控件 / 生成器目录驱动动态参数表单 + 实时 spec 预览)。
  降级: 目录不可用 → 模板区降级条 + 生成器类型禁用;字面量 CRUD 不受影响。
-->
<template>
  <ListPage
    title="常量池"
    subtitle="常用字面值与生成器声明 — 编排页右栏「常量池」面板可直接复制/插入"
  >
    <div class="flex flex-col gap-4">
    <!-- ── 生成器模板目录 ── -->
    <section class="card catalog">
      <div class="section-head">
        <h2 class="text-heading text-signal-ink">生成器模板目录</h2>
        <span v-if="constantsStore.catalogError" class="degraded">
          {{ constantsStore.catalogError }} — 目录暂不可用,字面量条目不受影响
        </span>
      </div>
      <div v-for="k in constantsStore.catalog" :key="k.kind" class="kind-card" :data-kind="k.kind">
        <button class="kind-head" type="button" @click="toggleKind(k.kind)">
          <span class="chevron" :class="{ open: openKinds.has(k.kind) }">▸</span>
          <code class="kind-name">{{ k.kind }}</code>
          <span class="kind-summary">{{ k.summary }}</span>
        </button>
        <div v-if="openKinds.has(k.kind)" class="kind-body">
          <template v-if="fulls[k.kind]">
            <p class="kind-desc">{{ fulls[k.kind]!.description }}</p>
            <table v-if="fulls[k.kind]!.params.length" class="params-table slib-table">
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
              <Button variant="outline" size="sm" @click="copyExample(fulls[k.kind]!)">复制 JSON</Button>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- ── 我的常量池 ── -->
    <section class="card entries">
      <div class="section-head">
        <h2 class="text-heading text-signal-ink">我的常量池</h2>
        <Button data-action="pool-create" @click="openCreate">新增</Button>
      </div>
      <div class="lib-card">
        <Table class="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead class="w-[18%]">名称</TableHead>
              <TableHead class="w-[9%]">类型</TableHead>
              <TableHead class="w-[40%]">内容</TableHead>
              <TableHead class="w-[20%]">说明</TableHead>
              <TableHead class="w-[13%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="entries-table">
          <TableRow v-for="row in constantsStore.entries" :key="row.id">
            <TableCell><code>{{ row.name }}</code></TableCell>
            <TableCell>
              <span class="chip" :class="row.entry_kind === 'generator'
                ? 'bg-amber-50 text-amber-800' : 'bg-signal-soft text-signal'">
                {{ row.entry_kind === 'generator' ? '生成器' : '常量' }}
              </span>
            </TableCell>
            <TableCell><code class="entry-value">{{ entryValueText(row) }}</code></TableCell>
            <TableCell class="text-caption text-muted-foreground">{{ row.description }}</TableCell>
            <TableCell>
              <div class="flex items-center gap-1">
                <Button variant="outline" size="sm" data-action="edit" @click="openEdit(row)">编辑</Button>
                <Button variant="outline" size="sm" class="text-signal-failed" data-action="delete" @click="onDelete(row)">删除</Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
        </Table>
      </div>
    </section>

    <!-- ── 新增/编辑弹框(动态控制面板,reactive form + canSubmit 门控)── -->
    <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
      <DialogContent class="max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{{ editing ? '编辑常量' : '新增常量' }}</DialogTitle>
        </DialogHeader>

        <!-- data-testid 放内层真实元素:Portal 组件的 attrs 穿透不可查询 -->
        <div class="flex flex-col gap-3" data-testid="entry-dialog">
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <span class="text-label font-medium text-signal-ink">名称 *</span>
            <Input v-model="form.name" data-field="name" :disabled="!!editing" placeholder="A-Z a-z 0-9 _,1-64 字符" />
          </div>
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <span class="text-label font-medium text-signal-ink">说明</span>
            <Input v-model="form.description" data-field="description" placeholder="可选" />
          </div>
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <span class="text-label font-medium text-signal-ink">类型</span>
            <div class="seg" data-field="entry_kind">
              <button
                type="button"
                class="seg-btn"
                :class="{ active: form.entry_kind === 'literal' }"
                :disabled="!!editing"
                data-value="literal"
                @click="!editing && (form.entry_kind = 'literal')"
              >常量(字面值)</button>
              <button
                type="button"
                class="seg-btn"
                :class="{ active: form.entry_kind === 'generator' }"
                :disabled="!!editing || !!constantsStore.catalogError"
                data-value="generator"
                @click="!editing && !constantsStore.catalogError && (form.entry_kind = 'generator')"
              >生成器</button>
            </div>
          </div>

          <template v-if="form.entry_kind === 'literal'">
            <div class="grid grid-cols-[80px_1fr] items-center gap-2">
              <span class="text-label font-medium text-signal-ink">值类型</span>
              <Select v-model="form.valueType">
                <SelectTrigger data-field="valueType" class="h-8"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="string">字符串</SelectItem>
                  <SelectItem value="integer">整数</SelectItem>
                  <SelectItem value="decimal">小数</SelectItem>
                  <SelectItem value="boolean">布尔</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="grid grid-cols-[80px_1fr] items-center gap-2">
              <span class="text-label font-medium text-signal-ink">值 *</span>
              <Switch
                v-if="form.valueType === 'boolean'"
                v-model="form.valueBool"
                data-field="valueBool"
              />
              <Input
                v-else-if="form.valueType !== 'string'"
                type="number"
                :model-value="form.valueNum"
                data-field="valueNum"
                class="h-8 w-[160px]"
                @update:model-value="(v) => (form.valueNum = Number(v))"
              />
              <Input v-else v-model="form.valueStr" data-field="valueStr" placeholder="字面值文本" />
            </div>
          </template>

          <template v-else>
            <div class="grid grid-cols-[80px_1fr] items-start gap-2">
              <span class="mt-1.5 text-label font-medium text-signal-ink">生成器 *</span>
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
            </div>
            <p v-if="constantsStore.catalogError" class="muted m-0">目录不可用,无法配置生成器条目</p>
            <div
              v-for="p in genParams"
              :key="p.name"
              class="grid grid-cols-[80px_1fr] items-center gap-2"
            >
              <span class="text-label font-medium text-signal-ink">{{ p.name }}{{ p.required ? ' *' : '' }}</span>
              <div class="flex flex-col gap-0.5">
                <Select
                  v-if="p.enum"
                  :model-value="(form.genParams[p.name] as string | number | undefined)"
                  @update:model-value="(v) => setParam(p.name, v as string | number)"
                >
                  <SelectTrigger :data-field="`param-${p.name}`" class="h-8"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="v in p.enum" :key="String(v)" :value="(v as string | number)">{{ String(v) }}</SelectItem>
                  </SelectContent>
                </Select>
                <Switch
                  v-else-if="p.type === 'boolean'"
                  :model-value="form.genParams[p.name] === true"
                  :data-field="`param-${p.name}`"
                  @update:model-value="(v: boolean) => setParam(p.name, v)"
                />
                <Input
                  v-else-if="p.type === 'integer' || p.type === 'number'"
                  type="number"
                  :model-value="(form.genParams[p.name] as number | undefined) ?? ''"
                  :min="p.min ?? undefined"
                  :max="p.max ?? undefined"
                  :data-field="`param-${p.name}`"
                  class="h-8 w-[160px]"
                  @update:model-value="(v) => setParam(p.name, v === '' ? undefined : Number(v))"
                />
                <Input
                  v-else
                  :model-value="String(form.genParams[p.name] ?? '')"
                  :data-field="`param-${p.name}`"
                  class="h-8"
                  @update:model-value="(v) => setParam(p.name, v)"
                />
                <span class="muted param-hint">{{ p.description }}</span>
              </div>
            </div>
            <div class="grid grid-cols-[80px_1fr] items-center gap-2">
              <span class="text-label font-medium text-signal-ink">spec 预览</span>
              <div class="spec-preview">
                <pre data-testid="spec-preview">{{ specPreview }}</pre>
                <Button variant="outline" size="sm" data-action="copy-spec" @click="copySpec">复制</Button>
              </div>
            </div>
          </template>
        </div>

        <DialogFooter>
          <Button variant="outline" @click="dialogOpen = false">取消</Button>
          <Button data-action="submit" :disabled="!canSubmit" @click="onSubmit">
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import ListPage from '@/layouts/ListPage.vue'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { useConstantsStore } from '@/stores/constants'
import { getGeneratorKindFull } from '@/api/generator_catalog'
import { copyText } from '@/utils/clipboard'
import type {
  ConstantEntry,
  GeneratorKindDetailView,
  GeneratorParamDesc,
} from '@/types/constants'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

const constantsStore = useConstantsStore()

onMounted(() => {
  void constantsStore.ensureEntries().catch(() => toast.error('常量池加载失败'))
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
    toast.error(`加载 ${kind} 说明失败`)
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
    if (ok) toast.success('已复制示例 JSON')
  })
}

// ── 条目表 ──
function entryValueText(row: ConstantEntry): string {
  return row.entry_kind === 'generator' ? JSON.stringify(row.spec) : String(row.value)
}

async function onDelete(row: ConstantEntry): Promise<void> {
  const ok = await confirmAction(
    `删除常量「${row.name}」?`, '删除确认',
    { type: 'warning', danger: true, confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  if (!ok) return
  try {
    await constantsStore.removeEntry(row.id)
    toast.success('已删除')
  } catch {
    toast.error('删除失败')
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
  // 仅新建路径需要唯一性检查;编辑时 name 不可改,全库 name 唯一已保证无重复
  if (
    !editing.value &&
    constantsStore.entries.some((e) => e.name === form.name)
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
      toast.success('已保存')
    } else if (form.entry_kind === 'literal') {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'literal',
        value: literalValueFromForm(),
      })
      toast.success('已新增')
    } else {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'generator',
        spec: buildSpec() ?? undefined,
      })
      toast.success('已新增')
    }
    dialogOpen.value = false
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '保存失败')
  }
}

function copySpec(): void {
  const spec = buildSpec()
  if (!spec) return
  void copyText(JSON.stringify(spec)).then((ok) => {
    if (ok) toast.success('已复制 spec')
  })
}
</script>

<style scoped>
.muted { @apply text-label font-normal; color: var(--c-text-tertiary, #94a3b8); }
.card {
  background: var(--c-surface, #fff);
  border: 1px solid var(--c-border, #e1e5eb);
  border-radius: 10px;
  padding: 14px 16px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.degraded { @apply text-label font-normal; color: #b45309; }
.kind-card { border: 1px solid var(--c-border, #e1e5eb); border-radius: 8px; margin-bottom: 8px; }
.kind-head {
  @apply text-label font-normal;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
}
.chevron { display: inline-block; transition: transform 0.15s ease; color: var(--c-text-tertiary, #94a3b8); }
.chevron.open { transform: rotate(90deg); }
.kind-name { font-family: var(--font-mono, monospace); font-weight: 600; }
.kind-summary { color: #64748b; }
.kind-body { padding: 0 12px 10px; }
.kind-desc { @apply text-label font-normal; margin: 4px 0 8px; }
/* 发丝线表格;列头形制统一走 .slib-table thead th,这里只压密度 */
.params-table { @apply text-caption font-normal; width: 100%; border-collapse: collapse; }
.params-table th,
.params-table td { padding: 5px 8px; text-align: left; }
.params-table td { border-bottom: 1px solid var(--c-divider, #eef1f5); }
.params-table tbody tr:last-child td { border-bottom: none; }
.example-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.example-json {
  @apply text-caption font-normal;
  font-family: var(--font-mono, monospace);
  background: #f6f8fa;
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
}
.entry-value {
  @apply text-caption font-normal;
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}
.chip {
  @apply text-micro font-semibold;
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 4px;
}
.kind-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.kind-chip {
  @apply text-caption font-normal;
  border: 1px solid var(--c-border, #e1e5eb);
  background: #f6f8fa;
  border-radius: 12px;
  padding: 2px 10px;
  font-family: var(--font-mono, monospace);
  cursor: pointer;
}
/* 选中态对齐 Signal accent */
.kind-chip.active {
  background: #e7efff;
  border-color: #2f6fed;
  color: #2f6fed;
}
/* 类型分段选择(替代 el-radio-button) */
.seg { display: inline-flex; border: 1px solid #e1e5eb; border-radius: 8px; overflow: hidden; }
.seg-btn {
  @apply text-label font-normal;
  padding: 6px 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #5a6273;
}
.seg-btn.active { background: #2f6fed; color: #fff; font-weight: 600; }
.seg-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.param-hint { display: block; margin-top: 2px; }
.spec-preview { display: flex; align-items: center; gap: 8px; width: 100%; }
.spec-preview pre {
  @apply text-caption font-normal;
  flex: 1;
  font-family: var(--font-mono, monospace);
  background: #f6f8fa;
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
