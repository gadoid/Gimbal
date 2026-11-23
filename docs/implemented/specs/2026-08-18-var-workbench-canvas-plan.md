# 变量工作台迁移 — 实现计划 (2026-08-18)

设计文档: 2026-08-18-var-workbench-canvas-design.md(同目录)
分支: strbody_avaliable;每个 Task 一个 commit,带 Co-Authored-By。

## Task 顺序与依赖

```
T1 var-registry 纯函数层 ──→ T5 测试收尾(无依赖,可并行验证)
T2 FieldForm 下拉(门控,独立可用)
T3 Canvas 接线(依赖 T1 的注册表数据 + T2 的 emits)
T4 Config 摘除(独立)
```

顺序执行 T1 → T2 → T3 → T4 → T5。T3 是集成点,风险最高,放在两个
可独立验证的层之后。

---

## Task 1 — var-registry.ts: assignVarRefs + order 重定向 (设计 #10)

文件: src/gimbal-platform/frontend/src/utils/var-registry.ts
测试: src/gimbal-platform/frontend/src/utils/__tests__/var-registry.test.ts

1. 新增 `assignVarRefs(steps: StepLike[]): VarRefSite[]`
   - StepLike 增加可选 `strategy[].source`(assign 字段)
   - 收集 rule: `typeof source === 'string' && source.startsWith('$.')`
     → name = source.slice(2) 首段(到 `.` 或尾,变量名是顶层 key)
     — 嵌套 source(如 `$.resp.data.x`)取顶层 `resp`?不取 — 只匹配
     **恰好 `$.<name>` 整体形状**(变量提升都是顶层 key,嵌套读法属于
     scratch 路径,不是提升变量)。site.where = 'strategy', detail = `strategy[j].source`
2. `checkVarRefs` 改造:
   - 现有 `${var.x}` 循环里,entry.origin==='extract' 时的 order 判定**删除**
     (config 出身不判 order 的分支保留,落空进 dangling/missing_column 不变)
   - 新增第二遍: for site of assignVarRefs(steps) → entry = byName.get(name);
     entry && entry.origin==='extract' && entry.stepIdx >= site.stepIdx
     → order issue,message: `步骤 ${site.stepIdx+1} 的 assign 引用 \${$.${name}},
        但它在步骤 ${producer+1} 才产出(after_request)`
3. 测试 T1/T2/T3(见设计 §4);**先写失败测试再实现**

验收: var-registry 单测全绿(原 13 + 新 3+);不触碰其他文件。

## Task 2 — FieldForm: 字段下拉菜单(设计 #4/#5 前半,门控)

文件: src/gimbal-platform/frontend/src/components/composer/FieldForm.vue
测试: components/composer/__tests__/FieldForm.test.ts(已有文件,增补)

1. props 增: `fieldActions?: boolean`(门控);`varChoices?: { name, origin, stepIdx }[]`
   (引用子列表数据,Canvas 传 config 出身);`injectChoices?: 同形状 + disabled`
   (注入子列表数据);emits 增: `fieldExtract/fieldAssign/fieldAssert/varInsert`
2. 模板: text 控件组(input 尾)加 el-dropdown ▾(v-if="fieldActions");
   四菜单项;两个子列表用 el-dropdown 嵌套子菜单或二级 popover
   (实现取简: el-dropdown-item divided 触发 popover,复用现有 var-pop 样式)
3. **删除旧 Ⓥ popover**(var-btn 与 var-pop 段)与 varEntries prop —
   被菜单"引用共享变量"取代;textarea/json 控件的 Ⓥ 一并收进菜单
   (这些控件同样挂 ▾)
4. ui_kind=number/boolean/select 控件: 菜单照挂(注入/提取对任何字段类型合法)
5. 测试 T4/T10: 门控不传无 ▾;传了四项渲染;varInsert 追加 `${var.name}` 到值尾

验收: 单测绿;**不传 fieldActions 的现有挂载(StrategyForm)模板零变化**。

## Task 3 — Canvas: 接线(设计 #1/#2/#5/#6/#8,集成点)

文件: src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue
       src/gimbal-platform/frontend/src/components/composer/VariableRegistryPanel.vue
测试: components/composer/__tests__/CaseComposerCanvas.test.ts(新建)

1. **VariableRegistryPanel 重写紧凑形态**: grid 单列行
   `名字 | 徽章 | 产出者`;同名 entries 聚合 → 黄标"步骤 N、M 均产出,后者生效";
   消费处信息降 title;vr-unregistered 保留。props 不变(steps/configVars)
2. Canvas col-info "step 信息"块下挂 `<VariableRegistryPanel :steps="local"
   :config-vars="draftStore.draft?.definition?.config?.vars" />`
3. FieldForm 接线: fieldActions=true;varChoices=config 出身(+数据集提示行);
   injectChoices=extract 出身 map(产出步<当前步 → 可选;≥ → disabled+标"步骤 N 才产出")
4. handlers:
   - onFieldExtract(f): target=f.name;expression= currentAssertable 精确匹配
     (`$.data.${f.name}` 优先,其次 `$.${f.name}`,命中 assertable 才用);
     未命中 → `$.data.${f.name}` 兜底;push extract 骨架(scope:'scenario');展开
   - onFieldAssign(f, name): push assign 骨架 source=`$.${name}`,
     target=f.path.replace(/^\$\./, '$.request_body.');展开
   - onFieldAssert(f): target 同 extract 匹配逻辑;operator:'exists';展开
   - onVarInsert(f, name): f 值尾追加 `${var.name}`(原 Ⓥ 行为)
   - 三个快捷创建都走 justAddedStrategyIdx(现有引导);降级路径同样可用
     (骨架直接 push,不依赖 strategyKinds)
5. **addExtract scope 'step'→'scenario'**(设计 #8,降级 UI 的手动 extract)
6. VarSelectorModal(headers Ⓥ)分流: extract 出身条目 disabled +
   提示"响应变量不能进 headers,请在请求体字段上注入"(设计 #7)
7. 测试 T5/T6/T7/T8/T9 + T12(挂载级,mock plate 代理 API)

验收: Canvas 新测试全绿;手动冒烟(添加字段→四个菜单动作→策略卡展开→变量列表更新)。

## Task 4 — Config 摘除(设计 #11)

文件: src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue

1. 删 `<VariableRegistryPanel>` 与 import;删 `steps` prop 与 varsDict computed
   (varsDict 仅供面板);CaseComposer.vue 模板里 `:steps="definition.steps"` 一并删
2. 测试 T11: 现有 4 回声用例仍绿;渲染文本不含"变量注册表"(config 测试增一条断言)

验收: 全量 vitest 绿。

## Task 5 — 收尾

1. 全量 `npx vitest run`(在 src/gimbal-platform/frontend)目标: 17 files
   / 109+ tests 全绿(97 现有 + 新增,只增不减)
2. `npx vite build` 绿
3. 手动冒烟清单: 新建场景→添加接口→字段四菜单动作→变量列表三来源展示
   (config/extract/同名)→headers Ⓥ 分流→保存→/convert 预校验通过
4. 逐 Task commit(message 中文,引用设计编号 #N)

## 风险与回退

- 最大风险 T3(集成): FieldForm emits 命名/子列表交互错 → 菜单交互先行在
  FieldForm 单测锁死,T3 只做接线
- assignVarRefs 只认整体 `$.<name>` 形状(见 T1.1),窄匹配避免误报;
  宁可漏(用户手写嵌套 source 自己负责)不可误
- 回退单元 = Task 级 commit revert;T1/T2/T4 独立无害,T3 revert 即回到现状
