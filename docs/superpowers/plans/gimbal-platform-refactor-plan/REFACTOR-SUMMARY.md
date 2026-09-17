# 前端重构实施总结 — feat/frontend-signal-refactor 分支

> 对应方案:`docs/superpowers/plans/gimbal-platform-refactor-plan/plan.md`(v2.2 定稿 + 实施进度块)
> 分支:26 个提交,基线 d3dcdf50,未推送。全量 907 条测试绿 / vue-tsc 0 错 / vite build 通过。

## 一、交付总览

| 阶段 | 内容 | 关键提交 |
|---|---|---|
| Phase 0 | Tailwind v3.4 双栈接入 + Signal token + shadcn-vue 组件族 | 9c93d21 / 1b6f347 |
| Phase 1 | ElMessage→toast、ElMessageBox→confirmAction(交叉切面);四域侧边栏 + collapsed 面包屑 + /home | c7feecd / 1352649 / 4a3747f |
| 批次 0 | 数据集独立路由退役(D1),编辑/删除/新建能力收拢进方案工作台 | 6c072bb / c5803db / 94a0193 |
| 批次 1 | 登录/注册迁移新栈;Enter 双发回归修复 | c00bbc7 / f5326c9 |
| 表单范式 | vee-validate v4 + zod + shadcn Form 族(方案 A);zod 锁 3.24.4 | b4af2c9 |
| 批次 2 | 用户管理 / 传递字段 / 认证管理(admin 三页) | 54c37c0→0287290 |
| 批次 3 | 常量池 / 适配中心(含子组件随迁)/ 批次详情 | 172a9bb→36dc845 |
| 批次 4 | 执行历史 / 详情;状态色统一 Signal;失败数可点深链 | cb74233 |
| 批次 5 | 场景详情:断言覆盖率徽标(新建)+ 修订三项 | 07423ba |
| 批次 6 | 断言注册表 / schemes 族 / 共享组件 / 步骤组件族 / Scenarios / OpConstructDialog | e35b95b→ba1330f |
| §7 registry | WorkbenchCardDef + 卡片宿主 + 常量池首张卡 | 59f3209 |
| 工作台 v2 | 组装能力:市场添加 / 移除 / 拖拽排序,按用户持久化;新增最近执行、收藏场景卡 | 91d977b / d2d2f95 / 7bcfd55 / 4d94532 |
| Phase 3 | **Element Plus 彻底退场**(依赖卸载 / main.ts 摘除 / override.css 退役 / preflight 复位 / dev 页退役 / 死 action 清理) | b0cdab0 |

## 二、关键架构决策(均已记入方案文档)

1. **表单范式 A**:vee-validate v4 + zod + shadcn Form 族,统一组合式写法
   (`useForm` + 原生 `<form @submit="handleSubmit(...)">` + `FormField/FormMessage`)。
   版本硬约束:`@vee-validate/zod@4.15` 对 zod 3.25.x 混合内核不兼容,**锁 zod@3.24.4**。
2. **确认流单一出口**:全站确认/输入弹窗走 `confirmAction/promptAction`(confirmAction 单测
   兜底取消/ESC 语义);ElMessageBox 五处直调清零。
3. **toast 单一真源**:`utils/toast.ts`(reactive 队列 + ToastHost),143 处调用点一次迁移。
4. **D1 能力承接**:数据集路由退役后,新建/编辑/删除/选中全部在工作台数据区可做;
   审计教训沉淀:**退役页面独占的能力不能只查调用方断链,要对照被删文件的能力清单**
   (批次 0 曾漏编辑能力,后补齐双模式对话框 + TSV/CSV 粘贴 + CSV 导出)。
5. **§7 工作台**:WorkbenchCardDef 集中注册(懒加载/adminOnly/span);
   WorkbenchCardSlot 统一框架样式 + onErrorCaptured 故障隔离;
   组装 = 卡片市场 + 槽层把手/移除钮 + vuedraggable,布局按用户分键存 localStorage。

## 三、多轮评审结论(四轮:架构/状态流/测试/a11y)

**无 P0/P1。** 遗留:
- ~~P2 admin 降级幽灵卡~~(已随本文档提交修复:defOf 回退全量 registry)
- P3 清单(记录在案,不阻断):
  - 死 CSS 规则 18 处(指向已卸载 EP 组件的 `:deep(.el-*)`,清扫提交待做)
  - FieldStateSearch 用 6 个 `--el-*` 变量(有 fallback 值,视觉未坏;建议换 Signal 变量)
  - 复制失败分支(copyText reject → toast.warning)无测试
  - 拖拽把手无键盘通路(可后续加 Enter+方向键或上移/下移菜单项)
  - 刷新时 /home 布局有一次默认序→用户序的跳变(fetchMe 完成前渲染)
  - 复制钮仅 title 无 aria-label(读屏器部分配置下不朗读)

**测试纪律沉淀**(散见各提交,此处汇总):
- shadcn Dialog/Dropdown/Drawer 经 Portal 渲染 → 断言用 body 查询(DOMWrapper);
  Dialog Portal 的 attrs 穿透不可查询,data-testid 放内层真实元素
- reka TabsTrigger/Select 在 jsdom 不响应合成 click(Tabs 用 keydown Enter,
  Select 只断言触发器在场);Switch = button[role=switch]
- zod safeParseAsync 管线异步 → 断言用 vi.waitFor,双 flushPromises 不可靠
- vee-validate Input 更新载荷是 string|number → handler 统一 String() 收窄
- 属性绑定里的尖括号字面量(如 `${auth.<alias>.*}`)进文本节点必须实体转义
- store 会渲染 mock 返回值 → api mock 必须回完整对象;共享模块总线的组件测试
  卸载放 afterEach

## 四、验收状态

- **已达成**:方案 §五 完成标准的全部代码项(全路由新栈、EP 从 package.json 移除、
  测试全绿、vue-tsc 0 错);原型修订清单随批次全部落地;故障隔离实战验证一次
  (ConstantsSummaryCard 渲染崩溃被 §7 第 4 条接住,未白屏)
- **唯一遗留**:全路由侧边栏模式手动走查(Phase 1 验收条款,需后端在场;
  三服务已在本地跑通:plate 8765 / backend 8000 / vite 5173,代理链路已验证)

## 五、遗留技术债(均已在方案文档登记,不阻断)

- OpConstructDialog 曾为登记清零项,**已在批次 6 迁移完成**;全站业务面 el-* = 0,
  仅 /dev/dual-stack 验证页保留(Phase 3 已随本分支退役该页路由与视图——见 b0cdab0)
- store 数据集死 action(saveDataSet/removeDataSet)已随 Phase 3 清理移除
- 可选优化:上文 P3 清单
