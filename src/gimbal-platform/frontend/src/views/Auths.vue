<!-- Auths.vue — 凭证池管理页(2026-11-16 三轮:凭证一等公民)。
     心智模型:先有凭证,槽位是「引用凭证的键」— 关系方向 = 凭证 →
     挂载槽(数据模型里 slot 是凭证的单值字段,一条凭证只挂一个槽),
     引用它的服务别名/场景模板在行内「引用」列可数、可反查。槽不作为
     容器/分组层出现,只在两处作为属性露出:① 显式命名槽(slot≠alias)
     的行内小字(未声明时琥珀) ② 无默认/未声明/测败等槽级取用隐患,
     聚合为系统组头的徽章计数(独占槽的无默认直示行内)。浏览组织 =
     按系统分组、组内凭证平铺(同槽相邻,默认在前 → 环境 → alias)、
     环境名列示。组级状态由分组头 3px 左缘色带承载:红=有测败、琥珀=
     无默认∨未声明、绿=健康;问题组排前,「只看问题」一键滤出。取数
     单一链路(200 封顶),搜索/类型过滤照旧下推服务端;系统/环境为
     客户端过滤。创建/编辑(渐进披露)/删除(alias 硬确认 + 引用预取
     内联警示)/测试弹框(共享 CredentialTestDialog)/反查侧板原样。 -->
