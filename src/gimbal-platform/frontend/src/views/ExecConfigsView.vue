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
     2026-11-19 v4 原型改造(stitch_scenario_environment_profile_manager,
     用户拍板:信息架构照原型、.slib 基座):左栏套件列表(.svc-split +
     .svc-rail 两栏基座)替代 chip 行;右工作台节点卡化(逐服务一张
     svc-panel,展开态 = v3 表单原样,收起态摘要行),虚线追加节点大卡,
     sticky 底栏(保存/取消 + Ping All);机制说明升格显式横幅。原型中
     环境切换 Tab/节点级凭证挂载/carry 编辑/账号池与既定口径冲突,不采纳
     (§8.2 / 四层模型 / v3 退场决策)。**Ping All**:配置内全部服务部署行
     地址 ping + 换用绑定条目解析账户登录拨测(串行,ServiceAdmin
     testAllSlots 范式;场景声明条目不在本页知识范围,不测)。
     2026-11-19 v4.1 交互加固:保存/删除/复制/设默认成功 toast(原静默
     刷新);脏检查(payload 快照比对,切换配置/新建前 confirmAction 拦截,
     内部刷新走 selectConfig 绕过);移除服务节点在有绑定/carry 时确认;
     Ping All 竞态守卫(运行中切配置 → 本轮结果作废);节点摘要 loading/
     未登记不给假「装载齐」;左栏内部分滚(标题/搜索/新建固定);底栏窄屏
     换行 + 提示省略;徽章横排;装载/拨测徽章列宽放宽。
     2026-11-19 v4.2 工作台页签(用户决策):编辑配置(写)/ 服务列表(读)/
     关联与就绪度(诊断)/ 生效预览(验证)四页签 —— 四类任务体验不同,
     平铺互相稀释焦点。编辑页签 = 原节点卡编辑区;服务列表 = 服务装载
     概况读面(+「去编辑」定位节点);就绪度 = 地址矩阵 + 装载就绪 +
     Ping All(自底栏迁入,角标 = 缺口数);预览 = EffectivePreviewDialog
     内嵌模式(inline prop,去遮罩/关闭钮,双宿主默认弹窗行为不变)。
     新建模式隐页签(恒编辑);切配置/新建复位到编辑页签;表单态跨页签保留。
     2026-11-19 v5 §8.10 圈定调用身份(用户决策:管理范围语义):身份条目
     表从「注册表全量摊开」改为首列「纳入」勾选 —— aliases = 本配置采用
     的声明条目集合(persist,执行链不消费);取消纳入一并移除换用;
     未勾行灰显。就绪度装载面板/服务列表概况/Ping All 拨测目标全部改
     表单态勾选集口径(取用 = 换用后条目;未换用的所选行也进面板)。
     存量行缺省 aliases → 按 bindings 声明键推导展示,保存固化。
     2026-11-19 v6 交互重构(用户决策):①「服务列表」页签撤下(内容已
     被节点卡头摘要 + 只读态已选列表覆盖;服务子页深链移到卡头);②节点卡
     两态 —— 默认只读(已选身份紧凑列表,零控件),「编辑」进入写面
     (左侧 accent 色条高亮),新加节点默认编辑;③身份选择改为「已选列表 +
     搜索加入」—— 编辑态只列已选明细(调用身份/取用/坐标/装载/换用/移除),
     注册表候选经 搜索词 + 实例过滤 收窄后从下拉按环境分组选择加入,
     不再全量罗列(注册表 >200 未全量载入时提示去服务子页)。
     ③ 关联枢纽(§8):只关联不纳入 —— 地址就绪度(部署×实例并集矩阵,
     补登录口列;Ping All 结果就地渲染)+ 深链服务注册;绑定条目→个人池
     装载就绪(registry C3a 新链:换用条目 → ref → (system, env) 账户)
     + 缺账户深链 /auths 按 (system, envId) 预填直达;服务→逐服务子页深链;
     生效预览 pickable。 -->
