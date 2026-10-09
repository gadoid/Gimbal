<!--
  DebugConsole.vue — C6(P3-04)调试台:运行中的调试执行单步交互。

  布局三栏:会话状态头(轮询 /debug)+ 输出控制台(轮询 /debug/output,
  暂停提示在此出现)+ 命令面板(continue/step/abort/read/retry/skip 与
  write/patch 改值表单)。事件流复用 P2-07 的 /events 查询(after_seq
  增量轮询);执行器 token 全程不出后端(代理端点)。
-->
<template>
  <div class="dc-page">
    <div class="dc-head">
      <PageBack :to="`/executions/${execId}`" label="执行详情" />
      <h2>调试台 · 执行 #{{ execId }}</h2>
      <span class="dc-status" :class="{ active: info?.active }">
        {{ info?.active ? '会话进行中' : info ? `已结束(${info.status})` : '加载中…' }}
      </span>
    </div>

    <div class="dc-body">
      <section class="dc-panel dc-events">
        <h3>事件流</h3>
        <div class="dc-event-list" ref="eventListEl">
          <div v-for="ev in events" :key="ev.seq" class="dc-event" :class="{ log: ev.kind === 'log' }">
            <span class="dc-ev-seq">{{ ev.seq }}</span>
            <span class="dc-ev-type">{{ ev.event_type || ev.kind }}</span>
            <span class="dc-ev-where">{{ [ev.unit, ev.step].filter(Boolean).join('·') }}</span>
            <span class="dc-ev-msg">{{ ev.message ?? '' }}</span>
          </div>
          <div v-if="!events.length" class="muted small">暂无事件…</div>
        </div>
      </section>

      <div class="dc-right">
        <section class="dc-panel dc-console">
          <h3>会话输出 <span class="muted small">(暂停提示/命令回执)</span></h3>
          <div class="dc-console-list" ref="consoleEl">
            <div v-for="(line, i) in output" :key="i" class="dc-line">{{ line }}</div>
            <div v-if="!output.length" class="muted small">暂无输出(等待暂停点…)</div>
          </div>
        </section>

        <section class="dc-panel dc-commands">
          <h3>命令</h3>
          <div class="dc-cmd-row">
            <button v-for="c in quickCommands" :key="c"
              class="ghost-btn dc-cmd" :disabled="sending || !info?.active"
              :data-testid="`debug-cmd-${c}`" @click="send({ kind: c })">
              {{ c }}
            </button>
          </div>
          <div class="dc-cmd-form">
            <div class="dc-cmd-field">
              <span>write</span>
              <input v-model="writeVar" placeholder="变量名" />
              <input v-model="writeVal" placeholder='值(JSON,如 "O-9" 或 5)' />
              <button class="ghost-btn" :disabled="sending || !info?.active || !writeVar"
                data-testid="debug-cmd-write" @click="sendWrite">写入并继续</button>
            </div>
            <div class="dc-cmd-field">
              <span>patch</span>
              <input v-model="patchPath" placeholder="$.request.body.qty" />
              <input v-model="patchVal" placeholder='值(JSON)' />
              <button class="ghost-btn" :disabled="sending || !info?.active || !patchPath"
                data-testid="debug-cmd-patch" @click="sendPatch">补丁并继续</button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import PageBack from '@/components/chrome/PageBack.vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  getDebugOutput, getDebugSession, getExecutionEvents,
  postDebugCommand, type DebugCommandBody, type DebugSessionInfo,
  type ExecutionEventItem,
} from '@/api/executions'

const route = useRoute()
const execId = Number(route.params.id)

const info = ref<DebugSessionInfo | null>(null)
const events = ref<ExecutionEventItem[]>([])
const output = ref<string[]>([])
const sending = ref(false)
let lastSeq = 0

const quickCommands = ['continue', 'step', 'abort', 'read', 'retry', 'skip'] as const
const writeVar = ref('')
const writeVal = ref('')
const patchPath = ref('')
const patchVal = ref('')
const eventListEl = ref<HTMLElement | null>(null)
const consoleEl = ref<HTMLElement | null>(null)

function parseVal(raw: string): unknown {
  try { return JSON.parse(raw) } catch { return raw }
}

