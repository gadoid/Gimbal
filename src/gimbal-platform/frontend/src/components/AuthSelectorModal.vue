<!-- AuthSelectorModal.vue — Spec-2-4 §4.3 C4 认证注入选择器.
     用户在编辑 header value 时，弹此 modal 选 alias + 字段。
     模板格式: ${auth.<alias>.<field>}，运行时由 executor 解密。
     配套方案 §1.1(C3a):步骤服务是已绑凭证的别名/服务时,preselectAlias
     自动预填绑定凭证(从服务注册的身份面绑定带出);手工改选仍是逃生舱。 -->
<template>
  <Dialog :open="modelValue" @update:open="(v: boolean) => emit('update:modelValue', v)">
    <DialogContent class="max-w-[32.5rem]">
      <DialogHeader>
        <DialogTitle>ⓘ 选择认证（${auth.&lt;alias&gt;.&lt;field&gt;} 模板）</DialogTitle>
      </DialogHeader>
      <div class="flex flex-col gap-3.5">
        <div class="flex flex-col gap-1.5">
          <span class="text-label font-medium text-signal-ink">alias *</span>
          <!-- 2026-09-22(任务6):native select → CredentialSelect 样式化
               下拉(两行选项:alias+token_type / username·url)。原来选
               native 是为了 jsdom 可测,新组件同为自管面板,click 可驱
               动,测试契约不变。 -->
          <CredentialSelect
            v-model="alias"
            :credentials="auths"
            placeholder="选择一个凭证"
            data-testid="auth-alias"
          />
          <p v-if="originNote" class="origin-note" data-testid="auth-origin-note">⤷ {{ originNote }}</p>
          <p v-if="preselectMissing" class="origin-note" data-testid="auth-preselect-missing">
            绑定凭证不在你当前凭证池 — 模板仍可插入,执行时按执行者本人池解析
          </p>
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
import CredentialSelect from '@/components/credential/CredentialSelect.vue'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  modelValue: boolean
  auths: AuthSession[]
  /** 别名绑定带出的预填凭证名(配套方案 §1.1);null = 无绑定,不预填。 */
  preselectAlias?: string | null
  /** 预填来源说明(如「fin-service-uat 的绑定凭证」)。 */
  originNote?: string | null
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
      alias.value = props.preselectAlias ?? ''
      field.value = 'token'
    }
  },
)

/** 预填名不在本人池:模板仍可插(执行时按执行者池解析),提示说清。 */
const preselectMissing = computed(() =>
  !!props.preselectAlias && !props.auths.some((a) => a.alias === props.preselectAlias))

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
  padding: 0.25rem 0.5rem;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 0.25rem;
}

.origin-note {
  margin: 0.125rem 0 0;
  color: var(--color-text-secondary, #6b7280);
  font-size: 0.6875rem;
}

.preview-hint {
  margin: 0.375rem 0 0;
  color: var(--color-text-secondary);
  font-size: 0.6875rem;
}

.seg { display: inline-flex; border: 1px solid var(--sl-line); border-radius: 0.375rem; overflow: hidden; }
.seg-btn {
  padding: 0.3125rem 0.875rem;
  font-size: 0.75rem;
  font-family: var(--font-mono, monospace);
  background: transparent;
  border: none;
  cursor: pointer;
  color: #5a6273;
}
.seg-btn.active { background: var(--sl-accent); color: #fff; font-weight: 600; }
</style>