<template>
  <section class="slib" data-testid="exec-configs">
    <PageHead
      icon="sliders"
      title="配置"
      :count="loading ? '' : `${rows.length} 套配置`"
      :subtitle="pageHelp"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <div class="svc-split">
        <!-- ═══ 左栏:套件列表(原型左栏心智,.svc-rail sticky 内滚)═══ -->
        <aside class="svc-rail" data-testid="ec-list">
          <div class="svc-rail-title">
            <span>配置套件</span>
            <span class="n">{{ listQuery ? `${filteredRows.length}/${rows.length}` : `${rows.length}` }}</span>
          </div>
          <input v-model="listQuery" class="rail-search" type="search"
                 placeholder="搜索配置名…" data-testid="ec-list-search" />
          <div class="rail-rows">
            <button v-for="c in filteredRows" :key="c.id" type="button" class="rail-row"
                    :class="{ on: mode === 'edit' && c.id === selectedId }"
                    :data-testid="`ec-list-row-${c.id}`" @click="pick(c.id)">
              <span class="rail-name">
                <span class="rail-name-text">{{ c.name }}</span>
                <span v-if="c.isDefault" class="svc-flag green" :data-testid="`ec-list-default-${c.id}`">默认</span>
                <span v-for="t in (c.tags ?? []).slice(0, 2)" :key="t"
                      class="rail-tag" :data-testid="`ec-list-tag-${c.id}-${t}`">{{ t }}</span>
                <span v-if="(c.tags?.length ?? 0) > 2" class="rail-tag">
                  +{{ (c.tags?.length ?? 0) - 2 }}</span>
              </span>
              <span v-if="c.description" class="rail-desc"
                    :data-testid="`ec-list-desc-${c.id}`">{{ c.description }}</span>
              <span class="rail-sub">{{ rowSummary(c) }}</span>
            </button>
            <p v-if="!filteredRows.length" class="rail-empty">
              {{ rows.length ? '没有匹配的配置' : '暂无执行配置' }}
            </p>
          </div>
          <button type="button" class="rail-new" data-testid="ec-new"
                  @click="openCreate">+ 新建配置</button>
        </aside>

        <!-- ═══ 右工作台:套件头卡 + 节点卡 + 追加节点 + 枢纽 + sticky 底栏 ═══ -->
        <div v-if="!rows.length && !formOpen" class="slib-empty">
          <p>暂无执行配置 —— 新建一套默认配置(或从凭证管理/服务注册开始)</p>
        </div>

        <div v-else-if="formOpen" class="work" :data-testid="`ec-form-${mode}`">
          <!-- 套件头卡(v7 两态;v8.2 动作归位):只读 = 名称/标签/说明/元信息;
               编辑 = 名称/说明/标签输入 + 「完成」收起;取消/保存统一放卡片
               底部动作行(与 设默认/复制/删除 同处,底部常驻条撤下) -->
          <div class="svc-panel head-card" :class="{ editing: headEditing }">
            <div class="svc-panel-head">
              <span class="svc-panel-title">{{ mode === 'create' ? '新建配置' : '配置信息' }}</span>
              <span class="svc-panel-right">
                <template v-if="mode === 'edit' && selected">
                  <Button v-if="!headEditing" variant="outline" size="sm"
                          data-testid="ec-meta-edit" @click="metaEditing = true">编辑</Button>
                  <Button v-else variant="outline" size="sm"
                          data-testid="ec-meta-done" @click="metaEditing = false">完成</Button>
                </template>
              </span>
            </div>

            <!-- 只读态:名称 + 默认/标签 chips + 说明 -->
            <template v-if="!headEditing">
              <div class="meta-name-row">
                <h3 class="meta-name" data-testid="ec-meta-name">{{ selected?.name }}</h3>
                <span v-if="selected?.isDefault" class="svc-flag green"
                      data-testid="ec-is-default">默认配置</span>
                <TagPill v-for="t in selected?.tags ?? []" :key="t" :label="t" tone="accent"
                         :data-testid="`ec-meta-tag-${t}`" />
              </div>
              <p class="meta-desc" :class="{ empty: !selected?.description }"
                 data-testid="ec-meta-desc">
                {{ selected?.description || '暂无说明 —— 点「编辑」补充,便于在列表中快速识别' }}
              </p>
            </template>

            <!-- 编辑态:名称 / 说明 / 标签 -->
            <template v-else>
              <div class="head-row">
                <label class="lb">名称</label>
                <Input v-model="form.name" placeholder="如 商户B视角@UAT" maxlength="64"
                       data-testid="ec-name" />
                <span v-if="mode === 'edit' && selected?.isDefault"
                      class="svc-flag green" data-testid="ec-is-default">默认配置</span>
              </div>
              <div class="head-row">
                <label class="lb">说明</label>
                <Input v-model="form.description" maxlength="2048"
                       placeholder="一句话说明用途,如:商户B端回归主配置"
                       data-testid="ec-desc" />
              </div>
              <div class="head-row">
                <label class="lb">标签</label>
                <TagInput v-model="form.tags" data-testid="ec-tags"
                          placeholder="按 Enter / 逗号 添加,如 UAT、核心" />
              </div>
            </template>

            <!-- 元信息行(§8.10 表单态圈定集口径:N 服务 · M 换用 · K 缺装载) -->
            <p v-if="mode === 'edit' && selected" class="head-meta" data-testid="ec-head-meta">
              {{ formServices.length }} 个服务节点 · {{ totalSwaps }} 条换用 · {{ missLoads }} 条缺装载
            </p>
            <!-- 动作行(v8.2 归位):配置级动作(只读态)+ 取消/保存(常驻;
                 替代原底部 sticky 条 —— 保存作用于整张配置,不再分两处) -->
            <div class="head-acts">
              <template v-if="mode === 'edit' && selected && !headEditing">
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
              </template>
              <span class="head-acts-fill" />
              <Button variant="outline" size="sm" data-testid="ec-cancel"
                      :disabled="saving" @click="cancel">取消</Button>
              <Button size="sm" data-testid="ec-save" :disabled="saving"
                      @click="save">{{ saving ? '保存中…' : '保存' }}</Button>
            </div>
          </div>

          <!-- 头卡两态判定:create 恒编辑;edit 由 metaEditing 控制 -->
          <!-- (计算属性 headEditing 在 script 中定义) -->

          <!-- ═══ 页签:编辑配置 / 关联与就绪度 / 生效预览 ═══
               三类任务:配置(写)/ 就绪度(诊断)/ 预览(验证)。服务清单已
               并入节点卡(头摘要 + 只读态已选列表),不再单列页签。 -->
          <nav v-if="mode === 'edit' && selected" class="tabs" data-testid="ec-tabs">
            <button type="button" class="tab" :class="{ on: activeTab === 'edit' }"
                    data-testid="ec-tab-edit" @click="activeTab = 'edit'">
              编辑配置<span class="cnt">{{ sysRows.length }}</span></button>
            <button type="button" class="tab" :class="{ on: activeTab === 'readiness' }"
                    data-testid="ec-tab-readiness" @click="activeTab = 'readiness'">
              关联与就绪度<span v-if="readinessIssues" class="cnt alert"
                :title="`${readinessIssues} 处缺口(缺地址/缺账户)`">{{ readinessIssues }}</span></button>
            <button type="button" class="tab" :class="{ on: activeTab === 'preview' }"
                    data-testid="ec-tab-preview" @click="activeTab = 'preview'">
              生效预览</button>
          </nav>

          <!-- ── 页签:编辑配置(写面;机制说明统一收进页头问号帮助)── -->
          <template v-if="activeTab === 'edit'">
          <!-- ═══ 节点卡 × N(v6):只读/编辑两态 —— 默认只读(已选身份紧凑
               列表,无控件),点「编辑」进入写面;编辑中左侧色条高亮。
               收起态 = 摘要行。 -->
          <div v-for="(s, i) in sysRows" :key="i" class="svc-panel node"
               :class="{ editing: isEditing(i) }" :data-testid="`ec-node-${i}`">
            <div class="node-head">
              <span class="node-idx">{{ i + 1 }}</span>
              <div class="node-main">
                <div class="node-title-row">
                  <!-- ① 服务:主档选择器;主档缺席/为空 → 降级手输;存量值落兜底组 -->
                  <select v-if="svcRows.length" v-model="s.service"
                          class="field-select node-svc" :data-testid="`ec-sys-${i}`"
                          @change="s.instanceFilter = ''">
                    <option value="">(选择服务…)</option>
                    <option v-for="sv in svcRows" :key="sv.name" :value="sv.name"
                            :title="sv.description || sv.name">{{ svcLabel(sv) }}</option>
                    <optgroup v-if="s.service && !svcInCatalog(s.service)" label="存量(未在主档)">
                      <option :value="s.service">{{ s.service }}</option>
                    </optgroup>
                  </select>
                  <Input v-else v-model="s.service" class="node-svc"
                         placeholder="目录服务名,如 fin-service"
                         :data-testid="`ec-sys-${i}`" />
                <span v-if="s.service && sysTag(s.service)"
                        class="svc-flag violet mono">{{ sysTag(s.service) }}</span>
                <!-- v8·1:节点状态徽章组统一贴服务选框(未圈选/加载中/未登记/
                     条目·换用·装载同一展示位,不再居右侧) -->
                <span v-if="s.service" class="node-status">
                  <template v-if="nodeLoadState(s) === 'loading'">
                    <span class="svc-flag ink">条目加载中…</span>
                  </template>
                  <template v-else-if="nodeLoadState(s) === 'error'">
                    <span class="svc-flag amber" :data-testid="`ec-node-alias-err-${i}`">条目读取失败</span>
                  </template>
                  <template v-else-if="nodeLoadState(s) === 'empty'">
                    <span class="svc-flag amber">未登记条目</span>
                  </template>
                  <template v-else-if="!nodeSummary(s).entries">
                    <span class="svc-flag ink"
                          :data-testid="`ec-node-unpicked-${i}`">未圈选身份</span>
                  </template>
                  <template v-else>
                    <span class="svc-flag ink">{{ nodeSummary(s).entries }} 条目</span>
                    <span class="svc-flag blue">{{ nodeSummary(s).swaps }} 换用</span>
                    <span class="svc-flag" :class="nodeSummary(s).missing ? 'amber' : 'green'">
                      {{ nodeSummary(s).missing ? `${nodeSummary(s).missing} 缺装载` : '装载齐' }}
                    </span>
                  </template>
                </span>
              </div>
                <p v-if="s.service" class="node-sub">
                  {{ svcDesc(s.service) || '—' }}
                  <router-link
                    :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                    class="svc-link" :data-testid="`ec-goto-faces-${s.service}`"
                  >服务子页 ↗</router-link>
                </p>
              </div>
              <!-- 节点操作:只读/编辑切换 + 收起/展开 + 移除 -->
              <div class="node-opers">
                <button v-if="s.service" type="button" class="svc-btn"
                        :class="{ primary: !isEditing(i) }"
                        :data-testid="`ec-node-edit-${i}`" @click="toggleEdit(i)">
                  {{ isEditing(i) ? '完成' : '编辑' }}
                </button>
                <button type="button" class="svc-link node-toggle"
                        :data-testid="`ec-node-toggle-${i}`" @click="toggleNode(i)">
                  {{ isExpanded(i) ? '收起' : '展开' }}
                </button>
                <button type="button" class="svc-link danger"
                        :data-testid="`ec-sys-rm-${i}`"
                        @click="removeNode(i)">移除</button>
              </div>
            </div>

            <!-- 展开态:只读(已选列表)/ 编辑(选择器 + 明细 + 存量) -->
            <template v-if="isExpanded(i)">
              <!-- 空节点(刚追加/未选服务)引导 -->
              <p v-if="!s.service" class="hub-note">
                从上方主档选择服务 —— 选择后从注册表挑选调用身份。
              </p>
              <template v-else>
                <!-- ── 只读态:已选调用身份紧凑列表(零控件)── -->
                <div v-if="!isEditing(i)" class="node-view" :data-testid="`ec-node-view-${i}`">
                  <p v-if="!slotRowsOf(s).length" class="hub-note">
                    未圈选调用身份 —— 点上方「编辑」从注册表选择。
                  </p>
                  <table v-else class="slib-table">
                    <thead>
                      <tr><th>调用身份</th><th>取用条目</th><th>装载坐标</th>
                          <th style="width:7.5rem">装载</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="r in slotRowsOf(s)" :key="r.alias"
                          :data-testid="`ec-view-slot-${i}-${r.alias}`">
                        <td><span class="mono">{{ r.alias }}</span></td>
                        <td>
                          <span class="mono">{{ r.useName }}</span>
                          <span v-if="r.useName !== r.alias" class="svc-flag blue ml-1">换用</span>
                        </td>
                        <td><span class="mono">{{ r.use ? identCoord(r.use) : '—' }}</span></td>
                        <td>
                          <span v-if="r.loaded" class="svc-flag green">已装载</span>
                          <span v-else-if="!r.use" class="svc-flag red">{{ r.useFailed ? '✕ 读取失败' : '✕ 未登记' }}</span>
                          <span v-else class="svc-flag red">{{ r.loadedFailed ? '账户读取失败' : '缺账户' }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- ── 编辑态:搜索加入 + 已选明细 + 存量 ── -->
                <template v-else>
                  <!-- ② 实例过滤(表单态):收窄候选集 -->
                  <div v-if="instancesOf(s).length" class="line-row">
                    <label class="lb">实例</label>
                    <select v-model="s.instanceFilter" class="field-select"
                            :data-testid="`ec-inst-${i}`">
                      <option value="">全部环境</option>
                      <option v-for="ins in instancesOf(s)" :key="ins.envId"
                              :value="String(ins.envId)">
                        {{ ins.envName }}<template v-if="ins.tags.length"> · {{ ins.tags.join('/') }}</template>
                      </option>
                    </select>
                    <span class="svc-panel-desc">过滤候选条目 —— 执行时环境随换用身份走</span>
                  </div>

                  <p v-if="aliasLoad[s.service] === 'loading'" class="hub-note">条目加载中…</p>
                  <p v-else-if="!entriesOf(s).length" class="hub-note">
                    该服务暂无登记的身份条目 ——
                    <router-link :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                      class="svc-link">去服务子页登记 ↗</router-link>
                  </p>
                  <template v-else>
                    <!-- 选择行:搜索 + 候选下拉(按环境分组;选中即加入) -->
                    <div class="pick-row">
                      <Input v-model="s.pickQuery" class="pick-q"
                             placeholder="搜索条目名 / ref…"
                             :data-testid="`ec-pick-q-${i}`" />
                      <select class="field-select pick-sel" :data-testid="`ec-pick-${i}`"
                              :disabled="!pickCount(s)" @change="addUseFromPick(s, $event)">
                        <option value="">{{ pickCount(s)
                          ? `+ 选择加入(${pickCount(s)} 个候选)` : '没有可加入的条目' }}</option>
                        <optgroup v-for="g in pickGroups(s)" :key="g.env" :label="g.env">
                          <option v-for="a in g.items" :key="a.aliasName"
                                  :value="a.aliasName" :title="aliasTitle(a)">{{ a.aliasName }}</option>
                        </optgroup>
                      </select>
                      <span v-if="registryTruncated(s)" class="svc-panel-desc">
                        注册表超过 200 条未全量载入 —— 可去服务子页管理
                      </span>
                    </div>

                    <!-- 已选明细表:只列已选身份(行数 = 圈定数) -->
                    <table v-if="slotRowsOf(s).length" class="slib-table"
                           :data-testid="`ec-idents-${i}`">
                      <thead>
                        <tr><th>调用身份</th><th>取用条目</th><th>装载坐标</th>
                            <th style="width:9.375rem">个人池</th>
                            <th style="width:15rem">换用为</th>
                            <th style="width:4.375rem">操作</th></tr>
                      </thead>
                      <tbody>
                        <tr v-for="r in slotRowsOf(s)" :key="r.alias"
                            :data-testid="`ec-ident-${i}-${r.alias}`">
                          <td><span class="mono">{{ r.alias }}</span></td>
                          <td>
                            <span class="mono">{{ r.useName }}</span>
                            <span v-if="r.useName !== r.alias" class="svc-flag blue ml-1">换用</span>
                          </td>
                          <td><span class="mono">{{ r.use ? identCoord(r.use) : '—' }}</span></td>
                          <td>
                            <span v-if="r.loaded" class="svc-flag green">已装载</span>
                            <span v-else-if="!r.use" class="svc-flag red">{{ r.useFailed ? '✕ 读取失败' : '✕ 未登记' }}</span>
                            <template v-else>
                              <span class="svc-flag red">{{ r.loadedFailed ? '账户读取失败' : '缺账户' }}</span>
                              <a v-if="!r.loadedFailed" class="svc-link" :href="authHrefOf(r.use)"
                                 :data-testid="`ec-ident-auth-${r.alias}`">去补 ↗</a>
                            </template>
                          </td>
                          <td>
                            <select class="field-select w-full" :value="swapOf(s, r.alias)"
                                    :data-testid="`ec-swap-${i}-${r.alias}`"
                                    @change="setSwap(s, r.alias, ($event.target as HTMLSelectElement).value)">
                              <option value="">不覆盖(按场景声明)</option>
                              <optgroup v-for="g in swapGroups(s, r.alias)" :key="g.env" :label="g.env">
                                <option v-for="c in g.items" :key="c.aliasName" :value="c.aliasName"
                                        :title="aliasTitle(c)">{{ c.aliasName }}</option>
                              </optgroup>
                              <optgroup v-if="swapLegacyNeeded(s, r.alias)" label="存量(不在该服务条目表)">
                                <option :value="swapOf(s, r.alias)">{{ swapOf(s, r.alias) }}</option>
                              </optgroup>
                            </select>
                          </td>
                          <td>
                            <button type="button" class="svc-link danger"
                                    :data-testid="`ec-unuse-${i}-${r.alias}`"
                                    @click="toggleUse(s, r.alias, false)">移除</button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <p v-else class="hub-note" data-testid="ec-use-hint">
                      还没有选择调用身份 —— 从上方搜索并选择加入。
                    </p>
                  </template>

              <!-- ③·5 存量绑定:声明条目 ∉ 该服务注册表(未登记/跨服务)——
                   注册簿制下不再手输新增,仅保留存量可改可删 -->
              <div v-if="aliasLoad[s.service] === 'done' && legacyBinds(s).length"
                   class="carry-sys" :data-testid="`ec-legacy-binds-${i}`">
                <p class="carry-head">
                  <b>存量绑定</b>
                  <span class="svc-panel-desc">声明条目不在该服务注册表 —— 保留存量(恒视为已纳入);新换用请在上方行上选</span>
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
                </template><!-- /编辑态 -->
              </template><!-- /service v-else -->
            </template><!-- /expanded -->

            <!-- 收起态:紧凑摘要行(原型「展开详细编排」的反面) -->
            <div v-else class="node-fold" :data-testid="`ec-node-collapsed-${i}`">
              <template v-if="s.service">
                <template v-if="nodeLoadState(s) === 'loading'">
                  <span>条目加载中…</span>
                </template>
                <template v-else-if="nodeLoadState(s) === 'empty'">
                  <span>未登记条目</span>
                </template>
                <template v-else-if="nodeSummary(s).entries">
                  <span>{{ nodeSummary(s).entries }} 个身份条目</span>
                  <span class="fold-sep">|</span>
                  <span>{{ nodeSummary(s).swaps }} 条换用</span>
                  <span class="fold-sep">|</span>
                  <span :class="nodeSummary(s).missing ? 'miss' : ''">
                    {{ nodeSummary(s).missing ? `${nodeSummary(s).missing} 条缺装载` : '装载齐' }}</span>
                </template>
              </template>
              <span v-else class="svc-panel-desc">未选服务</span>
              <span class="flex-1" />
              <button type="button" class="svc-link" @click="toggleNode(i)">展开详细编排</button>
            </div>
          </div>

          <!-- 追加节点:虚线大卡(原型 Add System Matrix) -->
          <button type="button" class="node-add" data-testid="ec-node-add-card" @click="addNode">
            <span class="node-add-title">+ 追加被测服务节点</span>
            <span class="node-add-sub">从服务主档选择,如 fin-service、pay-core…</span>
          </button>
          </template>

          <!-- ── 页签:关联与就绪度(诊断面 + Ping All)── -->
          <div v-if="activeTab === 'readiness' && selected" class="hub" data-testid="ec-hub">
            <div class="svc-sec">
              <span class="t">关联与就绪度</span>
              <span class="n">只关联不纳入 —— 维护面留在各自页面</span>
              <span class="right">
                <span v-if="pingAllResult" class="svc-flag"
                      :class="pingAllOk ? 'green' : 'red'"
                      data-testid="ec-ping-all-result">{{ pingAllResult }}</span>
                <Button variant="outline" size="sm" data-testid="ec-ping-all"
                        :disabled="pingAllRunning"
                        title="配置内全部服务部署行地址 ping + 换用绑定条目解析账户登录拨测(场景声明条目不在本页知识范围,不测)"
                        @click="pingAll">
                  {{ pingAllRunning ? '逐一检测中…' : '测试全链路联通性 (Ping All)' }}
                </Button>
              </span>
            </div>

            <!-- ① 地址就绪度(部署 × 实例并集矩阵 —— 有实例无地址的环境也
                 出行;登录口列与 InstanceCredentialMatchPanel 行语义对齐;
                 §8.2 配置去 env 后按全环境展示)+ 深链「服务注册」;
                 Ping All 的地址结果就地渲染。§8.10:按当前编辑态(表单态
                 服务集合,保存后生效) -->
            <div class="svc-panel" data-testid="ec-hub-env">
              <div class="svc-panel-head">
                <span class="svc-panel-title">服务注册</span>
                <span class="svc-panel-desc">各服务按环境的地址与登录口就绪度(执行时按身份的环境标签取;按当前编辑态)</span>
                <span class="svc-panel-right">
                  <router-link v-if="auth.can('ops.write')" to="/service-admin"
                    class="svc-link">维护在「服务注册」↗</router-link>
                  <span v-else class="svc-panel-desc">地址由平台管理员在「服务注册」维护</span>
                </span>
              </div>
              <p v-if="!formServices.length" class="hub-note">
                本配置还没有服务节点 —— 地址就绪度按服务展示。
              </p>
              <table v-else class="slib-table" data-testid="ec-hub-deps">
                <thead>
                  <tr><th>服务</th><th>环境</th><th>地址</th><th>登录口</th>
                      <th style="width:4.375rem">就绪</th></tr>
                </thead>
                <tbody>
                  <template v-for="service in formServices" :key="`dep-${service}`">
                    <tr v-for="(r, i) in matrixOf(service).rows" :key="`dep-${service}-${r.envId}`"
                        :data-testid="`ec-dep-${service}-${r.envId}`">
                      <td v-if="i === 0" :rowspan="matrixOf(service).rows.length">
                        <span class="mono">{{ service }}</span>
                        <span v-if="sysTag(service)" class="sys-sub mono">({{ sysTag(service) }})</span>
                      </td>
                      <td>{{ envName(r.envId) }}</td>
                      <td>
                        <span class="mono">{{ r.baseUrl || '—' }}</span>
                        <!-- Ping All 地址结果(仅测过的行渲染) -->
                        <span v-if="depPing[depPingKey(service, r.envId)]"
                              class="svc-flag"
                              :class="depPing[depPingKey(service, r.envId)]?.ok ? 'green' : 'red'"
                              :data-testid="`ec-dep-ping-${service}-${r.envId}`">
                          {{ pingText(depPing[depPingKey(service, r.envId)]!) }}
                        </span>
                      </td>
                      <td><span class="mono">{{ r.loginUrl || '—' }}</span></td>
                      <td>
                        <span v-if="r.baseUrl" class="svc-flag green">就绪</span>
                        <span v-else class="svc-flag amber">缺地址</span>
                      </td>
                    </tr>
                    <tr v-if="!matrixOf(service).rows.length"
                        :data-testid="`ec-dep-${service}-none`">
                      <td><span class="mono">{{ service }}</span></td>
                      <td>—</td>
                      <td>—</td>
                      <td>—</td>
                      <td><span class="svc-flag amber">缺地址</span></td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>

            <!-- ② 圈定身份 → 取用条目装载就绪(ref→账户新链;C3a)+ 缺失
                 深链 /auths 预填直达;Ping All 拨测结果就地渲染。
                 §8.10:行 = 勾选集(表单态,保存后生效),取用 = 换用后条目 -->
            <div class="svc-panel" data-testid="ec-hub-slots">
              <div class="svc-panel-head">
                <span class="svc-panel-title">身份条目装载就绪</span>
                <span class="svc-panel-desc">按当前编辑态(保存后生效):圈定身份的取用条目(换用后)按 ref 取个人池账户;缺失点直达凭证管理</span>
              </div>
              <p v-if="!hasBindings" class="hub-note">
                未圈定调用身份 —— 在「编辑配置」页签的节点内搜索加入本配置采用的身份条目。
              </p>
              <table v-else class="slib-table" data-testid="ec-hub-bindings">
                <thead>
                  <tr><th>所选条目</th><th>取用条目</th><th>装载坐标</th>
                      <th style="width:9.375rem">个人池</th><th style="width:13.125rem">操作</th></tr>
                </thead>
                <tbody>
                  <template v-for="s in sysRows" :key="`slot-${s.service}`">
                    <tr v-for="r in slotRowsOf(s)" :key="`${s.service}:${r.alias}`"
                        :data-testid="`ec-slot-row-${r.alias}`">
                      <td><span class="mono">{{ r.alias }}</span></td>
                      <td>
                        <span class="mono">{{ r.useName }}</span>
                        <span v-if="r.useName !== r.alias" class="svc-flag blue ml-1">换用</span>
                      </td>
                      <td>
                        <span class="mono">{{ r.use ? identCoord(r.use) : '—' }}</span>
                      </td>
                      <td>
                          <span v-if="r.loaded" class="svc-flag green">已装载</span>
                          <span v-else-if="!r.use" class="svc-flag red"
                                :title="r.useFailed ? '条目面读取失败 — 无法判定是否登记' : '取用条目不在注册表 — 取不到 ref 坐标'">{{ r.useFailed ? '✕ 读取失败' : '✕ 未登记' }}</span>
                          <span v-else class="svc-flag red" :data-testid="`ec-slot-miss-${r.useName}`">{{ r.loadedFailed ? '账户读取失败' : '缺账户' }}</span>
                        <!-- Ping All 拨测结果(仅测过的行渲染) -->
                        <span v-if="slotProbe[r.useName]" class="svc-flag"
                              :class="slotProbe[r.useName]?.ok ? 'green' : 'red'"
                              :data-testid="`ec-slot-probe-${r.useName}`">
                          {{ slotProbe[r.useName]?.ok ? '拨测通过' : '拨测失败' }}
                        </span>
                      </td>
                      <td>
                        <!-- 取用条目未登记 → 该服务子页的身份条目注册表(登记
                             的家);缺个人池账户 → 凭证管理按取用条目 (system,
                             env) 预填直达 -->
                        <router-link
                          v-if="!r.use"
                          :to="`/service-admin/${encodeURIComponent(s.service)}?tab=faces`"
                          class="svc-link warn-link"
                          :data-testid="`ec-goto-faces-${r.alias}`"
                          >去登记 ↗</router-link>
                        <a v-else-if="!r.loaded" class="svc-link"
                           :data-testid="`ec-goto-auth-${r.useName}`"
                           :href="authHrefOf(r.use)">去凭证管理补 ↗</a>
                        <span v-else class="svc-panel-desc">按条目 ref 解析</span>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>

          </div>

          <!-- ── 页签:生效预览(内嵌,不弹窗;选场景 → 逐值带来源)── -->
          <div v-if="activeTab === 'preview'" data-testid="ec-hub-preview">
            <EffectivePreviewDialog inline :open="true"
              :scenarios="scenOptions" :exec-config-id="selected?.id"
              :env-names="envNames" />
            <p v-if="scenCapped" class="hint" data-testid="ec-scen-capped">
              场景超过 {{ scenOptions.length }} 条,下拉仅列前 {{ scenOptions.length }} 条 —— 用场景名精确定位或在场景列表发起预览。
            </p>
          </div>

          <!-- 存量绑定声明条目的软建议(各服务已加载条目并集) -->
          <datalist id="ec-alias-suggestions">
            <option v-for="n in aliasSuggestions" :key="n" :value="n" />
          </datalist>
        </div>
      </div>

      <div v-if="error" class="svc-banner bad mt-3.5" data-testid="ec-err">{{ error }}</div>
      <div v-if="bypassDegraded" class="svc-banner warn mt-3.5" data-testid="ec-bypass-degraded">{{ bypassDegraded }}</div>
    </template>
  </section>
</template>

<script setup lang="ts">
/** ExecConfigsView.vue — 执行配置管理页 + ③ 关联枢纽(设计方案 §4/§8)。
 * 列表(左栏 rail)/编辑(整体替换式 PATCH)/默认切换/复制/两步删除;
 * 错误内联。表单 v2(2026-11-18 晚,级联驱动):服务 select(主档)→
 * 实例过滤(表单态,§8.2 后配置不固化环境)→ 身份条目表(行 = 注册表
 * 条目,行内「换用为」select 候选按环境分组,选了即 upsert binds);
 * 存量绑定(声明 ∉ 注册表)落存量节。表单 v3(2026-11-19,carry 退场):
 * 配置级 carryOverrides 写面撤下 —— 业务参数随调用身份走;存量值只读
 * 保留、保存原样回写;枢纽④(carry 覆盖 + 漂移)随之退场。
 * v4(2026-11-19,原型改造):左栏列表 + 节点卡(展开/收起)+ 虚线追加
 * 节点 + sticky 底栏 + 机制横幅 —— 布局层重构,业务逻辑零改动;新增
 * Ping All(地址 ping + 绑定账户拨测,ServiceAdmin testAllSlots 串行
 * 范式,失败前端合成计入)。
 * 枢纽数据全部来自现有读面:部署表 + 实例表(listDeployments /
 * listInstances 并集矩阵)/个人池账户(listAll,补 id 供拨测)/条目
 * 注册表定向检索(listAliases)/主档(listServices,说明直读)/场景
 * options。 */
import { computed, onMounted, ref, watch } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import TagInput from '@/components/TagInput.vue'
import TagPill from '@/components/TagPill.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { pickAccountLikeBackend } from '@/utils/identityResolve'
import {
  listExecConfigs, createExecConfig, updateExecConfig,
  setDefaultExecConfig, copyExecConfig, deleteExecConfig,
  type ExecConfigRow, type SystemSubConfig,
} from '@/api/execConfigs'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments, pingDeployment, type Deployment, type PingResult } from '@/api/deployments'
import { listAll as listAllAuths, testConnection, type TestResult } from '@/api/auth_sessions'
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
  /** 圈定的调用身份条目名(声明侧,§8.10 管理范围):勾选集,不勾不进
   *  就绪度/拨测/凭证引导;执行链不消费 */
  aliases: string[]
  /** 实例过滤(表单态,不进 payload):'' = 全部环境,否则 String(envId) */
  instanceFilter: string
  /** 候选搜索词(表单态,v6):过滤可加入的注册表行 */
  pickQuery: string
  binds: BindRow[]
  carries: CarryRow[]
}