<template>
  <section class="slib">
    <PageHead
      icon="lock"
      title="凭证管理"
      :count="rowsTotal ? `${sysCount} 系统 · ${bindCount} 条凭证` : undefined"
      :meta="metaText"
    />

    <div class="slib-toolbar">
      <input
        v-model="searchQuery"
        class="slib-search"
        placeholder="搜索 alias / url"
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
      <!-- 状态优先:只看有问题的槽(无默认 · 上次测试失败) -->
      <button
        type="button" class="svc-chip" :class="{ on: problemOnly }"
        data-testid="problem-filter" @click="problemOnly = !problemOnly"
      >只看问题</button>
      <button type="button" class="slib-create" data-testid="open-create" @click="openCreate()">+ 新增认证</button>
    </div>

    <!-- 按系统分组的凭证表格:凭证行 = 管理主体(组内平铺,无容器层),
         行内按环境列示。槽是凭证的属性(挂载键),不是分组容器 —
         槽级取用隐患(无默认/未声明/测败)聚合为组头徽章计数 -->
    <div v-if="sysGroups.length" class="lib-card auth-table" data-testid="auth-board">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:10.75rem">alias</th>
            <th style="width:9.25rem">状态</th>
            <th style="width:6.75rem">类型</th>
            <th>环境 / 登录地址</th>
            <th style="width:7.25rem">账号</th>
            <th style="width:10rem">引用</th>
            <th style="width:7.5rem" />
          </tr>
        </thead>
        <tbody>
          <template v-for="g in sysGroups" :key="g.key">
            <!-- 系统组头:系统名 + 组级健康聚合(测败/无默认/未声明都是槽级
                 取用隐患,聚合到组头一眼看穿;3px 左缘色带承载组级状态) -->
            <tr class="grp" :class="`tone-${g.tone}`" :data-testid="`sys-card-${g.key}`">
              <td colspan="7">
                <div class="grp-in">
                  <span class="grp-sys"><b class="mono">{{ g.system || '未归类' }}</b></span>
                  <span class="muted grp-n">{{ g.binds.length }} 条凭证</span>
                  <span v-if="g.noDefaultSlots" class="svc-chip warn grp-chip" title="名字解析与环境未命中时无默认凭证可取">{{ g.noDefaultSlots }} 条无默认</span>
                  <span
                    v-if="g.failCount" class="svc-flag red"
                    :data-testid="`sys-fail-${g.key}`"
                    title="本机记录:该系统存在上次测试失败的凭证"
                  >✕{{ g.failCount }} 测败</span>
                  <span
                    v-if="g.undeclaredSlots" class="svc-flag amber"
                    :data-testid="`sys-undeclared-${g.key}`"
                    title="这些槽在服务注册的身份面无声明 — 经别名注入不会取用;仅场景 ${slot.X} 直接引用可达"
                  >✕{{ g.undeclaredSlots }} 未声明</span>
                  <span class="flex-1" />
                  <button
                    type="button" class="grp-add" :data-testid="`sys-add-${g.key}`"
                    @click="openCreate('', g.system)"
                  >+ 登记</button>
                </div>
              </td>
            </tr>

            <template v-for="row in g.visible" :key="row.id">
              <tr class="auth-row" :data-testid="`auth-row-${row.id}`">
                <td>
                  <div class="cell-alias">
                    <span class="mono alias-name">{{ row.alias }}</span>
                    <span
                      v-if="row.isDefault" class="svc-chip is-default"
                      :data-testid="`default-chip-${row.id}`"
                      title="名字解析与环境未命中时的取用行">默认</span>
                  </div>
                  <!-- 槽属性露出:此凭证挂载的槽(场景经 ${slot.X} 取用的键) -->
                  <div
                    v-if="row.slot && row.slot !== row.alias" class="slot-sub"
                    :class="{ 'slot-undeclared': slotsReady && !declaredSlots.has(row.slot) }"
                    :title="slotsReady && !declaredSlots.has(row.slot)
                      ? '槽未被服务注册声明 — 经别名注入不会取用' : `此凭证挂载到槽 ${row.slot} — 场景经 \${slot.${row.slot}} 取用`"
                  >槽 {{ row.slot }}</div>
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
                    <!-- 未设默认的取用键 = 隐患,行内直示(多键组由组头计数) -->
                    <span
                      v-if="!row.isDefault && soloSlots.has(row.slot || row.alias)"
                      class="svc-chip warn grp-chip"
                      title="此槽没有默认绑定行 — 名字解析与环境未命中时无凭证可取">无默认</span>
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
                  <div class="mono muted tgt-url" :title="row.url">{{ row.url || '静态令牌' }}</div>
                </td>
                <td><span class="mono muted">{{ row.username }}</span></td>
                <td>
                  <div class="cell-refs">
                    <!-- 引用方向:别名绑定/场景模板引用的是槽,经槽取到此凭证 -->
                    <button
                      v-if="row.alias_ref_count" type="button" class="svc-chip"
                      :data-testid="`refs-open-${row.alias}`"
                      :title="`${row.alias_ref_count} 个服务别名绑定槽 ${row.slot || row.alias} — 经别名注入取到此凭证,点击反查`"
                      @click="openRefs(row)"
                    >{{ row.alias_ref_count }} 别名</button>
                    <button
                      v-if="row.scenario_ref_count" type="button" class="svc-chip"
                      :data-testid="`refs-open-scenario-${row.alias}`"
                      :title="`${row.scenario_ref_count} 个场景经 \${slot.*} 模板引用,点击反查`"
                      @click="openRefs(row)"
                    >{{ row.scenario_ref_count }} 场景</button>
                    <span
                      v-if="!row.alias_ref_count && !row.scenario_ref_count" class="muted unref"
                      title="别名绑定与场景引用均为零(快照类不计)— 删除不触发 409 拦截"
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
              <td colspan="7">
                <button
                  type="button" class="more-link"
                  :data-testid="`sys-more-${g.key}`" @click="toggleSys(g.key)"
                >{{ expandedSys.has(g.key) ? '收起' : `还有 ${g.hiddenCount} 条凭证` }}</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-else-if="rowsLoading" class="py-10 text-center text-body text-muted-foreground">加载中…</div>
    <div v-else class="empty-cta" data-testid="auths-empty">
      <p>暂无认证 — 复制用例中的 alias 在此登记</p>
      <Button variant="outline" size="sm" @click="openCreate()">+ 新增认证</Button>
    </div>

    <!-- ── 创建 / 编辑(定稿表单范式)──────────────────────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[32.5rem]">
        <DialogHeader>
          <DialogTitle>{{ editingId ? '编辑认证' : '+ 新增认证' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onSubmitForm">
          <FormField v-slot="{ componentField }" name="alias">
            <FormItem>
              <FormLabel>alias<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingId"
                  placeholder="例 qa1 / staging-codfish（同 owner 内唯一）" data-testid="f-alias" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="url">
            <FormItem>
              <FormLabel>登录 URL<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="https://target/auth/login" data-testid="f-url" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>username<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="登录用户名" data-testid="f-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>password<span v-if="!editingId" class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="password"
                  :placeholder="editingId ? '留空表示不修改' : '登录密码'" data-testid="f-password" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <!-- 渐进披露:90% 场景是 alias+账号密码+URL;系统/环境/账号字段/
               token 类型/有效期收进「高级」折叠区(默认收起;深链预填或
               编辑态有非缺省值时自动展开;v-show 保持字段常驻,vee-validate
               不感知)。取用键 = alias 本身(slot 后端缺省 = alias),表单
               不再暴露槽概念 -->
          <button
            type="button" class="adv-toggle" data-testid="f-advanced-toggle"
            @click="advancedOpen = !advancedOpen"
          >{{ advancedOpen ? '▾' : '▸' }} 高级(系统 / 环境 / 账号字段 / token 类型 / 有效期)</button>

          <div v-show="advancedOpen" class="flex flex-col gap-3" data-testid="f-advanced-body">
            <div class="grid grid-cols-2 gap-3">
              <FormField v-slot="{ componentField }" name="system">
                <FormItem>
                  <FormLabel>系统</FormLabel>
                  <FormControl>
                    <Input v-bind="componentField" placeholder="例 fin-service(空=未归类)" data-testid="f-system" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
              <FormField v-slot="{ componentField }" name="envId">
                <FormItem>
                  <FormLabel>环境</FormLabel>
                  <FormControl>
                    <Select v-bind="componentField">
                      <SelectTrigger data-testid="f-env"><SelectValue placeholder="不限" /></SelectTrigger>
                      <SelectContent>
                        <!-- Radix Select 禁空串 value → 'none' 哨兵 = 不限 -->
                        <SelectItem value="none">不限</SelectItem>
                        <SelectItem v-for="e in envs" :key="e.id" :value="String(e.id)">
                          {{ e.name }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              </FormField>
            </div>

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
      :target="testTarget"
      :phase="testPhase"
      :result="testResult"
      @update:open="testOpen = $event"
      @retest="testTarget && runTest(testTarget)"
    />

    <!-- ── 删除确认(输入 alias 硬确认 + 引用预取内联警示)─────── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[26.25rem]">
        <DialogHeader>
          <DialogTitle>删除认证</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。alias <code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.alias }}</code>
            将从凭证池中移除（已使用此 alias 的历史执行记录不受影响）。
          </p>
          <!-- 与反查侧板同源的数据:把 409 拦截预告内联进确认框 -->
          <div v-if="deleteBlocking.length" class="drawer-warn" data-testid="del-block-warn">
            <p class="m-0 font-semibold">删除会被拦截:仍有 {{ deleteBlocking.length }} 个本人场景引用(模板)</p>
            <p class="m-0 mt-0.5">先解除别名绑定,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
          </div>
          <p class="m-0 text-body">要继续请输入 <code class="font-mono">{{ deleteTarget.alias }}</code> 确认：</p>
          <Input v-model="deleteConfirmInput" :placeholder="`输入 ${deleteTarget.alias} 以确认`" data-testid="del-confirm" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">取消</Button>
          <Button variant="destructive" :disabled="!deleteConfirmed || deleteSubmitting" data-testid="del-submit" @click="submitDelete">
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <!-- ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────
         原型 H-auths-v2 = 右侧滑入面板:用 Sheet(side=right)。项目的 vaul
         Drawer 是底部抽屉,先前把 max-w 加在它上面 = 底部居中窄条(位置不对)。 -->
    <Sheet :open="refsOpen" @update:open="refsOpen = $event">
      <SheetContent
        side="right"
        class="flex w-[28.75rem] max-w-[92vw] flex-col gap-0 p-0 sm:max-w-[28.75rem]"
        data-testid="refs-sheet"
      >
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle class="text-left">被引用 · {{ refsTarget?.alias }}</SheetTitle>
          <SheetDescription class="text-left">
            名字引用 — 场景与别名解析按执行者本人凭证池,非本条凭证对象(§1.4)
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto px-4 py-3 text-caption">
          <p v-if="refsLoading" class="m-0 py-4 text-center text-muted-foreground">扫描场景引用中…</p>
          <template v-else-if="refsData">
            <h4 class="m-0 mb-1.5 text-label font-semibold text-signal-ink">
              别名绑定({{ refsData.alias_refs.length }})
            </h4>
            <div v-for="a in refsData.alias_refs" :key="a.alias_name" class="ref-row">
              <router-link
                :to="`/service-admin/${encodeURIComponent(a.alias_name)}?tab=credential`"
                class="mono link"
              >{{ a.alias_name }}</router-link>
              <span class="ref-dim">→ {{ a.base_service }}</span>
            </div>
            <p v-if="!refsData.alias_refs.length" class="ref-dim m-0">无别名绑定</p>

            <h4 class="m-0 mb-1.5 mt-4 text-label font-semibold text-signal-ink">
              场景引用(可见 {{ refsData.scenario_refs.visible.length }})
            </h4>
            <div v-for="v in refsData.scenario_refs.visible" :key="v.scenario_id" class="ref-row">
              <router-link :to="`/scenarios/${v.scenario_id}/detail`" class="link">
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
            <p v-if="!refsData.scenario_refs.visible.length" class="ref-dim m-0">无可见场景引用</p>
            <p
              v-if="refsData.scenario_refs.hidden_count"
              class="ref-dim m-0 mt-1"
              data-testid="refs-hidden-count"
            >另有 {{ refsData.scenario_refs.hidden_count }} 条不可见(他人私有场景,仅计数不显名)</p>

            <!-- 原型 H-auths-v2 抽屉底部淡红预警:与 DELETE 409 同口径
                 (本人场景的模板引用才拦截;M2a S6 后方案绑定不再点名凭证)
                 提前告知,避免撞 409 -->
            <div v-if="drawerBlocking.length" class="drawer-warn" data-testid="refs-block-warn">
              <p class="m-0 font-semibold">删除会被拦截:仍有 {{ drawerBlocking.length }} 个本人场景引用(模板)</p>
              <p class="m-0 mt-0.5">先解除别名绑定,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
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
  type AuthReferences, type AuthSession, type TestResult,
} from '@/api/auth_sessions'
import { listAllAliases } from '@/api/service-aliases'
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

