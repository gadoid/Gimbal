<!-- ExecConfigsView.vue — 执行配置管理页(执行配置分层①/③,/exec-configs)。
     个人面·全员:一套默认 + 若干命名配置,每组配置按系统分组内联子配置
     (bindings + carryOverrides)。零凭证值零地址值 —— 凭证在凭证管理、
     地址在服务注册,这里只存引用键。
     ③ 关联枢纽(§8):对既有配置面只做**关联** —— 存引用键 + 放深链,
     不搬数据、不代管维护面与权限门。页内四路关联:地址就绪度(部署
     矩阵)+ 深链服务注册;绑定条目→个人池装载就绪(registry C3a 新链:
     换用条目 → ref → (system, env) 账户;与后端 pick_bindings 同构)+
     未登记深链服务子页 / 缺账户深链 /auths 按 (system, envId) 预填直达
     (注册表状态按名定向检索,规模安全);服务→逐系统子页(身份条目
     注册表+说明)深链;carry 覆盖→内联展示+漂移检查+层宿主深链;
     生效预览 pickable(选定配置即预览逐值带来源)。全部由现有读 API
     拼装 + 一个配置漂移读面,零新写面。
     形制与服务组其余页共用 .slib 基座(scenario-lib.css / service-area.css)。 -->
<template>
  <section class="slib" data-testid="exec-configs">
    <PageHead
      icon="sliders"
      title="配置"
      :count="loading ? '' : `${rows.length} 套配置`"
      :meta="mode === 'edit' && selected ? `当前配置 · ${selected.name}` : undefined"
      subtitle="场景外部支撑的跨场景载体:以谁(身份条目装载)、带什么业务参数(carry 覆盖)。一套默认 + 若干命名变体;执行时选一套注入。凭证在「凭证管理」按条目 ref 解析、地址按身份的环境标签取部署表 —— 本页零凭证值零地址值。"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 配置 chip 行 = 视图切换(单选),与凭证管理同族 -->
      <div class="slib-toolbar" data-testid="ec-chips">
        <span class="svc-stats tight">
          <button v-for="c in rows" :key="c.id" type="button" class="svc-chip"
                  :class="{ on: mode === 'edit' && c.id === selectedId }"
                  :data-testid="`ec-chip-${c.id}`" @click="pick(c.id)">
            {{ c.name }}<span v-if="c.isDefault" class="svc-flag green">默认</span>
          </button>
        </span>
        <button type="button" class="slib-create" data-testid="ec-new"
                @click="openCreate">+ 新建配置</button>
      </div>

      <div v-if="!rows.length" class="slib-empty">
        <p>暂无执行配置 —— 新建一套默认配置(或从凭证管理/服务注册开始)</p>
      </div>

      <!-- 新建 / 编辑(整体替换式) -->
      <div v-if="formOpen" class="svc-panel" :data-testid="`ec-form-${mode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ mode === 'create' ? '新建配置' : `编辑:${form.name || selected?.name}` }}
          </span>
          <span class="svc-panel-desc">
            子配置按被测系统分组:绑定 = 声明条目 → 换用条目(覆盖条目解析的
            配置层);carry 覆盖 = 该系统带的业务参数(删行 = 不覆盖、按层序
            合成;值留空 = 注入空串)
          </span>
        </div>

        <div class="form-grid">
          <label class="lb">名称</label>
          <Input v-model="form.name" placeholder="如 商户B视角@UAT"
                 data-testid="ec-name" />
        </div>

        <div v-for="(s, i) in sysRows" :key="i" class="sys">
          <div class="sys-head">
            <span class="sys-title">系统 {{ i + 1 }}</span>
            <button type="button" class="svc-link danger" :data-testid="`ec-sys-rm-${i}`"
                    @click="sysRows.splice(i, 1)">移除系统</button>
          </div>

          <div class="line-row">
            <label class="lb">系统</label>
            <Input v-model="s.service" class="flex-1"
                   placeholder="目录服务名,如 fin-service"
                   :data-testid="`ec-sys-${i}`" />
          </div>

          <div v-for="(b, j) in s.binds" :key="`b${j}`" class="line-row">
            <label class="lb">绑定</label>
            <Input v-model="b.alias" class="flex-1"
                   placeholder="声明条目名(场景里引用的,如 fin-service.merchant-b)"
                   :data-testid="`ec-bind-${i}-${j}`" />
            <span class="lb">→</span>
            <Input v-model="b.slot" class="flex-1" placeholder="换用条目名(池内实际取用的)"
                   :data-testid="`ec-slot-${i}-${j}`" />
            <button type="button" class="svc-link danger" :data-testid="`ec-bind-rm-${i}-${j}`"
                    @click="s.binds.splice(j, 1)">移除</button>
          </div>
          <div class="line-row">
            <Button variant="outline" size="sm" :data-testid="`ec-bind-add-${i}`"
                    @click="s.binds.push({ alias: '', slot: '' })">+ 添加绑定</Button>
          </div>

          <div v-for="(c, j) in s.carries" :key="`c${j}`" class="line-row">
            <label class="lb">carry</label>
            <Input v-model="c.field" class="flex-1"
                   placeholder="字段,如 merchant.grade"
                   :data-testid="`ec-carry-${i}-${j}`" />
            <span class="lb">=</span>
            <Input v-model="c.value" class="flex-1" placeholder="值"
                   :data-testid="`ec-carryv-${i}-${j}`" />
            <button type="button" class="svc-link danger" :data-testid="`ec-carry-rm-${i}-${j}`"
                    @click="s.carries.splice(j, 1)">移除</button>
          </div>
          <div class="line-row">
            <Button variant="outline" size="sm" :data-testid="`ec-carry-add-${i}`"
                    @click="s.carries.push({ field: '', value: '' })">+ 添加 carry 字段</Button>
          </div>
        </div>

        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="ec-sys-add"
                  @click="sysRows.push({ service: '', binds: [], carries: [] })">+ 添加系统</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="ec-save" @click="save">保存</Button>
            <Button variant="outline" size="sm" data-testid="ec-cancel" @click="cancel">取消</Button>
          </span>
        </div>
      </div>

      <!-- 选中配置的动作条 -->
      <div v-if="mode === 'edit' && selected" class="svc-stats" data-testid="ec-actions">
        <span>配置</span>
        <b>{{ selected.name }}</b>
        <span v-if="selected.isDefault" class="svc-flag green" data-testid="ec-is-default">默认配置</span>
        <span class="flex-1" />
        <Button v-if="!selected.isDefault" variant="outline" size="sm"
                data-testid="ec-set-default" @click="makeDefault">设为默认</Button>
        <template v-if="!copyArmed">
          <Button variant="outline" size="sm" data-testid="ec-copy"
                  @click="copyArmed = true">复制为新配置</Button>
        </template>
        <template v-else>
          <Input v-model="copyName" class="w-[11.25rem]" placeholder="新配置名"
                 data-testid="ec-copy-name" />
          <Button size="sm" data-testid="ec-copy-ok" @click="doCopy">复制</Button>
          <Button variant="outline" size="sm" @click="copyArmed = false">取消</Button>
        </template>
        <template v-if="!delArmed">
          <Button variant="outline" size="sm" class="text-signal-failed"
                  data-testid="ec-del" @click="delArmed = true">删除</Button>
        </template>
        <template v-else>
          <span class="svc-flag red">确认删除该配置?</span>
          <Button variant="destructive" size="sm" data-testid="ec-del-ok"
                  @click="del">确认删除</Button>
          <Button variant="outline" size="sm" @click="delArmed = false">取消</Button>
        </template>
      </div>

      <!-- ═══ ③ 关联枢纽:就绪度 + 四路深链(关联而非纳入)═══ -->
      <div v-if="mode === 'edit' && selected" class="hub" data-testid="ec-hub">
        <div class="svc-sec">
          <span class="t">关联与就绪度</span>
          <span class="n">只关联不纳入 —— 维护面留在各自页面</span>
        </div>

        <!-- ① 地址就绪度(部署矩阵读面;§8.2 配置去 env 后按全环境矩阵
             展示 —— 执行时地址按身份的环境标签取数)+ 深链「服务注册」 -->
        <div class="svc-panel" data-testid="ec-hub-env">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务注册</span>
            <span class="svc-panel-desc">各系统按环境的地址就绪度(执行时按身份的环境标签取)</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/service-admin"
                class="svc-link">维护在「服务注册」↗</router-link>
              <span v-else class="svc-panel-desc">地址由平台管理员在「服务注册」维护</span>
            </span>
          </div>
          <p v-if="!selected.systems.length" class="hub-note">
            本配置还没有系统子配置 —— 地址就绪度按系统展示。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-deps">
            <thead>
              <tr><th>系统</th><th>环境</th><th>地址</th><th style="width:4.375rem">就绪</th></tr>
            </thead>
            <tbody>
              <template v-for="s in selected.systems" :key="`dep-${s.service}`">
                <tr v-for="(d, i) in depsOf(s.service)" :key="`dep-${s.service}-${i}`"
                    :data-testid="`ec-dep-${s.service}`">
                  <td v-if="i === 0" :rowspan="depsOf(s.service).length || 1">
                    <span class="mono">{{ s.service }}</span>
                  </td>
                  <td>{{ envName(d.envId) }}</td>
                  <td><span class="mono">{{ d.baseUrl || '—' }}</span></td>
                  <td>
                    <span v-if="d.baseUrl" class="svc-flag green">就绪</span>
                    <span v-else class="svc-flag amber">缺地址</span>
                  </td>
                </tr>
                <tr v-if="!depsOf(s.service).length" :data-testid="`ec-dep-${s.service}`">
                  <td><span class="mono">{{ s.service }}</span></td>
                  <td>—</td>
                  <td>—</td>
                  <td><span class="svc-flag amber">缺地址</span></td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- ② 绑定条目 → 个人池装载就绪(ref→账户新链;C3a)+ 缺失深链
             /auths 预填直达(system+envId = 条目装载坐标) -->
        <div class="svc-panel" data-testid="ec-hub-slots">
          <div class="svc-panel-head">
            <span class="svc-panel-title">身份条目装载就绪</span>
            <span class="svc-panel-desc">换用条目按 ref 取个人池账户((系统, 环境) 坐标);缺失点直达凭证管理</span>
          </div>
          <p v-if="!hasBindings" class="hub-note">
            未配置绑定 —— 注入按场景声明的条目解析(配置层不覆盖)。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-bindings">
            <thead>
              <tr><th>声明条目</th><th>换用条目</th><th>装载坐标</th>
                  <th style="width:5.625rem">个人池</th><th style="width:13.125rem">操作</th></tr>
            </thead>
            <tbody>
              <template v-for="s in selected.systems">
                <tr v-for="(slot, alias) in s.bindings" :key="`${alias}=${slot}`">
                  <td>
                    <span class="mono">{{ alias }}</span>
                    <span v-if="facesLoaded && !aliasExists(String(alias))"
                          class="svc-flag red ml-1" title="身份条目注册表中不存在">✕ 未登记</span>
                  </td>
                  <td>
                    <span class="mono">{{ slot }}</span>
                    <span v-if="facesLoaded && !aliasExists(String(slot))"
                          class="svc-flag red ml-1" title="换用条目未登记 — 取不到 ref 坐标">✕ 未登记</span>
                  </td>
                  <td><span class="mono">{{ coordOf(String(slot)) }}</span></td>
                  <td>
                    <span v-if="entryLoaded(String(slot))" class="svc-flag green">已装载</span>
                    <span v-else class="svc-flag red" :data-testid="`ec-slot-miss-${slot}`">缺账户</span>
                  </td>
                  <td>
                    <!-- 未登记 → 该服务子页的身份条目注册表(登记的家);
                         缺个人池账户 → 凭证管理按 (system, env) 预填直达 -->
                    <router-link
                      v-if="facesLoaded && (!aliasExists(String(alias)) || !aliasExists(String(slot)))"
                      :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                      class="svc-link warn-link"
                      :data-testid="`ec-goto-faces-${alias}`"
                    >去登记 ↗</router-link>
                    <a class="svc-link" :data-testid="`ec-goto-auth-${slot}`"
                       :href="authHref(String(slot), s.service)">去凭证管理补 ↗</a>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- ③ 服务接入 → 逐系统子页(身份条目注册表 + 说明;读面全员)-->
        <div class="svc-panel" data-testid="ec-hub-svc">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务接入</span>
            <span class="svc-panel-desc">身份条目(条目名 → 服务 + 环境 + ref)在各服务子页登记;说明为服务级元数据</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/service-admin"
                class="svc-link">地址在「服务注册」↗</router-link>
            </span>
          </div>
          <p v-if="!selected.systems.length" class="hub-note">
            本配置还没有系统子配置 —— 身份条目按系统在各自子页登记。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-svcs">
            <thead>
              <tr><th>系统</th><th>说明</th><th style="width:6.875rem" class="c-center">身份条目</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in selected.systems" :key="`svc-${s.service}`"
                  :data-testid="`ec-svc-${s.service}`">
                <td><span class="mono">{{ s.service }}</span></td>
                <td class="muted">{{ svcDesc(s.service) || '—' }}</td>
                <td class="c-center">
                  <router-link
                    :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                    class="svc-link" :data-testid="`ec-goto-faces-${s.service}`"
                  >身份条目 ↗</router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ④ carry 覆盖 → 内联展示 + 漂移检查 + 层宿主深链 -->
        <div class="svc-panel" data-testid="ec-hub-carry">
          <div class="svc-panel-head">
            <span class="svc-panel-title">carry 覆盖</span>
            <span class="svc-panel-desc">本配置覆盖的字段与漂移检查;未覆盖字段按层序合成</span>
          </div>
          <p v-if="!hasCarries" class="hub-note">
            未配置覆盖 —— 全部字段按层序合成(公共项目层 &lt; 项目层;执行配置
            覆盖层位其上)。
          </p>
          <div v-for="s in selected.systems" :key="`carry-${s.service}`" class="carry-sys">
            <template v-if="Object.keys(s.carryOverrides).length">
              <p class="carry-head">
                <b>{{ s.service }}</b>
                <span v-if="driftOf(s.service)?.orphaned.length" class="svc-flag red">
                  漂移:{{ driftOf(s.service)!.orphaned.join('、') }} 已不在 plate 面</span>
                <span v-else-if="drift?.plateReachable" class="svc-flag green">无漂移</span>
              </p>
              <table class="slib-table">
                <tbody>
                  <tr v-for="(v, k) in s.carryOverrides" :key="k">
                    <td><span class="mono">{{ k }}</span></td>
                    <td><span class="mono">{{ v == null ? 'null(显式)' : String(v) }}</span></td>
                    <td><span class="svc-panel-desc">执行配置覆盖</span></td>
                  </tr>
                </tbody>
              </table>
              <p v-if="driftOf(s.service)?.uncovered.length" class="hub-note">
                面上还有 {{ driftOf(s.service)!.uncovered.length }} 个字段未被本配置覆盖
                (按层序合成,层宿主:
                <router-link to="/carry-config" class="svc-link">公共项目 · 配置 ↗</router-link>)
              </p>
            </template>
          </div>
          <p v-if="drift && !drift.plateReachable" class="svc-flag amber">
            plate 不可达 —— 漂移检查暂不可用(不可达 ≠ 全漂移)。
          </p>
        </div>

        <!-- ⑤ 生效预览:pickable(选定配置 + 任一场景 → 逐值带来源) -->
        <div class="svc-panel" data-testid="ec-hub-preview">
          <div class="svc-panel-head">
            <span class="svc-panel-title">生效预览</span>
            <span class="svc-panel-desc">
              选定本配置 + 任一你的场景 → 预览将生效的 地址/条目装载/carry(逐值带来源,与执行同源)
            </span>
          </div>
          <Button variant="outline" size="sm" data-testid="ec-preview-open"
                  @click="previewOpen = true">打开预览</Button>
        </div>
      </div>

      <div v-if="error" class="svc-banner bad mt-3.5" data-testid="ec-err">{{ error }}</div>
    </template>

    <EffectivePreviewDialog :open="previewOpen" :scenarios="scenOptions"
      :exec-config-id="selected?.id" :env-names="envNames"
      @close="previewOpen = false" />
  </section>
