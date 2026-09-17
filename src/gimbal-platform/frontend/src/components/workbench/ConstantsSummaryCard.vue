<!--
  ConstantsSummaryCard.vue — 工作台首张注册卡(§7 落地节奏;参照物 =
  编排页常量池面板的"三行键值 + 快捷操作 + 管理深链"形制,但这是
  独立摘要组件 — 复用 store 取数,不复用面板组件)。

  数据契约(§7 第 5 条):常量池本身小数据量,list API 直取;
  快捷操作 = 复制生成器 key / 字面量值(与编排面板同款 payload)。
-->
<template>
  <div class="card-root" data-testid="wb-card-constants">
    <header class="card-head">
      <span class="card-title">常量池</span>
      <span class="card-count">{{ state.entries.length }}</span>
      <span class="spacer" />
      <router-link to="/constants" class="manage-link">管理 →</router-link>
    </header>

    <!-- 三行键值(最近 3 条;空态 = 引导 CTA,§7 第 3 条) -->
    <div v-if="state.entries.length" class="kv-list">
      <div v-for="e in state.entries.slice(0, 3)" :key="e.id" class="kv-row">
        <span class="kv-name mono">{{ e.name }}</span>
        <span class="kv-kind">{{ e.entry_kind === 'generator' ? '生成器' : '常量' }}</span>
        <button
          class="kv-copy"
          type="button"
          title="复制值 / 生成器 key"
          @click="copyEntry(e)"
        >复制</button>
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

/** 卡片喂给包装层的三态数据面(§7 第 3 条:loading/empty/error 由
 *  工作台统一样式;本卡 list 失败静默回空 — 完整页有重试入口)。 */
const state = reactive({ entries: [] as ConstantEntry[] })

onMounted(async () => {
  try {
    state.entries = await store.ensureEntries()
  } catch {
    state.entries = []
  }
})

/** 快捷操作:复制载荷与编排面板同款 — 生成器复制 ${var.name} key,
 *  字面量复制值文本(§7 参照物:ConstantPoolPanel F5)。 */
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
.card-root {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  height: 100%;
  box-sizing: border-box;
}

.card-head { display: flex; align-items: center; gap: 8px; }
.card-title { font-size: 14px; font-weight: 700; color: #10151c; }
.card-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: #64748b; background: #f1f5f9; border-radius: 3px;
}
.spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 500; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

.kv-list { display: flex; flex-direction: column; gap: 4px; }
.kv-row {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 12.5px;
}
.kv-name { flex: 1; min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kv-kind {
  flex: none; padding: 0 6px; font-size: 10.5px; font-weight: 600;
  color: #475569; background: #f1f5f9; border-radius: 3px;
}
.kv-copy {
  flex: none; padding: 1px 8px; font-size: 11px;
  color: #5a6273; background: transparent;
  border: 1px solid #e1e5eb; border-radius: 4px; cursor: pointer;
}
.kv-copy:hover { color: #2f6fed; border-color: #2f6fed; }
.more-hint { margin: 2px 0 0; font-size: 11px; color: #94a3b8; }

/* 空态 = 引导 CTA(不是虚线占位,§7 第 3 条) */
.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 14px 0; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta { font-size: 12.5px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.cta:hover { text-decoration: underline; }

.mono { font-family: var(--font-mono, monospace); }
</style>
