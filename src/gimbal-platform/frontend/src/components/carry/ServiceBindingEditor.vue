<!--
  ServiceBindingEditor.vue — carry 绑定键编辑器(配套方案 §2,C2 拆分)。
  从 CarryConfig 服务绑定 tab 整体提取,语义不变 + 两处扩展:
  * 锁定键:serviceKey 由父页指定(别名详情 / 服务详情),不再内置选择器
    —— 配置入口收拢到服务信息管理,自由输入键的路线废止;
  * 「来源」列(§2.4):无本键行的字段显式标注有效值来自哪层 ——
    本键 / 服务级(别名键时) / 默认值 / 无行(不注入),三态各有位置。
  三态(hasRow/isNull/值)布尔列编码、CSV 三件套、degraded 保存门控、
  R1-B1 编码修复全部原样(真源 utils/carry-entries + carry-csv)。
-->
<template>
  <div class="svc-panel">
    <div class="svc-panel-head">
      <span class="svc-panel-title">
      <svg class="head-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
        {{ ownLabel }}绑定(覆盖层)
      </span>
      <span class="svc-panel-desc">
        <code class="mono">{{ serviceKey }}</code> → 拉取 carry 字段面(plate 声明并集)→ 逐字段填值;
        保存 = 本键整表替换{{ isAlias ? ',只写别名键的行,其余层不动' : '' }}
      </span>
    </div>

    <TooltipProvider>
      <div class="svc-bar">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button variant="outline" :disabled="!rows.length" data-testid="import-csv" @click="pickCsv">导入 CSV</Button>
          </TooltipTrigger>
          <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
            CSV 三列:path,value,is_null —— 表头按名定位(列序任意);is_null=1 为显式 null,两列都留空 = 该行不导入;面外字段会被跳过
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button variant="outline" :disabled="!rows.length" data-testid="dl-template" @click="downloadTemplate">下载模板</Button>
          </TooltipTrigger>
          <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
            按当前字段面生成模板(预填全部 path 与已绑定值);不改直接导回 = 绑定态不变
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button variant="outline" :disabled="!hasBoundRows" data-testid="export-csv" @click="downloadBoundCsv">导出 CSV</Button>
          </TooltipTrigger>
          <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
            导出本键的已绑定行(未绑定的面字段不进文件);导出→不改→导回 = 绑定态不变
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

    <div v-if="loadingFields" class="slib-loading">加载字段面…</div>
    <div v-else-if="rows.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:28%">字段路径</th>
            <th style="width:7%">类型</th>
            <th style="width:11%">来源</th>
            <th style="width:18%">说明</th>
            <th style="width:24%">值</th>
            <th style="width:12%" class="c-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.path" :data-testid="`svc-row-${row.path}`">
            <td>
              <code class="path">{{ row.path }}</code>
              <!-- G6:贡献端点上下文 —— 字段属于服务内哪个(哪些)接口 -->
              <div
                v-if="row.endpoints?.length"
                class="svc-endpoints muted"
                :title="row.endpoints.map(e => e.id).join(', ')"
              >
                <span
                  v-for="e in row.endpoints"
                  :key="e.id"
                  class="svc-ep-chip"
                >{{ e.name || e.method || e.id }}</span>
              </div>
            </td>
            <td class="muted">{{ row.type }}</td>
            <td>
              <!-- 「来源」= 三层链的落点,配色与键详情那条链同一族:
                   本键蓝 · 服务级紫 · 默认值(可点跳兜底层)· 无行虚线 -->
              <button
                v-if="sourceOf(row) === 'default'"
                type="button"
                class="svc-flag src-link"
                :data-testid="`svc-source-${row.path}`"
                :title="`该兜底值在「默认值」页的位置(${row.path})`"
                @click="router.push(`/carry-config?path=${encodeURIComponent(row.path)}`)"
              >{{ sourceLabel(row) }} ↗</button>
              <span
                v-else
                class="svc-flag"
                :class="`src-${sourceOf(row)}`"
                :data-testid="`svc-source-${row.path}`"
              >
                {{ sourceLabel(row) }}
              </span>
            </td>
            <td class="muted">{{ row.description }}</td>
            <td>
              <Input
                v-model="row.value"
                :disabled="row.isNull"
                :placeholder="valuePlaceholder(row)"
                class="h-8"
              />
            </td>
            <td class="c-center">
              <div class="row-acts">
                <button type="button" class="svc-link" @click="toggleNull(row)">
                  {{ row.isNull ? '取消 null' : '设 null' }}
                </button>
                <button v-if="row.hasRow" type="button" class="svc-link danger" @click="removeBindingRow(row)">
                  删行
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="slib-empty">
      <p>该键无声明的 carry 字段(plate 未声明或服务名未命中)</p>
    </div>

    <div class="svc-foot">
      <!-- 原型 H-alias-detail 表底统计:共 N 字段 · 本键已覆盖 N · 兜底完整度 -->
      <span class="footer-stats" data-testid="editor-stats">
        共 {{ rows.length }} 字段 · {{ ownLabel }}已覆盖 {{ ownCount }} · 链路兜底完整度 {{ coveredCount }}/{{ rows.length }}
      </span>
      <span class="svc-foot-right">
        <Button variant="outline" :disabled="loadingFields || degraded" data-testid="reload-face" @click="reload">刷新</Button>
        <Button data-testid="save-service" :disabled="degraded" @click="save">保存</Button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ServiceBindingEditor —— 单个 carry 绑定键的编辑器(配套方案 §2.3)。
 *
 * 键 = serviceKey(别名全名或 base 服务名),保存只写本键的行
 * (putBindings 整表替换),运行时三层解析(精确键 > base > 默认)在
 * carry_injection / 字段面在 routers/carry(键归一)完成,本组件只管
 * 本键这一层的编辑面 + 「来源」列把其余两层透出来(§2.4 三态各有
 * 显式位置:本键行 / 继承层 placeholder / 无行 = 不注入)。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { buildServiceEntries, type ServiceCarryRow } from '@/utils/carry-entries'
