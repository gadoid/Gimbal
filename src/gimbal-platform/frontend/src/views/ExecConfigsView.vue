<!-- ExecConfigsView.vue — 执行配置管理页(执行配置分层①/③,/exec-configs)。
     个人面·全员:一套默认 + 若干命名配置。零凭证值零地址值 —— 凭证在
     凭证管理、地址在服务注册,这里只存引用键。
     2026-11-18 注册簿驱动重构 + 表单 v2(级联驱动,手写拼行退场):
     选服务 → 实例过滤(表单态,不进 payload —— §8.2 后配置不固化环境,
     执行时环境随换用身份走)→ 身份条目表(行 = 该服务注册表条目,行内
     显装载坐标/个人池解析账户/「换用为」select —— 选了即成绑定,候选按
     环境分组,跨环境换用即换实例)。存量绑定(声明 ∉ 注册表)落存量节
     保留不断数据。
     2026-11-19 表单 v3(carry 退场,用户决策):carry 值在 条目键/服务键
     + 默认值层已有维护面(运行时 条目 > 实例 > 服务 > 层默认,§8.9),
     "带什么业务参数"内聚在调用身份上 —— 配置级 carryOverrides 写面退场,
     **配置收敛为"选身份"**;存量 carryOverrides 只读保留、保存原样回写
     (执行链照常消费,端点与数据不动)。
     ③ 关联枢纽(§8):只关联不纳入 —— 地址就绪度(部署×实例并集矩阵,
     补登录口列)+ 深链服务注册;绑定条目→个人池装载就绪(registry C3a
     新链:换用条目 → ref → (system, env) 账户)+ 缺账户深链 /auths 按
     (system, envId) 预填直达;服务→逐服务子页深链;生效预览 pickable。
     形制与服务组其余页共用 .slib 基座(scenario-lib.css / service-area.css)。 -->
