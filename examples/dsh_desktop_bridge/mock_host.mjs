#!/usr/bin/env node
// 在没有 DSH 桌面端的环境里，用桩 sessionController 挂载真实的 dsh-desktop-bridge 插件。
//
// 走的是插件本体的 apply()：随机端口、随机 token、写 <DSH_HOME>/desktop-bridge.json、
// Host / Origin / Bearer 校验、审计日志全部是真代码，只有 sessionController 是内存桩。
//
// 用法：
//   BRIDGE_DIR=/path/to/dsh-desktop-bridge DSH_HOME=/tmp/dsh-mock node mock_host.mjs
//
// 可选环境变量：
//   BRIDGE_ALLOW_CREATE=false   对应插件 config.allowCreate
//   BRIDGE_CWD_ALLOWLIST=a:b    对应插件 config.cwdAllowlist（path.delimiter 分隔）
import { randomUUID } from 'node:crypto'
import { delimiter, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const bridgeDir = process.env.BRIDGE_DIR
if (!bridgeDir) {
  console.error('BRIDGE_DIR must point at a dsh-desktop-bridge checkout')
  process.exit(2)
}
if (!process.env.DSH_HOME) {
  console.error('DSH_HOME must be set so the descriptor does not land in ~/.dsh')
  process.exit(2)
}

const { apply } = await import(pathToFileURL(resolve(bridgeDir, 'src/index.js')).href)

// ── 内存版 sessionController：只实现插件用到的五个方法 ──────────────────────
const sessions = new Map()

function addSession(cwd, title = 'untitled') {
  const sessionId = `session-${randomUUID()}`
  sessions.set(sessionId, {
    sessionId,
    cwd,
    title,
    events: [
      { seq: 1, type: 'session/created', cwd },
      { seq: 2, type: 'session/renamed', title },
      { seq: 3, type: 'agent/idle' },
    ],
  })
  return sessionId
}

function notFound(sessionId) {
  const error = new Error(`session not found: ${sessionId}`)
  error.code = 'session/not-found'
  return error
}

const sessionController = {
  async list() {
    return {
      items: [...sessions.values()].map(({ sessionId, cwd, title }) => ({ sessionId, cwd, title })),
    }
  },
  async inspect(sessionId) {
    const session = sessions.get(sessionId)
    if (!session) throw notFound(sessionId)
    return { events: session.events }
  },
  async create({ cwd }) {
    return { sessionId: addSession(cwd), agentPreset: 'standard' }
  },
  async rename({ sessionId, title }) {
    const session = sessions.get(sessionId)
    if (!session) throw notFound(sessionId)
    session.title = title
    return { title, seq: session.events.length + 1 }
  },
  async prompt({ sessionId, requestId, content }) {
    const session = sessions.get(sessionId)
    if (!session) throw notFound(sessionId)
    session.events.push({
      seq: session.events.length + 1,
      type: 'user/message',
      requestId,
      text: content.map((part) => part.text).join(''),
    })
    return { accepted: true }
  },
}

// 预置一个会话，只读用例不必先创建
addSession(process.cwd(), 'seeded by mock_host')

// ── 最小 Cordis ctx ─────────────────────────────────────────────────────────
const disposers = []
const ctx = {
  sessionController,
  config: {
    allowCreate: process.env.BRIDGE_ALLOW_CREATE !== 'false',
    auditLog: true,
    cwdAllowlist: process.env.BRIDGE_CWD_ALLOWLIST
      ? process.env.BRIDGE_CWD_ALLOWLIST.split(delimiter)
      : [],
  },
  effect(factory) { disposers.push(factory()) },
  logger: { info: (message) => console.log(message) },
}

await apply(ctx)

async function shutdown() {
  for (const dispose of disposers.reverse()) await dispose()
  process.exit(0)
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
