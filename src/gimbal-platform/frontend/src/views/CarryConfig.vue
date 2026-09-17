<!-- CarryConfig.vue — 传递字段配置(spec §6)。批次 2 迁移新栈:
     shadcn Tabs/Table/Tooltip/Alert/Button/Input;服务选择器用原生
     datalist 组合框(shadcn Select 不支持 allow-create 自由输入,
     原 el-select filterable+allow-create 的能力由 Input+datalist 承接)。
     业务逻辑零改动:三态(hasRow/isNull/值)编码、CSV 三件套、
     degraded 门控、R1-B1/R1-M2 修复语义全部保留(真源在
     utils/carry-csv + carry-entries + api/carry)。 -->
<template>
  <section class="carry-config mx-auto max-w-[1480px] px-8 pb-12 pt-7">
    <header class="mb-3.5">
      <h2 class="m-0 text-display text-signal-ink">传递字段配置</h2>
      <p class="mt-1 mb-0 text-caption text-muted-foreground">carry 值表两层:服务绑定(覆盖)→ 全局默认;删行 = 不注入,null = 显式注入 JSON null</p>
    </header>

    <Tabs v-model="activeTab" class="carry-tabs">
      <!-- ── 服务绑定 ─────────────────────────────── -->
      <TabsList>
        <TabsTrigger value="service">服务绑定</TabsTrigger>
        <TabsTrigger value="defaults">全局默认</TabsTrigger>
      </TabsList>

      <TabsContent value="service">
        <div class="c-card">
          <div class="c-card-head">
            <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            <div>
              <h3>服务绑定(覆盖层)</h3>
              <p class="c-head-desc">选服务 → 拉取该服务 carry 字段面(plate 声明并集)→ 逐字段填值;绑定值覆盖全局默认,保存 = 整表替换</p>
            </div>
          </div>

          <TooltipProvider>
          <div class="svc-bar">
            <Input
              v-model="service"
              class="w-[320px] max-w-full"
              list="carry-known-services"
              placeholder="选择或输入目录服务名"
              data-testid="svc-input"
              @change="onServiceChange"
            />
            <datalist id="carry-known-services">
              <option v-for="s in knownServices" :key="s" :value="s" />
            </datalist>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" :disabled="!service || !rows.length" data-testid="import-csv" @click="pickCsv">导入 CSV</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                CSV 三列:path,value,is_null —— 表头按名定位(列序任意);is_null=1 为显式 null,两列都留空 = 该行不导入;面外字段会被跳过
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" :disabled="!rows.length" data-testid="dl-template" @click="downloadTemplate">下载模板</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                按当前服务的字段面生成模板(预填全部 path 与已绑定值);不改直接导回 = 绑定态不变
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" :disabled="!hasBoundRows" data-testid="export-csv" @click="downloadBoundCsv">导出 CSV</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                导出该服务的已绑定行(未绑定的面字段不进文件);导出→不改→导回 = 绑定态不变
              </TooltipContent>
            </Tooltip>
            <input
              ref="csvInput"
              type="file"
              accept=".csv,text/csv"
              class="hidden"
              @change="onCsvPicked"
            />
          </div>
          </TooltipProvider>

          <Alert v-if="degraded" variant="destructive" class="mb-3.5">
            <AlertTitle>字段面部分降级,保存已禁用</AlertTitle>
            <AlertDescription>
              字段面部分降级(部分端点不可达),保存会删除不可见端点的绑定值,已禁用;请稍后刷新重试
            </AlertDescription>
          </Alert>

          <div v-if="loadingFields" class="py-6 text-center text-body text-muted-foreground">加载字段面…</div>
          <Table v-else-if="rows.length" class="rounded-field border border-signal-line bg-signal-card">
            <TableHeader>
              <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
                <TableHead class="text-caption font-semibold text-muted-foreground">字段路径</TableHead>
                <TableHead class="w-[90px] text-caption font-semibold text-muted-foreground">类型</TableHead>
                <TableHead class="text-caption font-semibold text-muted-foreground">说明</TableHead>
                <TableHead class="text-caption font-semibold text-muted-foreground">值</TableHead>
                <TableHead class="w-[150px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in rows" :key="row.path" :data-testid="`svc-row-${row.path}`">
                <TableCell><code class="path font-mono font-semibold text-signal">{{ row.path }}</code></TableCell>
                <TableCell class="text-caption text-muted-foreground">{{ row.type }}</TableCell>
                <TableCell class="text-caption text-muted-foreground">{{ row.description }}</TableCell>
                <TableCell>
                  <Input
                    v-model="row.value"
                    :disabled="row.isNull"
                    :placeholder="valuePlaceholder(row)"
                    class="h-8"
                  />
                </TableCell>
                <TableCell>
                  <div class="flex items-center gap-1">
                    <Button variant="link" size="sm" class="h-7 px-2" @click="toggleNull(row)">
                      {{ row.isNull ? '取消 null' : '设 null' }}
                    </Button>
                    <Button v-if="row.hasRow" variant="link" size="sm" class="h-7 px-2 text-signal-failed" @click="removeBindingRow(row)">
                      删行
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <div v-else class="c-empty">
            <p>{{ service ? '该服务无声明的 carry 字段(plate 未声明或服务名未命中)' : '先选择或输入服务名,拉取字段面' }}</p>
          </div>

          <div class="card-footer">
            <Button data-testid="save-service" :disabled="!service || degraded" @click="saveService">保存</Button>
          </div>
        </div>
      </TabsContent>

      <!-- ── 全局默认 ─────────────────────────────── -->
      <TabsContent value="defaults">
        <div class="c-card">
          <div class="c-card-head">
            <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
            <div>
              <h3>全局默认(兜底层)</h3>
              <p class="c-head-desc">保存 = 整表替换;删行后保存即移除该默认</p>
            </div>
          </div>

          <Alert class="mb-3.5">
            <AlertTitle>全局默认按纯 path 跨服务生效 —— 契约门控只保证不注入未声明字段;</AlertTitle>
            <AlertDescription>
              $.type 类语义敏感路径请用服务绑定覆盖兜底(配置纪律,spec §6)。
            </AlertDescription>
          </Alert>

          <TooltipProvider>
          <div class="svc-bar">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" data-testid="import-defaults-csv" @click="pickDefaultsCsv">导入 CSV</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                CSV 三列:path,value,is_null —— 表头按名定位(列序任意);已有 path 更新、新 path 追加,两列都留空 = 该行不导入;导入后仍须手动保存
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" data-testid="dl-defaults-template" @click="downloadDefaultsTemplate">下载模板</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                表头 + 一行示例(path 已填、值列留空 → 原样导回也是无操作)
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button variant="outline" :disabled="!hasDefaultRows" data-testid="export-defaults-csv" @click="downloadDefaultsCsv">导出 CSV</Button>
              </TooltipTrigger>
              <TooltipContent class="max-w-[320px]">
                导出当前全部默认行;导出→不改→导回 = 默认态不变
              </TooltipContent>
            </Tooltip>
            <input
              ref="defaultsCsvInput"
              type="file"
              accept=".csv,text/csv"
              class="hidden"
              @change="onDefaultsCsvPicked"
            />
          </div>
          </TooltipProvider>

          <Table v-if="defaultRows.length" class="rounded-field border border-signal-line bg-signal-card">
            <TableHeader>
              <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
                <TableHead class="text-caption font-semibold text-muted-foreground">字段路径</TableHead>
                <TableHead class="text-caption font-semibold text-muted-foreground">值</TableHead>
                <TableHead class="w-[130px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="(row, i) in defaultRows" :key="i" :data-testid="`defaults-row-${i}`">
                <TableCell>
                  <Input v-model="row.path" placeholder="$.headers.X-Trace-Id" class="h-8" />
                </TableCell>
                <TableCell>
                  <Input
                    v-model="row.value"
                    :disabled="row.isNull"
                    :placeholder="row.isNull ? '显式 null(屏蔽注入)' : ''"
                    class="h-8"
                  />
                </TableCell>
                <TableCell>
                  <div class="flex items-center gap-1">
                    <Button variant="link" size="sm" class="h-7 px-2" @click="row.isNull = !row.isNull">
                      {{ row.isNull ? '取消 null' : '设 null' }}
                    </Button>
                    <Button variant="link" size="sm" class="h-7 px-2 text-signal-failed" @click="defaultRows.splice(i, 1)">
                      删
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <div v-if="!defaultRows.length" class="c-empty">
            <p>还没有全局默认 — 加一行(例 $.headers.X-Trace-Id)</p>
          </div>

          <div class="card-footer">
            <Button variant="outline" data-testid="add-default-row" @click="addDefaultRow">加一行</Button>
            <Button data-testid="save-defaults" @click="saveDefaults">保存</Button>
          </div>
        </div>
      </TabsContent>
    </Tabs>
  </section>
