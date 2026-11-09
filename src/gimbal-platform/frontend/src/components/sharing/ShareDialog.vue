<!-- ShareDialog.vue — 副本分享弹窗(S7.4 引用模式退役后仅剩 copy)。

     属主视角:选人(排除自己)→ POST /shares(mode=copy)。
     模式后果写明:副本不可撤回、归对方独立修改。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="share-dialog">
      <DialogHeader>
        <DialogTitle>分享{{ typeLabel }}:{{ resource?.name }}</DialogTitle>
      </DialogHeader>

      <p class="section-label">
        副本分享 — 独立拷贝归对方,可编辑;不可撤回。
        <span class="muted small">(引用分享已退役,历史引用已转为对方私有副本)</span>
      </p>

      <Input
        v-model="q"
        placeholder="搜索用户名 / 昵称…"
        aria-label="搜索成员"
        @keydown.stop
      />
      <div class="share-list" data-testid="share-list">
        <p v-if="loading" class="muted">成员加载中…</p>
        <p v-else-if="!filtered.length" class="muted">
          {{ roster.length ? '没有匹配的成员' : '平台暂无其他成员' }}
        </p>
        <label
          v-for="u in filtered"
          v-else
          :key="u.id"
          class="share-item"
          :class="{ picked: selectedId === u.id }"
        >
          <input v-model="selectedId" type="radio" name="share-target" :value="u.id" />
          <span class="who">
            <b>{{ u.display_name || u.username }}</b>
            <span class="muted small">{{ u.username }}</span>
          </span>
        </label>
      </div>

      <div class="share-foot">
        <Button variant="outline" data-testid="share-cancel"
                @click="emit('update:open', false)">取消</Button>
        <Button
          :disabled="selectedId === null || busy"
          data-testid="share-confirm"
          @click="confirm"
        >{{ busy ? '分享中…' : '拷贝分享' }}</Button>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getRoster, type RosterItem } from '@/api/handoff'
import { createShare } from '@/api/shares'

const props = defineProps<{
  open: boolean
  resource: { type: 'scenario' | 'suite'; id: string; name: string } | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
  /** 分享后通知调用方刷新。 */
  changed: []
}>()

const q = ref('')
const roster = ref<RosterItem[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(false)
const busy = ref(false)

const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return roster.value
  return roster.value.filter((u) =>
    u.username.toLowerCase().includes(kw)
    || u.display_name.toLowerCase().includes(kw))
})
const typeLabel = computed(() =>
  props.resource?.type === 'suite' ? '用例组' : '场景')

watch(() => props.open, (open) => {
  if (!open || !props.resource) return
  q.value = ''
  selectedId.value = null
  loading.value = true
  const p = roster.value.length
    ? Promise.resolve({ items: roster.value })
    : getRoster()
  p.then((r) => { roster.value = r.items })
    .finally(() => { loading.value = false })
}, { immediate: true })  // 挂载即开(同 AddToSuiteDialog 教训)

async function confirm(): Promise<void> {
  const res = props.resource
  if (!res || selectedId.value === null || busy.value) return
  busy.value = true
  try {
    await createShare({
      resourceType: res.type, resourceId: res.id,
      granteeUserId: selectedId.value, mode: 'copy',
    })
    const grantee = roster.value.find((u) => u.id === selectedId.value)
    const granteeName = grantee
      ? (grantee.display_name || grantee.username) : ''
    toast.success(`已拷贝分享给「${granteeName}」(副本归对方,不可撤回)`)
    emit('changed')
    emit('update:open', false)
  } catch (e) {
    toast.error(`分享失败:${(e as Error).message}`)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.share-dialog { min-width: 420px; }
.section-label { font-size: 12px; color: rgb(100 116 139); margin: 4px 0; }
.share-list {
  max-height: 220px; overflow-y: auto; display: flex;
  flex-direction: column; gap: 4px; margin: 8px 0;
}
.share-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 6px; cursor: pointer; border: 1px solid transparent;
}
.share-item:hover { background: rgb(0 0 0 / 4%); }
.share-item.picked { border-color: hsl(var(--primary)); background: hsl(var(--accent)); }
.share-item .who { display: flex; gap: 8px; align-items: baseline; flex: 1; }
.share-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.muted { color: rgb(100 116 139); }
.small { font-size: 12px; }
</style>
