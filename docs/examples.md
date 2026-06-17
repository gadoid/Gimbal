# 示例索引

本目录汇总 Gimbal 框架常用的运行示例与最小可复现用法，对应 `examples/` 下的目录。

## 当前示例目录结构

```
examples/
├── asset_library/          # 资产库示例（push / pull / list）
├── hello/                  # Hello World 最小示例
├── login_and_query/        # 登录与查询组合示例
└── suites/                 # Suite 多场景编排示例
```

> 仓库初始时每个目录只有 `.gitkeep` 占位文件，真实示例随项目一起提交。在使用某个示例前请先检查目录中是否存在对应的 `scenario.yaml` / `suite.yaml`。

## 快速开始

### 1. Hello World

最简单的单 Step Scenario 示例：

```bash
gimbal run launch examples/hello/scenario.yaml
```

或者按 ID 从本地资产仓库执行（先把 suite/scenario 推入仓库）：

```bash
gimbal run scenario hello/smoke
```

### 2. 登录与查询

展示多 Step 顺序执行、变量提取与传递、认证注入：

```bash
gimbal run launch examples/login_and_query/scenario.yaml
```

### 3. 执行 Suite

执行包含多个 Scenario 的 Suite：

```bash
gimbal run suite examples/suites/my-suite.yaml
```

或从资产库执行：

```bash
gimbal run suite my-suite:v1.0
```

### 4. 资产仓库操作（仿 Docker）

```bash
# 推入一个 suite 资产
gimbal asset push customs/declare:v1.0 -f suite.json -k suite

# 列出全部资产
gimbal asset list

# 查看某个资产的元数据（不下载内容）
gimbal asset inspect customs/declare:v1.0

# 拉取到本地
gimbal asset pull customs/declare:v1.0 -o ./declare.json

# 给已有 digest 打新 tag
gimbal asset tag customs/declare:v1.0 customs/declare:stable

# 删除某个 tag（孤儿 blob 由 gc 回收）
gimbal asset remove customs/declare:v1.0

# 清理孤儿 blob
gimbal asset gc
```

### 5. 框架自检

```bash
gimbal self-check
```

走 bootstrap + 手动 exercise EventBus / HookRegistry，验证基础设施回路；CI 中可作为冒烟测试。

## 示例说明

### examples/hello/

最小可运行示例，展示：

- Scenario 的基本字段（`scenarioId` / `meta` / `config` / `steps`）
- 单个 `Step` 定义
- HTTP GET 请求
- 单条 `assertion` 验证

适用场景：第一次接触 Gimbal 时的"看一眼就跑通"。

### examples/login_and_query/

展示完整的多 Step 协作流程：

- 多 Step 顺序执行（Step 之间共享 context）
- `extract` 策略提取响应字段并写入 context
- `assign` 策略在请求前注入变量
- 模板字符串 `${var.*}` / `${auth.*}` 跨 Step 引用
- 多条 `assertion` 验证业务结果

适用场景：日常 Web API 测试的标准模板。

### examples/suites/

展示 Suite 层级的使用：

- 多个 Scenario 组合（顺序 / 并发可选）
- Suite 级共享配置
- `--fail-fast` / `--continue-on-error` 控制执行

适用场景：回归测试集、CI smoke / full 套件的组织。

### examples/asset_library/

展示资产仓库的使用：

- `gimbal asset push` 上传 suite / scenario / data 资产
- 跨项目 / 跨环境复用同一资产
- `gimbal asset list` / `inspect` / `pull` 浏览与消费
- `gimbal asset tag` / `remove` / `gc` 维护仓库

适用场景：把稳定的回归集 push 到共享仓库，新环境 pull 后直接 `gimbal run suite` 执行。

## 如何运行示例

### 准备工作

1. 准备 Python 3.11+ 环境。
2. 安装框架：`pip install -e .`（开发模式）。
3. 在仓库根目录准备好 `gimbal.yaml`（或使用默认配置）。
4. （可选）把示例 suite / scenario 推入本地资产仓库：

```bash
gimbal asset push demo/hello:v1 -f examples/hello/scenario.yaml -k scenario
```

### 常用执行命令

```bash
# 直接执行本地文件
gimbal run launch examples/hello/scenario.yaml

# 按 ID 执行（资产库优先）
gimbal run scenario demo/hello

# 多 scenario 通配
gimbal run scenario "demo/*"

# 套件执行
gimbal run suite examples/suites/my-suite.yaml

# 服务模式（接收远程任务）
gimbal run server --port=8765

# 仅输出 JSON 摘要
gimbal run launch examples/hello/scenario.yaml --output json

# 启用 reporter
gimbal run launch examples/hello/scenario.yaml --reporter html --report-dir ./report
```

### 常用过滤 / 注入

```bash
# 按 tag 过滤
gimbal run suite examples/suites/my-suite.yaml --tag smoke --tag "not slow"

# 注入变量
gimbal run scenario demo/hello --var env=staging --var user=admin

# 从变量文件加载
gimbal run scenario demo/hello --var-file ./vars.yaml

# 失败立即终止
gimbal run suite examples/suites/my-suite.yaml --fail-fast
```

### 调试技巧

- `--log-level debug` 查看 framework / plugin / executor 详细日志。
- `--output json` 获得结构化结果，便于接入外部 CI。
- `gimbal self-check` 在新环境先跑一次，确认基础设施（EventBus / Hook / Reporter）正常。
- 浏览器访问本机 `localhost:8765`（`gimbal run server`）可触发远程执行，适合做 webhook / 调度触发。