</template>

<script setup lang="ts">
/**
 * CarryConfig —— 传递字段配置(spec §6)。
 * 服务绑定 tab:选服务 → 拉该服务 carry 字段面并集 → 逐字段填值;
 *   placeholder = 全局默认值(无行时);删行 = 不注入(回退全局默认);
 *   「设 null」= 显式注入 JSON null(§3.1)。
 * 全局默认 tab:整表编辑;常驻提示纯 path 跨服务生效(§6)。
 */
import { computed, onMounted, ref } from 'vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { buildServiceEntries, type ServiceCarryRow } from '@/utils/carry-entries'
import {
  CarryCsvError, buildBoundCsv, buildCarryTemplate, buildDefaultsCsv,
  buildDefaultsTemplateCsv, mergeCarryCsv, mergeDefaultsCsv, parseCarryCsv,
  type DefaultCarryRow,
} from '@/utils/carry-csv'
import {
  getDefaults, putDefaults, getBindings, getBindingsFor, putBindings, getServiceFields,
  type CarryFieldFace, type CarryValues,
} from '@/api/carry'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const activeTab = ref('service')

// ── 服务绑定 ──────────────────────────────────────────────
/** 行三态:hasRow=false 无行;isNull=true 显式 null;否则空串/字串值。
 *  拆成布尔列是必须的 —— Input 的 v-model 会把 null 折叠成 '',
 *  空串值/null/无行在输入框里不可区分(task-15 执行注)。
 *  保存编码(任何输入即建行,修复 R1-B1)收敛在 buildServiceEntries。 */
