<!--
  ImportScenarioDialog.vue — 场景导入确认单(v2.3 方案 §3.2,W5)。

  界面是**确认单,不是编辑器**(P7-⑥):非敏感值只读展示、敏感字段无输入
  口(留空 = 保留字面值),要改值导入后去 carry 配置页。分区:
  * fatal(blocking):格式/convert/修订缺失 —— 只给「知道了」,修订缺失
    展示可用修订集引导改声明;
  * ID 冲突:勾选「分配新 ID」(预览 suggestedId,确认即回传,展示=最终);
  * 服务映射行:复用/映射/新建可切换;新建可换名(ref/账户装载在服务
    注册页配置,导入面不挂);文案说清全局副作用(base_url/carry 平台全局生效);
  * 认证引用栏(P7-③):${auth.*} × 你本人凭证池,只展示不阻塞;
  * 内置凭证栏(authz M2a S7.5,ref 重做 P2-B.6):文件 config.users 的键
    明文不落库 —— 模板键按同名身份条目装载,步骤键改写为所属服务的条目名;
  * 导入结果(S7.5):落库回报「需要装载的身份条目 × 我的装载状态」+
    改写 / 未落地 / 丢弃清单,未装载条目一键深链凭证登记(条目登记坐标
    system+env);无可报即直接进场景;
  * 步骤锚定(#323):可执行形态反查 —— 已回填计数 + 未锚黄条(原因与
    carry 降级后果),只警示不阻塞(手写裸调用是合法形态);
  * 409 自愈:scenario_id_exists/alias_name_taken/mapping_stale → 自动
    重新预检刷新建议,无需重选文件。
