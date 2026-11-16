<!-- Auths.vue — 账户池管理页(registry 重构 P1-8:凭证=账户实体)。
     心智模型:账户 = 登录信息实体,(system, env, username) 唯一,密码
     只存一份 —— 改密一处、所有装载它的身份条目/场景同时生效。alias/
     url/slot 已退役:登录地址在环境×系统实例(只读回显),装载关系在
     身份条目(ref 引用账户,反查可数)。浏览组织 = 按 system 分组、
     组内账户平铺(默认在前 → username);组级状态由分组头 3px 左缘
     色带承载:红=有测败、琥珀=有 (system,env) 无默认、绿=健康;问题组
     排前,「只看问题」一键滤出。取数单一链路(200 封顶),搜索(q 打
     username/system)/类型过滤下推服务端。创建/编辑(渐进披露)/删除
     (username 硬确认 + 引用预取内联警示)/测试弹框(共享
     CredentialTestDialog)/反查侧板(身份条目 + 场景引用)原样。 -->
<template>
  <section class="slib">
    <PageHead
      icon="lock"
      title="凭证管理"
      :count="rowsTotal ? `${sysCount} 系统 · ${bindCount} 个账户` : undefined"
      :meta="metaText"
    />

    <div class="slib-toolbar">
      <input
        v-model="searchQuery"
        class="slib-search"
        placeholder="搜索 username / system"
        data-testid="auth-search"
      />
      <span class="svc-stats tight" data-testid="tt-filter-group">
        <button
          v-for="t in TT_FILTERS"
          :key="t"
          type="button"
          class="svc-chip"
          :class="{ on: tokenTypeFilter === t }"
          :data-testid="`tt-filter-${t}`"
          @click="tokenTypeFilter = t"
        >{{ t === 'all' ? '全部类型' : t }}</button>
      </span>
      <!-- 客户端过滤:系统取值来自已加载数据,环境选项与表单共用 -->
      <Select v-model="systemFilter">
        <SelectTrigger class="tb-select" data-testid="sys-filter"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部系统</SelectItem>
          <SelectItem v-for="s in systemOptions" :key="s" :value="s">{{ s }}</SelectItem>
        </SelectContent>
      </Select>
      <Select v-model="envFilter">
        <SelectTrigger class="tb-select" data-testid="env-filter"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部环境</SelectItem>
          <SelectItem v-for="e in envs" :key="e.id" :value="String(e.id)">{{ e.name }}</SelectItem>
        </SelectContent>
      </Select>
      <!-- 状态优先:只看有问题的账户(无默认 · 上次测试失败) -->
      <button
        type="button" class="svc-chip" :class="{ on: problemOnly }"
        data-testid="problem-filter" @click="problemOnly = !problemOnly"
      >只看问题</button>
      <button type="button" class="slib-create" data-testid="open-create" @click="openCreate()">+ 新增账户</button>
    </div>

    <!-- 按 system 分组的账户表格:账户行 = 管理主体(组内平铺,无容器层)。
         (system, env) 无默认是取用隐患(default 型条目取不到行),聚合到
         组头徽章计数 -->
    <div v-if="sysGroups.length" class="lib-card auth-table" data-testid="auth-board">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:11rem">username</th>
            <th style="width:9.25rem">状态</th>
            <th style="width:6.75rem">类型</th>
            <th>环境 / 登录地址</th>
            <th style="width:10rem">引用</th>
            <th style="width:7.5rem" />
          </tr>
        </thead>
        <tbody>
          <template v-for="g in sysGroups" :key="g.key">
            <!-- 系统组头:系统名 + 组级健康聚合(测败/(system,env) 无默认
                 都是取用隐患,聚合到组头一眼看穿;3px 左缘色带承载组级状态) -->
            <tr class="grp" :class="`tone-${g.tone}`" :data-testid="`sys-card-${g.key}`">
              <td colspan="6">
                <div class="grp-in">
                  <span class="grp-sys"><b class="mono">{{ g.system }}</b></span>
                  <span class="muted grp-n">{{ g.binds.length }} 个账户</span>
                  <span v-if="g.noDefaultPairs" class="svc-chip warn grp-chip" title="default 型身份条目在该 (系统,环境) 取不到默认账户">{{ g.noDefaultPairs }} 组无默认</span>
                  <span
                    v-if="g.failCount" class="svc-flag red"
                    :data-testid="`sys-fail-${g.key}`"
                    title="本机记录:该系统存在上次测试失败的账户"
                  >✕{{ g.failCount }} 测败</span>
                  <span class="flex-1" />
                  <button
                    type="button" class="grp-add" :data-testid="`sys-add-${g.key}`"
                    @click="openCreate(g.system)"
                  >+ 登记</button>
                </div>
              </td>
            </tr>

            <template v-for="row in g.visible" :key="row.id">
              <tr class="auth-row" :data-testid="`auth-row-${row.id}`">
                <td>
                  <div class="cell-alias">
                    <span class="mono alias-name">{{ row.username }}</span>
                    <span
                      v-if="row.isDefault" class="svc-chip is-default"
                      :data-testid="`default-chip-${row.id}`"
                      title="default 型身份条目在该 (系统,环境) 的取用行">默认</span>
                  </div>
                </td>
                <td>
                  <div class="cell-status">
                    <span
                      v-if="testMemory[row.id]" class="svc-flag mem-flag"
                      :class="testMemory[row.id].ok ? 'green' : 'red'"
                      :data-testid="`test-mem-${row.id}`"
                      :title="`上次测试:${testMemory[row.id].ok ? '成功' : '失败'} · ${shortDateTime(new Date(testMemory[row.id].at))}(本机记录)`"
                    >{{ testMemory[row.id].ok ? '✓ 测通' : '✗ 测败' }} {{ shortDateTime(new Date(testMemory[row.id].at)) }}</span>
                    <span v-else class="muted">—</span>
                    <!-- 独占 (system,env) 组(全池仅此一账户)→ 无默认时行内直示 -->
                    <span
                      v-if="!row.isDefault && soloPairs.has(pairKey(row))"
                      class="svc-chip warn grp-chip"
                      title="该 (系统,环境) 没有默认账户 — default 型身份条目取不到行">无默认</span>
                  </div>
                </td>
                <td>
                  <div class="cell-tt">
                    <span class="svc-flag" :class="ttClass[row.token_type] ?? 'ink'">{{ row.token_type }}</span>
                    <span class="muted tt-exp">{{ formatExpires(row.expires_in) }}</span>
                  </div>
                </td>
                <td>
                  <div class="tgt-env">{{ envName(row.envId) }}</div>
                  <div
                    class="mono muted tgt-url" :title="row.loginUrl || '实例未配置登录地址(环境×系统实例页维护)'"
                  >{{ row.loginUrl || '— 实例未配置' }}</div>
                </td>
                <td>
                  <div class="cell-refs">
                    <!-- 引用方向:身份条目按 ref 装载本账户;场景经条目取到 -->
                    <button
                      v-if="row.identityRefCount" type="button" class="svc-chip"
                      :data-testid="`refs-open-${row.id}`"
                      :title="`${row.identityRefCount} 个身份条目 ref 本账户 — 点击反查`"
                      @click="openRefs(row)"
                    >{{ row.identityRefCount }} 条目</button>
                    <button
                      v-if="row.scenarioRefCount" type="button" class="svc-chip"
                      :data-testid="`refs-open-scenario-${row.id}`"
                      :title="`${row.scenarioRefCount} 个场景引用装载本账户的条目,点击反查`"
                      @click="openRefs(row)"
                    >{{ row.scenarioRefCount }} 场景</button>
                    <span
                      v-if="!row.identityRefCount && !row.scenarioRefCount" class="muted unref"
                      title="身份条目与场景引用均为零(快照类不计)— 删除不触发 409 拦截"
                    >未被引用 · 可安全删除</span>
                  </div>
                </td>
                <td>
                  <div class="cell-acts">
                    <!-- 高频操作升为一键:测试连通不进菜单(结果回写行内状态) -->
                    <button
                      type="button" class="svc-link"
                      :data-testid="`auth-test-inline-${row.id}`"
                      @click="runTest(row)"
                    >测试</button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        class="more-btn"
                        aria-label="更多操作"
                        :data-testid="`auth-more-${row.id}`"
                      >⋯</DropdownMenuTrigger>
                      <DropdownMenuContent align="end" class="sl-menu">
                        <DropdownMenuItem
                          v-if="!row.isDefault"
                          class="sl-menu-item" data-testid="auth-set-default"
                          @click="makeDefault(row)"
                        >设为默认</DropdownMenuItem>
                        <DropdownMenuItem class="sl-menu-item" data-testid="auth-edit" @click="openEdit(row)">编辑</DropdownMenuItem>
                        <DropdownMenuItem
                          class="sl-menu-item danger"
                          data-testid="auth-del"
                          @click="openDelete(row)"
                        >删除</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </tr>
            </template>

            <tr v-if="g.collapsible" class="grp-more">
              <td colspan="6">
                <button
                  type="button" class="more-link"
                  :data-testid="`sys-more-${g.key}`" @click="toggleSys(g.key)"
                >{{ expandedSys.has(g.key) ? '收起' : `还有 ${g.hiddenCount} 个账户` }}</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-else-if="rowsLoading" class="py-10 text-center text-body text-muted-foreground">加载中…</div>
    <div v-else class="empty-cta" data-testid="auths-empty">
      <p>暂无账户 — 按系统登记登录账号</p>
      <Button variant="outline" size="sm" @click="openCreate()">+ 新增账户</Button>
    </div>

    <!-- ── 创建 / 编辑(定稿表单范式;账户四元组 = 实体键)────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[32.5rem]">
        <DialogHeader>
          <DialogTitle>{{ editingId ? '编辑账户' : '+ 新增账户' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onSubmitForm">
          <div class="grid grid-cols-2 gap-3">
            <FormField v-slot="{ componentField }" name="system">
              <FormItem>
                <FormLabel>系统<span class="required-dot">*</span></FormLabel>
                <FormControl>
                  <Input v-bind="componentField" :disabled="!!editingId"
                    placeholder="例 fin-service(与 Plate 侧一致)" data-testid="f-system" />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
            <FormField v-slot="{ componentField }" name="envId">
              <FormItem>
                <FormLabel>环境<span class="required-dot">*</span></FormLabel>
                <FormControl>
                  <!-- 原生 select(P1-8):jsdom 可测 + 键盘可达;Phase 2 页面
                       重做时统一 ui/Select -->
                  <select v-bind="componentField" class="native-select" data-testid="f-env">
                    <option value="" disabled>选择环境</option>
                    <option v-for="e in envs" :key="e.id" :value="String(e.id)">
                      {{ e.name }}
                    </option>
                  </select>
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>

          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>username<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingId"
                  placeholder="登录用户名(同系统内唯一,创建后不可改)" data-testid="f-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>password<span v-if="!editingId" class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="password"
                  :placeholder="editingId ? '留空表示不修改(改密一处,所有装载它的条目/场景同时生效)' : '登录密码'" data-testid="f-password" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <!-- 渐进披露:90% 场景是 system+env+账号密码;账号字段/token
               类型/有效期收进「高级」折叠区(默认收起;深链预填或编辑态
               有非缺省值时自动展开;v-show 保持字段常驻,vee-validate
               不感知)。system/env/username 是实体键,编辑态锁定 -->
          <button
            type="button" class="adv-toggle" data-testid="f-advanced-toggle"
            @click="advancedOpen = !advancedOpen"
          >{{ advancedOpen ? '▾' : '▸' }} 高级(账号字段 / token 类型 / 有效期)</button>

          <div v-show="advancedOpen" class="flex flex-col gap-3" data-testid="f-advanced-body">
            <!-- FormField 外置 KV 行(vee-validate 不管控,提交时聚合) -->
            <div class="flex flex-col gap-1.5">
              <label class="text-label font-medium text-signal-ink">账号字段(供 ${slot.X.field} 注入,如 orgNo)</label>
              <div class="flex flex-col gap-2">
                <div v-for="(af, i) in accountFields" :key="i" class="flex items-center gap-2">
                  <Input v-model="af.key" placeholder="字段名,例 orgNo" class="flex-1"
                    :data-testid="`f-af-key-${i}`" />
                  <Input v-model="af.value" placeholder="值" class="flex-1"
                    :data-testid="`f-af-value-${i}`" />
                  <Button type="button" variant="ghost" size="sm" :data-testid="`f-af-del-${i}`"
                    @click="accountFields.splice(i, 1)">✕</Button>
                </div>
                <Button type="button" variant="outline" size="sm" data-testid="f-af-add"
                  @click="accountFields.push({ key: '', value: '' })">+ 加字段</Button>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <FormField v-slot="{ componentField }" name="token_type">
                <FormItem>
                  <FormLabel>token_type</FormLabel>
                  <FormControl>
                    <Select v-bind="componentField">
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Bearer">Bearer</SelectItem>
                        <SelectItem value="Basic">Basic</SelectItem>
                        <SelectItem value="Cookie">Cookie</SelectItem>
                        <SelectItem value="Authorization">Authorization（整段头）</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
              <FormField v-slot="{ componentField }" name="expires_in">
                <FormItem>
                  <FormLabel>expires_in（秒）</FormLabel>
                  <FormControl>
                    <Input v-bind="componentField" type="number" :min="0" :max="86400" class="w-[8.75rem]" data-testid="f-expires" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
            </div>
          </div>

          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="submit" :disabled="submitting">{{ editingId ? '保存' : '创建' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 测试结果弹框(共享件:个人池/项目凭证面板同一交互)────── -->
    <CredentialTestDialog
      :open="testOpen"
      :target="testTarget && { name: `${testTarget.system} / ${testTarget.username}`,
                               target: testTarget.loginUrl || '实例未配置登录地址' }"
      :phase="testPhase"
      :result="testResult"
      @update:open="testOpen = $event"
      @retest="testTarget && runTest(testTarget)"
    />

    <!-- ── 删除确认(输入 username 硬确认 + 引用预取内联警示)───── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[26.25rem]">
        <DialogHeader>
          <DialogTitle>删除账户</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。<code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.system }} / {{ deleteTarget.username }}</code>
            将从账户池中移除(ref 它的身份条目将取不到凭据,历史执行记录不受影响)。
          </p>
          <!-- 与反查侧板同源的数据:把 409 拦截预告内联进确认框 -->
          <div v-if="deleteBlocking.length" class="drawer-warn" data-testid="del-block-warn">
            <p class="m-0 font-semibold">删除会被拦截:仍有 {{ deleteBlocking.length }} 个本人场景引用(模板)</p>
            <p class="m-0 mt-0.5">先解除身份条目的 ref,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
          </div>
          <p class="m-0 text-body">要继续请输入 <code class="font-mono">{{ deleteTarget.username }}</code> 确认：</p>
          <Input v-model="deleteConfirmInput" :placeholder="`输入 ${deleteTarget.username} 以确认`" data-testid="del-confirm" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">取消</Button>
          <Button variant="destructive" :disabled="!deleteConfirmed || deleteSubmitting" data-testid="del-submit" @click="submitDelete">
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <!-- ── 被引用反查侧板(重构 §1.2/§1.3:条目 ref + 场景)─────────
         原型 H-auths-v2 = 右侧滑入面板:用 Sheet(side=right)。 -->
    <Sheet :open="refsOpen" @update:open="refsOpen = $event">
      <SheetContent
        side="right"
        class="flex w-[28.75rem] max-w-[92vw] flex-col gap-0 p-0 sm:max-w-[28.75rem]"
        data-testid="refs-sheet"
      >
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle class="text-left">被引用 · {{ refsTarget?.username }}</SheetTitle>
          <SheetDescription class="text-left">
            身份条目按 ref 装载本账户;场景经条目取到凭据(§1.4)
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto px-4 py-3 text-caption">
          <p v-if="refsLoading" class="m-0 py-4 text-center text-muted-foreground">扫描引用中…</p>
          <template v-else-if="refsData">
            <h4 class="m-0 mb-1.5 text-label font-semibold text-signal-ink">
              身份条目({{ refsData.identityRefs.length }})
            </h4>
            <div v-for="a in refsData.identityRefs" :key="a.aliasName" class="ref-row">
              <router-link
                :to="`/service-admin/${encodeURIComponent(a.aliasName)}?tab=credential`"
                class="mono link"
              >{{ a.aliasName }}</router-link>
              <span class="ref-dim">→ {{ a.baseService }} · {{ envName(a.envId) }} · {{ refModeText(a) }}</span>
            </div>
            <p v-if="!refsData.identityRefs.length" class="ref-dim m-0">无身份条目装载</p>

            <h4 class="m-0 mb-1.5 mt-4 text-label font-semibold text-signal-ink">
              场景引用(可见 {{ refsData.scenarioRefs.visible.length }})
            </h4>
            <div v-for="v in refsData.scenarioRefs.visible" :key="v.scenarioId" class="ref-row">
              <router-link :to="`/scenarios/${v.scenarioId}/detail`" class="link">
                {{ v.name }}
              </router-link>
              <span
                v-for="k in v.kinds"
                :key="k"
                class="svc-flag"
                :class="KIND_TONE[k] ?? 'ink'"
                :title="kindTitle(k)"
              >{{ kindLabel(k) }}</span>
            </div>
            <p v-if="!refsData.scenarioRefs.visible.length" class="ref-dim m-0">无可见场景引用</p>
            <p
              v-if="refsData.scenarioRefs.hidden_count"
              class="ref-dim m-0 mt-1"
              data-testid="refs-hidden-count"
            >另有 {{ refsData.scenarioRefs.hidden_count }} 条不可见(他人私有场景,仅计数不显名)</p>

            <!-- 原型 H-auths-v2 抽屉底部淡红预警:与 DELETE 409 同口径
                 (本人场景的模板引用才拦截)提前告知,避免撞 409 -->
            <div v-if="drawerBlocking.length" class="drawer-warn" data-testid="refs-block-warn">
              <p class="m-0 font-semibold">删除会被拦截:仍有 {{ drawerBlocking.length }} 个本人场景引用(模板)</p>
              <p class="m-0 mt-0.5">先解除身份条目的 ref,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
            </div>
          </template>
        </div>
      </SheetContent>
    </Sheet>
  </section>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed, onMounted, ref, watch } from 'vue'