/** 页面功能说明(v8):原机制横幅/底栏提示/头卡说明统一收进页头问号。
 *  QTip 弹层支持 \n\n 分段(max-w 26.25rem)。 */
const pageHelp = `执行配置 = 场景外部支撑的跨场景载体(左侧选套件,右侧编排)。

① 配置 = 圈定调用身份:每个服务节点内搜索并选择本配置采用的调用身份(圈定集);行上「换用为」把场景声明的条目换成取用条目(即绑定)。装载就绪、全链路检测与凭证补录引导都按圈定集走 —— 不圈定 = 本配置不用;存量配置未圈定时按绑定声明键推导展示。

② 业务参数随调用身份走:carry 值维护在 条目/服务/实例 的 carry 默认值层(服务注册页),本页只读回显存量覆盖;凭证在「凭证管理」按条目 ref 解析,地址按身份的环境标签取部署表 —— 本页零凭证值零地址值。

③ 配置不固化环境:执行时环境随换用身份走(§8.2)。

④ 页签:编辑配置(写面)/ 关联与就绪度(地址矩阵 + 装载就绪 + 全链路检测)/ 生效预览(选场景 → 逐值带来源,与执行同源)。

⑤ 保存:「配置信息」卡动作行的「保存」为全量保存(名称/说明/标签/节点配置);切换/设默认/复制前有未保存改动会先确认。全链路检测(Ping All)= 全部服务部署行地址 ping + 圈定身份取用条目解析账户的登录拨测(逐条最长约 30s,可能较慢)。`

