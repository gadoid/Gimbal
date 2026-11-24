# Gimbal

> **企业约束本体与 API 测试编排平台**

Gimbal 把接口契约、业务需求、PRD、数据结构、测试编排和执行证据统一到一套可版本化、可评审、可机器消费的体系中。它既能作为独立 Python 执行框架使用，也能由 **Plate + 平台后端 + Web 控制台 + Gimbal Runner** 组成可内部使用的 API 测试平台。

核心版本由单人 + AI 协作在约半年内完成。当前已经具备可内部使用的核心业务闭环，正在收口工程与运营问题，并按 **CLI 化 → Agent 集成 → Plate 多切片投影** 的方向推进 AI Native。

> **当前边界**
>
> - 核心链路：编排、版本与适配、凭证、派发、执行、结果落库、报告和外部回调已贯通。
> - AI Native：服务画像与 Plate 本体投影已预留实现位置；MCP、APIDoc、Mock 等独立外部消费方尚未交付。
> - 部署：PostgreSQL-only、单后端进程；当前不承诺多实例 HA、水平扩展或无停机滚动升级。
> - 工程事实：以[当前功能说明](docs/functional-spec/README.md)和代码、测试为准，不以历史设计稿替代实现状态。

## 核心理念

Gimbal 不是把一组测试工具拼在一起，而是用同一套约束体系连接软件交付中的不同事实切片。

1. **约束优先**：接口结构、业务规则、需求、数据和执行结果都应可校验、可追溯，而不是散落在文档和脚本里。
2. **定义与运行分离**：Plate 持有定义态事实；平台持有资产、权限和运行态；执行器只消费物化后的执行副本。
3. **单一事实源**：Markdown 交付物是 Plate 的可编辑真源，release 构件是不可变产物，内存索引和平台缓存只是派生层。
4. **图是产物形态，不是存储形态**：服务画像把接口、能力、需求、数据、场景和执行投影成关系，不要求引入图数据库。
5. **Agent 受约束参与**：Agent 可以读取本体、提出候选和解释影响，但修改必须经过 Plate 校验、预览和评审。
6. **稳定契约，自由实现**：对外 URL、对象身份和版本语义保持稳定；内部装载、索引和调度方式可以独立演进。

## 组件与职责

| 组件 | 目录 | 职责 | 不负责什么 |
|---|---|---|---|
| **Plate** | `src/gimbal_plate/` | Markdown 方言、接口/词条/片段模型、结构查询、校验、release、内容寻址构件 | 测试执行、平台用户权限、运行态资产 |
| **Gimbal Runner** | `src/gimbal/` | 编译 Plan、协议调用、策略、状态机、调度、事件、报告、Server/SSE | 多租户资产管理、跨进程执行网格 |
| **平台后端** | `src/gimbal-platform/backend/` | 用户/项目/场景/Suite、权限、身份与环境、预检、物化、队列、派发、结果与集成 | 直接协议调用、分布式执行网格 |
| **平台前端** | `src/gimbal-platform/frontend/` | 服务目录、场景编排、运行观察、调试、适配、服务画像与管理交互 | 独立业务真源、最终权限判定 |
| **交付物语料** | `systems/`、`types/` | 被测系统 Markdown 定义与交付物类型模板 | 平台运行记录 |

Plate 启动器与本地开发辅助文件位于 `src/gimbal-plate/`；Python 包本体位于 `src/gimbal_plate/`。

## 端到端链路

```text
systems/*.md + types/*.yaml
          │
          ▼
┌──────────────────────┐
│ Plate                │  解析 / 校验 / 注册 / 查询 / 修订 / 冻结
│ 定义态事实源          │
└──────────┬───────────┘
           │ HTTP / 离线构件
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│ 平台后端              │────▶│ 平台前端              │
│ 资产 / 权限 / 身份     │     │ 编排 / 运行 / 画像    │
│ 预检 / 物化 / 队列     │     └──────────────────────┘
└──────────┬───────────┘
           │ 执行副本
           ▼
┌──────────────────────┐
│ Gimbal Runner        │  编译 / 调用 / 提取 / 断言 / SSE
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ PostgreSQL            │  Execution / Row / Step / Event / Evidence
└──────────┬───────────┘
           ▼
   报告 / 通知 / Webhook / 服务画像
```

下一阶段的 AI Native 链路沿同一事实源展开：

```text
Plate 多切片事实
  接口定义 + capability + db_design + PRD + user_story
          │
          ▼
服务画像关系投影
  用途 / 上下游 / 数据支撑 / 变更影响 / 证据来源
          │
          ▼
Agent 受约束分析
  解释与建议 → Plate validate / dry-run → 人确认 → 执行反馈
```

