<!-- ShareDialog.vue — 引用/副本分享弹窗(权限域二期 P2,§7.1/§7.11)。

     属主视角:选模式(副本默认/引用)+ 选人(排除自己)→ POST /shares。
     再次打开列出该资源现有引用(direction=out),逐条可撤销(§7.11)。
     模式后果写明:副本不可撤回、引用实时跟随属主修改(live link)。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="share-dialog">
      <DialogHeader>
        <DialogTitle>分享{{ typeLabel }}:{{ resource?.name }}</DialogTitle>
      </DialogHeader>

      <!-- 现有引用(§7.11:再次打开列出,逐条可撤销) -->
      <div v-if="existing.length" class="existing-refs" data-testid="share-existing">
        <p class="section-label">现有引用({{ existing.length }})</p>
        <div v-for="r in existing" :key="r.id" class="ref-row">
          <span class="ref-who">{{ r.granteeName }}</span>
          <span class="muted small">{{ relTime(r.grantedAt) }}</span>
          <button
            type="button"
            class="revoke-btn"
            :data-testid="`share-revoke-${r.id}`"
            :disabled="busy"
            @click="revoke(r)"
          >撤销</button>
        </div>
      </div>

      <div class="mode-section">
        <p class="section-label">模式</p>
        <label class="mode-item" :class="{ on: mode === 'copy' }">
          <input v-model="mode" type="radio" value="copy" data-testid="share-mode-copy" />
          <span>
            <b>副本</b>(默认)
            <span class="muted small">— 独立拷贝归对方,可编辑;不可撤回</span>
          </span>
        </label>
        <label class="mode-item" :class="{ on: mode === 'ref' }">
          <input v-model="mode" type="radio" value="ref" data-testid="share-mode-ref" />
          <span>
            <b>引用</b>(同步)
            <span class="muted small">— 只读可执行;实时跟随你的修改;可撤销</span>
          </span>
        </label>
      </div>

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
          <span v-if="isReferenced(u.id)" class="muted small ref-tag">已引用</span>
        </label>
      </div>

      <div class="share-foot">
        <Button variant="outline" data-testid="share-cancel"
                @click="emit('update:open', false)">取消</Button>
        <Button
          :disabled="selectedId === null || busy"
          data-testid="share-confirm"
          @click="confirm"
        >{{ busy ? '分享中…' : confirmLabel }}</Button>
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
import { relTime } from '@/utils/datetime'
import { getRoster, type RosterItem } from '@/api/handoff'
import {
  createShare, deleteShare, listShares, type ShareRefItem,
} from '@/api/shares'

const props = defineProps<{
  open: boolean
  resource: { type: 'scenario' | 'suite'; id: string; name: string } | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
  /** 分享/撤销后通知调用方刷新徽标。 */
  changed: []
}>()

const q = ref('')
const mode = ref<'ref' | 'copy'>('copy')
const roster = ref<RosterItem[]>([])
const existing = ref<ShareRefItem[]>([])
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
const confirmLabel = computed(() =>
  mode.value === 'ref' ? '以引用分享' : '拷贝分享')

function isReferenced(userId: number): boolean {
  return existing.value.some((r) => r.granteeUserId === userId)
}

watch(() => props.open, (open) => {
  if (!open || !props.resource) return
  q.value = ''
  mode.value = 'copy'
  selectedId.value = null
  loading.value = true
  const res = props.resource
  Promise.all([
    roster.value.length ? Promise.resolve({ items: roster.value }) : getRoster(),
    listShares({
      direction: 'out', resourceType: res.type, resourceId: res.id,
    }).catch(() => [] as ShareRefItem[]),
  ]).then(([r, refs]) => {
    roster.value = r.items
    existing.value = refs
  }).finally(() => { loading.value = false })
}, { immediate: true })  // 挂载即开(同 AddToSuiteDialog 教训)

async function confirm(): Promise<void> {
  const res = props.resource
  if (!res || selectedId.value === null || busy.value) return
  busy.value = true
  try {
    const out = await createShare({
      resourceType: res.type, resourceId: res.id,
      granteeUserId: selectedId.value, mode: mode.value,
    })
    const grantee = roster.value.find((u) => u.id === selectedId.value)
    const granteeName = grantee
      ? (grantee.display_name || grantee.username) : ''
    if (out && typeof out === 'object' && 'id' in out) {
      // ShareRefItem(引用模式,后端返回带 id)
      toast.success(
        `已以引用分享给「${out.granteeName || granteeName}」(对方实时看到你的修改)`)
    } else {
      toast.success(`已拷贝分享给「${granteeName}」(副本归对方,不可撤回)`)
    }
    existing.value = await listShares({
      direction: 'out', resourceType: res.type, resourceId: res.id,
    }).catch(() => existing.value)
    emit('changed')
    emit('update:open', false)
  } catch (e) {
    toast.error(`分享失败:${(e as Error).message}`)
  } finally {
    busy.value = false
  }
}

async function revoke(r: ShareRefItem): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    await deleteShare(r.id)
    existing.value = existing.value.filter((x) => x.id !== r.id)
    toast.success(`已撤销「${r.granteeName}」的引用`)
    emit('changed')
  } catch (e) {
    toast.error(`撤销失败:${(e as Error).message}`)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.share-dialog { min-width: 420px; }
.section-label { font-size: 12px; color: rgb(100 116 139); margin: 4px 0; }
.existing-refs { max-height: 140px; overflow-y: auto; }
.ref-row {
  display: flex; align-items: center; gap: 8px; padding: 4px 0;
  border-bottom: 1px dashed rgb(100 116 139 / 25%);
}
.ref-who { flex: 1; font-weight: 500; }
.revoke-btn {
  font-size: 12px; padding: 2px 10px; border-radius: 6px; cursor: pointer;
  color: #b91c1c; background: rgb(239 68 68 / 8%);
  border: 1px solid rgb(239 68 68 / 35%);
}
.revoke-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mode-section { display: flex; flex-direction: column; gap: 2px; }
.mode-item {
  display: flex; gap: 8px; padding: 6px 8px; border-radius: 6px;
  cursor: pointer; border: 1px solid transparent;
}
.mode-item:hover { background: rgb(0 0 0 / 4%); }
.mode-item.on { border-color: hsl(var(--primary)); background: hsl(var(--accent)); }
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
.ref-tag { color: #15803d; }
.share-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.muted { color: rgb(100 116 139); }
.small { font-size: 12px; }
</style>
