<!--
  VariableRegistryPanel.vue — 变量注册表 (#3 变量全局化)

  只读面板,挂在 ③ 配置步 vars 卡片下方:把草稿里"会产生的变量"
  (config.vars + 各 step 的 extract)与"谁在消费"(headers/body/策略
  里的 ${var.*})摊开成一张表 — 变量名 / 出身 / 产出者 / 消费处。

  纯推导零 IO:steps + configVars 进来,deriveVarRegistry/varUsages
  出去;数据集列变量运行期才注入(dispatcher layer),此处不列,
  以"未注册引用"提示条兜底(可能拼错,也可能是数据集列)。
-->
<template>
  <div class="c-card vr-card">
    <div class="c-card-head">
      <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
      <div>
        <h3>变量注册表 <span class="c-count">{{ registry.entries.length }}</span></h3>
        <p class="c-head-desc">草稿里全部变量的出身与去向 — 在 headers / body / 策略中用 <code class="c-code">${var.x}</code> 引用</p>
      </div>
    </div>

    <div v-if="!registry.entries.length" class="c-empty">
      <p>还没有注册的变量 — 在上方添加共享变量,或在步骤里配置 extract 策略后这里会列出</p>
    </div>

    <div v-else class="vr-table">
      <div class="vr-row vr-head-row">
        <span class="vr-col-name">变量名</span>
        <span class="vr-col-origin">出身</span>
        <span class="vr-col-producer">产出者</span>
        <span class="vr-col-usage">消费处</span>
      </div>
      <div v-for="e in registry.entries" :key="e.name" class="vr-row">
        <span class="vr-col-name" :title="e.name">{{ e.name }}</span>
        <span class="vr-col-origin">
          <span class="vr-badge" :class="e.origin">{{ e.origin }}</span>
        </span>
        <span class="vr-col-producer">
          <template v-if="e.origin === 'config'">共享变量</template>
          <template v-else>
            步骤 {{ (e.stepIdx ?? 0) + 1 }}
            <code v-if="e.expression" class="vr-expr" :title="e.expression">{{ e.expression }}</code>
          </template>
        </span>
        <span class="vr-col-usage">
          <template v-if="usageSites(e.name).length">
            <span
              v-for="s in usageSites(e.name).slice(0, 4)"
              :key="`${s.stepIdx}-${s.where}-${s.detail}`"
              class="vr-chip"
            >{{ siteLabel(s) }}</span>
            <span v-if="usageSites(e.name).length > 4" class="vr-chip more">
              +{{ usageSites(e.name).length - 4 }}
            </span>
          </template>
          <span v-else class="vr-unused">未被引用</span>
        </span>
      </div>
    </div>

    <p v-if="unregisteredRefs.length" class="vr-unregistered">
      引用了但未注册:{{ unregisteredRefs.join('、') }}
      — 可能是数据集列(运行期注入),请核对拼写
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  deriveVarRegistry,
  varUsages,
  type StepLike,
  type VarRefSite,
} from '@/utils/var-registry'

const props = defineProps<{
  /** 草稿 steps(消费 extract 出身 + ${var.*} 引用位置) */
  steps: StepLike[]
  /** definition.config.vars 折叠后的 dict(config 出身) */
  configVars: Record<string, unknown>
}>()

const registry = computed(() => deriveVarRegistry(props.steps, props.configVars))
const usages = computed(() => varUsages(props.steps))

function usageSites(name: string): VarRefSite[] {
  return usages.value.get(name)?.sites ?? []
}

/** 消费处 chip 文案:步骤 N · 位置(细位) */
function siteLabel(s: VarRefSite): string {
  const at = `步骤${s.stepIdx + 1}`
  if (s.where === 'headers') return `${at}·headers(${s.detail})`
  if (s.where === 'body') return `${at}·body`
  return `${at}·${s.detail}`
}

/** 被引用但不在注册表的名字(数据集列或拼写错误 — 面板无法区分,提示核对) */
const unregisteredRefs = computed(() => {
  const known = registry.value.byName
  return [...usages.value.keys()]
    .filter((n) => !known.has(n))
    .map((n) => `\${var.${n}}`)
})
</script>

<style scoped>
/* 通栏卡(与 vars-card 同列),表体 4 列:名字 | 出身 | 产出者 | 消费处 */
.vr-card { grid-column: 1 / -1; }

.vr-table { display: flex; flex-direction: column; gap: 2px; }
.vr-row {
  display: grid;
  grid-template-columns: minmax(120px, 1.1fr) 72px minmax(140px, 1fr) 2.2fr;
  gap: 8px;
  align-items: center;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 12px;
}
.vr-row:nth-child(odd) { background: var(--c-bg-secondary); }
.vr-head-row {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-tertiary);
  background: transparent !important;
  padding-top: 0;
}

.vr-col-name {
  font-family: var(--font-mono);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vr-col-producer { color: var(--c-text-secondary); }
.vr-expr {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-text-tertiary);
  background: var(--c-bg-secondary);
  padding: 1px 4px;
  border-radius: 4px;
  margin-left: 4px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  vertical-align: middle;
}

/* 出身徽章:extract 绿 / config 蓝(对齐 phase-tag 用色) */
.vr-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
}
.vr-badge.extract { background: #d1fae5; color: #065f46; }
.vr-badge.config { background: #eef2ff; color: #4338ca; }

/* 消费处 chips — 数量不定,独立 flex(不复用固定列数的 c-kv-row) */
.vr-col-usage { display: flex; flex-wrap: wrap; gap: 4px; }
.vr-chip {
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--c-text-secondary);
  white-space: nowrap;
}
.vr-chip.more { border-style: dashed; color: var(--c-text-tertiary); }
.vr-unused { color: var(--c-text-tertiary); font-size: 11px; }

/* 未注册引用提示:非错误(可能是数据集列),muted 落款 */
.vr-unregistered {
  margin: 10px 0 0;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  font-size: 11px;
  font-family: var(--font-mono);
  line-height: 1.6;
}

@media (max-width: 720px) {
  .vr-row { grid-template-columns: 1fr 64px; }
  .vr-col-producer, .vr-col-usage { grid-column: 1 / -1; }
}
</style>
