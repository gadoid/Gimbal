<!-- CarryConfig.vue — 默认值(配套方案 §2.2,C2 拆分后只剩兜底层)。
     原「服务绑定」tab 已整体迁出:别名 / 服务的字段默认值编辑在
     服务信息管理的键详情页(ServiceAliasDetail + ServiceBindingEditor),
     本页只留跨服务的全局兜底层。三态编码、CSV 三件套、R1-M2 重复
     path 拦截原样(真源 utils/carry-csv + api/carry)。 -->
<template>
  <section class="slib">
    <PageHead
      icon="sliders"
      title="默认值"
      :count="loading ? '' : `${defaultRows.length} 行`"
      subtitle="哪个服务 / 别名都没配时生效(兜底层);删行 = 不注入,null = 显式注入 JSON null"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div v-else class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">
          <span class="icon-badge" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 7h16M4 12h16M4 17h16" />
              <circle cx="9" cy="7" r="2.2" />
              <circle cx="15" cy="12" r="2.2" />
              <circle cx="7" cy="17" r="2.2" />
            </svg>
          </span>
          全局默认(兜底层)
        </span>
        <span class="svc-panel-desc">保存 = 整表替换;删行后保存即移除该默认。服务 / 别名级的覆盖层在服务信息管理的键详情里配</span>
      </div>

      <div class="svc-banner warn">
        <span>
          <b>全局默认按纯 path 跨服务生效</b> —— 契约门控只保证不注入未声明字段;
          $.type 类语义敏感路径请用服务绑定覆盖兜底(配置纪律,spec §6)。
        </span>
      </div>

      <TooltipProvider>
        <div class="svc-bar">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" data-testid="import-defaults-csv" @click="pickDefaultsCsv">导入 CSV</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
              CSV 三列:path,value,is_null —— 表头按名定位(列序任意);已有 path 更新、新 path 追加,两列都留空 = 该行不导入;导入后仍须手动保存
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" data-testid="dl-defaults-template" @click="downloadDefaultsTemplate">下载模板</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
              表头 + 一行示例(path 已填、值列留空 → 原样导回也是无操作)
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="outline" size="sm" :disabled="!hasDefaultRows" data-testid="export-defaults-csv" @click="downloadDefaultsCsv">导出 CSV</Button>
            </TooltipTrigger>
            <TooltipContent class="max-w-[min(320px,calc(100vw-2rem))]">
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

      <div v-if="defaultRows.length" class="lib-card">
        <table class="slib-table">
          <thead>
            <tr>
              <th style="width:45%">字段路径</th>
              <th style="width:41%">值</th>
              <th style="width:14%" class="c-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in defaultRows"
              :key="i"
              :data-testid="`defaults-row-${i}`"
              :data-path="row.path"
              :class="{ 'path-hit': !!highlightPath && row.path === highlightPath }"
            >
              <td><Input v-model="row.path" placeholder="$.headers.X-Trace-Id" class="h-8" /></td>
              <td>
                <Input
                  v-model="row.value"
                  :disabled="row.isNull"
                  :placeholder="row.isNull ? '显式 null(屏蔽注入)' : ''"
                  class="h-8"
                />
              </td>
              <td class="c-center">
                <div class="row-acts">
                  <button type="button" class="svc-link" @click="row.isNull = !row.isNull">
                    {{ row.isNull ? '取消 null' : '设 null' }}
                  </button>
                  <button type="button" class="svc-link danger" @click="defaultRows.splice(i, 1)">删</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="slib-empty">
        <p>还没有全局默认 —— 加一行(例 <code class="mono">$.headers.X-Trace-Id</code>)</p>
      </div>

      <div class="svc-foot">
        <span class="svc-foot-right">
          <Button variant="outline" data-testid="add-default-row" @click="addDefaultRow">加一行</Button>
          <Button data-testid="save-defaults" @click="saveDefaults">保存</Button>
        </span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * CarryConfig —— 默认值(全局兜底层,配套方案 §2.2 拆分后)。
 * 服务 / 别名绑定层 → ServiceBindingEditor(服务信息管理 · 键详情)。
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import {
  CarryCsvError, buildDefaultsCsv, buildDefaultsTemplateCsv, mergeDefaultsCsv, parseCarryCsv,
  type DefaultCarryRow,
} from '@/utils/carry-csv'
import { getDefaults, putDefaults, type CarryValues } from '@/api/carry'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

const loading = ref(true)
const defaultRows = ref<DefaultCarryRow[]>([])

async function loadDefaults() {
  const d = await getDefaults()
  defaultRows.value = Object.entries(d).map(([path, value]) => ({
    path,
    value: value ?? '',
    isNull: value === null,
  }))
}

function addDefaultRow() {
  defaultRows.value.push({ path: '', value: '', isNull: false })
}

// ── CSV(与绑定层同格式;导入 = upsert 表编辑,不自动保存)─────────
const defaultsCsvInput = ref<HTMLInputElement | null>(null)
/** 有可导出的默认行(非空白 path);全空时导出按钮禁用。 */
const hasDefaultRows = computed(() => defaultRows.value.some((r) => r.path))

function pickDefaultsCsv() {
  defaultsCsvInput.value?.click()
}

/** 下载文本文件:前缀 BOM 保证 Excel 识别 UTF-8。 */
function downloadText(filename: string, text: string) {
  const blob = new Blob([`﻿${text}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
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
    // 回读:让 isNull/value 与后端规范化结果一致
    await loadDefaults()
  } catch (e) {
    showError('保存', e)
  }
}

// ── init ─────────────────────────────────────────────────
// ?path= 深链(配套方案附录5:键详情「默认值」来源 chip 的落点)—
// 高亮命中行并滚动到位;找不到(未配兜底)只高亮条幅提示,不报错。
const route = useRoute()
const highlightPath = computed(() => {
  const p = route.query.path
  return typeof p === 'string' ? p : ''
})

onMounted(async () => {
  try {
    await loadDefaults()
  } catch (e) {
    showError('加载', e)
    loading.value = false
    return
  }
  loading.value = false
  if (highlightPath.value) {
    await nextTick()
    // 不用 CSS.escape(jsdom 无 CSS 全局):按属性值直接比较
    const hit = [...document.querySelectorAll<HTMLElement>('[data-path]')]
      .find((el) => el.getAttribute('data-path') === highlightPath.value)
    hit?.scrollIntoView?.({ block: 'center' })
  }
})
</script>

<style scoped>
/* ?path= 深链命中行:蓝环 + 淡蓝底高亮 */
.path-hit td {
  background: var(--sl-accent-soft);
}

.path-hit {
  outline: 2px solid var(--sl-accent);
  outline-offset: -2px;
}
</style>