<template>
  <section class="slib" data-testid="exec-configs">
    <PageHead
      icon="sliders"
      title="配置"
      :count="loading ? '' : `${rows.length} 套配置`"
      :meta="mode === 'edit' && selected ? `当前配置 · ${selected.name}` : undefined"
      subtitle="场景外部支撑的跨场景载体:以谁的身份跑(身份条目换用)。选服务后行从注册簿长出来,身份条目行上选「换用为」即成绑定;业务参数随调用身份走(条目/服务/实例 carry 绑定与默认值层),凭证在「凭证管理」按条目 ref 解析、地址按身份的环境标签取部署表 —— 本页零凭证值零地址值。"
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

      <!-- 新建 / 编辑(整体替换式;表单 v2:行从注册簿长出来) -->
      <div v-if="formOpen" class="svc-panel" :data-testid="`ec-form-${mode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ mode === 'create' ? '新建配置' : `编辑:${form.name || selected?.name}` }}
          </span>
          <span class="svc-panel-desc">
            子配置按被测服务分组:身份条目行上选「换用为」即成绑定(候选按
            环境分组 —— 跨环境换用即换实例);业务参数不再配置在本页
            (随调用身份走:条目/服务/实例 carry 绑定与默认值层);实例选择
            仅过滤行集,配置不固化环境(§8.2)
          </span>
        </div>

        <div class="form-grid">
          <label class="lb">名称</label>
          <Input v-model="form.name" placeholder="如 商户B视角@UAT"
                 data-testid="ec-name" />
        </div>

        <div v-for="(s, i) in sysRows" :key="i" class="sys">
          <div class="sys-head">
            <span class="sys-title">服务 {{ i + 1 }}</span>
            <button type="button" class="svc-link danger" :data-testid="`ec-sys-rm-${i}`"
                    @click="sysRows.splice(i, 1)">移除服务</button>
          </div>

          <!-- ① 服务:主档选择器;主档缺席/为空 → 降级手输;存量值落兜底组 -->
          <div class="line-row">
            <label class="lb">服务</label>
            <select v-if="svcRows.length" v-model="s.service"
                    class="field-select flex-1" :data-testid="`ec-sys-${i}`"
                    @change="s.instanceFilter = ''">
              <option value="">(选择服务…)</option>
              <option v-for="sv in svcRows" :key="sv.name" :value="sv.name"
                      :title="sv.description || sv.name">{{ svcLabel(sv) }}</option>
              <optgroup v-if="s.service && !svcInCatalog(s.service)" label="存量(未在主档)">
                <option :value="s.service">{{ s.service }}</option>
              </optgroup>
            </select>
            <Input v-else v-model="s.service" class="flex-1"
                   placeholder="目录服务名,如 fin-service"
                   :data-testid="`ec-sys-${i}`" />
          </div>

          <!-- ② 实例过滤(表单态,不进 payload):该服务归属 system 的实例行 -->
          <div v-if="s.service && instancesOf(s).length" class="line-row">
            <label class="lb">实例</label>
            <select v-model="s.instanceFilter" class="field-select"
                    :data-testid="`ec-inst-${i}`">
              <option value="">全部环境</option>
              <option v-for="ins in instancesOf(s)" :key="ins.envId"
                      :value="String(ins.envId)">
                {{ ins.envName }}<template v-if="ins.tags.length"> · {{ ins.tags.join('/') }}</template>
              </option>
            </select>
            <span class="svc-panel-desc">过滤身份条目行集 —— 执行时环境随换用身份走</span>
          </div>

          <!-- ③ 身份条目表:行 = 该服务注册表条目(按实例过滤);行内选
               「换用为」即成绑定,候选按环境分组(跨环境换用 = 换环境机制) -->
          <div v-if="s.service" class="ident">
            <p class="ident-head">
              身份条目(行 = 该服务注册表{{ s.instanceFilter ? ' · 按实例过滤' : '' }})
            </p>
            <p v-if="aliasLoad[s.service] === 'loading'" class="hub-note">条目加载中…</p>
            <p v-else-if="!entriesOf(s).length" class="hub-note">
              该服务暂无登记的身份条目 ——
              <router-link :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                class="svc-link">去服务子页登记 ↗</router-link>
            </p>
            <table v-else class="slib-table" :data-testid="`ec-idents-${i}`">
              <thead>
                <tr><th>条目</th><th>装载坐标</th><th style="width:11.25rem">个人池</th>
                    <th style="width:16.25rem">换用为</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in identRows(s)" :key="a.aliasName"
                    :data-testid="`ec-ident-${i}-${a.aliasName}`">
                  <td><span class="mono">{{ a.aliasName }}</span></td>
                  <td><span class="mono">{{ identCoord(a) }}</span></td>
                  <td>
                    <span v-if="resolvedAccount(a)" class="svc-flag green">
                      账户 {{ resolvedAccount(a) }}</span>
                    <template v-else>
                      <span class="svc-flag red">缺账户</span>
                      <a class="svc-link" :href="authHrefOf(a)"
                         :data-testid="`ec-ident-auth-${a.aliasName}`">去补 ↗</a>
                    </template>
                  </td>
                  <td>
                    <select class="field-select w-full" :value="swapOf(s, a.aliasName)"
                            :data-testid="`ec-swap-${i}-${a.aliasName}`"
                            @change="setSwap(s, a.aliasName, ($event.target as HTMLSelectElement).value)">
                      <option value="">不覆盖(按场景声明)</option>
                      <optgroup v-for="g in swapGroups(s, a.aliasName)" :key="g.env" :label="g.env">
                        <option v-for="c in g.items" :key="c.aliasName" :value="c.aliasName"
                                :title="aliasTitle(c)">{{ c.aliasName }}</option>
                      </optgroup>
                      <optgroup v-if="swapLegacyNeeded(s, a.aliasName)" label="存量(不在该服务条目表)">
                        <option :value="swapOf(s, a.aliasName)">{{ swapOf(s, a.aliasName) }}</option>
                      </optgroup>
                    </select>
                  </td>
                </tr>
                <tr v-if="!identRows(s).length">
                  <td colspan="4" class="hub-note">该实例标签下没有条目 —— 换个实例或选「全部环境」。</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- ③·5 存量绑定:声明条目 ∉ 该服务注册表(未登记/跨服务)——
               注册簿制下不再手输新增,仅保留存量可改可删 -->
          <div v-if="aliasLoad[s.service] === 'done' && legacyBinds(s).length"
               class="carry-sys" :data-testid="`ec-legacy-binds-${i}`">
            <p class="carry-head">
              <b>存量绑定</b>
              <span class="svc-panel-desc">声明条目不在该服务注册表 —— 保留存量;新换用请在上方行上选</span>
            </p>
            <div v-for="(b, j) in legacyBinds(s)" :key="`lb${j}`" class="line-row">
              <Input v-model="b.alias" class="flex-1" list="ec-alias-suggestions"
                     placeholder="声明条目名" :data-testid="`ec-bind-${i}-${j}`" />
              <span class="lb">→</span>
              <Input v-model="b.slot" class="flex-1"
                     placeholder="换用条目名" :data-testid="`ec-slot-${i}-${j}`" />
              <button type="button" class="svc-link danger"
                      :data-testid="`ec-bind-rm-${i}-${j}`"
                      @click="s.binds.splice(s.binds.indexOf(b), 1)">移除</button>
            </div>
          </div>

          <!-- ④ 存量 carry 覆盖(只读保留;配置级 carry 写面已退场 ——
               值维护在 条目/服务/实例 carry 绑定与默认值层,执行链照常
               消费存量值,保存原样回写) -->
          <div v-if="s.service && s.carries.length" class="carry-sys"
               :data-testid="`ec-carry-legacy-${i}`">
            <p class="carry-head">
              <b>存量 carry 覆盖(只读)</b>
              <span class="svc-panel-desc">配置级 carry 编辑已退场 —— 值随调用身份走(条目/服务/实例绑定与默认值层)</span>
            </p>
            <table class="slib-table">
              <tbody>
                <tr v-for="c in s.carries" :key="c.field">
                  <td><span class="mono">{{ c.field }}</span></td>
                  <td><span class="mono">{{ c.isNull ? 'null(显式)' : c.value }}</span></td>
                  <td><span class="svc-panel-desc">执行配置覆盖(存量)</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="ec-sys-add"
                  @click="sysRows.push({ service: '', instanceFilter: '', binds: [], carries: [] })">+ 添加服务</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="ec-save" @click="save">保存</Button>
            <Button variant="outline" size="sm" data-testid="ec-cancel" @click="cancel">取消</Button>
          </span>
        </div>

        <!-- 存量绑定声明条目的软建议(各服务已加载条目并集) -->
        <datalist id="ec-alias-suggestions">
          <option v-for="n in aliasSuggestions" :key="n" :value="n" />
        </datalist>
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

        <!-- ① 地址就绪度(部署 × 实例并集矩阵 —— 有实例无地址的环境也
             出行;登录口列与 InstanceCredentialMatchPanel 行语义对齐;
             §8.2 配置去 env 后按全环境展示)+ 深链「服务注册」 -->
        <div class="svc-panel" data-testid="ec-hub-env">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务注册</span>
            <span class="svc-panel-desc">各服务按环境的地址与登录口就绪度(执行时按身份的环境标签取)</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/service-admin"
                class="svc-link">维护在「服务注册」↗</router-link>
              <span v-else class="svc-panel-desc">地址由平台管理员在「服务注册」维护</span>
            </span>
          </div>
          <p v-if="!selected.systems.length" class="hub-note">
            本配置还没有服务子配置 —— 地址就绪度按服务展示。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-deps">
            <thead>
              <tr><th>服务</th><th>环境</th><th>地址</th><th>登录口</th>
                  <th style="width:4.375rem">就绪</th></tr>
            </thead>
            <tbody>
              <template v-for="s in selected.systems" :key="`dep-${s.service}`">
                <tr v-for="(r, i) in matrixOf(s.service).rows" :key="`dep-${s.service}-${r.envId}`"
                    :data-testid="`ec-dep-${s.service}-${r.envId}`">
                  <td v-if="i === 0" :rowspan="matrixOf(s.service).rows.length">
                    <span class="mono">{{ s.service }}</span>
                    <span v-if="sysTag(s.service)" class="sys-sub mono">({{ sysTag(s.service) }})</span>
                  </td>
                  <td>{{ envName(r.envId) }}</td>
                  <td><span class="mono">{{ r.baseUrl || '—' }}</span></td>
                  <td><span class="mono">{{ r.loginUrl || '—' }}</span></td>
                  <td>
                    <span v-if="r.baseUrl" class="svc-flag green">就绪</span>
                    <span v-else class="svc-flag amber">缺地址</span>
                  </td>
                </tr>
                <tr v-if="!matrixOf(s.service).rows.length"
                    :data-testid="`ec-dep-${s.service}-none`">
                  <td><span class="mono">{{ s.service }}</span></td>
                  <td>—</td>
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

        <!-- ③ 服务接入 → 逐服务子页(主档说明 + 系统归属;读面全员)-->
        <div class="svc-panel" data-testid="ec-hub-svc">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务接入</span>
            <span class="svc-panel-desc">身份条目(条目名 → 服务 + 环境 + ref)在各服务子页登记;说明与系统归属来自服务主档</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/service-admin"
                class="svc-link">地址在「服务注册」↗</router-link>
            </span>
          </div>
          <p v-if="!selected.systems.length" class="hub-note">
            本配置还没有服务子配置 —— 身份条目按服务在各自子页登记。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-svcs">
            <thead>
              <tr><th>服务</th><th style="width:9.375rem">系统</th><th>说明</th>
                  <th style="width:6.875rem" class="c-center">身份条目</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in selected.systems" :key="`svc-${s.service}`"
                  :data-testid="`ec-svc-${s.service}`">
                <td><span class="mono">{{ s.service }}</span></td>
                <td><span class="mono">{{ systemOfBase(s.service) ?? '—' }}</span></td>
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

        <!-- ④ 生效预览:pickable(选定配置 + 任一场景 → 逐值带来源) -->
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
 * 表单 v2(2026-11-18 晚,级联驱动):服务 select(主档)→ 实例过滤
 * (表单态,§8.2 后配置不固化环境)→ 身份条目表(行 = 注册表条目,行内
 * 「换用为」select 候选按环境分组,选了即 upsert binds);存量绑定
 * (声明 ∉ 注册表)落存量节。
 * 表单 v3(2026-11-19,carry 退场):配置级 carryOverrides 写面撤下 ——
 * 业务参数随调用身份走(条目/服务/实例 carry 绑定与默认值层);存量值
 * 只读保留、保存原样回写(fillForm 装载 isNull 保 null 不丢真,执行链
 * 照常消费);枢纽④(carry 覆盖 + 漂移)随之退场,execConfigDrift 调用
 * 移除(API 导出与后端端点保留)。
 * 枢纽数据全部来自现有读面:部署表 + 实例表(listDeployments /
 * listInstances 并集矩阵)/个人池账户(listAll)/条目注册表定向检索
 * (listAliases)/主档(listServices,说明直读)/场景 options。 */
