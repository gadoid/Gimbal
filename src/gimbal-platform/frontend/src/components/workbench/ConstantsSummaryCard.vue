<!--
  ConstantsSummaryCard.vue — 工作台首张注册卡(§7;参照物 = 编排页
  常量池面板"三行键值 + 快捷操作 + 管理深链",独立摘要组件)。
  视觉框架由 WorkbenchCardSlot 统一供给 — 本组件只出内容
  (图标题头 + 键值行 + 空态 CTA)。
-->
<template>
  <div data-testid="wb-card-constants" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <ellipse cx="12" cy="5" rx="8" ry="3" />
          <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
          <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
        </svg>
      </span>
      <span class="chead-title">常量池</span>
      <span class="chead-count">{{ state.entries.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/constants" class="manage-link">管理 →</router-link>
    </header>

    <div v-if="state.entries.length" class="rows">
      <div v-for="e in state.entries.slice(0, 3)" :key="e.id" class="kv-row">
        <span class="kv-name mono" :title="e.name">{{ e.name }}</span>
        <span class="kv-kind" :class="e.entry_kind === 'generator' ? 'kg-gen' : 'kg-lit'">
          {{ e.entry_kind === 'generator' ? '生成器' : '常量' }}
        </span>
        <button class="kv-copy" type="button" title="复制值 / 生成器 key" @click="copyEntry(e)">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
          复制
        </button>
      </div>
      <p v-if="state.entries.length > 3" class="more-hint">
        还有 {{ state.entries.length - 3 }} 条 — 到完整页查看
      </p>
    </div>
    <div v-else class="card-empty">
      <p>还没有常量 — 在编排里可直接引用,先去登记一条</p>
      <router-link to="/constants" class="cta">去常量池 →</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { useConstantsStore } from '@/stores/constants'
import { copyText } from '@/utils/clipboard'
import { toast } from '@/utils/toast'
import type { ConstantEntry } from '@/types/constants'

const store = useConstantsStore()

const state = reactive({ entries: [] as ConstantEntry[] })

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
.wcard { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

/* ── 题头(三卡共用形制)────────────────────────────────── */
.chead { display: flex; align-items: center; gap: 8px; }
.chead-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 7px; flex: none;
}
.ci-blue { color: #2f6fed; background: #e7efff; }
.chead-title { font-size: 13.5px; font-weight: 700; color: #10151c; }
.chead-count {
  padding: 0 7px; font-size: 11px; font-weight: 700; line-height: 17px;
  color: #64748b; background: #f1f5f9; border-radius: 999px;
}
.chead-spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

/* ── 键值行(网格列:名称 1fr / 类型 chip / 复制钮 — 不重叠)── */
.rows { display: flex; flex-direction: column; gap: 2px; }
.kv-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  margin: 0 -8px;
  border-radius: 7px;
  font-size: 12.5px;
  transition: background 0.12s ease;
}
.kv-row:hover { background: #f6f8fa; }
.kv-name {
  min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.kv-kind {
  padding: 1px 7px; font-size: 10.5px; font-weight: 600; border-radius: 4px;
  white-space: nowrap;
}
.kg-gen { color: #92400e; background: #fef3c7; }
.kg-lit { color: #475569; background: #f1f5f9; }
.kv-copy {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; font-size: 11px; font-weight: 500;
  color: #64748b; background: transparent;
  border: 1px solid #e1e5eb; border-radius: 5px; cursor: pointer;
  transition: color 0.12s ease, border-color 0.12s ease;
}
.kv-row:hover .kv-copy { color: #2f6fed; border-color: #2f6fed; }
.more-hint { margin: 4px 0 0; font-size: 11px; color: #94a3b8; }

/* ── 空态 = 引导 CTA(非虚线占位,§7 第 3 条)─────────────── */
.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 16px 0 8px; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta {
  padding: 4px 14px; font-size: 12.5px; font-weight: 600;
  color: #2f6fed; text-decoration: none;
  border: 1px solid #bcd0f7; border-radius: 6px;
  transition: background 0.12s ease;
}
.cta:hover { background: #e7efff; }

.mono { font-family: var(--font-mono, monospace); }
</style>
