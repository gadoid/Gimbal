<!-- CarryDefaultsEditor.vue — S7.3:carry 兜底默认值编辑(可复用)。
     从 CarryConfig.vue(/carry-config 退役)抽取的可编辑草稿表:三态
     编码、CSV 三件套、R1-M2 重复 path 拦截原样;作用域由 props.target
     决定(project/user/global),写面权限由父级 canWrite 守门。 -->
<template>
  <div class="editor" data-testid="carry-defaults-editor">
    <div v-if="loading" class="muted">加载中…</div>
    <template v-else>
      <div v-if="canWrite" class="bar">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" :data-testid="`${tid}-import-csv`" @click="pickCsv">导入 CSV</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
              CSV 三列:path,value,is_null —— 表头按名定位(列序任意);已有 path 更新、新 path 追加,两列都留空 = 该行不导入;导入后仍须手动保存
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" :data-testid="`${tid}-dl-template`" @click="downloadTemplate">下载模板</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
              表头 + 一行示例(path 已填、值列留空 → 原样导回也是无操作)
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" :disabled="!hasRows" :data-testid="`${tid}-export-csv`" @click="downloadCsv">导出 CSV</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
              导出当前全部默认行;导出→不改→导回 = 默认态不变
            </TooltipContent>
          </Tooltip>
          <input ref="csvInput" type="file" accept=".csv,text/csv" class="hidden" @change="onCsvPicked" />
        </TooltipProvider>
      </div>

      <div v-if="rows.length" class="lib-card">
        <table class="tbl">
          <thead>
            <tr>
              <th style="width:45%">字段路径</th>
              <th style="width:41%">值</th>
              <th v-if="canWrite" style="width:14%" class="c-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in paged" :key="pageBase + i" :data-testid="`${tid}-row-${pageBase + i}`"
                :data-path="row.path" :class="{ 'path-hit': !!highlightPath && row.path === highlightPath }">
              <td><Input v-model="row.path" placeholder="$.headers.X-Trace-Id" class="h-8" :disabled="!canWrite" /></td>
              <td>
                <Input
                  v-model="row.value"
                  :disabled="!canWrite || row.isNull"
                  :placeholder="row.isNull ? '显式 null(屏蔽注入)' : ''"
                  class="h-8"
                />
              </td>
              <td v-if="canWrite" class="c-center">
                <div class="row-acts">
                  <button type="button" class="link" @click="row.isNull = !row.isNull">
                    {{ row.isNull ? '取消 null' : '设 null' }}
                  </button>
                  <button type="button" class="link danger" @click="rows.splice(pageBase + i, 1)">删</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="pageCount > 1 || rows.length > 0" class="mt-2 flex justify-end">
        <Pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="rows.length"
          show-page-size
          show-jump
        />
      </div>
      <p v-else class="muted empty-hint">
        还没有默认行<template v-if="canWrite"> —— 加一行(例 <code class="mono">$.headers.X-Trace-Id</code>)</template>
      </p>

      <div v-if="canWrite" class="foot">
        <span class="foot-right">
          <Button variant="outline" :data-testid="`${tid}-add-row`" @click="rows.push({ path: '', value: '', isNull: false })">加一行</Button>
          <Button :data-testid="`${tid}-save`" @click="save">保存</Button>
        </span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * CarryDefaultsEditor —— carry 兜底默认值按层编辑(S7.3)。
 * 数据面 = api/carry getDefaults/putDefaults(target 作用域);CSV/分页/
 * 去重守卫与原 /carry-config 页同源(utils/carry-csv + useClientPager)。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import {
  CarryCsvError, buildDefaultsCsv, buildDefaultsTemplateCsv, mergeDefaultsCsv, parseCarryCsv,
  type DefaultCarryRow,
} from '@/utils/carry-csv'
import { getDefaults, putDefaults, type CarryValues, type ScopeTarget } from '@/api/carry'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Pagination } from '@/components/ui/pagination'
import { useClientPager } from '@/composables/useClientPager'

const props = defineProps<{
  target: ScopeTarget
  canWrite: boolean
  /** 测试锚前缀(多实例并存时区分) */
  tid?: string
  /** ?path= 深链命中行高亮(原 /carry-config 行为;键详情「默认值」
   * 来源 chip 的落点) */
  highlightPath?: string
}>()

const emit = defineEmits<{ saved: [] }>()

const tid = computed(() => props.tid ?? 'cde')

const loading = ref(true)
const rows = ref<DefaultCarryRow[]>([])