import {
  CarryCsvError, buildBoundCsv, buildCarryTemplate, mergeCarryCsv, parseCarryCsv,
} from '@/utils/carry-csv'
import {
  getDefaults, getBindingsFor, putBindings, getServiceFields,
  type CarryEndpointMini, type CarryFieldFace, type CarryValues,
} from '@/api/carry'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const props = defineProps<{
  /** 绑定键:别名全名或 base 服务名(保存整表替换的键)。 */
  serviceKey: string
  /** 归一后的 base 目录服务;= serviceKey 时无「服务级」继承层。 */
  baseService?: string | null
}>()

/** 行三态:hasRow=false 无行;isNull=true 显式 null;否则空串/字串值。
 *  拆布尔列是必须的 —— Input 的 v-model 会把 null 折叠成 '',空串/null/
 *  无行在输入框里不可区分;保存编码收敛在 buildServiceEntries(R1-B1)。 */
interface ServiceRow extends ServiceCarryRow {
  type: string
  /** G6:贡献端点上下文(来自 face 折叠,展示 chip)。 */
  endpoints: CarryEndpointMini[]
  description: string
}

const isAlias = computed(() => !!props.baseService && props.baseService !== props.serviceKey)
const ownLabel = computed(() => (isAlias.value ? '本别名' : '本服务'))
const router = useRouter()

/** 表底统计(原型 H-alias-detail):本键行数 / 非 none 来源的链路覆盖数。 */
const ownCount = computed(() => rows.value.filter((r) => r.hasRow).length)
const coveredCount = computed(() => rows.value.filter((r) => sourceOf(r) !== 'none').length)

const rows = ref<ServiceRow[]>([])
const defaultsMap = ref<CarryValues>({})
const baseBindings = ref<CarryValues>({})
const loadingFields = ref(false)
/** 字段面降级门控(数据安全):rows 仅由 plate 面构建,而保存是整表替换 —
 *  面不完整(单端点 /full 失败,或加载整体失败)时放行保存会不可逆删除
 *  不可见端点的绑定值。每次 reload 重置。 */
const degraded = ref(false)

type Source = 'own' | 'service' | 'default' | 'none'

/** 无本键行时的来源判定(与 carry_injection 三层链同构,只读展示)。 */
function sourceOf(row: ServiceRow): Source {
  if (row.hasRow) return 'own'
  if (isAlias.value && row.path in baseBindings.value) return 'service'
  if (row.path in defaultsMap.value) return 'default'
  return 'none'
}

function sourceLabel(row: ServiceRow): string {
  switch (sourceOf(row)) {
    case 'own': return ownLabel.value
    case 'service': return '服务级'
    case 'default': return '默认值'
    default: return '无行'
  }
}