-->
<template>
  <div v-if="open" class="imp-overlay" @click.self="onClose">
    <div class="imp-dialog lib-card">
      <div class="imp-head">
        <span class="text-body font-semibold">导入场景</span>
        <span class="text-caption text-signal-muted">导入 = 新建:与源场景无关,配置由你接手维护</span>
        <span class="flex-1"></span>
        <button type="button" class="imp-x" data-testid="import-close" @click="onClose">✕</button>
      </div>

      <div class="imp-body">
        <!-- S7.5(ref 重做)导入结果:需要装载的身份条目 × 我的装载状态 -->
        <div v-if="result" data-testid="import-result">
          <p class="imp-ok">已导入 <code class="imp-id">{{ result.scenarioId }}</code> —— 内置凭证明文未落库,步骤认证已落到本机身份条目;执行时按条目 ref 取你(或项目)登记的账户。</p>
          <div v-if="resultEntries.length" class="imp-section">
            <p class="imp-sec-title">需要装载的身份条目</p>
            <table class="imp-table">
              <thead><tr><th>条目</th><th>来源</th><th>账户装载</th><th></th></tr></thead>
              <tbody>
                <tr v-for="s in resultEntries" :key="s.entry" :data-testid="`import-entry-${s.entry}`">
                  <td class="mono">{{ s.entry }}</td>
                  <td>{{ s.fromBuiltin ? '内置凭证转来' : '场景引用' }}</td>
                  <td>
                    <span class="imp-chip" :class="{ 'imp-chip-miss': !s.bound }">{{ s.bound ? '已装载' : '未装载' }}</span>
                  </td>
                  <td>
                    <button type="button" class="imp-link" :data-testid="`import-entry-go-${s.entry}`" @click="goBind(s)">{{ s.bound ? '查看' : '去登记' }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="result.authRenames?.length" class="imp-warn" data-testid="import-auth-renames">
            步骤认证已落到本机身份条目:<template v-for="r in result.authRenames" :key="r.service">{{ r.service }}:{{ r.from }} → {{ r.to }};</template>
          </p>
          <p v-if="result.identityWarnings?.length" class="imp-warn" data-testid="import-identity-warnings">
            ⚠ 仍有未登记引用(已按 audit 放行):<b class="mono">{{ result.identityWarnings.join('、') }}</b>
            —— 请到「服务注册」登记条目,或改绑已有条目;enforce 后保存将被拒。
          </p>
          <p v-if="result.serviceWarnings?.unregistered?.length || result.serviceWarnings?.declaredUrls?.length"
             class="imp-warn" data-testid="import-service-warnings">
            ⚠ 服务引用(已按 audit 放行):<b class="mono">{{ [result.serviceWarnings.unregistered.length ? `未注册:${result.serviceWarnings.unregistered.join('、')}` : '', result.serviceWarnings.declaredUrls.length ? `内嵌地址:${result.serviceWarnings.declaredUrls.join('、')}` : ''].filter(Boolean).join(';') }}</b>
            —— 服务到「服务注册」登记,地址配置到部署表;enforce 后保存将被拒。
          </p>
          <p v-if="result.identityBaseWarnings?.length" class="imp-warn" data-testid="import-base-warnings">
            ⚠ 跨源引用(已按 audit 放行):<b class="mono">{{ result.identityBaseWarnings.map((r) => `${r.identity}(${r.identityBase})@步骤${r.index + 1}[${r.service}]`).join('、') }}</b>
            —— 条目与所在步骤服务不同源,请改绑同源条目;enforce 后保存将被拒。
          </p>
          <div v-if="result.undeclaredUsers?.length" class="imp-warn" data-testid="import-undeclared">
            <p v-for="u in result.undeclaredUsers" :key="u.tag" class="imp-warn-line">
              ⚠ 认证标签 <b class="mono">{{ u.tag }}</b>({{ u.services.join('、') }})未落地为身份条目:{{ undeclaredReasonLabel(u.reason) }} —— 这些步骤执行时会报错。
            </p>
          </div>
          <p v-if="result.droppedUsers?.length" class="text-caption text-signal-muted" data-testid="import-dropped">
            未被任何步骤使用的内置凭证已丢弃:{{ result.droppedUsers.join('、') }}
          </p>
          <p class="text-caption text-signal-muted">
            <button type="button" class="imp-link" data-testid="import-my-bindings" @click="goBind()">凭证管理</button>
          </p>
        </div>

        <!-- fatal 区 -->
        <div v-else-if="fatal" class="imp-fatal" data-testid="import-fatal">
          <p class="imp-fatal-title">无法导入</p>
          <p v-for="e in precheck?.convert.errors || []" :key="e" class="imp-fatal-line">{{ e }}</p>
          <p v-if="revisionsHint" class="imp-fatal-line">{{ revisionsHint }}</p>
          <p class="text-caption text-signal-muted">请修改文件后重试;文件请用「导出 JSON」产物 —— 带方案导出含导出人明文凭证,不建议用于传递。</p>
        </div>

        <template v-else>
          <!-- 版本声明 / working 黄条 -->
          <div class="imp-section">
            <p class="imp-sec-title">版本声明</p>
            <div class="imp-chips">
              <span v-for="(ref, sys) in precheck?.metaPlate || {}" :key="sys" class="imp-chip">{{ sys }} → {{ ref }}</span>
            </div>
            <p v-if="workingDeclarations.length" class="imp-warn" data-testid="import-working">
              ⚠ {{ workingDeclarations.join('、') }} 声明为 working(源平台工作区)——本机同名 working 内容可能不同,建议先钉修订。
            </p>
          </div>

          <!-- 步骤锚定(#323):可执行形态反查;未锚步骤落库后执行将走
               carry 降级门控(服务绑定全表字段可能注入请求体) -->
          <div v-if="anchorUnresolved.length || anchorAnchored.length" class="imp-section" data-testid="import-anchoring">
            <p class="imp-sec-title">步骤锚定(可执行形态反查)</p>
            <p v-if="anchorAnchored.length" class="text-caption text-signal-muted">
              已回填锚点 {{ anchorAnchored.length }} 步(与编排器保存形态一致)。
            </p>
            <div v-if="anchorUnresolved.length" class="imp-warn">
              <p v-for="a in anchorUnresolved" :key="a.index" class="imp-warn-line">
                ⚠ 步骤{{ a.index + 1 }} <span class="mono">{{ a.method }} {{ a.path }}</span><span v-if="a.service">({{ a.service }})</span>
                未锚:{{ anchorReasonLabel(a.reason) }}<span v-if="a.reason === 'not_in_revision' && a.endpoint">(working 曾命中 {{ a.endpoint }})</span>
                —— 执行时该步将走 carry 降级注入,服务绑定全表字段可能进入请求体。
              </p>
            </div>
          </div>

          <!-- ID 冲突区 -->
          <div v-if="precheck?.idConflict" class="imp-section" data-testid="import-id-zone">
            <p class="imp-sec-title">场景 ID 冲突</p>
            <label class="imp-check">
              <input v-model="assignNewId" type="checkbox" data-testid="import-assign-new" />
              分配新 ID:<code v-if="effectiveNewId" class="imp-id">{{ effectiveNewId }}</code>
            </label>
          </div>

          <!-- 服务映射区 -->
          <div v-if="rows.length" class="imp-section">
            <p class="imp-sec-title">服务映射(析出分析)</p>
            <table class="imp-table">
              <thead>
                <tr><th>服务键</th><th>建议</th><th>交别名</th><th>保留字面值</th><th>决策</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.serviceKey" :data-testid="`import-svc-${row.serviceKey}`">
                  <td class="mono">{{ row.serviceKey }}</td>
                  <td>{{ suggestionLabel(row.suggestion) }}</td>
                  <td>{{ toAliasCount(row) }}</td>
                  <td>{{ keptLiteralCount(row) }}<span v-if="row.sensitivePaths.length" class="text-caption text-signal-muted">(含敏感 {{ row.sensitivePaths.length }})</span><span v-if="row.inconsistentPaths.length" class="text-caption text-signal-muted">(取值不一致 {{ row.inconsistentPaths.length }})</span></td>
                  <td>
                    <template v-if="exists(row)">
                      <label class="imp-inline"><input type="radio" :name="`d-${row.serviceKey}`" value="reuse" :checked="decision(row) !== 'create'" @change="setDecision(row, 'map')" />映射到已有</label>
                      <!-- authz W7/W8:新建别名需 alias.write(Admin 职责),
                           无能力者不见此选项,后端同门 403 兜底 -->
                      <label v-if="canCreateAlias" class="imp-inline"><input type="radio" :name="`d-${row.serviceKey}`" value="create" :checked="decision(row) === 'create'" @change="setDecision(row, 'create')" />新建</label>
                    </template>
                    <span v-else class="text-caption text-signal-muted">
                      新建{{ canCreateAlias ? '' : '(需别名管理权 alias.write — 联系管理员登记后再导入)' }}
                    </span>
                  </td>
                </tr>
                <tr v-for="row in createRows" :key="`${row.serviceKey}-cfg`" class="imp-create-cfg">
                  <td colspan="5">
                    <div class="imp-cfg-line">
                      <label>新别名名:<input v-model="createNames[row.serviceKey]" class="imp-input mono" :data-testid="`import-newname-${row.serviceKey}`" /></label>
                      <!-- registry:导入建的条目默认 ref=默认账户(后端兜底);
                           账户装载关系在服务注册页按 ref 配置,导入面不再挂 -->
                    </div>
                    <p class="text-caption text-signal-muted">
                      base_url 与 carry 绑定对全平台生效(其他场景引用同名服务键也会命中);敏感字段不写入 carry,保留字面值。
                      <span v-if="!createNameOk(row)">⚠ 该名不可原样登记(不在目录派生范围或已被占用),需换名。</span>
                    </p>
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="Object.keys(inconsistentMap).length" class="imp-warn" data-testid="import-inconsistent">
              ⚠ 以下字段在各步骤取值不一致,不交给别名接管,各步骤保留文件里的原值:<template v-for="(paths, key) in inconsistentMap" :key="key">{{ key }} {{ paths.join('、') }};</template>
            </p>
          </div>

          <!-- 认证引用栏(P7-③) -->
          <div v-if="precheck?.authRefs?.length" class="imp-section" data-testid="import-authrefs">
            <p class="imp-sec-title">认证引用(config.users 清空后的可解析性)</p>
            <div class="imp-chips">
              <span v-for="a in precheck.authRefs" :key="a.tag" class="imp-chip" :class="{ 'imp-chip-miss': !a.inMyPool }">
                {{ a.tag }}:{{ a.inMyPool ? '你的凭证池已有' : '你的凭证池没有' }}
              </span>
            </div>
            <p class="text-caption text-signal-muted">「没有」的引用执行时该步会报错——到凭证管理补配你自己的凭证。</p>
          </div>

          <!-- 内置凭证 → 身份条目(S7.5,ref 重做 P2-B.6) -->
          <div v-if="builtinUsers.length" class="imp-section" data-testid="import-builtin-users">
            <p class="imp-sec-title">内置凭证 → 身份条目</p>
            <div class="imp-chips">
              <span v-for="u in builtinUsers" :key="u.tag" class="imp-chip" :class="{ 'imp-chip-miss': u.templated && !u.bound }">
                {{ u.tag }}<template v-if="u.services.length">({{ u.services.join('、') }})</template>:{{ builtinUserLabel(u) }}
              </span>
            </div>
            <p class="text-caption text-signal-muted">
              文件里的凭证明文不会导入。被 ${auth.*} 模板引用的键按本机同名身份条目装载;仅步骤使用的键在导入时改写为所属服务的身份条目名。导入后列出最终需要装载的条目。
            </p>
          </div>
        </template>
      </div>

      <div v-if="result" class="imp-foot">
        <span class="flex-1"></span>
        <button type="button" class="imp-btn imp-btn-primary" data-testid="import-open-scenario" @click="openScenario">进入场景</button>
      </div>
      <div v-else class="imp-foot">
        <span v-if="reprechecking" class="text-caption text-signal-muted">已重新预检(配置有变化)…</span>
        <span class="flex-1"></span>
        <button type="button" class="imp-btn" @click="onClose">{{ fatal ? '知道了' : '取消' }}</button>
        <button
          v-if="!fatal"
          type="button"
          class="imp-btn imp-btn-primary"
          :disabled="importing"
          data-testid="import-confirm"
          @click="onConfirm"
        >{{ importing ? '导入中…' : '确认导入' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { ApiError } from '@/api/http'
import {
  importPrecheck, importScenario,
  type ImportPrecheck, type ImportServiceRow, type ImportMapping,
  type ImportAnchorEntry, type ImportAuthEntry, type ImportResult,
  type ImportBuiltinUser,
} from '@/api/scenario-import'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ open: boolean; bundle: Record<string, unknown> | null }>()
const emit = defineEmits<{ close: []; imported: [scenarioId: string] }>()

const auth = useAuthStore()
const router = useRouter()
/** authz W7:新建别名需 alias.write(表 A:admin+);User 只能映射到已有 */
const canCreateAlias = computed(() => auth.can('alias.write'))

const precheck = ref<ImportPrecheck | null>(null)
const loading = ref(false)
const importing = ref(false)
const reprechecking = ref(false)
const decisions = ref<Record<string, 'reuse' | 'map' | 'create'>>({})
const createNames = ref<Record<string, string>>({})
const assignNewId = ref(true)
/** S7.5:落库回报(非空 = 结果视图) */
const result = ref<ImportResult | null>(null)

const fatal = computed(() => !!precheck.value?.blocking)
const rows = computed(() => precheck.value?.services || [])
const createRows = computed(() => rows.value.filter((r) => decision(r) === 'create'))
const workingDeclarations = computed(() => precheck.value?.workingDeclarations || [])
const builtinUsers = computed(() => precheck.value?.builtinUsers || [])
// 未装载在前(结果页的行动项优先)
const resultEntries = computed(() =>
  [...(result.value?.authEntries || [])].sort((a, b) => Number(a.bound) - Number(b.bound)))
// 锚定判定只看 reason(#323 口径):not_in_revision 条目的 endpoint 是被拒
// 候选的排查信息,不代表已锚;缺省键(旧负载/阻断路径)按空处理
const anchorUnresolved = computed(
  () => precheck.value?.anchoring?.unresolved || [])
const anchorAnchored = computed(
  () => precheck.value?.anchoring?.anchored || [])
const inconsistentMap = computed<Record<string, string[]>>(() => {
  const out: Record<string, string[]> = {}
  for (const r of rows.value) {
    if (r.inconsistentPaths?.length) out[r.serviceKey] = r.inconsistentPaths
  }
  return out
})
const effectiveNewId = computed(() =>
  assignNewId.value ? precheck.value?.suggestedId ?? null : null)
const revisionsHint = computed(() => {
  const revs = precheck.value?.availableRevisions || {}
  const parts = Object.entries(revs).map(([line, rs]) => `${line}: ${rs.join('、')}`)
  return parts.length ? `本机可用修订 — ${parts.join(';')}` : ''
})

function exists(row: ImportServiceRow): boolean {
  return row.suggestion !== 'create'
}
function decision(row: ImportServiceRow): 'reuse' | 'map' | 'create' {
  return decisions.value[row.serviceKey] || row.suggestion
}
function setDecision(row: ImportServiceRow, d: 'map' | 'create') {
  decisions.value = { ...decisions.value, [row.serviceKey]: d }
}
function createNameOk(row: ImportServiceRow): boolean {
  if (decision(row) !== 'create') return true
  return row.createNameAvailable && !createNames.value[row.serviceKey]?.trim()
    ? row.createNameAvailable
    : !!createNames.value[row.serviceKey]?.trim()
}
function suggestionLabel(s: string): string {
  return s === 'reuse' ? '复用(值一致)' : s === 'map' ? '映射(本机为准)' : '新建'
}
function undeclaredReasonLabel(r: string): string {
  return r === 'no_identity'
    ? '所用服务没有登记身份条目(请管理员在服务注册页登记)'
    : '该服务用到多个账号,无法自动改写到单一身份条目'
}
function builtinUserLabel(u: ImportBuiltinUser): string {
  if (u.templated) return u.bound ? '同名条目已装载' : '同名条目未装载'
  return '将改写到所属服务的条目'
}
/** 结果视图有可报内容才停留;否则保持「导入即进场景」旧流程。
 *  identityWarnings(2c):登记闸 audit 黄条也是可报内容 —— 停留展示。
 *  identityBaseWarnings(阶段 3):同 base 闸 audit 黄条同款。 */
function hasReport(r: ImportResult): boolean {
  return !!(r.authEntries?.length || r.authRenames?.length
    || r.undeclaredUsers?.length || r.droppedUsers?.length
    || r.identityWarnings?.length || r.identityBaseWarnings?.length
    || r.serviceWarnings?.unregistered?.length
    || r.serviceWarnings?.declaredUrls?.length)
}
/** 已装载 → 检索定位;未装载 → 按条目登记坐标深链(条目自主档派生
 *  system+env;悬空条目无坐标,退普通入口)。 */
function goBind(e?: ImportAuthEntry): void {
  const query = !e ? {}
    : e.bound ? { q: e.entry }
      : (e.system
        ? { system: e.system, ...(e.envId != null ? { envId: String(e.envId) } : {}) }
        : {})
  emit('close')
  void router?.push({ path: '/auths', query })
}
function openScenario(): void {
  if (result.value) emit('imported', result.value.scenarioId)
}
function anchorReasonLabel(r: ImportAnchorEntry['reason']): string {
  switch (r) {
    case 'not_in_catalog': return '声明修订的端点清单中无匹配(method+path 未命中)'
    case 'ambiguous': return '多个候选端点匹配,无法唯一确定'
    case 'not_in_revision': return 'working 命中但钉定修订内 method/path 已漂移'
    case 'catalog_unavailable': return 'plate 端点清单不可用,未能反查'
    default: return '未知原因'
  }
}
// 计数按当前决策取(切换决策接管面不同,确认内容必须
// 与实际执行一致);旧负载无 countsByDecision 时回落顶层建议计数
function toAliasCount(row: ImportServiceRow): number {
  return row.countsByDecision?.[decision(row)]?.fieldsToAlias ?? row.fieldsToAlias
}
function keptLiteralCount(row: ImportServiceRow): number {
  return row.countsByDecision?.[decision(row)]?.fieldsKeptLiteral ?? row.fieldsKeptLiteral
}

async function runPrecheck(): Promise<void> {
  if (!props.bundle) return
  loading.value = true
  try {
    precheck.value = await importPrecheck(props.bundle)
    result.value = null
    decisions.value = {}
    createNames.value = {}
    assignNewId.value = true
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail
    toast.error(`预检失败: ${detail?.message || (e as Error).message}`)
    emit('close')
  } finally {
    loading.value = false
  }
}

async function onConfirm(): Promise<void> {
  if (!props.bundle) return
  importing.value = true
  try {
    const mappings: ImportMapping[] = rows.value.map((r) => {
      const d = decision(r)
      const m: ImportMapping = { serviceKey: r.serviceKey, decision: d }
      if (d === 'create') {
        const name = createNames.value[r.serviceKey]?.trim()
        if (name && name !== r.serviceKey) m.createName = name
      }
      return m
    })
    const res = await importScenario({
      bundle: props.bundle,
      mappings,
      ...(effectiveNewId.value
        ? { idMode: 'new' as const, newId: effectiveNewId.value }
        : {}),
    })
    if (hasReport(res)) {
      result.value = res
      return
    }
    toast.success(`已导入 ${res.scenarioId} —— 建议先跑一次执行预检`)
    emit('imported', res.scenarioId)
  } catch (e) {
    if (e instanceof ApiError && (e.hasCode('scenario_id_exists')
        || e.hasCode('alias_name_taken') || e.hasCode('mapping_stale'))) {
      // 409 自愈:自动重新预检刷新建议(方案 §3.2)
      toast.info('配置有变化,已重新预检 — 请再确认一次')
      reprechecking.value = true
      await runPrecheck()
      reprechecking.value = false
      return
    }
    const detail = (e instanceof ApiError ? e.detail : null)
      ?? (e as { response?: { data?: { detail?: { message?: string } } } })
        ?.response?.data?.detail
    toast.error(`导入失败: ${detail?.message || (e as Error).message}`)
  } finally {
    importing.value = false
  }
}

function onClose(): void {
  // 结果视图下场景已落库:关闭 = 进场景(与旧「导入即进场景」一致)
  if (result.value) {
    openScenario()
    return
  }
  emit('close')
}

watch(() => props.open, (v) => {
  if (v) {
    void runPrecheck()
  }
}, { immediate: true })
</script>

<style scoped>
.imp-overlay {
  position: fixed; inset: 0; z-index: 60;
  background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 6vh 1rem; overflow-y: auto;
}
.imp-dialog {
  width: min(47.5rem, 100%);
  display: flex; flex-direction: column;
  max-height: 86vh;
}
.imp-head {
  display: flex; align-items: center; gap: 0.625rem;
  padding: 0.875rem 1.125rem; border-bottom: 1px solid #eef0f4;
}
.imp-x {
  border: none; background: transparent; cursor: pointer;
  color: var(--color-text-secondary); font-size: 0.875rem;
}
.imp-body { padding: 0.875rem 1.125rem; overflow-y: auto; }
.imp-section { margin-bottom: 0.875rem; }
.imp-sec-title {
  font-size: 0.78125rem; font-weight: 600; color: #334155; margin-bottom: 0.375rem;
}
.imp-chips { display: flex; flex-wrap: wrap; gap: 0.375rem; }
.imp-chip {
  padding: 0.0625rem 0.5rem; border-radius: 62.4375rem; font-size: 0.71875rem;
  border: 1px solid var(--sl-line); background: var(--surface-raised); color: #334155;
}
.imp-chip-miss { border-color: #f59e0b; background: #fffbeb; color: var(--sl-warn); }
.imp-warn {
  margin-top: 0.375rem; font-size: 0.71875rem; color: var(--sl-warn);
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 0.375rem; padding: 0.25rem 0.5rem;
}
.imp-warn-line { font-size: 0.75rem; line-height: 1.5; }
.imp-warn-line + .imp-warn-line { margin-top: 0.125rem; }
.imp-fatal {
  border: 1px solid #fecaca; background: #fef2f2; border-radius: 0.5rem;
  padding: 0.75rem;
}
.imp-fatal-title { font-weight: 600; color: #b91c1c; font-size: 0.8125rem; }
.imp-fatal-line { font-size: 0.75rem; color: #7f1d1d; margin-top: 0.25rem; word-break: break-all; }
.imp-check { font-size: 0.78125rem; color: #334155; display: flex; gap: 0.375rem; align-items: center; }
.imp-id { font-family: ui-monospace, monospace; background: var(--soft-neutral-bg); padding: 0.0625rem 0.375rem; border-radius: 0.25rem; }
.imp-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.imp-table th {
  text-align: left; font-weight: 600; color: var(--color-text-secondary); font-size: 0.6875rem;
  padding: 0.25rem 0.5rem; border-bottom: 1px solid #eef0f4;
}
.imp-table td { padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--soft-neutral-bg); vertical-align: top; }
.imp-create-cfg td { background: var(--surface-raised); }
.imp-cfg-line { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.25rem; font-size: 0.75rem; color: #334155; }
.imp-inline { display: inline-flex; gap: 0.25rem; align-items: center; margin-right: 0.625rem; font-size: 0.75rem; }
.imp-input {
  border: 1px solid var(--sl-line); border-radius: 0.375rem; padding: 0.125rem 0.5rem;
  font-size: 0.75rem; background: var(--c-surface); min-width: 8.75rem;
}
.imp-foot {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 1.125rem; border-top: 1px solid #eef0f4;
}
.imp-btn {
  padding: 0.3125rem 1rem; border-radius: 0.375rem; border: 1px solid var(--sl-line);
  background: var(--c-surface); font-size: 0.78125rem; cursor: pointer; color: #334155;
}
.imp-btn-primary { background: var(--sl-accent); border-color: var(--sl-accent); color: #fff; }
.imp-btn-primary:disabled { opacity: 0.6; cursor: default; }
.mono { font-family: ui-monospace, monospace; }
.imp-ok { font-size: 0.78125rem; color: #166534; margin-bottom: 0.625rem; }
.imp-link {
  border: none; background: transparent; padding: 0; cursor: pointer;
  color: var(--sl-accent); font-size: 0.75rem; text-decoration: underline;
}
</style>