import { toTypedSchema } from '@/utils/zod-typed-schema'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import {
  getReferences, list as apiList, setDefault as apiSetDefault,
  type AuthReferences, type AuthSession, type IdentityRefItem, type TestResult,
} from '@/api/auth_sessions'
import { listEnvironments } from '@/api/environments'
import { shortDateTime } from '@/utils/datetime'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import CredentialTestDialog from '@/components/credential/CredentialTestDialog.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const store = useAuthSessionsStore()

/** 引用类型 → 徽标配色档:模板引用绿、快照(不拦截)灰。 */
const KIND_TONE: Record<string, string> = {
  template: 'green',
  snapshot: 'ink',
}
/** token_type → 徽标配色档(与 .svc-flag 同族) */
const ttClass: Record<string, string> = {
  Bearer: 'blue',
  Basic: 'amber',
  Cookie: 'green',
  Authorization: 'red',
}

// ── filters(M4:检索/类型过滤下推服务端,Page 信封)───────────────
// useServerList 观察 params 签名:q/类型任一变化 → 300ms 防抖重拉 + 回页 1。
// q 打 username/system(账户实体键,账户池可检索面)。
const route = useRoute()
// W3:凭证角标跳转带 ?q= 定位缺失项(无路由环境守卫)
const searchQuery = ref(
  typeof route?.query?.q === 'string' ? route.query.q : '')
