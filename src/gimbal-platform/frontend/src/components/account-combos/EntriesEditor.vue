<!-- EntriesEditor.vue — 账户组合条目编辑器(§8.2 区②:服务 → 身份条目)。

     一行一服务;alias 输入带 datalist(登记面单源,保存面校验由后端
     422 兜底);就绪度 v1 = 未登记条目标红提示(完整池命中/地址矩阵/
     Ping All 随 §8.2 区③ 后续片收编)。 -->
<template>
  <div class="ee" data-testid="ac-entries">
    <div class="ee-head">
      <span>服务 → 身份条目</span>
      <button type="button" class="ee-add" data-testid="ac-add-entry"
        @click="add">+ 添加条目</button>
    </div>
    <table v-if="entries.length" class="ee-table">
      <thead>
        <tr>
          <th style="width: 40%">服务(目录服务名)</th>
          <th>身份条目</th>
          <th style="width: 5.5rem"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(e, i) in entries" :key="i">
          <td>
            <input v-model="e.service" :data-testid="`ac-entry-service-${i}`"
              maxlength="128" placeholder="如 fin-service" />
          </td>
          <td>
            <input v-model="e.alias" :data-testid="`ac-entry-alias-${i}`"
              :list="datalistId" maxlength="128" placeholder="选择或输入已登记条目名"
              :class="{ unreg: !registered(e.alias) }" />
          </td>
          <td class="ee-ops">
            <span v-if="e.alias && !registered(e.alias)" class="ee-flag"
              title="条目未登记(就绪度 v1):保存会被后端拦截,先在服务注册页登记">未登记</span>
            <button type="button" class="ee-del" :data-testid="`ac-entry-del-${i}`"
              @click="entries.splice(i, 1)">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="ee-empty">暂无条目 —— 空组合可先建后补(绑定后生效)。</p>
    <datalist :id="datalistId">
      <option v-for="a in aliasNames" :key="a" :value="a" />
    </datalist>
  </div>
</template>

<script setup lang="ts">
/**
 * 条目编辑器:entries 双向绑定(整体替换式保存由父级决定);
 * ``aliasNames`` = 登记面条目名(就绪度 v1 的「未登记」标红数据源)。
 */
import { computed, ref } from 'vue'
import type { ComboEntry } from '@/api/accountCombos'

const props = defineProps<{ aliasNames?: string[] }>()
const entries = defineModel<ComboEntry[]>('entries', { default: () => [] })

const datalistId = ref(`ee-alias-${Math.random().toString(36).slice(2, 8)}`)
const known = computed(() => new Set(props.aliasNames ?? []))
const registered = (alias: string) => !alias || known.value.has(alias)

function add() {
  entries.value = [...entries.value, { service: '', alias: '' }]
}
</script>

<style scoped>
.ee { border: 1px solid var(--sl-line, #E3E7EE); border-radius: 0.5rem;
  padding: 0.625rem 0.75rem; margin-bottom: 0.75rem; }
.ee-head { display: flex; justify-content: space-between; align-items: center;
  font-size: 0.6875rem; color: var(--sl-ink-3, #5B6472); margin-bottom: 0.5rem; }
.ee-add { border: 0; background: none; color: #175CD3; font-size: 0.75rem; cursor: pointer; padding: 0; }
.ee-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
.ee-table th { text-align: left; font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1);
  font-weight: 500; padding: 0.25rem 0.375rem; border-bottom: 1px solid var(--sl-line, #E3E7EE); }
.ee-table td { padding: 0.25rem 0.375rem; border-bottom: 1px solid var(--sl-line, #EEF1F5); }
.ee-table input { width: 100%; padding: 0.25rem 0.375rem; font-size: 0.8125rem;
  border: 1px solid var(--sl-line, #D5DAE3); border-radius: 0.375rem;
  background: var(--c-surface, #fff); color: var(--sl-ink, #1F2430); box-sizing: border-box; }
.ee-table input.unreg { border-color: #F04438; }
.ee-ops { display: flex; gap: 0.375rem; align-items: center; justify-content: flex-end; }
.ee-flag { font-size: 0.625rem; color: #B42318; background: #FEE4E2;
  border-radius: 0.25rem; padding: 0.0625rem 0.3125rem; white-space: nowrap; }
.ee-del { border: 0; background: none; color: var(--sl-ink-3, #8B93A1);
  font-size: 0.75rem; cursor: pointer; }
.ee-del:hover { color: #B42318; }
.ee-empty { font-size: 0.75rem; color: var(--sl-ink-3, #8B93A1); margin: 0; }
</style>
