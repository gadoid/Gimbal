<!-- AuthSelectorModal.vue — Spec-2-4 §4.3 C4 认证注入选择器.
     用户在编辑 header value 时，弹此 modal 选 alias + 字段。
     模板格式: ${auth.<alias>.<field>}，运行时由 executor 解密。 -->
<template>
  <Dialog :open="modelValue" @update:open="(v: boolean) => emit('update:modelValue', v)">
    <DialogContent class="max-w-[520px]">
      <DialogHeader>
        <DialogTitle>ⓘ 选择认证（${auth.&lt;alias&gt;.&lt;field&gt;} 模板）</DialogTitle>
      </DialogHeader>
      <div class="flex flex-col gap-3.5">
        <div class="flex flex-col gap-1.5">
          <span class="text-label font-medium text-signal-ink">alias *</span>
          <!-- 原为 filterable select;凭证池通常不大,native select 兼具
               键盘过滤与零依赖(jsdom 亦可用) -->
          <select v-model="alias" class="auth-select" data-testid="auth-alias">
            <option value="" disabled>选择一个凭证</option>
            <option v-for="a in auths" :key="a.id" :value="a.alias">
              {{ a.alias }} · {{ a.username }} · {{ a.token_type }}
            </option>
          </select>
        </div>
        <div class="flex flex-col gap-1.5">
          <span class="text-label font-medium text-signal-ink">字段</span>
          <div class="seg">
            <button v-for="f in FIELDS" :key="f" type="button" class="seg-btn"
              :class="{ active: field === f }" :data-testid="`auth-field-${f}`"
              @click="field = f">{{ f }}</button>
          </div>
        </div>
        <div v-if="alias" class="flex flex-col gap-1">
          <span class="text-label font-medium text-signal-ink">预览</span>
          <code class="preview mono">{{ templatePreview }}</code>
          <p class="preview-hint">
            运行时由 executor 解密并替换 — 仅当本用例「执行用认证」列表包含
            <code class="mono">{{ alias }}</code> 时才生效。
          </p>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="emit('update:modelValue', false)">取消</Button>
        <Button :disabled="!alias" @click="confirm">
          确认插入
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AuthSession } from '@/api/auth_sessions'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  modelValue: boolean
  auths: AuthSession[]
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'select': [template: string]
}>()

const FIELDS = ['token', 'username', 'password'] as const

const alias = ref<string>('')
const field = ref<'token' | 'username' | 'password'>('token')

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      alias.value = ''
      field.value = 'token'
    }
  },
)

const templatePreview = computed(() => {
  if (!alias.value) return ''
  return '${auth.' + alias.value + '.' + field.value + '}'
})

function confirm() {
  if (!alias.value) return
  emit('select', templatePreview.value)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.preview {
  display: inline-block;
  padding: 4px 8px;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
}

.preview-hint {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.auth-select {
  height: 34px;
  padding: 0 10px;
  font-size: 13px;
  color: #10151c;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 6px;
}
.seg { display: inline-flex; border: 1px solid #e1e5eb; border-radius: 6px; overflow: hidden; }
.seg-btn {
  padding: 5px 14px;
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  background: transparent;
  border: none;
  cursor: pointer;
  color: #5a6273;
}
.seg-btn.active { background: #2f6fed; color: #fff; font-weight: 600; }
</style>