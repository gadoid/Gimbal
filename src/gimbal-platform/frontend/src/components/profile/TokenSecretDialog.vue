<!-- TokenSecretDialog.vue — 令牌明文一次性展示(创建 / 重新生成 / 后配回调
     发密钥 / 轮换密钥共用;原型 TokenCreated)。两项只显示这一次,勾选
     「我已妥善保存」才能关闭;明文绝不回传后端,关闭即丢。 -->
<template>
  <Dialog :open="open" @update:open="(v) => !v && onClose()">
    <DialogContent class="max-w-xl" data-testid="token-secret-dialog">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>{{ subtitle }}</DialogDescription>
      </DialogHeader>

      <div class="flex flex-col gap-4">
        <div class="flex items-start gap-2.5 rounded-lg bg-amber-50 px-3 py-2.5 text-[12px] text-amber-800">
          <ExclamationTriangleIcon class="mt-0.5 h-4 w-4 flex-none" />
          <span>下面{{ secretKeys.length > 1 ? '两项' : '该项' }}只显示这一次，关闭后无法再查看；丢失请重新生成。</span>
        </div>

        <div v-if="token" class="flex flex-col gap-1.5">
          <span class="text-caption text-signal-ink/60">访问令牌 · Authorization: Bearer</span>
          <div class="flex items-center gap-2">
            <code class="mono min-w-0 flex-1 overflow-hidden rounded-md border border-signal-line bg-signal-canvas px-2.5 py-2 text-[12px] whitespace-nowrap text-ellipsis">{{ token }}</code>
            <Button variant="outline" size="sm" @click="copy(token, '令牌已复制')">复制</Button>
          </div>
        </div>

        <div v-if="callbackSecret" class="flex flex-col gap-1.5">
          <span class="text-caption text-signal-ink/60">回调签名密钥（HMAC，验签用）</span>
          <div class="flex items-center gap-2">
            <code class="mono min-w-0 flex-1 overflow-hidden rounded-md border border-signal-line bg-signal-canvas px-2.5 py-2 text-[12px] whitespace-nowrap text-ellipsis">{{ callbackSecret }}</code>
            <Button variant="outline" size="sm" @click="copy(callbackSecret!, '密钥已复制')">复制</Button>
          </div>
        </div>

        <div class="flex flex-col gap-1.5">
          <div class="flex items-center justify-between">
            <span class="text-caption text-signal-ink/60">调用示例</span>
            <Button variant="outline" size="sm" class="h-6" @click="copy(sampleCurl, '示例已复制')">复制</Button>
          </div>
          <pre class="overflow-x-auto rounded-md bg-slate-900 px-3 py-2.5 text-[12px] leading-relaxed text-slate-200">{{ sampleCurl }}</pre>
        </div>
      </div>

      <DialogFooter class="items-center sm:justify-between">
        <label class="flex items-center gap-2 text-body" data-testid="token-secret-saved">
          <input v-model="saved" type="checkbox" class="h-4 w-4" />
          我已妥善保存
        </label>
        <Button :disabled="!saved" data-testid="token-secret-done" @click="onClose">完成</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ExclamationTriangleIcon } from '@radix-icons/vue'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from '@/utils/toast'

const props = defineProps<{
  open: boolean
  /** 场景标题:创建 / 重新生成 / 轮换签名密钥 */
  title: string
  subtitle?: string
  token?: string | null
  callbackSecret?: string | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const saved = ref(false)
watch(() => props.open, (v) => { if (v) saved.value = false })

const secretKeys = computed(() =>
  [props.token, props.callbackSecret].filter(Boolean))

const sampleCurl = computed(() =>
  `curl -X POST https://<gimbal-host>/api/runs \\
  -H "Authorization: Bearer ${props.token ?? 'gtk_••••••••'}" \\
  -d '{"scenarioId": "sc-…", "schemeId": "…"}'`)

async function copy(text: string, okMsg: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(okMsg)
  } catch {
    toast.error('复制失败,请手动选择复制')
  }
}

function onClose() {
  emit('close')
}
</script>