async function load(): Promise<void> {
  const d = await getDefaults(props.target)
  rows.value = Object.entries(d).map(([path, value]) => ({
    path,
    value: value ?? '',
    isNull: value === null,
  }))
}

/** 重复 path 会让后写行静默覆盖先行(dict 键折叠)— 保存前拦截(R1-M2)。 */
function firstDuplicatePath(list: DefaultCarryRow[]): string | null {
  const seen = new Set<string>()
  for (const r of list) {
    if (!r.path) continue
    if (seen.has(r.path)) return r.path
    seen.add(r.path)
  }
  return null
}

async function save(): Promise<void> {
  const dup = firstDuplicatePath(rows.value)
  if (dup) {
    toast.warning(`字段路径重复:${dup} — 保存会静默覆盖,请先去重`)
    return
  }
  const entries: CarryValues = {}
  for (const r of rows.value) {
    if (!r.path) continue
    entries[r.path] = r.isNull ? null : r.value
  }
  try {
    await putDefaults(entries, props.target)
    toast.success('已保存')
    await load() // 回读:让 isNull/value 与后端规范化结果一致
    emit('saved')
  } catch (e) {
    showError('保存', e)
  }
}

// ── CSV(与绑定层同格式;导入 = upsert 表编辑,不自动保存)─────────
const csvInput = ref<HTMLInputElement | null>(null)
/** 有可导出的默认行(非空白 path);全空时导出按钮禁用。 */
const hasRows = computed(() => rows.value.some((r) => r.path))

function pickCsv(): void { csvInput.value?.click() }

/** 下载文本文件:前缀 BOM 保证 Excel 识别 UTF-8。 */
function downloadText(filename: string, text: string): void {
  const blob = new Blob([`\ufeff${text}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function downloadTemplate(): void {
  downloadText('carry-defaults-template.csv', buildDefaultsTemplateCsv())
}

function downloadCsv(): void {
  downloadText('carry-defaults.csv', buildDefaultsCsv(rows.value))
}

async function onCsvPicked(e: Event): Promise<void> {
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
  const report = mergeDefaultsCsv(rows.value, parsed)
  toast.success(
    `已导入:更新 ${report.updated} 条、新增 ${report.added} 条(尚未保存,请核对后点「保存」)`,
  )
}

// 客户端分页:pageBase = 当前页首行的全局下标,删行/编辑/splice 都按
// 全局下标写 rows 草稿。
const { page, pageSize, paged, pageCount } = useClientPager(
  () => rows.value, 10, `carry-defaults-${tid.value}`,
)
const pageBase = computed(() => (page.value - 1) * pageSize.value)

async function reload(): Promise<void> {
  loading.value = true
  try { await load() } finally { loading.value = false }
}

watch(() => props.target, reload, { deep: true })
onMounted(async () => {
  await reload()
  // ?path= 深链:命中行可能不在第 1 页 → 先翻到所在页再滚动
  if (props.highlightPath) {
    const idx = rows.value.findIndex((r) => r.path === props.highlightPath)
    if (idx >= 0) page.value = Math.floor(idx / pageSize.value) + 1
    await nextTick()
    // 不用 CSS.escape(jsdom 无 CSS 全局):按属性值直接比较
    const hit = [...document.querySelectorAll<HTMLElement>('[data-path]')]
      .find((el) => el.getAttribute('data-path') === props.highlightPath)
    hit?.scrollIntoView?.({ block: 'center' })
  }
})
</script>

<style scoped>
/* ?path= 深链命中行:蓝环 + 淡蓝底高亮(原 /carry-config 行为) */
.path-hit td { background: rgb(37 99 235 / 8%); }
.path-hit { outline: 2px solid #2563eb; outline-offset: -2px; }
.editor { display: flex; flex-direction: column; gap: 0.5rem; }
.bar { display: flex; gap: 0.5rem; align-items: center; }
.mt-2 { margin-top: 0.5rem; }
.muted { color: #94a3b8; }
.empty-hint { font-size: 0.85rem; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.tbl th, .tbl td { text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.tbl th { color: #64748b; font-weight: 500; }
.c-center { text-align: center; }
.row-acts { display: flex; gap: 0.5rem; justify-content: center; }
.link { border: none; background: none; color: #2563eb; cursor: pointer; font-size: 0.78rem; padding: 0; }
.link.danger { color: #dc2626; }
.foot { display: flex; justify-content: flex-end; }
.foot-right { display: flex; gap: 0.5rem; }
</style>