/** 引用类型 → 徽标配色档:模板引用绿、快照(不拦截)灰。
 *  scheme(方案绑定)已随 authz M2a S6 退役 — serviceBindings 选注册表
 *  别名,不再点名凭证,反查不会再报该种类。 */
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
// username 是服务端 Fernet 密文不可检索(q 只打 alias/url,占位文案如实)。
const route = useRoute()
// W3:凭证角标跳转带 ?q=别名 定位缺失项(无路由环境守卫)
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

// ── 槽位主轴直连:该槽在服务注册的身份面注册表里有无声明 ──────────
// 读面全员(listAllAliases);拉不到不亮 chip(静默降级,不阻塞凭证池)
const declaredSlots = ref<Set<string>>(new Set())
const slotsReady = ref(false)

/** 只看问题:无默认 ∨ 有测败的槽(分组级过滤)。 */
const problemOnly = ref(false)

// ── 客户端过滤(系统/环境;数据已整页在端上,不必下推服务端)──────
const systemFilter = ref('all')
const envFilter = ref('all')
/** 系统选项来自已加载绑定行的取值并集(密文字段外的可聚合一列) */
const systemOptions = computed(() =>
  [...new Set(rows.value.map((r) => r.system).filter((s): s is string => Boolean(s)))].sort())

