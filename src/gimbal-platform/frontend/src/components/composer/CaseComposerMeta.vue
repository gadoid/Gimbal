<!--
  CaseComposerMeta.vue — ① 基本信息 (平面风统一)
  composer.css 共享层: .c-card / .c-card-head / .c-grid-* / .c-form
-->
<template>
  <div class="c-page">
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <div>
          <h3>核心信息</h3>
          <p class="c-head-desc">
            <span v-if="local.system.length" class="system-chips">
              <span v-for="s in local.system" :key="s" class="system-chip" :class="`s-${s}`">
                {{ systemLabel(s) }}
              </span>
            </span>
            <template v-else>scenarioId 由顶层 definition.scenarioId 管理 (新建时设定, 顶部 crumb 可见)</template>
          </p>
        </div>
      </div>
      <div class="c-form">
        <div class="mf-item"><span class="mf-label">名称 *</span>
          <Input v-model="local.name" placeholder="订单创建 e2e" maxlength="64" />
        </div>
        <div class="mf-item"><span class="mf-label">描述</span>
          <textarea
            v-model="local.description"
            rows="3"
            maxlength="2048"
            class="w-full rounded-field border border-input bg-transparent p-2 text-body"
            placeholder="覆盖订单创建主链路, 验证状态机 + 字段映射"
          ></textarea>
        </div>
        <div class="c-grid-3">
          <div class="mf-item"><span class="mf-label">module *</span>
            <Input v-model="local.module" placeholder="订单" maxlength="64" />
          </div>
          <div class="mf-item"><span class="mf-label">priority *</span>
            <select v-model.number="local.priority" class="meta-select">
              <option :value="0">P0 · 最高</option>
              <option :value="1">P1 · 高</option>
              <option :value="2">P2 · 中</option>
              <option :value="3">P3 · 低</option>
            </select>
          </div>
          <div class="mf-item"><span class="mf-label">version</span>
            <Input v-model="local.version" maxlength="32" />
          </div>
        </div>
      </div>
    </div>

    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
        <div>
          <h3>归属 & 标签</h3>
          <p class="c-head-desc">owner 由服务端自动设为当前用户</p>
        </div>
      </div>
      <div class="c-form">
        <div class="c-grid-2">
          <div class="mf-item"><span class="mf-label">author</span>
            <Input v-model="local.author" placeholder="王" />
          </div>
          <div class="mf-item"><span class="mf-label">owner</span>
            <Input v-model="local.owner" placeholder="(由服务端覆盖)" disabled />
          </div>
        </div>
        <div class="mf-item"><span class="mf-label">归属系统 (V3.2 多系统) *</span>
          <!-- multiple+allow-create:候选 checkbox 芯片 + 自由输入追加
               (回车确认;键入非候选值即自建) -->
          <div class="sys-chips" data-testid="meta-system">
            <label v-for="c in plateSystems" :key="c" class="sys-chip" :class="{ on: local.system.includes(c) }">
              <input
                type="checkbox"
                :value="c"
                :checked="local.system.includes(c)"
                @change="toggleSystem(c)"
              />{{ systemLabel(c) }}
            </label>
            <input
              v-model="systemDraft"
              class="sys-add"
              placeholder="+ 输入系统回车添加"
              @keydown.enter.prevent="addSystem"
            />
          </div>
          <span class="hint">支持多选 — 跨系统编排 (如 fin+logi)</span>
        </div>
        <div class="mf-item"><span class="mf-label">tags</span>
          <TagInput v-model="local.tags" placeholder="按 Enter 添加 tag" />
        </div>
        <div class="mf-item">
          <Switch v-model="local.expire" />
          <span class="switch-label">过期 (expire)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue'
import TagInput from '@/components/TagInput.vue'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { fetchPlateSystems } from '@/api/plate'
import type { MetaView } from '@/types/plate'

// 下拉选项 = plate 已注册系统 (api/plate 统一查询层拉取),
// 不再硬编码 fin/logi/wms/mall/common。SYS_LABELS 只做已知系统的中文
// 显示优化;未知系统 (含已保存场景里的旧值) 回退显示原始 id。
const SYS_LABELS: Record<string, string> = {
  fin: '财务', logi: '物流', wms: '仓储', mall: '商城', common: '通用',
}
function systemLabel(s: string) {
  const v = SYS_LABELS[s] || s
  return s === 'common' ? `common (${v})` : `${s} (${v})`
}

const plateSystems = ref<string[]>([])
const systemDraft = ref('')

function toggleSystem(s: string) {
  const i = local.system.indexOf(s)
  if (i >= 0) local.system.splice(i, 1)
  else local.system.push(s)
}
function addSystem() {
  const v = systemDraft.value.trim()
  if (v && !local.system.includes(v)) local.system.push(v)
  systemDraft.value = ''
}

onMounted(async () => {
  try {
    plateSystems.value = await fetchPlateSystems()
  } catch (e) {
    // 静默降级:选项为空,下拉 allow-create 手输不受影响
    console.warn('[CaseComposerMeta] plate 系统列表加载失败:', e)
  }
})

// scenarioId 已上移到 definition.scenarioId (顶层),MetaView 不再含该字段。
const props = defineProps<{ modelValue: MetaView }>()
const emit = defineEmits<{ 'update:modelValue': [MetaView] }>()

const local = reactive<MetaView>({ ...props.modelValue })

watch(() => props.modelValue, (v) => {
  Object.assign(local, v)
}, { deep: true })

watch(local, (v) => {
  emit('update:modelValue', { ...v })
}, { deep: true })
</script>

<style scoped>
/* 大部分样式来自 composer.css 共享层 (.c-page/.c-card/.c-form/.c-grid-*) */
.system-chips { display: inline-flex; gap: 4px; }
.system-chip {
  display: inline-block;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
}
.system-chip.s-fin { background: #dbeafe; color: #1e40af; }
.system-chip.s-logi { background: #d1fae5; color: #065f46; }
.system-chip.s-wms { background: #fef3c7; color: #92400e; }
.system-chip.s-mall { background: #fce7f3; color: #9d174d; }
.system-chip.s-common { background: #f3e8ff; color: #6b21a8; }

.hint { display: block; font-size: 11px; color: var(--c-text-tertiary); margin-top: 4px; }
.opt-sys { font-weight: 500; }
.switch-label { margin-left: 12px; font-size: 13px; color: var(--c-text-secondary); }
.mf-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.mf-label { font-size: 11px; font-weight: 600; color: var(--color-text-secondary, #64748b); }
.meta-select {
  height: 34px; padding: 0 8px; font-size: 13px;
  color: #10151c; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 6px;
}
.sys-chips { display: flex; flex-wrap: wrap; gap: 4px 6px; }
.sys-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; font-size: 11.5px;
  color: #374151; border: 1px solid #e1e5eb; border-radius: 10px;
  cursor: pointer; user-select: none;
}
.sys-chip.on { color: #2f6fed; border-color: #2f6fed; background: #e7efff; }
.sys-chip input { accent-color: #2f6fed; margin: 0; }
.sys-add {
  border: none; outline: none; background: transparent;
  font-size: 11.5px; color: #2f6fed; width: 130px;
}
.sys-add::placeholder { color: #94a3b8; }
</style>
