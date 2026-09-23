<!-- HandoffDialog.vue — 资源分发的成员选择与结果面板(F1,2026-09-23)。

     分发 = Fork:副本归接收方、不可撤回、凭据引用不迁移。流程:
     roster(排除自己)本地过滤选人 → POST /handoff → 结果面板
     (重命名时明确告知计数后缀)。失败留在选择态可重试。 -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import {
  getRoster, postHandoff,
  type RosterItem, type HandoffResult,
} from '@/api/handoff'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{
  open: boolean
  scenario: { id: string; name: string } | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
  done: [HandoffResult]
}>()

const q = ref('')
const roster = ref<RosterItem[]>([])
const loading = ref(false)
const selectedId = ref<number | null>(null)
const submitting = ref(false)
/** 成功后停结果态(面板换内容),直到关闭重置。 */
const result = ref<HandoffResult | null>(null)

const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return roster.value
  return roster.value.filter((u) =>
    u.username.toLowerCase().includes(kw)
    || u.display_name.toLowerCase().includes(kw))
})
const selected = computed(() =>
  roster.value.find((u) => u.id === selectedId.value) ?? null)

watch(() => props.open, (open) => {
  if (!open) return
  q.value = ''
  selectedId.value = null
  result.value = null
  if (roster.value.length) return
  loading.value = true
  getRoster()
    .then((r) => { roster.value = r.items })
    .catch((e) => toast.error(`成员列表加载失败:${(e as Error).message}`))
    .finally(() => { loading.value = false })
})

async function confirmHandoff() {
  const sc = props.scenario
  if (!sc || selectedId.value === null || submitting.value) return
  submitting.value = true
  try {
    const res = await postHandoff(sc.id, selectedId.value)
    result.value = res
    emit('done', res)
  } catch (e) {
    // 403/404/422 已由后端分流,这里只呈现人话
    toast.error(`分发失败:${(e as Error).message}`)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="handoff-dialog">
      <DialogHeader>
        <DialogTitle>
          {{ result ? '分发结果' : `分发给…:${scenario?.name ?? ''}` }}
        </DialogTitle>
      </DialogHeader>

      <!-- ── 结果态:成功面板(重命名时明确告知)────────────────── -->
      <div v-if="result" class="handoff-result" data-testid="handoff-result">
        <p class="ok-line">✅ 已分发</p>
        <p>
          场景「{{ scenario?.name }}」已发送给
          <b>{{ selected?.display_name || selected?.username }}</b>
        </p>
        <p v-if="result.renamed" class="rename-note">
          ⚠️ 对方名下已有同名场景,副本已自动重命名为「{{ result.new_name }}」
        </p>
        <p class="muted small">
          副本归接收方所有,你的后续修改不会同步;不支持撤回。
        </p>
        <div class="handoff-foot">
          <Button data-testid="handoff-close" @click="emit('update:open', false)">关闭</Button>
        </div>
      </div>

      <!-- ── 选择态:搜索 + 单选列表 ───────────────────────────── -->
      <template v-else>
        <Input
          v-model="q"
          placeholder="搜索用户名 / 昵称…"
          aria-label="搜索成员"
          @keydown.stop
        />
        <div class="handoff-list" data-testid="handoff-list">
          <p v-if="loading" class="muted">成员加载中…</p>
          <p v-else-if="!filtered.length" class="muted">
            {{ roster.length ? '没有匹配的成员' : '平台暂无其他成员' }}
          </p>
          <label
            v-for="u in filtered"
            v-else
            :key="u.id"
            class="handoff-item"
            :class="{ picked: u.id === selectedId }"
          >
            <input
              v-model="selectedId"
              type="radio"
              name="handoff-target"
              :value="u.id"
              :data-testid="`handoff-user-${u.id}`"
            />
            <span class="who">
              <b>{{ u.display_name || u.username }}</b>
              <span class="muted small">{{ u.username }}</span>
            </span>
          </label>
        </div>
        <div class="handoff-foot">
          <Button
            variant="outline"
            data-testid="handoff-cancel"
            @click="emit('update:open', false)"
          >取消</Button>
          <Button
            :disabled="selectedId === null || submitting"
            data-testid="handoff-confirm"
            @click="confirmHandoff"
          >{{ submitting ? '分发中…' : '确认分发' }}</Button>
        </div>
      </template>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.handoff-list {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 8px 0;
}
.handoff-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.handoff-item:hover { background: rgb(0 0 0 / 4%); }
.handoff-item.picked { border-color: hsl(var(--primary)); background: hsl(var(--accent)); }
.handoff-item .who { display: flex; gap: 8px; align-items: baseline; }
.handoff-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.handoff-result p { margin: 6px 0; }
.ok-line { font-weight: 600; }
.rename-note { color: #b45309; }
.muted { color: rgb(100 116 139); }
.small { font-size: 12px; }
</style>
