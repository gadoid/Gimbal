<!-- UnbindTokenDialog.vue — 解绑令牌确认(D26:4 条说明,原型
     IntegrationDetail「解绑令牌 · 确认」)。集成中心与集成详情共用;
     第 3 条按身份模式区分(评审 2026-11-05 P2:平台任务解绑后仍以
     平台身份运行)。确认即 PATCH tokenId:null,完成后交由父级刷新。 -->
<template>
  <Dialog :open="open && !!task" @update:open="(v) => !v && emit('close')">
    <DialogContent class="max-w-md">
      <DialogHeader>
        <DialogTitle>把「{{ task?.name }}」转为我管理？</DialogTitle>
        <DialogDescription>解绑任务所属的访问令牌，转由你的账号管理</DialogDescription>
      </DialogHeader>
      <ul class="m-0 flex flex-col gap-1.5 pl-5 text-caption text-signal-ink/70">
        <li>任务与令牌 {{ task?.tokenName ?? `#${task?.tokenId}` }} 解除绑定，此后不再受这张令牌的状态与范围约束。</li>
        <li>不再向令牌的回调地址推送事件；需要结果请在 Gimbal 内查看或订阅通知。</li>
        <!-- 第 3 条按身份模式区分(评审 2026-11-05 P2):平台任务解绑后
             仍以平台身份运行,固定写「以你的身份」会误导 member -->
        <li v-if="task?.identityMode === 'platform'">平台任务解绑后仍以平台身份、平台凭证池运行；仅公共场景与只读约束不变。</li>
        <li v-else>个人任务解绑后以你的身份、你的凭证池运行。</li>
        <li>解绑后任务处于暂停，确认无误后点「启动」。</li>
      </ul>
      <DialogFooter>
        <Button variant="outline" @click="emit('close')">取消</Button>
        <Button data-testid="ig-unbind-confirm" :disabled="busy" @click="doUnbind">解绑</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  patchIntegrationTask, integrationErr,
  type IntegrationTaskItem,
} from '@/api/integration'
import { toast } from '@/utils/toast'

const props = defineProps<{
  open: boolean
  task: IntegrationTaskItem | null
}>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'done'): void }>()

const busy = ref(false)

async function doUnbind(): Promise<void> {
  const t = props.task
  if (!t || busy.value) return
  busy.value = true
  try {
    await patchIntegrationTask(t.id, { tokenId: null })
    toast.success('已解绑;任务暂停待你启动')
    emit('done')
    emit('close')
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    busy.value = false
  }
}
</script>