import { computed, onMounted, ref, watch } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  listExecConfigs, createExecConfig, updateExecConfig,
  setDefaultExecConfig, copyExecConfig, deleteExecConfig,
  type ExecConfigRow, type SystemSubConfig,
} from '@/api/execConfigs'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments, type Deployment } from '@/api/deployments'
import { listAll as listAllAuths } from '@/api/auth_sessions'
import { listAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { listServices, listInstances, type ServiceRow, type InstanceRow } from '@/api/services'
import { listScenarioOptions } from '@/api/scenario-composer'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'
import { useAuthStore } from '@/stores/auth'

interface BindRow { alias: string; slot: string }
/** 存量 carry 覆盖行(v3 只读保留):isNull=true 显式 JSON null;fillForm
 *  装载 → payloadOf 原样回写,不提供编辑(写面退场,执行链照常消费) */
interface CarryRow { field: string; value: string; isNull: boolean }
interface SysRow {
  service: string
  /** 实例过滤(表单态,不进 payload):'' = 全部环境,否则 String(envId) */
  instanceFilter: string
  binds: BindRow[]
  carries: CarryRow[]
}

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

// ── ③ 枢纽数据(读面拼装;失败降级为空,不阻塞编辑面)────────────
const deps = ref<Deployment[]>([])
/** 实例行(登录口就绪度 + 表单实例过滤;loginUrl 归 (system, env) 实例) */
const instRows = ref<InstanceRow[]>([])
/** 个人池账户(C3a 装载就绪链 + 表单身份表行内解析:账户化形状
 *  system/envId/username/isDefault) */
const authRows = ref<Array<{ system: string | null; envId: number | null;
                            username?: string; isDefault?: boolean | null }>>([])
const scenOptions = ref<Array<{ id: string; name: string }>>([])
const previewOpen = ref(false)
/** 主档(服务选项 + 装载坐标 baseService → system + 说明) */
const svcRows = ref<ServiceRow[]>([])

// ── 写面注册簿数据(懒加载,静默降级;单一数据源 = binds)──────────
/** 逐服务身份条目表(listAliases base 过滤;与 listAllAliases 同口径) */
const aliasCache = ref<Record<string, ServiceAliasRow[]>>({})
/** 逐服务条目加载状态:loading = 占位;done 后看 cache 决定形态 */
const aliasLoad = ref<Record<string, 'loading' | 'done'>>({})

async function ensureAliases(service: string): Promise<void> {
  if (!service || aliasLoad.value[service]) return
  aliasLoad.value = { ...aliasLoad.value, [service]: 'loading' }
  try {
    const page = await listAliases({ base: service, page_size: 200 })
    aliasCache.value = { ...aliasCache.value, [service]: page.items }
  } catch {
    aliasCache.value = { ...aliasCache.value, [service]: [] }
  } finally {
    aliasLoad.value = { ...aliasLoad.value, [service]: 'done' }
  }
}

// 表单里出现过的服务 → 懒加载该服务条目表(fillForm 与手选都走这)
watch(() => sysRows.value.map((r) => r.service).filter(Boolean).join('\u0001'),
  (joined) => {
    for (const service of new Set(joined.split('\u0001'))) {
      void ensureAliases(service)
    }
  }, { immediate: true })

function svcInCatalog(name: string): boolean {
  return svcRows.value.some((s) => s.name === name)
}
function svcLabel(sv: ServiceRow): string {
  return sv.system && sv.system !== sv.name ? `${sv.name}(${sv.system})` : sv.name
}

// ── 表单 v2 派生视图(注册表行 → binds/carries 单一数据源)────────
/** 该服务的注册表条目(未加载 = 空) */
function entriesOf(s: SysRow): ServiceAliasRow[] {
  return aliasCache.value[s.service] ?? []
}
/** 身份表行集:实例过滤(表单态)收窄 */
function identRows(s: SysRow): ServiceAliasRow[] {
  const all = entriesOf(s)
  if (!s.instanceFilter) return all
  return all.filter((a) => a.envId === Number(s.instanceFilter))
}
/** 实例过滤选项:该服务归属 system 的实例行 */
function instancesOf(s: SysRow): InstanceRow[] {
  const sys = systemOfBase(s.service)
  return sys ? instRows.value.filter((r) => r.system === sys) : []
}
/** 存量绑定:声明条目 ∉ 该服务注册表(未登记/跨服务) */
function legacyBinds(s: SysRow): BindRow[] {
  const known = new Set(entriesOf(s).map((a) => a.aliasName))
  return s.binds.filter((b) => b.alias && !known.has(b.alias))
}
/** 行的换用值(派生自 binds;'' = 不覆盖) */
function swapOf(s: SysRow, alias: string): string {
  return s.binds.find((b) => b.alias === alias)?.slot ?? ''
}
/** 行上选「换用为」:''=移除(不覆盖),有值=upsert */
function setSwap(s: SysRow, alias: string, slot: string): void {
  const i = s.binds.findIndex((b) => b.alias === alias)
  if (!slot) {
    if (i >= 0) s.binds.splice(i, 1)
    return
  }
  if (i >= 0) s.binds[i].slot = slot
  else s.binds.push({ alias, slot })
}
/** 换用候选分组:该服务全部条目按环境 optgroup(跨环境换用 = §8.2 后
 *  的换环境机制,不被实例过滤收窄);排除行自身 */
function swapGroups(s: SysRow, self: string): Array<{ env: string; items: ServiceAliasRow[] }> {
  const groups = new Map<string, ServiceAliasRow[]>()
  for (const a of entriesOf(s)) {
    if (a.aliasName === self) continue
    const env = a.envId != null ? envName(a.envId) : '无环境'
    const bucket = groups.get(env)
    if (bucket) bucket.push(a)
    else groups.set(env, [a])
  }
  return [...groups.entries()].map(([env, items]) => ({ env, items }))
}
/** 换用值不在候选集(存量/跨服务)→ 存量兜底 optgroup */
function swapLegacyNeeded(s: SysRow, alias: string): boolean {
  const val = swapOf(s, alias)
  if (!val) return false
  return !entriesOf(s).some((a) => a.aliasName === val)
}
/** 条目装载坐标(建账户的落点) */
function identCoord(a: ServiceAliasRow): string {
  const sys = systemOfBase(a.baseService)
  const env = a.envId != null ? envName(a.envId) : '无环境'
  const ref = a.refMode === 'username' ? `ref ${a.refUsername ?? '?'}` : 'ref 默认'
  return `${sys ?? '?'} × ${env} · ${ref}`
}
/** 条目在个人池解析到的账户(与后端 pick_bindings 的 ref 语义同构;
 *  default ref 只认 isDefault===true,username ref 认用户名) */
function resolvedAccount(a: ServiceAliasRow): string {
  if (a.envId == null) return ''
  const sys = systemOfBase(a.baseService)
  if (!sys) return ''
  return authRows.value.find((r) =>
    r.system === sys && r.envId === a.envId
    && (a.refMode === 'username'
      ? r.username === a.refUsername
      : r.isDefault === true))?.username ?? ''
}
/** 缺账户 → /auths 预填直达(坐标 = 条目装载的 (system, envId)) */
function authHrefOf(a: ServiceAliasRow): string {
  const q = new URLSearchParams()
  const sys = systemOfBase(a.baseService)
  if (sys) q.set('system', sys)
  if (a.envId != null) q.set('envId', String(a.envId))
  return `/auths?${q.toString()}`
}
function aliasTitle(a: ServiceAliasRow): string {
  const ref = a.refMode === 'username' ? `ref ${a.refUsername ?? '?'}` : 'ref 默认'
  return `${a.display || a.aliasName} · ${ref}`
}

// ── 存量绑定声明条目的软建议(各服务已加载条目并集)──────────────
const aliasSuggestions = computed(() => {
  const seen = new Set<string>()
  for (const s of sysRows.value) {
    for (const a of aliasCache.value[s.service] ?? []) seen.add(a.aliasName)
  }
  return [...seen]
})

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

/** 服务说明(自主档直读;拉不到显「—」) */
function svcDesc(service: string): string {
  return svcRows.value.find((s) => s.name === service)?.description ?? ''
}

const envNames = computed<Record<number, string>>(() =>
  Object.fromEntries(envs.value.map((e) => [e.id, e.name])))

function envName(id: number): string {
  return envNames.value[id] ?? `环境 #${id}`
}
/** 条目 → 装载坐标系统归属(自主档 baseService → system) */
function systemOfBase(base: string | undefined | null): string | null {
  if (!base) return null
  return svcRows.value.find((s) => s.name === base)?.system ?? null
}
/** 矩阵分组格的系统标注(与目录服务名不同才显) */
function sysTag(service: string): string {
  const sys = systemOfBase(service)
  return sys && sys !== service ? sys : ''
}
/** 地址就绪度矩阵行 = 该服务的部署环境 ∪ 归属 system 的实例环境
 *  (有实例无地址的环境也出行;登录口按 (system, env) 匹配实例) */
interface MatrixRow { envId: number; baseUrl: string; loginUrl: string }
function matrixOf(service: string): { system: string | null; rows: MatrixRow[] } {
  const system = systemOfBase(service)
  const depsHere = deps.value.filter((d) => d.baseService === service)
  const instHere = system ? instRows.value.filter((r) => r.system === system) : []
  const envIds = new Set<number>([
    ...depsHere.map((d) => d.envId),
    ...instHere.map((r) => r.envId),
  ])
  const rows = [...envIds].sort((a, b) => a - b).map((envId) => ({
    envId,
    baseUrl: depsHere.find((d) => d.envId === envId)?.baseUrl ?? '',
    loginUrl: instHere.find((r) => r.envId === envId)?.loginUrl ?? '',
  }))
  return { system, rows }
}
function aliasExists(alias: string): boolean {
  return faceMeta.value[alias] != null
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
/** 缺账户 → /auths 预填直达(§8 预填直达;坐标 = 条目装载的
 *  (system, envId),注册表缺席时回落子配置服务名) */
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
    // 绑定别名的注册表状态(定向检索,永不全量)
    loadFacesFor(c),
    // 部署矩阵(§8.2 配置去 env 后地址就绪度按全环境矩阵展示;实例行
    // 与表单共用,在 onMounted 旁路拉取)。v3:carry 漂移读面随配置级
    // carry 写面退场一并撤下(execConfigDrift 端点保留)
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
    instanceFilter: '',
    binds: Object.entries(s.bindings ?? {}).map(([alias, slot]) => ({ alias, slot })),
    // null 三态:null → isNull(修复旧实现 null 被折成 '' 存回的丢真)
    carries: Object.entries(s.carryOverrides ?? {})
      .map(([field, value]) => ({ field, value: value ?? '', isNull: value == null })),
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
      // v3:存量 carry 覆盖只读原样回写(isNull → null 保真;写面已
      // 退场,执行链照常消费存量值)
      carryOverrides: Object.fromEntries(
        s.carries
          .map((c) => ({ field: c.field.trim(), c }))
          .filter(({ field }) => field)
          .map(({ field, c }) => [field, c.isNull ? null : c.value]),
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
    error.value = '子配置里服务名重复'
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
  // 旁路数据(一次性;失败静默降级):个人池账户(装载判定/表单解析列)、
  // 主档(服务选项 + 装载坐标 + 说明;拉不到 → 服务列降级手输、坐标显 ?)、
  // 实例行(表单实例过滤 + 枢纽①登录口列)、场景 options(预览下拉)
  listAllAuths().then((r) => { authRows.value = r as never }).catch(() => {})
  listServices()
    .then((out) => { svcRows.value = out.services })
    .catch(() => { svcRows.value = [] })
  listInstances()
    .then((r) => { instRows.value = r })
    .catch(() => { instRows.value = [] })
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

/* 注册簿选择器(与 Input 同高同框;ProjectConfigPanel .field-select 同族) */
.field-select {
  height: 2.25rem;
  padding: 0 0.5rem;
  font-size: 0.8125rem;
  font-family: inherit;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
  min-width: 0;
}
.field-select:focus { border-color: var(--sl-accent); }
.field-select:disabled { opacity: 0.6; cursor: not-allowed; }

/* 身份条目表(行 = 注册表条目) */
.ident { display: flex; flex-direction: column; gap: 0.375rem; }
.ident-head { margin: 0; font-size: 0.71875rem; font-weight: 700; color: var(--sl-ink-2); }

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
.sys-sub { font-size: 0.65625rem; color: var(--sl-ink-3); }
</style>