interface ServiceRow extends ServiceCarryRow {
  type: string
  description: string
}

const service = ref('')
const rows = ref<ServiceRow[]>([])
const defaultsMap = ref<CarryValues>({})
const knownServices = ref<string[]>([])
const loadingFields = ref(false)
/** 字段面降级门控(数据安全):rows 仅由 plate 面构建,而保存是整表替换 —
 *  面不完整(单端点 /full 失败,或加载整体失败)时放行保存会不可逆删除
 *  不可见端点的绑定值。每次 onServiceChange 刷新时重置。 */
const degraded = ref(false)

async function loadBindings() {
  const bindings = await getBindings()
  knownServices.value = Object.keys(bindings)
}

/** 无行时的 placeholder:透出该 path 的全局默认(兜底层会注入什么)。 */
function valuePlaceholder(row: ServiceRow): string {
  if (row.isNull) return '显式 null(不注入值)'
  if (row.hasRow) return ''
  if (!(row.path in defaultsMap.value)) return '未配置(不注入)'
  const v = defaultsMap.value[row.path]
  if (v === null) return '默认注入 null'
  return v === '' ? '默认注入(空串)' : v
}

async function onServiceChange() {
  degraded.value = false
  if (!service.value) {
    rows.value = []
    return
  }
  loadingFields.value = true
  try {
    const [faceRes, bound] = await Promise.all([
      getServiceFields(service.value),
      getBindingsFor(service.value),
    ])
    degraded.value = faceRes.degraded
    rows.value = faceRes.fields.map((f: CarryFieldFace) => {
      const hasRow = f.path in bound
      const boundValue = bound[f.path]
      return {
        path: f.path,
        type: f.type,
        description: f.description,
        value: hasRow && boundValue !== null ? boundValue : '',
        isNull: hasRow && boundValue === null,
        hasRow,
      }
    })
  } catch (e) {
    showError('加载字段面', e)
    rows.value = []
    // 加载整体失败是最大降级:rows=[] 下保存 = 清空该服务全部绑定
    degraded.value = true
  } finally {
    loadingFields.value = false
  }
}

function toggleNull(row: ServiceRow) {
  row.isNull = !row.isNull
  if (row.isNull) row.hasRow = true // 设 null 隐含建行
}

// ── CSV 批量导入(表编辑动作,不自动保存)────────────────────
const csvInput = ref<HTMLInputElement | null>(null)

function pickCsv() {
  csvInput.value?.click()
}