/** 搜索/类型走服务端;系统/环境在端上再滤一层(组表的数据面) */
const filteredRows = computed(() => rows.value.filter((r) =>
  (systemFilter.value === 'all' || r.system === systemFilter.value)
  && (envFilter.value === 'all' || String(r.envId) === envFilter.value)))
const bindCount = computed(() => filteredRows.value.length)

// ── 按系统分组的凭证列表(凭证是一等公民,槽是行属性)──────────────
const BIND_CAP = 5   // 单系统组凭证行折叠阈值(>5 收起为「还有 N 条」)
const UNCLASSIFIED = 'uncategorized'   // system 为空时的组键(展示为「未归类」,排最后)

interface SysGroup {
  key: string            // system || 'uncategorized'
  system: string         // 展示用原始值('' → 未归类)
  binds: AuthSession[]   // 全量(计数/折叠判定/信号聚合)
  visible: AuthSession[] // 折叠截断后的行(平铺,无簇层)
  collapsible: boolean
  hiddenCount: number
  failCount: number
  noDefaultSlots: number
  undeclaredSlots: number
  tone: 'bad' | 'warn' | 'ok'
}

const expandedSys = ref<Set<string>>(new Set())
function toggleSys(key: string): void {
  const next = new Set(expandedSys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSys.value = next
}

/** 环境列:环境名(表单同源 envs);未命中/未填回落 #id / 不限。 */
function envName(envId: number | null | undefined): string {
  if (envId == null) return '环境不限'
  const hit = envs.value.find((e) => e.id === envId)
  return hit ? hit.name : `环境#${envId}`
}

/** 独占槽(全池仅此一条凭证挂载)→ 无默认时行内直示该隐患。 */
const soloSlots = computed<Set<string>>(() => {
  const n = new Map<string, number>()
  for (const r of filteredRows.value) {
    const s = r.slot || r.alias
    n.set(s, (n.get(s) ?? 0) + 1)
  }
  return new Set([...n.entries()].filter(([, c]) => c === 1).map(([s]) => s))
})

/** 组序:问题组(测败 ∨ 无默认槽)排前,「未归类」殿后,其余字典序;
 *  组内凭证平铺:同槽相邻(槽是行属性,不是容器)→ 槽内默认在前 → 环境 → alias。 */
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
    const key = system || UNCLASSIFIED
    const ordered = [...list].sort((x, y) => {
      const sx = x.slot || x.alias
      const sy = y.slot || y.alias
      return sx.localeCompare(sy)
        || Number(y.isDefault) - Number(x.isDefault)
        || (x.envId ?? -1) - (y.envId ?? -1)
        || x.alias.localeCompare(y.alias)
    })
    const open = expandedSys.value.has(key)
    // 组级聚合:槽是取用键,无默认/未声明都是槽级隐患 → 计槽数报组头
    const bySlot = new Map<string, AuthSession[]>()
    for (const r of ordered) {
      const s = r.slot || r.alias
      const arr = bySlot.get(s)
      if (arr) arr.push(r)
      else bySlot.set(s, [r])
    }
    const noDefaultSlots = [...bySlot.values()].filter((b) => !b.some((r) => r.isDefault)).length
    const undeclaredSlots = slotsReady.value
      ? [...bySlot.keys()].filter((s) => !declaredSlots.value.has(s)).length
      : 0
    const failCount = ordered.filter((r) => testMemory.value[r.id]?.ok === false).length
    groups.push({
      key, system,
      binds: ordered,
      visible: open ? ordered : ordered.slice(0, BIND_CAP),
      collapsible: ordered.length > BIND_CAP,
      hiddenCount: Math.max(0, ordered.length - BIND_CAP),
      failCount, noDefaultSlots, undeclaredSlots,
      tone: failCount ? 'bad' : (noDefaultSlots || undeclaredSlots) ? 'warn' : 'ok',
    })
  }
  // 问题口径与旧版一致:测败 ∨ 无默认(「未声明」只染色不计数 —
  // 声明注册表缺席/拉空时不宜把整池都判成问题)
  const weight = (g: SysGroup) =>
    (g.failCount ? 2 : 0) + (g.noDefaultSlots ? 1 : 0)
  const kept = problemOnly.value ? groups.filter((g) => weight(g) > 0) : groups
  return kept.sort((x, y) =>
    weight(y) - weight(x)
    || Number(x.key === UNCLASSIFIED) - Number(y.key === UNCLASSIFIED)
    || x.key.localeCompare(y.key))
})
const sysCount = computed(() => sysGroups.value.length)

