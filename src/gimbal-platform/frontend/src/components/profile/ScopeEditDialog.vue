<!-- ScopeEditDialog.vue — 编辑令牌授权范围(原型 ScopeEdit)。
     收紧前先 dryRun:列出将不满足的已注册任务,确认后「仍然保存」。
     空维度合法(D4):不勾即不允许使用该类资源;已删对象在候选中标
     删除线红边。 -->
<template>
  <Dialog :open="open" @update:open="(v) => !v && $emit('close')">
    <DialogContent class="max-w-xl" data-testid="scope-edit-dialog">
      <DialogHeader>
        <DialogTitle>编辑授权范围 · {{ token?.name }}</DialogTitle>
        <DialogDescription>保存即生效；已注册任务在下次运行前重新核对</DialogDescription>
      </DialogHeader>

      <div v-if="loading" class="py-8 text-center text-caption text-signal-ink/60">候选装载中…</div>
      <template v-else>
        <div class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="w-16 flex-none text-caption text-signal-ink/60">服务别名</span>
            <button
              v-for="a in candidates?.aliases ?? []" :key="a"
              type="button" class="chip-toggle mono"
              :class="aliasSelected(a) ? 'is-on' : ''"
              :aria-pressed="aliasSelected(a)"
              @click="toggleAlias(a)"
            >{{ a }}</button>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="w-16 flex-none text-caption text-signal-ink/60">凭证</span>
            <button
              v-for="c in candidates?.auths ?? []" :key="c.id"
              type="button" class="chip-toggle mono"
              :class="authSelected(c) ? 'is-on' : ''"
              :aria-pressed="authSelected(c)"
              @click="toggleAuth(c)"
            >{{ c.alias }}</button>
          </div>

          <div v-if="unsatisfied.length" class="flex flex-col gap-2 rounded-lg border border-red-200 bg-red-50 p-3.5">
            <span class="text-[12px] font-semibold text-red-800">
              收紧后，{{ unsatisfied.length }} 个已注册任务将不满足范围，会在下次运行前暂停
            </span>
            <div
              v-for="t in unsatisfied" :key="t.id"
              class="flex items-center gap-2.5 rounded-md border border-signal-line bg-white px-2.5 py-2 text-[12px]"
            >
              <span class="flex-1">{{ t.name }}</span>
              <span class="text-signal-ink/60">
                用到 {{ t.missing.map((m) => m.name).join(' · ') }}
              </span>
            </div>
            <span class="text-caption text-signal-ink/60">
              范围恢复后任务可在集成详情里重新启动；调用方的即时调用会直接返回范围外的别名与凭证。
            </span>
          </div>
          <p v-else class="text-caption text-signal-ink/60">
            某一维度可以不选：不选即不允许使用该类资源。别名或凭证被删除后，授权随之移除。
          </p>
        </div>
      </template>

      <DialogFooter>
        <Button variant="outline" @click="$emit('close')">取消</Button>
        <Button
          :disabled="saving" :variant="unsatisfied.length ? 'destructive' : 'default'"
          data-testid="scope-edit-save" @click="save"
        >{{ saving ? '保存中…' : unsatisfied.length ? '仍然保存' : '保存' }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  getScopeCandidates, putTokenScope,
  type AccessTokenListItem, type ScopeCandidates, type UnsatisfiedTask,
} from '@/api/access-tokens'
import { toast } from '@/utils/toast'

const props = defineProps<{
  open: boolean
  token: AccessTokenListItem | null
  /** 初始范围(详情页带出) */
  initialAliases?: string[]
  initialAuthIds?: number[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const loading = ref(false)
const saving = ref(false)
const candidates = ref<ScopeCandidates | null>(null)
const aliases = ref<Set<string>>(new Set())
const authIds = ref<Set<number>>(new Set())
const unsatisfied = ref<UnsatisfiedTask[]>([])

watch(() => props.open, async (v) => {
  if (!v || !props.token) return
  unsatisfied.value = []
  loading.value = true
  try {
    candidates.value = await getScopeCandidates(props.token.kind)
    aliases.value = new Set(props.initialAliases ?? [])
    authIds.value = new Set(props.initialAuthIds ?? [])
  } catch (e) {
    toast.error((e as Error).message || '候选装载失败')
    emit('close')
  } finally {
    loading.value = false
  }
})

function aliasSelected(a: string) { return aliases.value.has(a) }
function authSelected(c: { id: number }) { return authIds.value.has(c.id) }
function toggleAlias(a: string) {
  const next = new Set(aliases.value)
  if (next.has(a)) next.delete(a)
  else next.add(a)
  aliases.value = next
  void dryRun()
}
function toggleAuth(c: { id: number }) {
  const next = new Set(authIds.value)
  if (next.has(c.id)) next.delete(c.id)
  else next.add(c.id)
  authIds.value = next
  void dryRun()
}

async function dryRun() {
  if (!props.token) return
  try {
    const out = await putTokenScope(props.token.id, payload(), true)
    unsatisfied.value = out.unsatisfied
  } catch {
    /* dryRun 失败不拦编辑;保存时再报 */
  }
}

function payload() {
  return { aliases: [...aliases.value], authIds: [...authIds.value] }
}

async function save() {
  if (!props.token || saving.value) return
  saving.value = true
  try {
    await putTokenScope(props.token.id, payload())
    toast.success('授权范围已更新')
    emit('saved')
    emit('close')
  } catch (e) {
    toast.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.chip-toggle {
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--color-signal-line, #e1e5eb);
  background: #fff;
  color: var(--color-signal-ink, #10151c);
  font-size: 12px;
}
.chip-toggle.is-on {
  border-color: var(--color-signal, #2f6fed);
  background: #e7efff;
  color: #1f55c4;
}
</style>