## 快速开始

### 只使用 Runner

要求 Python 3.11+。

```bash
python -m pip install -e ".[dev]"

# 执行最小 HTTP 场景
gimbal run launch examples/hello/scenario.yaml

# 查看命令帮助
gimbal --help
plate --help
```

常用入口：

```bash
gimbal run match <GLOB>                 # 匹配并执行本地用例
gimbal run launch <PATH>                # 直接加载并执行
gimbal run show --from-path <FILE>      # 只读展示步骤索引
gimbal run server                       # 启动 Runner HTTP Server
gimbal self-check                       # 框架自检
```

### 启动完整平台

开发环境另需 Node.js 20+、Docker 和 PostgreSQL 16。

```bash
# 1. 起本地数据库
docker compose -f compose.pg.yml up -d

# 2. 安装 Runner / Plate 与平台后端
python -m pip install -e ".[dev]"
python -m pip install -e src/gimbal-platform/backend

# 3. 准备后端配置
cp -n src/gimbal-platform/backend/.env.example src/gimbal-platform/backend/.env
```

在 `src/gimbal-platform/backend/.env` 中至少配置：

- `JWT_SECRET`：持久化会话密钥；
- `FERNET_KEY`：持久化凭证加密密钥；
- `DATABASE_URL`：`postgresql+asyncpg://...`；
- `PLATE_BASE_URL=http://127.0.0.1:8890`：与下方 Plate 启动端口一致。

密钥生成示例：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

分别在不同终端启动服务：

```bash
# 终端 1：Plate（端口 8890 与前端 /plate 代理保持一致）
python src/gimbal-plate/run_plate.py --port 8890
```

```bash
# 终端 2：工作目录 src/gimbal-platform/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# 终端 3：工作目录 src/gimbal-platform/frontend
npm ci
npm run dev
```

访问：

- 平台前端：<http://localhost:5173>
- 后端 OpenAPI：<http://127.0.0.1:8000/docs>
- Plate：<http://127.0.0.1:8890>

空库首次启动会走 baseline fresh 并 stamp head；已有版本库若落后于 head，后端会拒绝启动。升级前必须备份，并在维护窗口手动执行 Alembic。完整约束见 [PG 运维 Runbook](src/gimbal-platform/docs/runbook-pg.md)。

`src/restart-services.ps1` 是当前开发机的便捷启动脚本，包含本机解释器、路径和端口，不是跨机器部署契约。

## Runner 执行模型

Runner 使用七阶段编译流水线：

```text
load → normalize → patch → desugar → expand → bind → validate
```

步骤状态：

```text
PENDING → PREPARE → INVOKING → EXTRACTING → VERIFYING → TEARDOWN
                                                      │
                                   PASSED / FAILED / ERROR / SKIPPED
```

主要扩展点：

- `StrategyExecutor`：Assign、Call、Extract、Assertion 等策略；
- `Reporter`：控制台、JSON、HTML 与自定义报告；
- `Authenticator`：认证与会话；
- EventBus / HookBus：观察事件与介入执行；
- PluginLoader：manifest、依赖解析、加载和启停。

超时与取消是协作式的；无法安全终止的协议调用线程不会被强制杀死。Runner Server 当前按单 run 串行执行。

## 服务画像与 Ontology 方向

服务画像不是普通服务详情页，而是 Plate 本体事实在平台侧的消费投影。

### 当前已实现

- 服务级热力网格：接口清单、用例覆盖、最近执行、适配告警；
- 接口级线索板：场景、执行、适配事件、自建卡和风险轨迹；
- 二度展开：场景 → 同场景引用的其他接口；
- 节点/边/象限模型：已为需求、数据、拓扑象限预留结构。

### 后续接通

- **需求切片**：endpoint → capability → rule/outcome/step → PRD/user_story；
- **数据切片**：db_design、`表.列` 锚点、attr 与 refers；
- **关系投影**：接口用途、上下游服务、数据支撑和变更影响；
- **Agent 消费**：每条判断携带源切片、锚点、修订和证据，不把模型猜测写成事实。

因此，统一关系图不需要另建独立图谱模块；它的自然落点就是 **Plate 多切片事实 + 服务画像投影 + Agent 分析**。

## 当前能力状态

| 能力 | 状态 |
|---|---|
| 接口定义、方言校验、结构查询与修订追溯 | 已实现 |
| Scenario/Suite 编排、数据与方案 | 已实现 |
| 项目权限、身份引用、凭证加密隔离 | 已实现 |
| 预检、物化、持久队列、Runner 派发与 SSE | 已实现 |
| 行/步骤/事件/证据落库、报告、重跑 | 已实现 |
| 接口差异适配、应用/回滚与过期检测 | 已实现 |
| 服务画像测试象限与卡片 | 已实现 |
| 服务画像需求/数据/拓扑多切片聚合 | 已预留，尚未完整接通 |
| 完整跨执行分析仪表盘 | 后续阶段 |
| MCP / APIDoc / Mock 独立消费方 | 尚未交付 |
| 多实例 HA / 水平扩展 | 当前不支持 |