const metaText = computed(() => {
  const total = rowsTotal.value
  if (total === 0) return '用户级独立凭证池 · 与 yaml 文件 Config.users 解耦'
  const unref = rows.value.filter(
    (a) => !a.alias_ref_count && !a.scenario_ref_count,
  ).length
  // 原型 H-auths-v2 统计行:「N 条凭证 · …未被任何引用」(已过期无数据源,不列)。
  // 类型计数走 tokenTypeCounts(全量口径,M4 服务端聚合;unref 是当前页口径)。
  const unrefSeg = unref ? ` · ${unref} 条未被任何引用` : ''
  const bearer = tokenTypeCounts.value.Bearer ?? 0
  const wholeHeader = tokenTypeCounts.value.Authorization ?? 0
  return `${total} 条凭证${unrefSeg} · ${bearer} Bearer · ${wholeHeader} 整段头`
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
/** 渐进披露:高级区(系统/环境/账号字段/token/有效期)默认收起 */
const advancedOpen = ref(false)

const schema = toTypedSchema(z.object({
  alias: z.string()
    .min(1, '请输入 alias')
    .regex(/^[A-Za-z0-9_-]{1,64}$/, '1-64 位字母数字下划线连字符'),
  system: z.string(),
  // 环境选值是字符串 id('none' 哨兵 = 不限),提交时转 number
  envId: z.string(),
  // authz C2:静态令牌认证(自举系统 platform 等)—— 登录 URL 可空
  url: z.string().url('URL 格式不正确').or(z.literal('')),
  username: z.string().min(1, '请输入 username'),
  // 编辑态可留空(= 不修改) — 创建态必填由 onSubmitForm 补判
  password: z.string(),
  token_type: z.enum(['Bearer', 'Basic', 'Cookie', 'Authorization']),
  expires_in: z.coerce.number().int('整数秒').min(0).max(86400, '最大 86400'),
}))

const { handleSubmit, resetForm, setFieldError } = useForm({
  validationSchema: schema,
  initialValues: {
    alias: '', system: '', envId: 'none',
    url: '', username: '', password: '',
    token_type: 'Bearer' as const, expires_in: 7200,
  },
})

// ── S7.3 表单辅面:环境选项 + 账号字段 KV 行(vee-validate 外置)──
const envs = ref<Array<{ id: number; name: string }>>([])
const accountFields = ref<Array<{ key: string; value: string }>>([])

function accountFieldsFromRow(row: AuthSession): Array<{ key: string; value: string }> {
  const src = (row as AuthSession & { accountFields?: Record<string, unknown> }).accountFields
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

/** ``slot``(深链 ?newSlot=):预填别名 — 取用键 = alias 本身(S7.5 导入
 *  结果「去绑定」;表单不再暴露槽字段,后端 slot 缺省 = alias);
 *  ``system``/``envId``:执行配置枢纽「缺失深链预填直达」(分层③)。 */
function openCreate(slot = '', system = '', envId = '') {
  editingId.value = null
  accountFields.value = []
  // 高级区:深链带 system/envId 预填时自动展开(alias 预填在主区)
  advancedOpen.value = Boolean(system || envId)
  resetForm({
    values: {
      alias: slot, system, envId: envId || 'none',
      url: '', username: '', password: '', token_type: 'Bearer', expires_in: 7200,
    },
  })
  createOpen.value = true
}

/** authz M2a S3:置为默认取用行(名字/环境未命中时取这条;后端原子清除旧默认)。 */
async function makeDefault(row: AuthSession) {
  try {
    await apiSetDefault(row.id)
    toast.success(`已将 ${row.alias} 设为默认取用`)
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
    row.system || row.envId != null || accountFields.value.length
    || row.token_type !== 'Bearer' || row.expires_in !== 7200)
  resetForm({
    values: {
      alias: row.alias,
      system: row.system || '',
      envId: row.envId != null ? String(row.envId) : 'none',
      url: row.url,
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
  submitting.value = true
  try {
    if (editingId.value) {
      const patch: Record<string, unknown> = {
        url: values.url,
        username: values.username,
        token_type: values.token_type,
        expires_in: values.expires_in,
        // env none=清空(显式 null 语义由值本身表达)
        system: values.system,
        envId: values.envId === 'none' ? null : Number(values.envId),
        accountFields: accountFieldsToObject(),
      }
      if (values.password) patch.password = values.password
      await store.patchAuth(editingId.value, patch)
      toast.success('已保存')
    } else {
      await store.createAuth({
        alias: values.alias,
        // 不送 slot:后端缺省 = alias,取用键即别名(表单无槽概念)
        system: values.system,
        ...(values.envId !== 'none' ? { envId: Number(values.envId) } : {}),
        accountFields: accountFieldsToObject(),
        url: values.url,
        username: values.username,
        password: values.password,
        token_type: values.token_type,
        expires_in: values.expires_in,
      })
      toast.success(`已创建 ${values.alias}`)
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
// 详情展开/收起策略移入共享 CredentialTestDialog(成功收起/失败展开)。
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
// 后端无测试历史面,v1 以 localStorage 记每条凭证的最近一次结果
// (per-browser;跨设备不同步 — chip 标注"本机记录"如实降级)。
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
  return deleteRefs.value.scenario_refs.visible.filter(
    (v) => v.owner_id === me && v.kinds.includes('template'),
  )
})

// ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────────────
const auth = useAuthStore()
const refsOpen = ref(false)
const refsTarget = ref<AuthSession | null>(null)
const refsLoading = ref(false)
const refsData = ref<AuthReferences | null>(null)

/** 删除拦截预告(与后端 DELETE 409 同口径):可见引用里
 *  「本人场景 × template」的条数(M2a S6 后 scheme 种类已退役)—
 *  抽屉底部淡红警示。 */
const drawerBlocking = computed(() => {
  const me = auth.currentUser?.id
  if (!refsData.value || me == null) return []
  return refsData.value.scenario_refs.visible.filter(
    (v) => v.owner_id === me && v.kinds.includes('template'),
  )
})

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
    refsData.value = await getReferences(refsTarget.value.alias)
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
  template: 'steps 里的 ${auth.<alias>.*} 模板 — 下次运行会用到',
  snapshot: 'config.users 的同名快照副本 — 自足,不随凭证池轮换',
}

function kindLabel(k: string): string {
  return KIND_LABELS[k] ?? k
}

function kindTitle(k: string): string {
  return KIND_TITLES[k] ?? k
}

const deleteConfirmed = computed(() =>
  Boolean(deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.alias),
)

function openDelete(row: AuthSession) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  deleteRefs.value = null
  deleteOpen.value = true
  // 预取反查(打开即查,不另设"检查引用"步骤):失败静默 — 硬确认仍在,
  // 409 拦截兜底语义不变
  getReferences(row.alias)
    .then((d) => { deleteRefs.value = d })
    .catch(() => { deleteRefs.value = null })
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  deleteSubmitting.value = true
  try {
    await store.deleteAuth(deleteTarget.value.id)
    toast.success(`已删除 ${deleteTarget.value.alias}`)
    deleteOpen.value = false
    void reloadList()
  } catch (e) {
    // 409 = 本人场景的模板/方案引用拦截(配套方案 §1.5 窄口径):
    // 错误信息带场景清单 — 保持弹框开着让用户看完再处理
    showError('删除', undefined, (e as Error).message)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── init ───────────────────────────────────────────────────────
onMounted(async () => {
  loadTestMemory()
  // 槽位声明反查(服务注册身份面注册表,读面全员;失败静默不亮 chip)
  listAllAliases()
    .then((rows) => {
      declaredSlots.value = new Set(
        rows.map((a) => a.slot).filter((s): s is string => Boolean(s)))
      slotsReady.value = true
    })
    .catch(() => { /* 注册表拉不到 — ✕ 未声明 chip 不亮 */ })
  // S7.5:导入结果「去绑定」→ 直接开新建表单并预填别名;分层③:执行配置
  // 枢纽的缺失深链补 system/envId 预填(?newSlot=&system=&envId=)
  const q = route?.query ?? {}
  const newSlot = typeof q.newSlot === 'string' ? q.newSlot : ''
  const qSystem = typeof q.system === 'string' ? q.system : ''
  const qEnv = typeof q.envId === 'string' ? q.envId : ''
  if (newSlot || qSystem || qEnv) openCreate(newSlot, qSystem, qEnv)
  // 环境选项给表单下拉
  listEnvironments()
    .then((rows) => { envs.value = rows.map((e) => ({ id: e.id, name: e.name })) })
    .catch(() => { /* 表单环境下拉退化为「不限」单项 */ })
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

/* ── 按槽分组的表格(槽级状态 = 分组头 3px 左缘色带;凭证行 = 主体)── */
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
/* 语义露出①:显式命名槽的行内小字(场景 ${slot.X} 的引用键) */
.slot-sub { font-size: 0.65625rem; color: var(--sl-ink-3); white-space: nowrap; }
.slot-sub.slot-undeclared { color: var(--sl-warn); }
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