async function send(body: DebugCommandBody): Promise<void> {
  sending.value = true
  try {
    const resp = await postDebugCommand(execId, body)
    if (resp.output?.length) output.value.push(...resp.output)
    else if (!resp.accepted) output.value.push('[会话已结束,命令未受理]')
  } catch (e) {
    output.value.push(`[命令失败] ${e instanceof Error ? e.message : String(e)}`)
  } finally {
    sending.value = false
    scrollConsole()
  }
}

function sendWrite() {
  if (!writeVar.value) return
  void send({ kind: 'write', variable: writeVar.value, value: parseVal(writeVal.value) })
  writeVar.value = ''; writeVal.value = ''
}
function sendPatch() {
  if (!patchPath.value) return
  void send({ kind: 'patch', path: patchPath.value, value: parseVal(patchVal.value) })
  patchPath.value = ''; patchVal.value = ''
}

function scrollConsole() {
  requestAnimationFrame(() => {
    if (consoleEl.value) consoleEl.value.scrollTop = consoleEl.value.scrollHeight
    if (eventListEl.value) eventListEl.value.scrollTop = eventListEl.value.scrollHeight
  })
}

async function tickInfo() {
  try { info.value = await getDebugSession(execId) } catch { /* 稍后重试 */ }
}
async function tickEvents() {
  try {
    const { items } = await getExecutionEvents(execId, { after_seq: lastSeq, limit: 200 })
    if (items.length) {
      events.value.push(...items)
      lastSeq = items[items.length - 1].seq
      scrollConsole()
    }
  } catch { /* 稍后重试 */ }
}
async function tickOutput() {
  if (!info.value?.active) return
  try {
    const { output: lines } = await getDebugOutput(execId)
    if (lines.length) { output.value.push(...lines); scrollConsole() }
  } catch { /* 稍后重试 */ }
}

let infoTimer: number | undefined
let eventTimer: number | undefined
let outputTimer: number | undefined

onMounted(async () => {
  await tickInfo()
  await tickEvents()
  infoTimer = window.setInterval(tickInfo, 1500)
  eventTimer = window.setInterval(tickEvents, 1000)
  outputTimer = window.setInterval(tickOutput, 800)
})
onBeforeUnmount(() => {
  window.clearInterval(infoTimer)
  window.clearInterval(eventTimer)
  window.clearInterval(outputTimer)
})
</script>

<style scoped>
.dc-page { padding: 20px 24px; max-width: 1280px; margin: 0 auto; }
.dc-head { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.dc-head h2 { margin: 0; font-size: 18px; }
.dc-status { font-size: 13px; padding: 2px 10px; border-radius: 10px; background: #EEF1F5; color: #5A6472; }
.dc-status.active { background: #E6F7EE; color: #0E7A43; }
.dc-body { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 16px; }
.dc-right { display: flex; flex-direction: column; gap: 16px; }
.dc-panel { border: 1px solid #E3E7ED; border-radius: 10px; padding: 14px; background: #fff; }
.dc-panel h3 { margin: 0 0 10px; font-size: 14px; }
.dc-event-list, .dc-console-list {
  height: 420px; overflow-y: auto; font-family: ui-monospace, Consolas, monospace;
  font-size: 12px; background: #FAFBFC; border-radius: 6px; padding: 8px;
}
.dc-event { display: flex; gap: 8px; padding: 2px 0; border-bottom: 1px dashed #EEF1F5; }
.dc-event.log { color: #7B8590; }
.dc-ev-seq { color: #98A2AE; min-width: 36px; text-align: right; }
.dc-ev-type { color: #2456E6; min-width: 110px; }
.dc-ev-where { color: #0E7A43; min-width: 90px; }
.dc-ev-msg { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-line { padding: 2px 0; white-space: pre-wrap; word-break: break-all; color: #37414D; }
.dc-cmd-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.dc-cmd { min-width: 76px; }
.dc-cmd-form { display: flex; flex-direction: column; gap: 8px; }
.dc-cmd-field { display: grid; grid-template-columns: 44px 1fr 1fr auto; gap: 6px; align-items: center; font-size: 12px; }
.dc-cmd-field input { border: 1px solid #D6DBE3; border-radius: 6px; padding: 4px 8px; font-size: 12px; }
.muted { color: #7B8590; }
.small { font-size: 12px; }
.ghost-btn { cursor: pointer; }
</style>