const TT_FILTERS = ['all', 'Bearer', 'Basic', 'Cookie', 'Authorization'] as const
type TtFilter = typeof TT_FILTERS[number]
const tokenTypeFilter = ref<TtFilter>('all')

// ── 数据(单一链路:200 封顶取回;搜索/类型过滤下推服务端)────────
const rows = ref<AuthSession[]>([])
const rowsTotal = ref(0)
const rowsLoading = ref(false)
const tokenTypeCounts = ref<Record<string, number>>({})

async function reloadList(): Promise<void> {
  rowsLoading.value = true
  try {
    const env = await apiList({
      q: searchQuery.value.trim() || undefined,
      token_type: tokenTypeFilter.value === 'all' ? undefined : tokenTypeFilter.value,
      page: 1, page_size: 200,
    })
    tokenTypeCounts.value = env.tokenTypeCounts ?? {}
    rows.value = env.items
    rowsTotal.value = env.total
  } finally {
    rowsLoading.value = false
  }
}

let filterDebounce: ReturnType<typeof setTimeout> | undefined
watch([searchQuery, tokenTypeFilter], () => {
  clearTimeout(filterDebounce)
  filterDebounce = setTimeout(() => { void reloadList() }, 300)
})

/** 只看问题:无默认 ∨ 有测败的账户(分组级过滤)。 */
const problemOnly = ref(false)

