# ADR 0004:plate 结构重构——Markdown 方言 + 三概念 + 主线流程 + 内容寻址构件

## 状态

已定稿 / Accepted（2026-10-07；设计真源 `claude/plate-design.md`，修订九版）。

## 背景

plate 此前以 Python 实例（`systems/*/endpoint/*.py`）为 M1 真源：`app.py` lifespan 写死导入、dim 注册散落在各系统 `dimensions.py`、C1 内存注册与「文件为真源」冲突、contract_gen 生成物「可手改 + 默认不覆盖」构成双真源协议；注册顺序在 `by_route`（后写覆盖）与 `_ep_key_map`（先注册者胜）两处携带相反语义。

## 决策

1. **P1**：Markdown 方言（frontmatter + `gimbal:` 围栏块，块体 YAML）是被测系统 M1 的唯一真源；M2 仍是封闭 pydantic 模型；不生成 Python 实例文件。
2. **三概念**：交付物（= 文件，frontmatter 记 id/type）、块（定义块 endpoint/system/defaults、片段块 statement、词条块 term）、词条（概念身份，语义关联只经词条）。
3. **P2 主线流程**：编写（人 / Agent）→ 评审 → 入库；不走自动生成（contract_gen / twin_generator 降为参考输入，附录 C 记录冲突）。两道闸门：入库（CI 执行 F/T/S 阻塞级规则）与发布（只检查不编辑）。
4. **P5 协议中立**：`Binding` 判别联合与执行器 ProtocolRegistry 注册的协议一一对应；binding 模型随批次 C 收回 plate（推翻 2026-09-27「plate 只承载 protocol 判别字段」的拍板——本次重构即该反转的执行）。
5. **P7 + 内容寻址**：文件为全部数据的存放地；release 冻结为 `plate_artifacts/objects/<hash>.json`（全局对象池）+ 每系统 manifest（对象 hash、call 投影、模板 / 方言 / M2 版本）。hash 规范序列化排除默认值字段（P8 加法演进的配套，防适配风暴与去重失效）。
6. **8n**：删除 `EndpointSpec.version` / `updated_at`（每系统常量与构造期假时间戳）；版本管理四层承担——历史归 git、版本归 release 快照 / manifest（对象 hash；适配检测用 shape_hash）、变更归结构化 diff、消费侧钉住归 release_id。
7. dim 路由语法沿用 ADR 0002；框架自描述 dim 全局挂载，数据 dim 按系统挂载。

## 实施批次

S1-0 清理 → A1 方言内核（M2 + 解析 / 渲染 + 规范序列化 + hash golden / 往返测试先行）→ A2 消费方切换（151 接口迁移 + 平台前后端 + `spec_json`）→ B release → C 收回自描述 → D 编写评审支撑（含 CI）→ E 自举切片。CLI 入口为独立 console script `plate`（不用 `gimbal plate` 子命令，保持执行器零依赖 plate）。