const auth = useAuthStore()
const loading = ref(true)
const rows = ref<ExecConfigRow[]>([])
const envs = ref<EnvironmentRow[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'edit' | 'create'>('edit')
/** 表单态(配置级):名称 + 元信息(v7 说明/标签,列表识别用) */
const form = ref({ name: '', description: '', tags: [] as string[] })
/** 头卡只读/编辑两态(v7):编辑态恒假于 create 模式 */
const metaEditing = ref(false)
const sysRows = ref<SysRow[]>([])
const error = ref('')
const delArmed = ref(false)
const copyArmed = ref(false)
const copyName = ref('')

// ── v4 布局态:左栏搜索 + 节点展开/收起(默认全展开)──────────────
const listQuery = ref('')
const expanded = ref<Record<number, boolean>>({})
/** 工作台页签(v4.2):编辑(写)/ 服务列表(读)/ 就绪度(诊断)/ 预览(验证)
 *  —— 四类任务体验不同,平铺会让焦点互相稀释;新建模式隐页签(恒编辑)。 */
type WorkTab = 'edit' | 'readiness' | 'preview'
const activeTab = ref<WorkTab>('edit')
/** 未保存改动快照(fillForm/selectConfig 时落;切换/新建前比对) */
const snapshot = ref('')

const selected = computed(() =>
  rows.value.find((c) => c.id === selectedId.value) ?? null)
const formOpen = computed(() => mode.value === 'create' || selected.value !== null)
/** 头卡两态:新建恒编辑;编辑态由「编辑」按钮切换 */
const headEditing = computed(() => mode.value === 'create' || metaEditing.value)
const hasBindings = computed(() =>
  sysRows.value.some((s) => slotRowsOf(s).length))
/** 左栏过滤(v7:名称 ∪ 说明 ∪ 标签 —— 帮助按用途快速找配置) */
const filteredRows = computed(() => {
  const q = listQuery.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((c) => {
    const hay = [c.name, c.description ?? '', ...(c.tags ?? [])]
      .join(' ').toLowerCase()
    return hay.includes(q)
  })
})
/** 头卡元信息(§8.10 表单态勾选集口径):换用 = 取用≠声明;缺装载 =
 *  取用条目未登记或个人池无账户 */
const totalSwaps = computed(() =>
  sysRows.value.reduce((n, s) =>
    n + slotRowsOf(s).filter((r) => r.useName !== r.alias).length, 0))
const missLoads = computed(() =>
  sysRows.value.reduce((n, s) =>
    n + slotRowsOf(s).filter((r) => !r.loaded).length, 0))

// ── ③ 枢纽数据(读面拼装;失败降级为空,不阻塞编辑面)────────────
const deps = ref<Deployment[]>([])
/** 实例行(登录口就绪度 + 表单实例过滤;loginUrl 归 (system, env) 实例) */
const instRows = ref<InstanceRow[]>([])
/** 个人池账户(C3a 装载就绪链 + 表单身份表行内解析 + Ping All 拨测目标;
 *  账户化形状补 id —— testConnection 需要) */
const authRows = ref<Array<{ id: number; system: string | null; envId: number | null;
                            username?: string; isDefault?: boolean | null }>>([])
const scenOptions = ref<Array<{ id: string; name: string }>>([])
/** 翻页上限外还有场景(>1000)时提示 —— 下拉是选择面不是台账,截断可接受 */
const scenCapped = ref(false)
/** 主档(服务选项 + 装载坐标 baseService → system + 说明) */
const svcRows = ref<ServiceRow[]>([])
/** 旁路面失败标记(FE-02):静默降级不再伪装成空数据/未装载 */
const authFailed = ref(false)
const svcRowsFailed = ref(false)
const instRowsFailed = ref(false)
const scenOptionsFailed = ref(false)
/** 旁路降级横幅文案(只列失败面;全部成功 = 空串不渲染) */
const bypassDegraded = computed(() => {
  const faces = [
    authFailed.value && '账户(装载判定)',
    svcRowsFailed.value && '主档(服务选项)',
    instRowsFailed.value && '实例(登录口)',
    scenOptionsFailed.value && '场景(预览下拉)',
  ].filter(Boolean) as string[]
  return faces.length ? `${faces.join(' / ')}读取失败 —— 相关列显示「读取失败」,不代表真实状态` : ''
})

// ── 写面注册簿数据(懒加载,静默降级;单一数据源 = binds)──────────
/** 逐服务身份条目表(listAliases base 过滤;与 listAllAliases 同口径) */
const aliasCache = ref<Record<string, ServiceAliasRow[]>>({})
/** 逐服务注册表总条数(截断提示:>200 未全量载入) */
const aliasTotal = ref<Record<string, number>>({})
/** 逐服务条目加载状态:loading = 占位;done 后看 cache 决定形态 */
const aliasLoad = ref<Record<string, 'loading' | 'done' | 'error'>>({})

// ── Ping All 状态(地址 ping + 换用账户拨测;结果就地渲染)────────
const pingAllRunning = ref(false)
const pingAllResult = ref('')
const pingAllOk = ref(false)
/** 逐部署行 ping 结果:key = `${service}#${envId}` */
const depPing = ref<Record<string, PingResult>>({})
/** 逐换用条目拨测结果:key = 条目名 */
const slotProbe = ref<Record<string, TestResult>>({})

async function ensureAliases(service: string): Promise<void> {
  if (!service || aliasLoad.value[service] === 'loading'
    || aliasLoad.value[service] === 'done') return
  aliasLoad.value = { ...aliasLoad.value, [service]: 'loading' }
  try {
    const page = await listAliases({ base: service, page_size: 200 })
    aliasCache.value = { ...aliasCache.value, [service]: page.items }
    aliasTotal.value = { ...aliasTotal.value, [service]: page.total }
    aliasLoad.value = { ...aliasLoad.value, [service]: 'done' }
  } catch {
    // FE-02:失败≠空表 —— error 态让节点徽章/就绪判定显「读取失败」,
    // 不再与「未登记条目」混淆;下次 ensure 可重试
    aliasLoad.value = { ...aliasLoad.value, [service]: 'error' }
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

// ── v4 派生视图:左栏副行 / 节点摘要 / 展开态 ────────────────────
/** 左栏副行:N 服务 · M 换用 */
function rowSummary(c: ExecConfigRow): string {
  const svcs = c.systems?.length ?? 0
  const swaps = (c.systems ?? []).reduce(
    (n, s) => n + Object.keys(s.bindings ?? {}).length, 0)
  return `${svcs} 服务 · ${swaps} 换用`
}
/** 节点摘要(§8.10 勾选集口径):条目 = 圈定数,换用 = 圈定行上有 bind,
 *  缺装载 = 取用条目未登记或个人池无账户 */
function nodeSummary(s: SysRow): { entries: number; swaps: number; missing: number } {
  const rows = slotRowsOf(s)
  return {
    entries: rows.length,
    swaps: rows.filter((r) => r.useName !== r.alias).length,
    missing: rows.filter((r) => !r.loaded).length,
  }
}
/** 节点注册表加载态:loading = 占位;empty = 该服务未登记条目(不能报
 *  「装载齐」—— 0 条目时「齐」是误导);ok = 正常统计 */
function nodeLoadState(s: SysRow): 'loading' | 'error' | 'empty' | 'ok' {
  if (aliasLoad.value[s.service] === 'loading') return 'loading'
  if (aliasLoad.value[s.service] === 'error') return 'error'
  return entriesOf(s).length ? 'ok' : 'empty'
}
/** 表单态服务集合(去重;地址矩阵 / Ping All 地址目标 / 头卡计数用) */
const formServices = computed(() =>
  [...new Set(sysRows.value.map((s) => s.service.trim()).filter(Boolean))])
/** 节点只读/编辑两态(v6):默认只读;新加节点即编辑;fillForm 复位 */
const editing = ref<Record<number, boolean>>({})
function isEditing(i: number): boolean {
  return editing.value[i] === true
}
function toggleEdit(i: number): void {
  editing.value = { ...editing.value, [i]: !isEditing(i) }
}
/** §8.10 候选(可加入的调用身份):注册表行 − 已选 − 搜索词 − 实例过滤,
 *  按环境分组(选中即加入;不再全量罗列) */
function pickGroups(s: SysRow): Array<{ env: string; items: ServiceAliasRow[] }> {
  const chosen = new Set(chosenAliases(s))
  const q = s.pickQuery.trim().toLowerCase()
  const groups = new Map<string, ServiceAliasRow[]>()
  for (const a of entriesOf(s)) {
    if (chosen.has(a.aliasName)) continue
    if (s.instanceFilter && a.envId !== Number(s.instanceFilter)) continue
    if (q) {
      const hay = [a.aliasName, a.display ?? '', a.refUsername ?? '']
        .join(' ').toLowerCase()
      if (!hay.includes(q)) continue
    }
    const env = a.envId != null ? envName(a.envId) : '无环境'
    const bucket = groups.get(env)
    if (bucket) bucket.push(a)
    else groups.set(env, [a])
  }
  return [...groups.entries()].map(([env, items]) => ({ env, items }))
}
function pickCount(s: SysRow): number {
  return pickGroups(s).reduce((n, g) => n + g.items.length, 0)
}
/** 候选下拉选中即加入(下拉自身复位,保持「+ 选择加入」占位语义) */
function addUseFromPick(s: SysRow, ev: Event): void {
  const sel = ev.target as HTMLSelectElement
  const alias = sel.value
  if (alias) toggleUse(s, alias, true)
  sel.value = ''
}
/** 注册表加载截断(page_size 200):提示去服务子页管理 */
function registryTruncated(s: SysRow): boolean {
  const total = aliasTotal.value[s.service] ?? 0
  return total > entriesOf(s).length
}
/** 就绪度页签角标 = 缺地址行 + 圈定身份缺裂数(§8.10 表单态勾选集口径;
 *  0 不显;该服务注册表加载完成后再计条目缺,避免初载误报) */
const readinessIssues = computed(() => {
  if (mode.value !== 'edit' && !selected.value) return 0
  let n = 0
  for (const s of sysRows.value) {
    if (!s.service) continue
    for (const r of matrixOf(s.service).rows) if (!r.baseUrl) n += 1
    if (aliasLoad.value[s.service] === 'done') {
      n += slotRowsOf(s).filter((r) => !r.loaded).length
    }
  }
  return n
})
function isExpanded(i: number): boolean {
  return expanded.value[i] !== false
}
function toggleNode(i: number): void {
  expanded.value = { ...expanded.value, [i]: !isExpanded(i) }
}
/** 追加节点(虚线大卡):新行默认展开且直接进入编辑态 */
function addNode(): void {
  sysRows.value.push({ service: '', aliases: [], instanceFilter: '',
                       pickQuery: '', binds: [], carries: [] })
  const i = sysRows.value.length - 1
  expanded.value = { ...expanded.value, [i]: true }
  editing.value = { ...editing.value, [i]: true }
}

// ── 表单 v2 派生视图(注册表行 → binds/carries 单一数据源)────────
/** §8.10 圈定集(声明侧):行内勾选 ∪ 存量绑定声明键(存量绑定 ∉ 注册表,
 *  无行可勾,恒视为已纳入 —— payloadOf 同口径并入) */
function chosenAliases(s: SysRow): string[] {
  const inTable = new Set(entriesOf(s).map((a) => a.aliasName))
  const out = [...s.aliases]
  for (const b of s.binds) {
    if (b.alias && !inTable.has(b.alias) && !out.includes(b.alias)) out.push(b.alias)
  }
  return out
}
/** 加入/移除:移除时一并移除该行换用 bind(不用即不换) */
function toggleUse(s: SysRow, alias: string, on: boolean): void {
  const i = s.aliases.indexOf(alias)
  if (on) {
    if (i < 0) s.aliases.push(alias)
    return
  }
  if (i >= 0) s.aliases.splice(i, 1)
  const bi = s.binds.findIndex((b) => b.alias === alias)
  if (bi >= 0) s.binds.splice(bi, 1)
}
/** 所选条目 → 取用行(换用后;无换用 = 自身):row = 该服务注册表行,
 *  跨服务换用/未登记回落 faceMeta 定向检索;loaded = 取用条目 ref 在
 *  个人池解析到账户。就绪度装载面板 / Ping All 拨测 / 摘要统计共用。 */
interface SlotRow {
  alias: string; useName: string
  use: ServiceAliasRow | null
  loaded: boolean
  /** 取用条目解析不到的原因可能是读取失败(FE-02)而非未登记 */
  useFailed: boolean
  /** 账户面读取失败时 loaded=false 不代表缺账户(FE-02) */
  loadedFailed: boolean
}
function slotRowsOf(s: SysRow): SlotRow[] {
  return chosenAliases(s).map((alias) => {
    const useName = swapOf(s, alias) || alias
    const use = entriesOf(s).find((a) => a.aliasName === useName)
      ?? faceMeta.value[useName] ?? null
    const useFailed = !use && (faceError.value[useName] === true
      || aliasLoad.value[s.service] === 'error')
    return {
      alias, useName, use,
      loaded: !!use && accountRowOf(use) != null,
      useFailed,
      loadedFailed: !!use && accountRowOf(use) == null && authFailed.value,
    }
  })
}
/** 该服务的注册表条目(未加载 = 空) */
function entriesOf(s: SysRow): ServiceAliasRow[] {
  return aliasCache.value[s.service] ?? []
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
/** 条目在个人池解析到的账户行(前端单源 pickAccountLikeBackend,镜像
 *  后端 pick_bindings/_pick_one;§8.3 引用不校验标签,默认账户跨标签
 *  共用正常)—— slotRowsOf(装载判定)/ Ping All 拨测目标共用。 */
function accountRowOf(a: ServiceAliasRow):
    { id: number; username?: string } | null {
  const sys = systemOfBase(a.baseService)
  if (!sys) return null
  return pickAccountLikeBackend(authRows.value, sys, a) ?? null
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
/** faceMeta 定向检索失败标记(FE-02):null ≠ 未登记,可能是查不到 */
const faceError = ref<Record<string, boolean>>({})
const facesLoaded = ref(false)
async function loadFacesFor(c: ExecConfigRow): Promise<void> {
  const names = [...new Set(c.systems.flatMap((s) => [
    ...Object.keys(s.bindings),
    ...Object.values(s.bindings),
  ]))]
  const out: Record<string, ServiceAliasRow | null> = {}
  const errs = { ...faceError.value }
  await Promise.all(names.map(async (name) => {
    try {
      const env = await listAliases({ q: name, page_size: 10 })
      out[name] = env.items.find((a) => a.aliasName === name) ?? null
      delete errs[name]
    } catch {
      out[name] = null
      errs[name] = true
    }
  }))
  faceMeta.value = out
  faceError.value = errs
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

// ── Ping All:地址 ping(部署行)+ 绑定账户拨测(串行,ServiceAdmin
//    testAllSlots 范式);场景声明条目不在本页知识范围,不测 ─────────
function depPingKey(service: string, envId: number): string {
  return `${service}#${envId}`
}
function pingText(r: PingResult): string {
  return r.ok ? `${r.statusCode ?? '?'} · ${r.latencyMs ?? '?'}ms` : '不可达'
}
async function pingAll(): Promise<void> {
  const c = selected.value
  if (!c || pingAllRunning.value) return
  // 目标(§8.10 表单态勾选集口径):全部圈定服务的部署行(地址)+
  // 圈定身份的取用条目(换用后)解析账户(拨测;未圈定/未登记不计)
  const pingTargets = sysRows.value
    .filter((s) => !!s.service)
    .flatMap((s) => deps.value.filter((d) => d.baseService === s.service))
  const probeTargets: Array<{ slot: string; id: number }> = []
  for (const s of sysRows.value) {
    for (const r of slotRowsOf(s)) {
      if (!r.use) continue
      const acc = accountRowOf(r.use)
      if (acc) probeTargets.push({ slot: r.useName, id: acc.id })
    }
  }
  if (!pingTargets.length && !probeTargets.length) {
    toast.warning('没有可检测的目标 —— 本配置没有服务部署行,也没有已装载的换用条目')
    return
  }
  const startId = c.id
  /** 运行中切换了配置 → 本轮结果作废(不写入新配置的视图) */
  const stale = (): boolean => selectedId.value !== startId
  pingAllRunning.value = true
  pingAllResult.value = ''
  depPing.value = {}
  slotProbe.value = {}
  let ok = 0
  let total = 0
  for (const d of pingTargets) {
    if (stale()) break
    total += 1
    try {
      const r = await pingDeployment(d.id)
      if (!stale()) {
        depPing.value = { ...depPing.value, [depPingKey(d.baseService, d.envId)]: r }
      }
      if (r.ok) ok += 1
    } catch (e) {
      // 拨测/测速失败是结果不是异常(ServiceAdmin 同款前端合成)
      if (!stale()) {
        depPing.value = {
          ...depPing.value,
          [depPingKey(d.baseService, d.envId)]:
            { ok: false, statusCode: null, latencyMs: null, message: msg(e) },
        }
      }
    }
  }
  for (const p of probeTargets) {
    if (stale()) break
    total += 1
    try {
      const r = await testConnection(p.id)
      if (!stale()) {
        slotProbe.value = { ...slotProbe.value, [p.slot]: r }
      }
      if (r.ok) ok += 1
    } catch (e) {
      if (!stale()) {
        slotProbe.value = {
          ...slotProbe.value,
          [p.slot]: { ok: false, status_code: null, message: msg(e) },
        }
      }
    }
  }
  pingAllRunning.value = false
  if (stale()) return
  pingAllResult.value = `${ok}/${total} 正常`
  pingAllOk.value = ok === total
  if (pingAllOk.value) toast.success(`全部 ${total} 项连通正常`)
  else toast.warning(`${total - ok} 项检测失败`)
}

async function loadHub(c: ExecConfigRow): Promise<void> {
  const jobs: Promise<void>[] = [
    // 绑定别名的注册表状态(定向检索,永不全量)
    loadFacesFor(c),
    // 部署矩阵(§8.2 配置去 env 后地址就绪度按全环境矩阵展示;实例行
    // 与表单共用,在 onMounted 旁路拉取)
    listDeployments()
      .then((d) => { deps.value = d })
      .catch(() => { deps.value = [] }),
  ]
  await Promise.all(jobs)
}

function msg(e: unknown): string {
  // FE-08e(2026-11-20 审计):e.response.data.detail 分支删除 —— http
  // 拦截器已把一切错误归一为 ApiError(message 含 detail 摘要),原始
  // response 不可达,该分支是永不可达的死代码。
  const m = (e as { message?: unknown })?.message
  if (typeof m === 'string' && m) return m
  return String(e)
}

// ── 未保存改动快照(脏检查):fillForm / 新建落快照;切换与新建前比对,
//    有改动 → confirmAction 拦截(取消则不切换)。save/复制/删除/设默认
//    的内部刷新走 selectConfig 绕过检查(此时改动已落库)。 ──────────
function snapshotOf(): string {
  return JSON.stringify({
    name: form.value.name.trim(),
    description: form.value.description.trim(),
    tags: form.value.tags,
    systems: payloadOf(),
  })
}
function markClean(): void {
  snapshot.value = snapshotOf()
}
function isDirty(): boolean {
  return snapshot.value !== snapshotOf()
}

function fillForm(c: ExecConfigRow): void {
  form.value = {
    name: c.name,
    description: c.description ?? '',
    tags: [...(c.tags ?? [])],
  }
  metaEditing.value = false
  sysRows.value = (c.systems ?? []).map((s) => ({
    service: s.service,
    // §8.10 圈定集:新行直取;存量行缺省(未圈定)→ 按 bindings 声明键
    // 推导(老配置平滑过渡,保存时固化进 aliases)
    aliases: s.aliases?.length ? [...s.aliases] : Object.keys(s.bindings ?? {}),
    instanceFilter: '',
    pickQuery: '',
    binds: Object.entries(s.bindings ?? {}).map(([alias, slot]) => ({ alias, slot })),
    // null 三态:null → isNull(修复旧实现 null 被折成 '' 存回的丢真)
    carries: Object.entries(s.carryOverrides ?? {})
      .map(([field, value]) => ({ field, value: value ?? '', isNull: value == null })),
  }))
  // 节点展开态复位(v4:默认全展开);两态复位(v6:默认只读)
  expanded.value = {}
  editing.value = {}
  markClean()
}

/** 选定配置(内部;不做脏检查 —— 保存/复制/删除后的刷新走这里) */
function selectConfig(id: number): void {
  selectedId.value = id
  mode.value = 'edit'
  activeTab.value = 'edit'
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
  // 切换配置即清上一套的 Ping All 结果(目标集合已变)
  depPing.value = {}
  slotProbe.value = {}
  pingAllResult.value = ''
  const c = rows.value.find((r) => r.id === id)
  if (c) {
    fillForm(c)
    void loadHub(c)
  }
}

/** 左栏点选:有未保存改动 → 先确认(取消则不动) */
async function pick(id: number): Promise<void> {
  if (id === selectedId.value) return
  if (formOpen.value && isDirty()) {
    const ok = await confirmAction(
      '当前配置有未保存的改动,切换后将丢弃。', '未保存的改动',
      { type: 'warning', danger: true, confirmButtonText: '放弃并切换' })
    if (!ok) return
  }
  selectConfig(id)
}

/** 新建前选中的配置 id(取消时回选;openCreate 会置空 selectedId,
 *  cancel 的「回到该配置」分支此前因此恒不可达 → 落空白工作台) */
let createReturnId: number | null = null

async function openCreate(): Promise<void> {
  if (formOpen.value && isDirty()) {
    const ok = await confirmAction(
      '当前配置有未保存的改动,新建后将丢弃。', '未保存的改动',
      { type: 'warning', danger: true, confirmButtonText: '放弃并新建' })
    if (!ok) return
  }
  createReturnId = selectedId.value
  mode.value = 'create'
  selectedId.value = null
  activeTab.value = 'edit'
  form.value = { name: '', description: '', tags: [] }
  metaEditing.value = true   // 新建即编辑态(无只读切换)
  sysRows.value = []
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
  markClean()
}

/** 有未保存改动时先确认(设默认/复制收尾会整表单回填,静默丢编辑态
 *  是 v4.1 脏检查的漏网路径 —— 与 pick/openCreate 同一守卫) */
async function confirmDiscard(verb: string): Promise<boolean> {
  if (!formOpen.value || !isDirty()) return true
  return confirmAction(
    `当前配置有未保存的改动,${verb}后将丢弃。`, '未保存的改动',
    { type: 'warning', danger: true, confirmButtonText: `放弃并${verb}` })
}

/** 移除服务节点:该节点有绑定/carry 时先确认(误点即丢数据) */
async function removeNode(i: number): Promise<void> {
  const s = sysRows.value[i]
  if (!s) return
  const binds = s.binds.filter((b) => b.alias && b.slot).length
  const carries = s.carries.length
  if (binds || carries) {
    const name = s.service || `服务 ${i + 1}`
    const ok = await confirmAction(
      `移除「${name}」将同时丢弃其 ${binds} 条绑定与 ${carries} 条 carry 覆盖(保存后生效)。`,
      '移除服务节点', { type: 'warning', danger: true, confirmButtonText: '移除' })
    if (!ok) return
  }
  sysRows.value.splice(i, 1)
  // 索引键控状态跟排(v4/v6:expanded/editing 按节点下标)—— 不重排会让
  // 后继节点原位继承被移除节点的编辑/展开态(未经操作进入写面)。
  const reindex = (m: Record<number, boolean>): Record<number, boolean> => {
    const out: Record<number, boolean> = {}
    for (const k of Object.keys(m)) {
      const idx = Number(k)
      if (idx < i) out[idx] = m[idx]
      else if (idx > i) out[idx - 1] = m[idx]
    }
    return out
  }
  editing.value = reindex(editing.value)
  expanded.value = reindex(expanded.value)
}

function cancel(): void {
  // 取消 = 显式放弃改动,不做脏检查(内部直接回填/回空态)
  if (mode.value === 'create') {
    // 回到新建前选中的配置(openCreate 已置空 selectedId,须凭快照回选;
    // 无选区/已删则回空列表态)
    const back = createReturnId
    if (back != null && rows.value.some((r) => r.id === back)) {
      selectConfig(back)
    } else { mode.value = 'edit'; snapshot.value = '' }
  } else if (selected.value) fillForm(selected.value)
}

function payloadOf(): SystemSubConfig[] {
  return sysRows.value
    .map((s) => ({ s, service: s.service.trim() }))
    .filter(({ service }) => service)
    .map(({ s, service }) => ({
      service,
      // §8.10:圈定集 = 行内勾选 ∪ 存量绑定声明键(chosenAliases 同口径;
      // 注册表未加载完时 entriesOf 空 → binds 键全并入,与勾选集不冲突)
      aliases: [...new Set([
        ...s.aliases.map((a) => a.trim()).filter(Boolean),
        ...s.binds
          .filter((b) => b.alias && b.slot
            && !entriesOf(s).some((a) => a.aliasName === b.alias.trim()))
          .map((b) => b.alias.trim()),
      ])],
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

/** FE-05(2026-11-20 审计):保存在飞守卫 —— create 双击发双 POST(后端
 *  名唯一兜底,第二个 409 误显为失败);saving 态 + 按钮禁用。 */
const saving = ref(false)

async function save(): Promise<void> {
  if (saving.value) return
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
    // v7 配置级元信息(卡片级保存与底栏保存同一路径:全量写入)
    description: form.value.description.trim(),
    tags: [...new Set(form.value.tags.map((t) => t.trim()).filter(Boolean))],
    systems: payloadOf(),
  }
  saving.value = true
  // FE-08h(2026-11-20 审计):selectConfig 会复位到编辑页签 —— 用户停在
  // 就绪度/预览页签保存时不应被跳走;保存后恢复原页签(切配置/新建的
  // 复位语义不变)。
  const tabBefore = activeTab.value
  try {
    if (mode.value === 'create') {
      const created = await createExecConfig(body)
      await reload()
      selectConfig(created.id)
      toast.success('配置已创建')
    } else if (selectedId.value != null) {
      await updateExecConfig(selectedId.value, body)
      await reload()
      selectConfig(selectedId.value)
      toast.success('配置已保存')
    }
    activeTab.value = tabBefore
  } catch (e) { error.value = msg(e) } finally { saving.value = false }
}

async function makeDefault(): Promise<void> {
  if (!selectedId.value) return
  // 收尾 selectConfig 会整表单回填 —— 有未保存改动先确认(v4.1 脏检查
  // 漏网:设默认看似只动默认位,实则丢弃编辑态)
  if (!(await confirmDiscard('设为默认'))) return
  error.value = ''
  try {
    await setDefaultExecConfig(selectedId.value)
    await reload()
    selectConfig(selectedId.value)
    toast.success('已设为默认配置')
  } catch (e) { error.value = msg(e) }
}

async function doCopy(): Promise<void> {
  if (!selectedId.value) return
  // 切到副本必然丢弃当前编辑态 —— 有未保存改动先确认(同上)
  if (!(await confirmDiscard('复制'))) return
  error.value = ''
  const name = copyName.value.trim()
  if (!name) { error.value = '新配置名不能为空'; return }
  try {
    const dup = await copyExecConfig(selectedId.value, name)
    copyArmed.value = false
    copyName.value = ''
    await reload()
    selectConfig(dup.id)
    toast.success(`已复制为「${name}」`)
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
    if (first) selectConfig(first.id)
    else { selectedId.value = null; mode.value = 'edit'; snapshot.value = '' }
    toast.success('配置已删除')
  } catch (e) { error.value = msg(e) }
}

/** 预览场景候选:翻页取全(收尾批在 ProjectConfigPanel 修过同一问题,
 *  此前本页只拉单页 50 条,'mine' 场景多于 50 时后排场景选不到);
 *  上限 10 页,超出提示。 */
async function loadScenOptions(): Promise<void> {
  const out: Array<{ id: string; name: string }> = []
  let total = Infinity
  let page = 1
  while (out.length < total && page <= 10) {
    const envelope = await listScenarioOptions(
      { page, page_size: 100, scope: 'mine' })
    total = envelope.total
    if (!envelope.items.length) break
    out.push(...envelope.items.map((i) => ({
      id: i.scenarioId, name: i.name || i.scenarioId })))
    page += 1
  }
  scenOptions.value = out
  scenCapped.value = total > out.length
}

onMounted(async () => {
  try {
    const [cfgs, envRows] = await Promise.all([
      listExecConfigs(), listEnvironments(),
    ])
    rows.value = cfgs
    envs.value = envRows
    if (cfgs.length) selectConfig(cfgs[0].id)
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
  // 旁路数据(一次性;失败置降级标记,FE-02 不再静默伪装空态):个人池账户
  // (装载判定/表单解析列/Ping All 拨测目标)、主档(服务选项 + 装载坐标 +
  // 说明;拉不到 → 服务列降级手输、坐标显 ?)、实例行(表单实例过滤 +
  // 枢纽①登录口列)、场景 options(预览下拉)
  // FE-08f:去掉 `as never` 硬转 —— AuthSession 形状与 authRows 声明
  // 结构兼容(system/envId/username/isDefault 均为宽化方向)。
  listAllAuths().then((r) => { authRows.value = r })
    .catch(() => { authFailed.value = true })
  listServices()
    .then((out) => { svcRows.value = out.services })
    .catch(() => { svcRows.value = []; svcRowsFailed.value = true })
  listInstances()
    .then((r) => { instRows.value = r })
    .catch(() => { instRows.value = []; instRowsFailed.value = true })
  loadScenOptions().catch(() => { scenOptionsFailed.value = true })
})
</script>

<style scoped>
/* ── 左栏套件列表(.svc-rail 内的行集;选中态与 .svc-tree-row.on 同读法)──
   内部分滚:标题/搜索固定,行集滚动,新建按钮贴底常驻。
   栏宽 20rem(原型 w-80 口径,24→320px):配置名/副行更从容;
   ≤1180px 仍折单列(与 .svc-split 基座断点一致,见文件末媒体查询)。 */
.svc-split {
  grid-template-columns: 20rem minmax(0, 1fr);
}
.svc-rail {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.rail-search {
  flex: none;
  width: 100%;
  margin: 0.5rem 0 0.25rem;
  padding: 0.3125rem 0.5rem;
  font: inherit;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--sl-canvas);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  outline: none;
  appearance: none;
}
.rail-search:focus { border-color: var(--sl-accent); }
.rail-rows {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  margin-top: 0.375rem;
}
.rail-row {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.4375rem 0.5rem;
  font: inherit;
  text-align: left;
  background: none;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
}
.rail-row:hover { background: var(--sl-canvas); }
.rail-row.on {
  background: var(--sl-accent-soft);
  border-left-color: var(--sl-accent);
}
.rail-name {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
}
.rail-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78125rem;
  font-weight: 600;
  color: var(--sl-ink);
}
.rail-row.on .rail-name-text { color: var(--sl-accent); }
.rail-sub {
  font-size: 0.65625rem;
  color: var(--sl-ink-3);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
/* v7:左栏标签 chip + 说明副行(帮助快速识别/选择) */
.rail-tag {
  flex: none;
  max-width: 6rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 0.3125rem;
  font-size: 0.625rem;
  line-height: 1.1rem;
  color: var(--sl-ink-3);
  background: var(--sl-canvas);
  border: 1px solid var(--sl-line);
  border-radius: 0.25rem;
}
.rail-desc {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 0.65625rem;
  color: var(--sl-ink-3);
}
.rail-empty {
  margin: 0.5rem 0;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
}
/* 预览场景下拉截断提示(与 ProjectConfigPanel .hint 同款) */
.hint { margin: 0.5rem 0 0; color: var(--sl-ink-3); font-size: 0.75rem; }
.rail-new {
  flex: none;
  margin-top: 0.625rem;
  padding: 0.4375rem 0.5rem;
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--sl-accent);
  background: none;
  border: 1px dashed var(--sl-accent);
  border-radius: 0.375rem;
  cursor: pointer;
}
.rail-new:hover { background: var(--sl-accent-soft); }

/* ── 右工作台 ─────────────────────────────────────────────────── */
.work { display: flex; flex-direction: column; gap: 0.875rem; min-width: 0; }

/* 工作台页签(与项目详情页 .tabs/.tab/.cnt 同族;alert = 就绪度缺口角标) */
.tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid var(--sl-line); }
.tab {
  border: none;
  background: none;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--sl-ink-2);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab:hover { color: var(--sl-ink); }
.tab.on { color: var(--sl-accent); border-bottom-color: var(--sl-accent); font-weight: 600; }
.cnt {
  margin-left: 0.375rem;
  font-size: 0.6875rem;
  padding: 0.0625rem 0.4375rem;
  border-radius: 62.4375rem;
  color: var(--sl-ink-3);
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.tab.on .cnt { color: var(--sl-accent); border-color: var(--sl-accent); }
.cnt.alert { color: var(--sl-bad); background: var(--sl-bad-soft); border-color: var(--sv-bad-line, var(--sl-bad)); }

/* ── 套件头卡(v7 两态 + 说明/标签)────────────────────────────── */
.head-card.editing { border-color: var(--sl-accent); }
.head-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 45rem;
  margin-bottom: 0.375rem;
}
.head-row .lb { flex: none; min-width: 2.25rem; font-size: 0.71875rem; color: var(--sl-ink-3); }
/* TagInput 是子组件:铺满剩余宽度 */
.head-row :deep(.tag-input) { flex: 1; min-width: 0; }
.meta-name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.meta-name {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--sl-ink);
}
.meta-desc {
  margin: 0.375rem 0 0;
  max-width: 60rem;
  font-size: 0.78125rem;
  line-height: 1.5;
  color: var(--sl-ink-2);
}
.meta-desc.empty { color: var(--sl-ink-3); }
.head-meta {
  margin: 0.5rem 0 0;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.head-meta .miss { color: var(--sl-warn); font-weight: 600; }
.head-acts {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.625rem;
  padding-top: 0.625rem;
  border-top: 1px solid var(--sl-divider);
  flex-wrap: wrap;
}
/* 取消/保存右对齐(配置级动作居左) */
.head-acts-fill { flex: 1 1 auto; }

/* 节点卡(v4 原型系统节点卡 .slib 化;v6 两态 + 视觉升级) */
.node {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-left: 3px solid var(--sl-line);
  transition: border-color 0.15s ease;
}
/* 编辑中:左侧 accent 色条 + 实边强调 */
.node.editing {
  border-left-color: var(--sl-accent);
  border-color: var(--sl-accent);
  box-shadow: 0 2px 10px var(--sl-accent-soft);
}
.node-head {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}
.node-idx {
  flex: none;
  width: 1.625rem;
  height: 1.625rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sl-accent-soft);
  color: var(--sl-accent);
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 700;
}
.node-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
.node-title-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.node-svc {
  max-width: 25rem;
  font-size: 0.875rem;
  font-weight: 600;
}
.node-toggle { flex: none; }
.node-sub {
  margin: 0;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
}
.node-opers {
  flex: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
/* 节点状态徽章组:贴服务选框(未圈选 / 条目·换用·装载 同一展示位) */
.node-status {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
}
/* 只读态:已选身份紧凑列表(零控件) */
.node-view { display: flex; flex-direction: column; gap: 0.375rem; }
/* 编辑态选择行:搜索 + 候选下拉 */
.pick-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.pick-q { max-width: 16rem; }
.pick-sel { min-width: 12rem; max-width: 22.5rem; }
/* 收起态摘要行 */
.node-fold {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
  font-size: 0.75rem;
  color: var(--sl-ink-2);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.node-fold .fold-sep { color: var(--sl-ink-3); }
.node-fold .miss { color: var(--sl-warn); font-weight: 600; }

/* 追加节点虚线大卡(原型 Add System Matrix) */
.node-add {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 1.125rem;
  font: inherit;
  background: transparent;
  border: 2px dashed var(--sl-line);
  border-radius: 0.625rem;
  cursor: pointer;
  transition: border-color 0.12s ease, background 0.12s ease, color 0.12s ease;
}
.node-add:hover {
  border-color: var(--sl-accent);
  background: var(--sl-canvas);
}
.node-add-title { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink-2); }
.node-add:hover .node-add-title { color: var(--sl-accent); }
.node-add-sub { font-size: 0.71875rem; color: var(--sl-ink-3); }

/* ── 既有表单形制(v2/v3 原样迁移)────────────────────────────── */
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

/* 身份条目表(只列已选行,v6:选择经搜索+候选下拉) */
.ident { display: flex; flex-direction: column; gap: 0.375rem; }
.ident-head { margin: 0; font-size: 0.71875rem; font-weight: 700; color: var(--sl-ink-2); }

.hub { display: flex; flex-direction: column; gap: 0.875rem; }
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

/* ── 右栏随栏宽收窄的自适应 ─────────────────────────────────────── */
/* 长地址/等宽 id 不撑破表格(地址矩阵、服务列表的服务名/描述等) */
.slib-table .mono { word-break: break-all; }
/* 就绪度/节点表在窄右栏下允许横向滚动兜底(不压坏列) */
.hub .svc-panel { overflow-x: auto; }

/* 窄屏(≤1180px)折单列:与 service-area.css 基座断点一致;scoped 覆盖
   的 grid 列定义特异性更高,需在此同步复位,否则基座媒体查询被压掉。 */
@media (max-width: 1180px) {
  .svc-split { grid-template-columns: minmax(0, 1fr); }
  .svc-rail { position: static; max-height: none; }
}
</style>
