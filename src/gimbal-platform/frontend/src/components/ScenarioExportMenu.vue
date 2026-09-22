<!--
  ScenarioExportMenu.vue — 复用的场景导出菜单(批次 6 迁移 shadcn DropdownMenu)
  - 三个动作: JSON / YAML / 复制;按方案导出 = 方案子菜单(与场景库行菜单同款,
    闭包持方案对象按身份导出,加载中 / 无方案置灰说明)
  - 触发器 = 编排页顶栏图形按钮同款(36×36 图标钮,下载形;无草稿置灰,
    title 说明) — 与旁边 icon-btn 一列站齐,不再自带文字 + 箭头
  - 内部直接读 Pinia store (scenario-draft),所以挂载点不需要传 props
-->
<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child :disabled="!hasDraft">
      <!-- 必须是真按钮:as-child 会把触发器行为合到子元素上,直接放 svg
           会让 svg 本身变成触发器(被 CSS 拉成 36px 方框、图形跟着放大) -->
      <button
        type="button"
        class="se-trigger"
        :class="{ 'se-disabled': !hasDraft }"
        :title="labelText"
        :aria-label="labelText"
        @click="refreshSchemes"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" class="sl-menu">
      <DropdownMenuItem class="sl-menu-item" :disabled="exporting" @click="onCommand('json')">导出 JSON</DropdownMenuItem>
      <DropdownMenuItem class="sl-menu-item" :disabled="exporting" @click="onCommand('yaml')">导出 YAML</DropdownMenuItem>
      <DropdownMenuItem class="sl-menu-item" :disabled="exporting" @click="onCommand('copy')">复制 JSON</DropdownMenuItem>
      <!-- 按方案导出(spec §8):方案的 serviceBindings 物化进导出(envId 已退役)。
           形态与场景库行菜单同款(2026-09-22 重设计):方案平铺为子菜单项,
           闭包持方案对象(同名方案以身份区分不串台);加载中 / 无方案有
           置灰说明;Separator 与上方三动作分组。菜单面板走 sl-menu 体系。 -->
      <DropdownMenuSeparator />
      <DropdownMenuSub>
        <DropdownMenuSubTrigger class="sl-menu-item" :disabled="schemesLoading" data-testid="export-sub-trigger">
          按方案导出
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent class="sl-menu" data-testid="export-sub">
          <DropdownMenuItem v-if="schemesLoading" class="sl-menu-item" disabled>方案加载中…</DropdownMenuItem>
          <DropdownMenuItem v-else-if="!schemes.length" class="sl-menu-item" disabled>该场景暂无方案</DropdownMenuItem>
          <DropdownMenuItem
            v-for="s in schemes"
            :key="s.schemeId"
            class="sl-menu-item"
            :disabled="exporting"
            :data-testid="`export-scheme-${s.schemeId}`"
            @click="onSchemeExport(s)"
          >{{ s.name }}</DropdownMenuItem>
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    </DropdownMenuContent>
  </DropdownMenu>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useScenarioDraftStore, schemeToOverlay } from '@/stores/scenario-draft'
import { toast } from '@/utils/toast'
import { listRunSchemes } from '@/api/scenario-composer'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent,
  DropdownMenuSubTrigger, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { SchemeV2 } from '@/api/scenario-composer'

const store = useScenarioDraftStore()
const exporting = ref(false)

const hasDraft = computed(() => !!store.draft)
/** 图形按钮的 title/aria-label;无草稿时顺带说明为什么置灰。 */
const labelText = computed(() => hasDraft.value ? '导出' : '导出（当前无草稿）')

/** 按方案导出迁方案工作台 CRUD(阶段④:V1 sidecar 读侧回填下线)— 点开
 *  菜单(触发按钮 click,即开菜单手势)重取方案列表(运行弹窗「另存为
 *  方案」后此处即时可见);新建未保存场景无服务端 id / 非属主 403 →
 *  空列表,子菜单落「该场景暂无方案」(静默降级)。 */
const schemes = ref<SchemeV2[]>([])
const schemesLoading = ref(false)
async function refreshSchemes() {
  const sid = store.draft?.scenarioId
  if (!sid) {
    schemes.value = []
    return
  }
  schemesLoading.value = true
  try {
    schemes.value = await listRunSchemes(sid)
  } catch {
    schemes.value = [] // 非属主等读侧失败 — 默认导出不受影响
  } finally {
    schemesLoading.value = false
  }
}

async function onCommand(cmd: string) {
  if (!hasDraft.value) {
    toast.warning('当前没有正在编辑的草稿,请先在 CaseComposer 里打开 / 新建一个场景')
    return
  }
  exporting.value = true
  try {
    if (cmd === 'json') await store.exportJson()
    else if (cmd === 'yaml') await store.exportYaml()
    else if (cmd === 'copy') await store.copyJson()
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
  } finally {
    exporting.value = false
  }
}

/** 与场景库行菜单同款:闭包持方案对象按身份导出(同名方案不串台),
 *  不再经 `scheme:${name}` 名字反查。 */
async function onSchemeExport(s: SchemeV2) {
  if (!hasDraft.value) return
  exporting.value = true
  try {
    await store.exportJson(schemeToOverlay(s))
  } catch (e) {
    toast.error(`导出失败: ${(e as Error).message}`)
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
/* 触发器 = 编排页顶栏 .icon-btn 同款(36×36 图标钮)。CaseComposer 的
   .icon-btn 是 scoped 样式够不到这里,按同一组值复刻 —— 改顶栏按钮
   风格时两处要同步。 */
.se-trigger {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid #e6e8ec;
  border-radius: 8px;
  color: #5a6273;
  cursor: pointer;
  transition: all 0.15s;
}
.se-trigger:hover:not(.se-disabled) { background: #f5f6fa; color: #1a1d24; }
.se-trigger:focus { outline: none; }
.se-trigger.se-disabled { cursor: not-allowed; opacity: 0.45; }
</style>