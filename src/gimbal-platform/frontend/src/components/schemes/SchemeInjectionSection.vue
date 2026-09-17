<script setup lang="ts">
/** 方案工作台 · 断言注入区:注册表条目复选(死条目禁选 + 灰显 + 悬空 title)、
 *  快建弹层(步骤号 + jsonpath → quickCreate)、「管理断言」跳编辑器(manage)。
 *  纯展示组件:条目/死集进 props,勾选/快建/管理出事件;持久化与导航归壳。
 *  快建失败回调化(§13 T6-1):quickCreate 契约 = [draft, onDone(ok)] —
 *  关闭/清空只在壳回报成功(onDone(true))后发生;PUT 失败 onDone(false)
 *  → 弹层保持打开、输入保留,用户改完可直接重试(乐观关闭会吞掉输入)。 */
import { ref } from 'vue'
import { toast } from '@/utils/toast'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{
  modelValue: string[]                 // injectionEntryIds(受控)
  entries: Array<{ id: string; label?: string }>   // 壳从 assertion_registry.entries 映射
  deadIds: Set<string>                 // 死条目(禁选 + 灰显 + 死因 title)
  locked?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [v: string[]]
  quickCreate: [draft: { stepIndex: number; jsonpath: string }, onDone: (ok: boolean) => void]
  manage: []                                                      // 跳断言编辑器
}>()

function toggle(id: string, on: boolean) {
  const has = props.modelValue.includes(id)
  if (on === has) return
  emit('update:modelValue',
    on ? [...props.modelValue, id] : props.modelValue.filter((x) => x !== id))
}

// ── 快建弹层(展开行;与数据区同款 inline 约定)───────────────────────
// 步骤号输入用 el-input(type=number)而非 el-input-number:el-input 把
// $attrs(含 data-testid)透传到原生 input,el-input-number 留在根 div 上 —
// 测试的 setValue 只对原生 input/textarea/select 生效(其余元素直接 throw)。
const showQuick = ref(false)
const pendingStep = ref<number | string>(0)
const pendingJsonpath = ref('')

function confirmQuick() {
  const stepIndex = Number(pendingStep.value)
  if (pendingStep.value === '' || pendingStep.value === null
    || !Number.isInteger(stepIndex) || stepIndex < 0) {
    toast.warning('要填步骤号(从 0 开始)')
    return
  }
  if (!pendingJsonpath.value.startsWith('$')) {
    toast.warning('注入路径需以 $ 开头(例:$.amount)')
    return
  }
  // 收尾交结果回调:壳 PUT 成功才关弹层清输入,失败则原样保留
  emit('quickCreate', { stepIndex, jsonpath: pendingJsonpath.value }, (ok: boolean) => {
    if (ok) {
      showQuick.value = false
      pendingJsonpath.value = ''
    }
  })
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">断言注入</span>
      <span class="zone-count">{{ entries.length }}</span>
      <span class="zone-spacer"></span>
      <div class="zone-ops">
        <Button size="sm" variant="link" class="h-7 px-2" data-testid="quick-add"
          @click="showQuick = !showQuick">+ 快建条目</Button>
        <Button size="sm" variant="link" class="h-7 px-2" data-testid="manage-assertions"
          @click="emit('manage')">管理断言</Button>
      </div>
    </header>

    <div v-if="showQuick" class="quick-row">
      <Input v-model="pendingStep" data-testid="qa-step" type="number"
        :disabled="locked" class="qa-step h-8" placeholder="步骤号" />
      <Input v-model="pendingJsonpath" data-testid="qa-path"
        :disabled="locked" class="qa-path h-8" placeholder="注入路径,如 $.amount" />
      <Button size="sm" data-testid="qa-ok" :disabled="locked" @click="confirmQuick">创建</Button>
    </div>

    <div class="inj-list">
      <!-- 原生 checkbox(与数据区同款):禁选/灰显/悬空 title 三态齐备 -->
      <label v-for="e in entries" :key="e.id" class="inj-item"
        :class="{ dead: deadIds.has(e.id) }" :title="deadIds.has(e.id) ? '已悬空' : undefined">
        <input type="checkbox" :checked="modelValue.includes(e.id)"
          :disabled="deadIds.has(e.id) || locked"
          @change="toggle(e.id, ($event.target as HTMLInputElement).checked)" />
        {{ e.label ?? e.id }}
      </label>
      <div v-if="!entries.length" class="empty-state">
        <p>暂无断言条目 — 可「+ 快建条目」或到断言管理器维护。</p>
        <Button size="sm" variant="outline" @click="showQuick = true">+ 快建条目</Button>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 分区卡片:对齐平台卡片体系(CaseDataSetsList .card / 编辑器 .meta) */
.wb-section {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
/* zone-head 体系(CaseDataSetsList 同款):左竖线标题 + 计数徽标 + 弹性空位 */
.zone-head { display: flex; align-items: center; gap: 10px; }
.zone-name {
  font-size: 14px; font-weight: 700; color: var(--color-text-primary);
  padding-left: 10px; border-left: 3px solid var(--accent);
}
.zone-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: var(--color-text-secondary); background: #f1f5f9; border-radius: 3px;
}
.zone-spacer { flex: 1; }
.zone-ops { display: flex; gap: 4px; }

/* 快建行:dashed 软面板(基准 .add-card / dead-keys-bar 的浅底虚线语言) */
.quick-row {
  display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  border: 1px dashed var(--accent-soft-border); border-radius: 6px; background: #fafbff;
}
.quick-row .qa-step { width: 110px; flex: none; }
.quick-row .qa-path { flex: 1; }

/* 条目行:行距 + hover(平台行交互语言 #f8faff,AssertionRegistryEditor .are-row 同款) */
.inj-list { display: flex; flex-direction: column; gap: 2px; }
.inj-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
  transition: background 0.15s ease;
}
.inj-item:hover { background: #f8faff; }
.inj-item input[type="checkbox"] { accent-color: var(--accent); }
/* 死条目:禁选 + 灰显 + 删除线(hover 不给反馈 — 不可选的东西不该亮) */
.inj-item.dead {
  color: var(--color-text-tertiary); cursor: not-allowed;
  text-decoration: line-through; opacity: 0.65;
}
.inj-item.dead:hover { background: none; }

/* 空态(三处统一形状:dashed 框 + muted 文案 + 引导按钮) */
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 18px 16px; text-align: center;
  border: 1px dashed var(--color-border-tertiary); border-radius: 8px;
}
.empty-state p { margin: 0; font-size: 12px; color: var(--color-text-tertiary); }
</style>