/** 下载文本文件:前缀 BOM 保证 Excel 识别 UTF-8(两 tab 共用)。 */
function downloadText(filename: string, text: string) {
  const blob = new Blob([`﻿${text}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 下载模板:字段面全量 path + 当前绑定值。 */
function downloadTemplate() {
  downloadText(`carry-${service.value || 'template'}.csv`, buildCarryTemplate(rows.value))
}

/** 导出已绑定行:无绑定行时按钮禁用,不会产出纯表头文件。 */
const hasBoundRows = computed(() => rows.value.some((r) => r.hasRow))

function downloadBoundCsv() {
  downloadText(`carry-${service.value}-bindings.csv`, buildBoundCsv(rows.value))
}

async function onCsvPicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 清掉选择,同名文件可重复导入
  if (!file) return
  let parsed
  try {
    parsed = parseCarryCsv(await file.text())
  } catch (err) {
    if (err instanceof CarryCsvError) {
      toast.error(`CSV 格式错误:${err.message}`)
    } else {
      showError('读取 CSV', err)
    }
    return
  }
  const report = mergeCarryCsv(rows.value, parsed)
  const unsaved = '尚未保存,请核对后点「保存」'
  if (report.skippedUnknown.length > 0) {
    toast.warning(
      `已导入 ${report.applied} 条(${unsaved});` +
      `面外跳过 ${report.skippedUnknown.length} 条(未声明,门控会滤掉):` +
      report.skippedUnknown.join('、'),
    )
  } else {
    toast.success(`已导入 ${report.applied} 条(${unsaved})`)
  }
}

/** 删行 = 保存时不再写入该 path → 运行时回退全局默认。 */
function removeBindingRow(row: ServiceRow) {
  row.hasRow = false
  row.isNull = false
  row.value = ''
}

async function saveService() {
  if (!service.value) return
  // 编码规则(R1-B1 修复):无行且无输入才跳过 —— hasRow=false 的行
  // 输入框可编辑(透全局默认 placeholder),用户填了值必须建行,
  // 旧 `!hasRow → continue` 会静默丢弃并假报"已保存"
  const entries = buildServiceEntries(rows.value)
  try {
    await putBindings(service.value, entries)
    toast.success('已保存')
    // 回读:让 hasRow/isNull 与刚落库的状态一致(新建行亮出「删行」)
    void onServiceChange()
    // 自由输入的新服务入库后刷新候选列表(datalist)
    loadBindings().catch(() => { /* 候选列表刷新失败不惊动已成功的保存提示 */ })
  } catch (e) {
    showError('保存', e)
  }
}

// ── 全局默认 ──────────────────────────────────────────────
const defaultRows = ref<DefaultCarryRow[]>([])

async function loadDefaults() {
  const d = await getDefaults()
  defaultsMap.value = d
  defaultRows.value = Object.entries(d).map(([path, value]) => ({
    path,
    value: value ?? '',
    isNull: value === null,
  }))
}

function addDefaultRow() {
  defaultRows.value.push({ path: '', value: '', isNull: false })
}

// ── 全局默认 CSV(与服务绑定同格式;导入 = upsert 表编辑,不自动保存)──
const defaultsCsvInput = ref<HTMLInputElement | null>(null)
/** 有可导出的默认行(非空白 path);全空时导出按钮禁用。 */
const hasDefaultRows = computed(() => defaultRows.value.some((r) => r.path))

function pickDefaultsCsv() {
  defaultsCsvInput.value?.click()
}

function downloadDefaultsTemplate() {
  downloadText('carry-defaults-template.csv', buildDefaultsTemplateCsv())
}

function downloadDefaultsCsv() {
  downloadText('carry-defaults.csv', buildDefaultsCsv(defaultRows.value))
}

async function onDefaultsCsvPicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 清掉选择,同名文件可重复导入
  if (!file) return
  let parsed
  try {
    parsed = parseCarryCsv(await file.text())
  } catch (err) {
    if (err instanceof CarryCsvError) {
      toast.error(`CSV 格式错误:${err.message}`)
    } else {
      showError('读取 CSV', err)
    }
    return
  }
  const report = mergeDefaultsCsv(defaultRows.value, parsed)
  toast.success(
    `已导入:更新 ${report.updated} 条、新增 ${report.added} 条(尚未保存,请核对后点「保存」)`,
  )
}

/** 重复 path 会让后写行静默覆盖先行(dict 键折叠)— 保存前拦截(R1-M2)。 */
function firstDuplicatePath(rows: DefaultCarryRow[]): string | null {
  const seen = new Set<string>()
  for (const r of rows) {
    if (!r.path) continue
    if (seen.has(r.path)) return r.path
    seen.add(r.path)
  }
  return null
}

async function saveDefaults() {
  const dup = firstDuplicatePath(defaultRows.value)
  if (dup) {
    toast.warning(`字段路径重复:${dup} — 保存会静默覆盖,请先去重`)
    return
  }
  const entries: CarryValues = {}
  for (const r of defaultRows.value) {
    if (!r.path) continue
    entries[r.path] = r.isNull ? null : r.value
  }
  try {
    await putDefaults(entries)
    toast.success('已保存')
    // 回读:让 isNull/value 与后端规范化结果一致,并刷新服务 tab 的默认 placeholder
    await loadDefaults()
  } catch (e) {
    showError('保存', e)
  }
}

// ── init ─────────────────────────────────────────────────
onMounted(() => {
  loadDefaults().catch((e) => showError('加载', e))
  loadBindings().catch((e) => showError('加载', e))
})
</script>

<style scoped>
.svc-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.path {
  word-break: break-all;
}

.card-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