/** 无行时的 placeholder:透出继承层会注入什么(值本身,不改此处)。 */
function valuePlaceholder(row: ServiceRow): string {
  if (row.isNull) return '显式 null(不注入值)'
  if (row.hasRow) return ''
  if (isAlias.value && row.path in baseBindings.value) {
    const v = baseBindings.value[row.path]
    if (v === null) return '服务级注入 null'
    return v === '' ? '服务级注入(空串)' : `服务级注入:${v}`
  }
  if (row.path in defaultsMap.value) {
    const v = defaultsMap.value[row.path]
    if (v === null) return '默认注入 null'
    return v === '' ? '默认注入(空串)' : v
  }
  return '未配置(不注入)'
}

async function reload(): Promise<void> {
  degraded.value = false
  loadingFields.value = true
  try {
    const tasks: [Promise<{ fields: CarryFieldFace[]; degraded: boolean }>, Promise<CarryValues>, Promise<CarryValues>] = [
      getServiceFields(props.serviceKey),
      getBindingsFor(props.serviceKey),
      isAlias.value ? getBindingsFor(props.baseService!) : Promise.resolve({}),
    ]
    const [faceRes, bound, base] = await Promise.all(tasks)
    degraded.value = faceRes.degraded
    baseBindings.value = base
    rows.value = faceRes.fields.map((f: CarryFieldFace) => {
      const hasRow = f.path in bound
      const boundValue = bound[f.path]
      return {
        path: f.path,
        type: f.type,
        description: f.description,
        endpoints: f.endpoints ?? [],
        value: hasRow && boundValue !== null ? boundValue : '',
        isNull: hasRow && boundValue === null,
        hasRow,
      }
    })
  } catch (e) {
    showError('加载字段面', e)
    rows.value = []
    // 加载整体失败是最大降级:rows=[] 下保存 = 清空本键全部绑定
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

/** 下载文本文件:前缀 BOM 保证 Excel 识别 UTF-8。 */
function downloadText(filename: string, text: string) {
  const blob = new Blob([`﻿${text}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function downloadTemplate() {
  downloadText(`carry-${props.serviceKey}-template.csv`, buildCarryTemplate(rows.value))
}

const hasBoundRows = computed(() => rows.value.some((r) => r.hasRow))

function downloadBoundCsv() {
  downloadText(`carry-${props.serviceKey}-bindings.csv`, buildBoundCsv(rows.value))
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

/** 删行 = 保存时不再写入该 path → 运行时回退继承层。 */
function removeBindingRow(row: ServiceRow) {
  row.hasRow = false
  row.isNull = false
  row.value = ''
}

async function save() {
  // 编码规则(R1-B1 修复):无行且无输入才跳过 —— hasRow=false 的行
  // 输入框可编辑(透继承层 placeholder),用户填了值必须建行
  const entries = buildServiceEntries(rows.value)
  try {
    await putBindings(props.serviceKey, entries)
    toast.success('已保存')
    void reload()
  } catch (e) {
    showError('保存', e)
  }
}

watch(() => [props.serviceKey, props.baseService], () => { void reload() })
onMounted(async () => {
  defaultsMap.value = await getDefaults().catch((): CarryValues => ({}))
  await reload()
})
</script>

<style scoped>
.head-icon { flex: none; color: var(--sl-accent); }

/* 字段路径 = 这张表的主键:等宽、加粗、可折行 */
.path {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  font-weight: 600;
  color: var(--sl-ink);
  word-break: break-all;
}

.footer-stats { font-size: 11px; color: var(--sl-ink-3); }

/* 「来源」四档 = 三层查找链的读法:本键蓝 → 服务级紫 → 默认值灰 → 无行虚线。
   无行(不注入)是语义终点,所以它必须占一个可见的位置,而不是留白。 */
.src-own { color: var(--sl-accent); background: var(--sl-accent-soft); }
.src-service { color: var(--sv-violet); background: var(--sv-violet-soft); }
.src-none {
  color: var(--sl-ink-3);
  background: transparent;
  border: 1px dashed var(--sl-star-off);
}
.src-link { cursor: pointer; border: 0; }
.src-link:hover { color: var(--sl-accent); text-decoration: underline; }
</style>

<style scoped>
.svc-endpoints {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.svc-ep-chip {
  font-size: 11px;
  line-height: 1.4;
  padding: 0 6px;
  border: 1px solid var(--border, #ddd);
  border-radius: 999px;
  white-space: nowrap;
}
</style>