// ── 客户端过滤(系统/环境;数据已整页在端上,不必下推服务端)──────
const systemFilter = ref('all')
const envFilter = ref('all')
/** 系统选项来自已加载账户行的取值并集 */
const systemOptions = computed(() =>
  [...new Set(rows.value.map((r) => r.system).filter(Boolean))].sort())

/** 搜索/类型走服务端;系统/环境在端上再滤一层(组表的数据面) */
const filteredRows = computed(() => rows.value.filter((r) =>
  (systemFilter.value === 'all' || r.system === systemFilter.value)
  && (envFilter.value === 'all' || String(r.envId) === envFilter.value)))
const bindCount = computed(() => filteredRows.value.length)

// ── 按 system 分组的账户列表(账户是一等公民)────────────────────
const BIND_CAP = 5   // 单系统组账户行折叠阈值(>5 收起为「还有 N 条」)

interface SysGroup {
  key: string            // system
  system: string
  binds: AuthSession[]   // 全量(计数/折叠判定/信号聚合)
  visible: AuthSession[] // 折叠截断后的行
  collapsible: boolean
  hiddenCount: number
  failCount: number
  noDefaultPairs: number // (system, env) 组内无默认账户的组数
  tone: 'bad' | 'warn' | 'ok'
}

const expandedSys = ref<Set<string>>(new Set())
function toggleSys(key: string): void {
  const next = new Set(expandedSys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSys.value = next
}

/** 环境列:环境名(表单同源 envs);未命中回落 #id。 */
function envName(envId: number | null | undefined): string {
  if (envId == null) return '环境未定'
  const hit = envs.value.find((e) => e.id === envId)
  return hit ? hit.name : `环境#${envId}`
}

function pairKey(r: AuthSession): string {
  return `${r.system}::${r.envId}`
}

/** 独占 (system,env) 组(全池仅此一账户)→ 无默认时行内直示该隐患。 */
const soloPairs = computed<Set<string>>(() => {
  const n = new Map<string, number>()
  for (const r of filteredRows.value) {
    const k = pairKey(r)
    n.set(k, (n.get(k) ?? 0) + 1)
  }
  return new Set([...n.entries()].filter(([, c]) => c === 1).map(([k]) => k))
})

/** 组序:问题组(测败 ∨ 无默认组)排前,其余字典序;
 *  组内账户平铺:默认在前 → username。 */
const sysGroups = computed<SysGroup[]>(() => {
  const bySys = new Map<string, AuthSession[]>()
  for (const a of filteredRows.value) {
    const k = a.system || ''
    const arr = bySys.get(k)
    if (arr) arr.push(a)
    else bySys.set(k, [a])
  }
  const groups: SysGroup[] = []
  for (const [system, list] of bySys) {
    const key = system
    const ordered = [...list].sort((x, y) =>
      Number(y.isDefault ?? false) - Number(x.isDefault ?? false)
        || x.username.localeCompare(y.username))
    const open = expandedSys.value.has(key)
    // 组级聚合:(system,env) 是 default 型条目的取用坐标,无默认即取用隐患
    const byPair = new Map<string, AuthSession[]>()
    for (const r of ordered) {
      const k = pairKey(r)
      const arr = byPair.get(k)
      if (arr) arr.push(r)
      else byPair.set(k, [r])
    }
    const noDefaultPairs = [...byPair.values()].filter(
      (b) => !b.some((r) => r.isDefault)).length
    const failCount = ordered.filter((r) => testMemory.value[r.id]?.ok === false).length
    groups.push({
      key, system,
      binds: ordered,
      visible: open ? ordered : ordered.slice(0, BIND_CAP),
      collapsible: ordered.length > BIND_CAP,
      hiddenCount: Math.max(0, ordered.length - BIND_CAP),
      failCount, noDefaultPairs,
      tone: failCount ? 'bad' : noDefaultPairs ? 'warn' : 'ok',
    })
  }
  const weight = (g: SysGroup) =>
    (g.failCount ? 2 : 0) + (g.noDefaultPairs ? 1 : 0)
  const kept = problemOnly.value ? groups.filter((g) => weight(g) > 0) : groups
  return kept.sort((x, y) =>
    weight(y) - weight(x) || x.key.localeCompare(y.key))
})
const sysCount = computed(() => sysGroups.value.length)

const metaText = computed(() => {
  const total = rowsTotal.value
  if (total === 0) return '用户级账户池 · 登录信息一处管理,身份条目按 ref 装载'
  const unref = rows.value.filter(
    (a) => !a.identityRefCount && !a.scenarioRefCount,
  ).length
  const unrefSeg = unref ? ` · ${unref} 个未被任何引用` : ''
  const bearer = tokenTypeCounts.value.Bearer ?? 0
  const wholeHeader = tokenTypeCounts.value.Authorization ?? 0
  return `${total} 个账户${unrefSeg} · ${bearer} Bearer · ${wholeHeader} 整段头`
})

function formatExpires(seconds: number): string {
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`
  return `${seconds}s`
}

// ── create / edit(定稿范式;password 条件必填在 submit 内补判)──
const createOpen = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
/** 渐进披露:高级区(账号字段/token/有效期)默认收起 */
const advancedOpen = ref(false)

const schema = toTypedSchema(z.object({
  // 实体键三件套(编辑态锁定;system 与 Plate 侧系统名一致)
  system: z.string().min(1, '请输入系统名'),
  // 环境选值是字符串 id(必选,无「不限」)
  envId: z.string().min(1, '请选择环境').refine((v) => v !== '', '请选择环境'),
  username: z.string().min(1, '请输入 username'),
  // 编辑态可留空(= 不修改) — 创建态必填由 onSubmitForm 补判
  password: z.string(),
  token_type: z.enum(['Bearer', 'Basic', 'Cookie', 'Authorization']),
  expires_in: z.coerce.number().int('整数秒').min(0).max(86400, '最大 86400'),
}))

const { handleSubmit, resetForm, setFieldError } = useForm({
  validationSchema: schema,
  initialValues: {
    system: '', envId: '',
    username: '', password: '',
    token_type: 'Bearer' as const, expires_in: 7200,
  },
})

// ── 表单辅面:环境选项 + 账号字段 KV 行(vee-validate 外置)──────
const envs = ref<Array<{ id: number; name: string }>>([])
const accountFields = ref<Array<{ key: string; value: string }>>([])

function accountFieldsFromRow(row: AuthSession): Array<{ key: string; value: string }> {
  const src = row.accountFields
  if (!src || typeof src !== 'object') return []
  return Object.entries(src).map(([k, v]) => ({ key: k, value: v == null ? '' : String(v) }))
}

function accountFieldsToObject(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const af of accountFields.value) {
    const k = af.key.trim()
    if (k) out[k] = af.value
  }
  return out
}

/** ``system``/``envId``:执行配置枢纽「缺失深链预填直达」(分层③);
 *  旧 ``?newSlot=`` 深链随槽概念退役,收到 system 预填位。 */
function openCreate(system = '', envId = '') {
  editingId.value = null
  accountFields.value = []
  // 高级区:无实体键预填时保持收起
  advancedOpen.value = false
  resetForm({
    values: {
      system, envId,
      username: '', password: '', token_type: 'Bearer', expires_in: 7200,
    },
  })
  createOpen.value = true
}

/** 置为 (system, env) 默认账户(default 型条目的取用行;后端原子清除旧默认)。 */
async function makeDefault(row: AuthSession) {
  try {
    await apiSetDefault(row.id)
    toast.success(`已将 ${row.username} 设为默认账户`)
    await reloadList()
  } catch (e) {
    showError('设为默认', undefined, (e as Error).message)
  }
}

function openEdit(row: AuthSession) {
  editingId.value = row.id
  accountFields.value = accountFieldsFromRow(row)
  // 编辑态:高级项有非缺省值时自动展开,一眼看到全部存量
  advancedOpen.value = Boolean(
    accountFields.value.length
    || row.token_type !== 'Bearer' || row.expires_in !== 7200)
  resetForm({
    values: {
      system: row.system,
      envId: row.envId != null ? String(row.envId) : '',
      username: row.username,
      password: '',
      // AuthSession.token_type 是宽 string;schema 是枚举 — 数据源即四选一
      token_type: row.token_type as 'Bearer' | 'Basic' | 'Cookie' | 'Authorization',
      expires_in: row.expires_in,
    },
  })
  createOpen.value = true
}

const onSubmitForm = handleSubmit(async (values) => {
  if (submitting.value) return
  // 创建态 password 必填(schema 静态化,条件规则在此单点补判)
  if (!editingId.value && !values.password) {
    setFieldError('password', '请输入 password')
    return
  }
  if (!values.envId) {
    setFieldError('envId', '请选择环境')
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      // 实体键(system/env/username)不可改;能改的只有密码与展示属性
      const patch: Record<string, unknown> = {
        token_type: values.token_type,
        expires_in: values.expires_in,
        accountFields: accountFieldsToObject(),
      }
      if (values.password) patch.password = values.password
      await store.patchAuth(editingId.value, patch)
      toast.success('已保存')
    } else {
      await store.createAuth({
        system: values.system,
        envId: Number(values.envId),
        accountFields: accountFieldsToObject(),
        username: values.username,
        password: values.password,
        token_type: values.token_type,
        expires_in: values.expires_in,
      })
      toast.success(`已创建 ${values.username}`)
    }
    createOpen.value = false
    void reloadList()
  } catch (e) {
    // store 的 mutation 不维护 lastError — 必须用捕获到的错误本身，
    // 否则会显示上一次 fetch 的陈旧错误。
    showError('保存', undefined, (e as Error).message)
  } finally {
    submitting.value = false
  }
})

// ── test ───────────────────────────────────────────────────────
// 状态机:开弹框即 testing(在途不假失败);返回/异常切终态。
const testOpen = ref(false)
const testPhase = ref<'testing' | 'success' | 'fail'>('testing')
const testResult = ref<TestResult | null>(null)
const testTarget = ref<AuthSession | null>(null)

async function runTest(row: AuthSession) {
  testTarget.value = row
  testResult.value = null
  testPhase.value = 'testing'
  testOpen.value = true
  try {
    testResult.value = await store.testConnection(row.id)
    testPhase.value = testResult.value.ok ? 'success' : 'fail'
  } catch (e) {
    testResult.value = {
      ok: false,
      status_code: null,
      message: (e as Error).message || '请求失败',
    }
    testPhase.value = 'fail'
  }
  // 终态回写本机记忆(行内 chip / 组头聚合;仅本浏览器,不落库)
  rememberTest(row.id, testPhase.value === 'success')
}

// ── 测试结果本机记忆(状态优先:列表回答"哪些还能用")─────────────
const TEST_MEM_KEY = 'auths.test-memory:v1'
const testMemory = ref<Record<number, { ok: boolean; at: number }>>({})

function loadTestMemory(): void {
  try {
    const raw = localStorage.getItem(TEST_MEM_KEY)
    if (raw) testMemory.value = JSON.parse(raw) as typeof testMemory.value
  } catch { testMemory.value = {} }
}

function rememberTest(id: number, ok: boolean): void {
  testMemory.value = { ...testMemory.value, [id]: { ok, at: Date.now() } }
  try { localStorage.setItem(TEST_MEM_KEY, JSON.stringify(testMemory.value)) }
  catch { /* 隐私模式等写入失败 — 内存态仍生效 */ }
}

// ── delete ─────────────────────────────────────────────────────
const deleteOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteTarget = ref<AuthSession | null>(null)
const deleteConfirmInput = ref('')
/** 删除框内联的 409 拦截预告(与反查侧板同源同口径) */
const deleteRefs = ref<AuthReferences | null>(null)

const deleteBlocking = computed(() => {
  const me = auth.currentUser?.id
  if (!deleteRefs.value || me == null) return []
  return deleteRefs.value.scenarioRefs.visible.filter(
    (v) => v.ownerId === me && v.kinds.includes('template'),
  )
})

// ── 被引用反查侧板(重构 §1.2/§1.3)──────────────────────────────
const auth = useAuthStore()
const refsOpen = ref(false)
const refsTarget = ref<AuthSession | null>(null)
const refsLoading = ref(false)
const refsData = ref<AuthReferences | null>(null)

/** 删除拦截预告(与后端 DELETE 409 同口径):可见引用里
 *  「本人场景 × template」的条数 — 抽屉底部淡红警示。 */
const drawerBlocking = computed(() => {
  const me = auth.currentUser?.id
  if (!refsData.value || me == null) return []
  return refsData.value.scenarioRefs.visible.filter(
    (v) => v.ownerId === me && v.kinds.includes('template'),
  )
})

function refModeText(a: IdentityRefItem): string {
  return a.refMode === 'username'
    ? `ref ${a.refUsername}`
    : 'ref 默认'
}

function openRefs(row: AuthSession) {
  refsTarget.value = row
  refsData.value = null
  refsOpen.value = true
  void loadRefs()
}

async function loadRefs() {
  if (!refsTarget.value) return
  refsLoading.value = true
  try {
    refsData.value = await getReferences(refsTarget.value.id)
  } catch (e) {
    showError('反查', undefined, (e as Error).message)
    refsData.value = null
  } finally {
    refsLoading.value = false
  }
}

const KIND_LABELS: Record<string, string> = {
  template: '模板', snapshot: '快照',
}
const KIND_TITLES: Record<string, string> = {
  template: 'steps 里的 ${auth.<条目名>.*} 模板 — 下次运行会用到',
  snapshot: 'config.users 的同名快照副本 — 自足,不随账户池轮换',
}

function kindLabel(k: string): string {
  return KIND_LABELS[k] ?? k
}

function kindTitle(k: string): string {
  return KIND_TITLES[k] ?? k
}

const deleteConfirmed = computed(() =>
  Boolean(deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.username),
)

function openDelete(row: AuthSession) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  deleteRefs.value = null
  deleteOpen.value = true
  // 预取反查(打开即查,不另设"检查引用"步骤):失败静默 — 硬确认仍在,
  // 409 拦截兜底语义不变
  getReferences(row.id)
    .then((d) => { deleteRefs.value = d })
    .catch(() => { deleteRefs.value = null })
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  deleteSubmitting.value = true
  try {
    await store.deleteAuth(deleteTarget.value.id)
    toast.success(`已删除 ${deleteTarget.value.username}`)
    deleteOpen.value = false
    void reloadList()
  } catch (e) {
    // 409 = 本人场景的模板引用拦截:错误信息带场景清单 —
    // 保持弹框开着让用户看完再处理
    showError('删除', undefined, (e as Error).message)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── init ───────────────────────────────────────────────────────
onMounted(async () => {
  loadTestMemory()
  // 深链补 system/envId 预填(?system=&envId=);旧 ?newSlot= 槽概念
  // 退役,收到 system 位兼容打开表单
  const q = route?.query ?? {}
  const qSystem = typeof q.system === 'string' ? q.system
    : (typeof q.newSlot === 'string' ? q.newSlot : '')
  const qEnv = typeof q.envId === 'string' ? q.envId : ''
  if (qSystem || qEnv) openCreate(qSystem, qEnv)
  // 环境选项给表单下拉
  listEnvironments()
    .then((rows) => { envs.value = rows.map((e) => ({ id: e.id, name: e.name })) })
    .catch(() => { /* 表单环境下拉退化为空 */ })
  try {
    await reloadList()
  } catch {
    // useServerList 默认 onError 已弹全局提示;这里静默即可。
  }
})
</script>

<style scoped>
/* 高级区折叠开关(渐进披露):贴表单节奏的弱化文字钮 */
.adv-toggle {
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: none;
  font-size: 0.71875rem;
  color: var(--sl-ink-3, #5b6472);
  cursor: pointer;
}
.adv-toggle:hover { color: var(--sl-ink, var(--sl-ink)); }

/* 原生 select(表单环境字段):观感对齐 ui/Input */
.native-select {
  height: 2.25rem;
  width: 100%;
  padding: 0 0.625rem;
  font-size: 0.875rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.native-select:focus { border-color: var(--sl-accent); }

/* ── 按系统分组的账户表格(组级状态 = 分组头 3px 左缘色带)──────── */
.auth-table { --lib-card-max: none; }   /* 分组随页面流,不卡内滚动 */
.tb-select { height: 2.125rem; width: 8.75rem; font-size: 0.78125rem; flex: none; }

.grp > td {
  padding: 0.375rem 0.75rem;
  background: var(--sl-th-bg);
  border-left: 3px solid var(--sl-divider);
}
.grp.tone-ok > td { border-left-color: var(--sl-ok); }
.grp.tone-warn > td { border-left-color: var(--sl-warn); }
.grp.tone-bad > td { border-left-color: var(--sl-bad); }
.grp-in {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.375rem;
  min-width: 0;
}
.grp-sys { font-size: 0.78125rem; color: var(--sl-ink); white-space: nowrap; }
.grp-sys b { font-size: 0.8125rem; }
.grp-n { font-size: 0.6875rem; }
.grp-chip { height: auto; min-height: 1.1875rem; padding: 0 0.5rem; }
.grp-add {
  padding: 0;
  border: 0;
  background: none;
  font-size: 0.71875rem;
  color: var(--sl-accent);
  cursor: pointer;
  white-space: nowrap;
}
.grp-add:hover { text-decoration: underline; }

.auth-row:hover td { background: var(--sl-row-hover); }
.cell-alias { display: flex; align-items: center; gap: 0.375rem; min-width: 0; flex-wrap: wrap; }
.alias-name {
  font-size: 0.78125rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.is-default { height: auto; min-height: 1.1875rem; padding: 0 0.5rem; font-size: 0.6875rem; flex: none; }
.cell-status { display: flex; flex-direction: column; gap: 0.1875rem; align-items: flex-start; }
.mem-flag { font-size: 0.6875rem; white-space: nowrap; }
.cell-tt { display: flex; flex-direction: column; gap: 0.125rem; align-items: flex-start; }
.tt-exp { font-size: 0.6875rem; }
.tgt-env { font-size: 0.71875rem; color: var(--sl-ink-2); white-space: nowrap; }
.tgt-url {
  font-size: 0.6875rem;
  max-width: 20rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-refs { display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }
.unref { font-size: 0.6875rem; }
.cell-acts { display: flex; align-items: center; justify-content: flex-end; gap: 0.375rem; }
.grp-more > td { padding: 0.25rem 0.75rem; }
.more-link {
  padding: 0;
  border: 0;
  background: none;
  font-size: 0.71875rem;
  color: var(--sl-accent);
  cursor: pointer;
}
.more-link:hover { text-decoration: underline; }

/* ── 反查侧板 ─────────────────────────────────────────────── */
.drawer-warn {
  margin-top: 0.875rem;
  padding: 0.5rem 0.625rem;
  font-size: 0.71875rem;
  line-height: 1.6;
  color: var(--sl-bad);
  background: var(--sl-bad-soft);
  border: 1px solid var(--sv-bad-line);
  border-radius: 0.5rem;
}

.ref-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.1875rem 0;
  flex-wrap: wrap;
}

.ref-dim { font-size: 0.6875rem; color: var(--sl-ink-3); }

.link { color: var(--sl-accent); }
.link:hover { text-decoration: underline; }

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}
</style>