</template>

<script setup lang="ts">
/** ExecConfigsView.vue — 执行配置管理页 + ③ 关联枢纽(设计方案 §4/§8)。
 * 列表(chip)/编辑(整体替换式 PATCH)/默认切换/复制/两步删除;错误内联。
 * 枢纽数据全部来自现有读面:部署表(listDeployments)/个人池账户(listAll)/
 * 条目注册表定向检索(listAliases)/主档(listServices)/场景 options +
 * 一个配置漂移读面。
 * 2026-11-12 形制对齐:旧 .page 壳迁到 .slib + PageHead + svc-panel 分段,
 * chip/表单/错误条复用 scenario-lib.css / service-area.css 构件。 */
import { computed, onMounted, ref } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  listExecConfigs, createExecConfig, updateExecConfig,
  setDefaultExecConfig, copyExecConfig, deleteExecConfig, execConfigDrift,
  type ExecConfigRow, type SystemSubConfig, type ExecConfigDriftService,
} from '@/api/execConfigs'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments, type Deployment } from '@/api/deployments'
import { listAll as listAllAuths } from '@/api/auth_sessions'
import { listAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { listServices, type ServiceRow } from '@/api/services'
import { listServiceMeta } from '@/api/service-meta'
import { listScenarioOptions } from '@/api/scenario-composer'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'
import { useAuthStore } from '@/stores/auth'

interface BindRow { alias: string; slot: string }
interface CarryRow { field: string; value: string }
interface SysRow { service: string; binds: BindRow[]; carries: CarryRow[] }

const auth = useAuthStore()
const loading = ref(true)
const rows = ref<ExecConfigRow[]>([])
const envs = ref<EnvironmentRow[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'edit' | 'create'>('edit')
const form = ref({ name: '' })
const sysRows = ref<SysRow[]>([])
const error = ref('')
const delArmed = ref(false)
const copyArmed = ref(false)
const copyName = ref('')

const selected = computed(() =>
  rows.value.find((c) => c.id === selectedId.value) ?? null)
const formOpen = computed(() => mode.value === 'create' || selected.value !== null)
const hasBindings = computed(() =>
  rows.value.find((c) => c.id === selectedId.value)?.systems
    .some((s) => Object.keys(s.bindings).length) ?? false)
const hasCarries = computed(() =>
  rows.value.find((c) => c.id === selectedId.value)?.systems
    .some((s) => Object.keys(s.carryOverrides).length) ?? false)

// ── ③ 枢纽数据(读面拼装;失败降级为空,不阻塞编辑面)────────────
const deps = ref<Deployment[]>([])
/** 个人池账户(C3a 装载就绪链:账户化形状 system/envId/username/isDefault) */
const authRows = ref<Array<{ system: string | null; envId: number | null;
                            username?: string; isDefault?: boolean | null }>>([])
const drift = ref<{ services: ExecConfigDriftService[]; plateReachable: boolean } | null>(null)
const scenOptions = ref<Array<{ id: string; name: string }>>([])
const previewOpen = ref(false)
/** 主档(条目装载坐标:baseService → system) */
const svcRows = ref<ServiceRow[]>([])

// 绑定条目名的注册表状态:按名精确检索(规模安全 —— 注册表过 200 后
// 全量拉取截断会误报「未登记」;绑定条目个数有限,每个名字一次 q 检索
// + 精确命中,永不全量)。检索面 = 声明条目 ∪ 换用条目(两者都要坐标)。
const faceMeta = ref<Record<string, ServiceAliasRow | null>>({})
const facesLoaded = ref(false)
async function loadFacesFor(c: ExecConfigRow): Promise<void> {
  const names = [...new Set(c.systems.flatMap((s) => [
    ...Object.keys(s.bindings),
    ...Object.values(s.bindings),
  ]))]
  const out: Record<string, ServiceAliasRow | null> = {}
  await Promise.all(names.map(async (name) => {
    try {
      const env = await listAliases({ q: name, page_size: 10 })
      out[name] = env.items.find((a) => a.aliasName === name) ?? null
    } catch {
      out[name] = null
    }
  }))
  faceMeta.value = out
  facesLoaded.value = true
}

// 服务说明(service-meta;③ 服务接入面板回显,失败静默降级为「—」)
const svcMetas = ref<Record<string, string>>({})
function svcDesc(service: string): string {
  return svcMetas.value[service] ?? ''
}

const envNames = computed<Record<number, string>>(() =>
  Object.fromEntries(envs.value.map((e) => [e.id, e.name])))

function envName(id: number): string {
  return envNames.value[id] ?? `环境 #${id}`
}
/** 系统的部署行(全环境矩阵;§8.2 后执行地址按身份的环境标签取) */
function depsOf(service: string): Deployment[] {
  return deps.value.filter((d) => d.baseService === service)
}
function aliasExists(alias: string): boolean {
  return faceMeta.value[alias] != null
}
/** 条目 → 装载坐标系统归属(自主档 baseService → system) */
function systemOfBase(base: string | undefined | null): string | null {
  if (!base) return null
  return svcRows.value.find((s) => s.name === base)?.system ?? null
}
/** 换用条目在个人池的装载判定(与后端 pick_bindings 的 ref 语义同构):
 *  条目登记 + 主档有系统 + (system, env, ref) 池内命中。 */
function entryLoaded(slot: string): boolean {
  const ident = faceMeta.value[slot]
  if (!ident || ident.envId == null) return false
  const sys = systemOfBase(ident.baseService)
  if (!sys) return false
  return authRows.value.some((a) =>
    a.system === sys && a.envId === ident.envId
    && (ident.refMode === 'username'
      ? a.username === ident.refUsername
      : a.isDefault === true))
}
/** 装载坐标展示:系统 × 环境 · ref(建账户的落点) */
function coordOf(slot: string): string {
  const ident = faceMeta.value[slot]
  if (!ident || ident.envId == null) return '—'
  const sys = systemOfBase(ident.baseService)
  const ref = ident.refMode === 'username'
    ? `ref ${ident.refUsername ?? '?'}` : 'ref 默认'
  return `${sys ?? '?'} × ${envName(ident.envId)} · ${ref}`
}
function driftOf(service: string): ExecConfigDriftService | undefined {
  return drift.value?.services.find((s) => s.service === service)
}
/** 缺账户 → /auths 预填直达(§8 预填直达;坐标 = 条目装载的
 *  (system, envId),注册表缺席时回落子配置系统名) */
function authHref(slot: string, fallbackService: string): string {
  const ident = faceMeta.value[slot]
  const system = systemOfBase(ident?.baseService) ?? fallbackService
  const q = new URLSearchParams()
  if (system) q.set('system', system)
  if (ident?.envId != null) q.set('envId', String(ident.envId))
  return `/auths?${q.toString()}`
}

async function loadHub(c: ExecConfigRow): Promise<void> {
  const jobs: Promise<void>[] = [
    execConfigDrift(c.id)
      .then((d) => { drift.value = d })
      .catch(() => { drift.value = null }),
    // 绑定别名的注册表状态(定向检索,永不全量)
    loadFacesFor(c),
    // 部署矩阵全量(listDeployments 固定拉全环境;§8.2 配置去 env 后
    // 地址就绪度按矩阵展示,不再按配置环境过滤)
    listDeployments()
      .then((d) => { deps.value = d })
      .catch(() => { deps.value = [] }),
  ]
  await Promise.all(jobs)
}

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  return String((e as Error)?.message ?? e)
}

function fillForm(c: ExecConfigRow): void {
  form.value = { name: c.name }
  sysRows.value = (c.systems ?? []).map((s) => ({
    service: s.service,
    binds: Object.entries(s.bindings ?? {}).map(([alias, slot]) => ({ alias, slot })),
    carries: Object.entries(s.carryOverrides ?? {})
      .map(([field, value]) => ({ field, value: value ?? '' })),
  }))
}

function pick(id: number): void {
  selectedId.value = id
  mode.value = 'edit'
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
  const c = rows.value.find((r) => r.id === id)
  if (c) {
    fillForm(c)
    void loadHub(c)
  }
}

function openCreate(): void {
  mode.value = 'create'
  selectedId.value = null
  form.value = { name: '' }
  sysRows.value = []
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
}

function cancel(): void {
  if (mode.value === 'create') {
    // 无选区则回到空列表态;有选区回到该配置编辑态
    if (selectedId.value) pick(selectedId.value)
    else mode.value = 'edit'
  } else if (selected.value) fillForm(selected.value)
}

function payloadOf(): SystemSubConfig[] {
  return sysRows.value
    .map((s) => ({ s, service: s.service.trim() }))
    .filter(({ service }) => service)
    .map(({ s, service }) => ({
      service,
      bindings: Object.fromEntries(
        s.binds
          .map((b) => ({ alias: b.alias.trim(), slot: b.slot.trim() }))
          .filter((b) => b.alias && b.slot)
          .map((b) => [b.alias, b.slot]),
      ),
      carryOverrides: Object.fromEntries(
        s.carries
          .map((c) => ({ field: c.field.trim(), value: c.value }))
          .filter((c) => c.field)
          .map((c) => [c.field, c.value]),
      ),
    }))
}

async function reload(): Promise<void> {
  rows.value = await listExecConfigs()
}

async function save(): Promise<void> {
  error.value = ''
  const name = form.value.name.trim()
  if (!name) { error.value = '配置名不能为空'; return }
  const services = sysRows.value.map((s) => s.service.trim()).filter(Boolean)
  if (new Set(services).size !== services.length) {
    error.value = '子配置里系统名重复'
    return
  }
  const body = {
    name,
    systems: payloadOf(),
  }
  try {
    if (mode.value === 'create') {
      const created = await createExecConfig(body)
      await reload()
      pick(created.id)
    } else if (selectedId.value != null) {
      await updateExecConfig(selectedId.value, body)
      await reload()
      pick(selectedId.value)
    }
  } catch (e) { error.value = msg(e) }
}

async function makeDefault(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  try {
    await setDefaultExecConfig(selectedId.value)
    await reload()
    pick(selectedId.value)
  } catch (e) { error.value = msg(e) }
}

async function doCopy(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  const name = copyName.value.trim()
  if (!name) { error.value = '新配置名不能为空'; return }
  try {
    const dup = await copyExecConfig(selectedId.value, name)
    copyArmed.value = false
    copyName.value = ''
    await reload()
    pick(dup.id)
  } catch (e) { error.value = msg(e) }
}

async function del(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  try {
    await deleteExecConfig(selectedId.value)
    delArmed.value = false
    await reload()
    const first = rows.value[0]
    if (first) pick(first.id)
    else { selectedId.value = null; mode.value = 'edit' }
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  try {
    const [cfgs, envRows] = await Promise.all([
      listExecConfigs(), listEnvironments(),
    ])
    rows.value = cfgs
    envs.value = envRows
    if (cfgs.length) pick(cfgs[0].id)
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
  // ③ 枢纽旁路数据(一次性;失败静默降级 —— 深链区退化为无提示)
  listServiceMeta()
    .then((rows) => {
      const m: Record<string, string> = {}
      for (const r of rows) m[r.serviceName] = r.description
      svcMetas.value = m
    })
    .catch(() => { /* 说明拉不到 — 面板显「—」 */ })
  listAllAuths().then((r) => { authRows.value = r as never }).catch(() => {})
  // 主档(装载坐标 system 归属;拉不到 → 坐标列显 ?,装载判定从严)
  listServices()
    .then((out) => { svcRows.value = out.services })
    .catch(() => { svcRows.value = [] })
  listScenarioOptions({ page_size: 50, scope: 'mine' })
    .then((envelope) => {
      scenOptions.value = envelope.items.map((i) => ({
        id: i.scenarioId, name: i.name || i.scenarioId }))
    }).catch(() => {})
})
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr);
  gap: 0.5rem 0.625rem;
  align-items: center;
  max-width: 45rem;
  margin-bottom: 0.75rem;
}
.form-grid .lb { font-size: 0.71875rem; color: var(--sl-ink-3); }

.sys {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  background: var(--sl-canvas);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
}
.sys + .sys { margin-top: 0.625rem; }
.sys-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid var(--sl-divider);
}
.sys-title { font-size: 0.71875rem; font-weight: 700; color: var(--sl-ink-2); }

.line-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 51.25rem;
}
.line-row .lb { flex: none; min-width: 2.25rem; font-size: 0.71875rem; color: var(--sl-ink-3); }

.hub { display: flex; flex-direction: column; }
.hub-note {
  margin: 0 0 0.5rem;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
}
.carry-sys + .carry-sys { margin-top: 0.625rem; }
.carry-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.375rem;
  font-size: 0.75rem;
}
</style>