## 部署与运行边界

- **PG-only**：SQLite 已退役；测试同样要求 PostgreSQL。
- **单后端进程**：禁止 `--reload` 和多 worker；活跃行状态、调度器和进程管理仍依赖单进程边界。
- **启动只校验 schema**：已有版本库不自动迁移；DDL 必须人工在备份窗口执行。
- **Plate 是内部服务**：无内置平台鉴权，必须放在受控网络边界后。
- **回调是 at-least-once**：不承诺 exactly-once；消费方需要幂等。
- **当前适合内部受控使用**：不能据此宣称企业级 HA、无限水平扩展或对外多租户 SaaS。

## 仓库布局

```text
.
├── systems/                       # Plate Markdown 交付物真源
├── types/                         # 交付物类型模板
├── src/
│   ├── gimbal/                    # Runner：编译、执行、协议、策略、状态机、报告
│   ├── gimbal_plate/              # Plate Python 包
│   ├── gimbal-plate/              # Plate 启动器与本地开发辅助文件
│   └── gimbal-platform/
│       ├── backend/               # FastAPI、SQLAlchemy、Alembic、业务服务
│       └── frontend/              # Vue 3 + TypeScript + Vite
├── tests/                         # Runner / Plate / 平台兼容测试
├── plugins/                       # Runner 插件
├── examples/                      # 最小 Runner 示例
├── docs/
│   ├── functional-spec/           # 按组件、按模块核实的当前功能说明
│   ├── adr/                       # 架构决策记录
│   └── implementation-issues-20261124.md
├── claude/                        # 设计背景与历史方案
├── scripts/                       # M2、迁移与工程检查脚本
├── compose.pg.yml                 # 本地 PostgreSQL 16
└── pyproject.toml                 # Runner / Plate 包与开发依赖
```

## 开发与验证

### Runner / Plate

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy src/gimbal
gimbal self-check
```

根目录 `pytest` 运行 `pyproject.toml` 中配置的默认测试集；CI 会显式覆盖 Plate、执行器、平台后端、迁移、打包和前端。

> Windows 开发提示：仓库脚本对子进程已显式 `encoding="utf-8"`（`scripts/gen_m2.py` 等），正常无需额外环境变量；个别工具链仍以本地代码页输出时，设 `PYTHONUTF8=1` 再跑即可（CI Linux 环境不受影响）。

### 平台后端

后端测试需要 PostgreSQL，并设置 `TEST_DATABASE_URL`。默认启用 pytest-xdist；单进程调试可加 `-n0`。

```bash
cd src/gimbal-platform/backend
python -m pip install -e ".[dev]"
pytest
```

### 平台前端

```bash
cd src/gimbal-platform/frontend
npm ci
npm run typecheck
npm test
npm run build
```

## 文档

- [当前功能说明文档](docs/functional-spec/README.md)：按 Runner、Plate、后端、前端拆分，描述当前代码行为。
- [系统总览](docs/functional-spec/00-system-overview.md)：组件边界、端到端链路、部署与当前缺口。
- [Plate 模块索引](docs/functional-spec/02-plate/README.md)：方言、注册、查询、release、CLI 与消费面。
- [Runner 模块索引](docs/functional-spec/01-runner/README.md)：执行、编译、协议、策略、扩展与未实现边界。
- [平台后端模块索引](docs/functional-spec/03-platform-backend/README.md)：资产、权限、派发、结果、集成与部署数据。
- [平台前端模块索引](docs/functional-spec/04-platform-frontend/README.md)：路由、编排、运行观察、画像与管理交互。
- [ADR 0002：Plate HTTP 统一语法](docs/adr/0002-plate-http-routing-grammar.md)：对外契约与对内实现分离。
- [ADR 0004：Plate 方言与内容寻址](docs/adr/0004-plate-dialect-three-concepts-content-addressing.md)：Markdown 真源、三概念、治理与构件。
- [Plate 结构设计](claude/plate-design.md)：设计背景；实现状态以功能说明和代码为准。
- [PG 运维 Runbook](src/gimbal-platform/docs/runbook-pg.md)：起库、备份、迁移、回滚和硬约束。
- [当前实现问题清单](docs/implementation-issues-20261124.md)：2026-11-24 的缺陷、边界与产品决策分层记录。

## License

TBD
