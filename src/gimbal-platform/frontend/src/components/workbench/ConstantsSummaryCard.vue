<!--
  ConstantsSummaryCard.vue — 工作台注册卡(§7;参照物 = 编排页
  常量池面板"三行键值 + 快捷操作 + 管理深链",独立摘要组件)。
  视觉框架由 WorkbenchCardSlot 统一供给 — 本组件只出内容。
  卡头形制三档一致(图标+标题+计数+管理深链+分隔线);三档只换
  正文密度(设计文档 §4,useCardSize 注入):
    S = 大数字结论(N 项常量);M = 3 行键值;L = 搜索框 + 5 行 +
    行尾 icon-only 复制(§2:默认低透明度,行 hover 增强)。
-->
<template>
  <div data-testid="wb-card-constants" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="database" :size="14" />
      </span>
      <span class="chead-title">常量池</span>
      <span class="chead-count">{{ state.entries.length }} 项</span>
      <span class="chead-spacer" />
      <router-link to="/constants" class="manage-link">管理 →</router-link>
    </header>

    <!-- S 档:只出结论(大数字) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <p class="s-num">{{ state.entries.length }}</p>
      <p class="s-label">项常量</p>
    </div>

    <template v-else>
      <!-- L 档专属:卡内搜索(常量多了翻找是真实需求,§4) -->
      <input
        v-if="size === 'L'"
        v-model="search"
        class="l-search"
        type="search"
        placeholder="搜索 key…"
        :data-testid="wbT('search')"
      >

      <div v-if="visible.length" class="rows">
        <div v-for="e in visible" :key="e.id" class="kv-row wrow">
          <span class="wrow-name mono" :title="e.name">{{ e.name }}</span>
          <span class="wrow-tag" :class="e.entry_kind === 'generator' ? 'kg-gen' : 'kg-lit'">
            {{ e.entry_kind === 'generator' ? '生成器' : '常量' }}
          </span>
          <button class="kv-copy" type="button" title="复制值 / 生成器 key" @click="copyEntry(e)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
          </button>
        </div>
        <p v-if="size === 'M' && state.entries.length > 3" class="more-hint">
          还有 {{ state.entries.length - 3 }} 条 — 到完整页查看
        </p>
        <p v-else-if="size === 'L' && state.entries.length > visible.length" class="more-hint">
          共 {{ state.entries.length }} 条 — 到完整页查看
        </p>
      </div>
      <div v-else-if="size === 'L' && search" class="card-empty">
        <p>没有匹配「{{ search }}」的常量</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有常量 — 在编排里可直接引用,先去登记一条</p>
        <router-link to="/constants" class="cta">去常量池 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useConstantsStore } from '@/stores/constants'
import { copyText } from '@/utils/clipboard'
import { toast } from '@/utils/toast'
import type { ConstantEntry } from '@/types/constants'

const size = useCardSize()
const store = useConstantsStore()

const state = reactive({ entries: [] as ConstantEntry[] })
const search = ref('')

/** M = 3 行;L = 搜索过滤后的前 5 行 */
const visible = computed(() => {
  if (size.value === 'M') return state.entries.slice(0, 3)
  const q = search.value.trim().toLowerCase()
  const hit = q
    ? state.entries.filter((e) => e.name.toLowerCase().includes(q))
    : state.entries
  return hit.slice(0, 5)
})

const wbT = (suffix: string) => `wb-card-constants-${suffix}`

onMounted(async () => {
  try {
    state.entries = await store.ensureEntries()
  } catch {
    state.entries = []
  }
})

/** 复制载荷与编排面板同款(ConstantPoolPanel F5)。 */
async function copyEntry(e: ConstantEntry): Promise<void> {
  const payload = e.entry_kind === 'generator'
    ? `\${var.${e.name}}`
    : String(e.value ?? '')
  const ok = await copyText(payload)
  if (ok) toast.success(`已复制 ${e.name}`)
  else toast.warning('复制失败 — 请手动复制')
}
</script>

<style scoped>
/* 形制在基座 scenario-lib.css(.wcard / .chead / .s-body / .wrow /
   .card-empty / .cta);常量卡只留自己的搜索框、行列宽与复制钮。 */

/* L 档专属:卡内搜索(常量多了翻找是真实需求,§4) */
.l-search {
  width: 100%;
  padding: 5px 10px;
  font-size: 12px;
  color: var(--sl-ink);
  background: #f8fafc;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  outline: none;
  transition: border-color 0.12s ease, background 0.12s ease;
}
.l-search:focus { border-color: var(--sl-accent); background: #fff; }

/* 键值行:名称 1fr / 类型 chip / 复制 icon */
.kv-row { grid-template-columns: minmax(0, 1fr) auto auto; font-size: 12.5px; }
.kg-gen { color: #92400e; background: #fef3c7; }
.kg-lit { color: #475569; background: var(--sl-divider); }

/* 行内操作独立:icon-only,默认低透明度,行 hover 才增强 —
   不抢 key/value 主内容的视觉权重 */
.kv-copy {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  color: var(--sl-ink-2); opacity: 0.35;
  background: transparent;
  border: none; border-radius: 5px; cursor: pointer;
  transition: opacity 0.12s ease, color 0.12s ease, background 0.12s ease;
}
.kv-row:hover .kv-copy { opacity: 1; }
.kv-copy:hover { color: var(--sl-accent); background: var(--sl-accent-soft); }
</style>
