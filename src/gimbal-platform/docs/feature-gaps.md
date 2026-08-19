# V1 → V3 功能差距清单(未实现项)

> 基线:V1「我的工作台」(/cases/mine)与「共享用例」(/cases/public),
> 从 git 历史(commit `b9db8bb` 之前)恢复的功能清单,与当前 V3 场景库/编排器逐项对照。
> 已覆盖的核心链路:搜索/筛选/三 tab(我的·公共·收藏)/收藏/查看详情/执行(RunDialog,
> 含次数·并发·前缀·凭证合并策略,为 V1 超集)/发布/下架/复制/删除/导出。

## 一、待实现(建议排期)

### 1. 场景导入(影响最大)
- V1:`+ 上传用例` / `+ 提交公共用例`,接受 `.yaml/.yml/.json` 文件,
  后端 `POST /api/cases/upload`(visibility 可选 private/public)。
- 现状:V3 只有导出(行级导出 JSON),**没有导入**。存量 V1 用例无法迁移。
- 方案:后端 `POST /api/scenarios/import`(接收 plate 转换后结构或 V1 yaml,
  走 plate 校验后落库,visibility=private);前端场景库「+ 新建」旁加「导入」按钮。

### 2. 场景重命名 / 另存为
- V1:`POST /api/cases/{id}/rename`、`POST /api/cases/{id}/save-as`,
  前端 RenameInputDialog(默认名 + 同名冲突检查)。
- 现状:无重命名;「复制到我的」自动生成新 id,已覆盖大部分场景,但
  自己名下场景改名只能重建。
- 方案:后端 `PATCH /api/scenarios/{id}/meta`(仅 name/description/tags);
  前端 ⋯ 菜单加「重命名」对话框。

### 3. admin 删除他人公共场景(治理兜底)
- V1:admin 可删除公共用例(下拉门控 `authStore.isAdmin`,双重确认)。
- 现状:只有 owner 能删除/下架自己的场景;admin 无法强制处理违规公共内容。
- 方案:后端 DELETE 路由放开 admin 分支;前端 ⋯ 菜单对 admin 显示「管理员删除」。

### 4. 审核标记 / 待审筛选(取决于是否保留审核流)
- V1:公共库有 `audited` 字段(✓已审/⏳待审 列 + 按审核状态筛选);
  发布时标记「待审核」。
- 现状:无 audit 字段,发布直上公共库。
- 决策点:若公共库需要治理流程 → Scenario meta 加 `audited`,列表筛选参数 + 列;
  若不需要 → 本项作废,发布即生效。

## 二、挂起(等执行链重构后再做)

> 背景:执行、存储与执行器连接方式即将重构,以下项与执行存储强耦合,现在做会返工。

### 5. 重跑(re-run)
- V1:执行历史可重放。
- 方案(重构后):`POST /api/runs/{id}/rerun`,重放 config_json 走新 dispatcher。

### 6. 僵尸派发对账(stale reconcile)
- 现状:服务重启后 running 状态的派发永远挂起,只记 `gimbal_unavailable`。
- 方案(重构后):启动时/定时对账,超时派发标记 failed + 明确原因。

### 7. RunDialog 预选数据集
- 现状:数据集页「单条/批量运行」只能跳到编排器,不能带数据集参数预选。
- 等执行参数模型稳定后:RunDialog 支持 `?dataSetId=` 预选。

## 三、明确不做(已决策放弃)

| V1 功能 | 不做原因 |
|---|---|
| `gimbal run show` 子进程拉取步骤说明 | 引擎常驻 HTTP(:8766)取代子进程 |
| PATCH-yaml 编辑模式 | 编排器四步结构化编辑取代 |
| admin command_line 覆盖 | 引擎连接方式重构后重新设计 |
| 文件目录扫描式用例发现 | 数据库场景库取代 |
| 作者档案 popover(AuthorProfile) | M4 可选,暂以 owner 文本展示 |
| 隐藏字段前端管理(hidden-path profile) | plate 契约隐藏字段由 schema 驱动,平台侧暂不单独管理 |

## 四、验收状态参考

- 后端测试:`backend && python -m pytest tests -q`(152 通过)
- 前端:`npx vitest run`(97 通过)+ `npx vue-tsc --noEmit`
- 主链路(建场景 → 编排 → 造数据 → RunDialog 运行 → 执行历史)可日常执行,
  作为重构前基线。
