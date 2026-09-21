# 示例索引

本目录汇总 Gimbal 框架常用的运行示例与最小可复现用法，对应 `examples/` 下的目录。

## 当前示例目录结构

```
examples/
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

### 2. 登录与查询

展示多 Step 顺序执行、变量提取与传递、认证注入：

```bash
gimbal run launch examples/login_and_query/scenario.yaml
```

### 3. 框架自检

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
- `--fail-fast` 控制执行

适用场景：回归测试集、CI smoke / full 套件的组织。

## 如何运行示例

### 准备工作

1. 准备 Python 3.11+ 环境。
2. 安装框架：`pip install -e .`（开发模式）。
3. 在仓库根目录准备好 `gimbal.yaml`（或使用默认配置）。

### 常用执行命令

```bash
# 直接执行本地文件
gimbal run launch examples/hello/scenario.yaml

# 按路径/模式匹配本地用例文件
gimbal run match "examples/**/*.yaml"

# 只读查看步骤索引（决定 --step-to 设到几）
gimbal run show --from-path examples/hello/scenario.yaml

# 服务模式（接收远程任务）
gimbal run server --port=8765

# 仅输出 JSON 摘要
gimbal run launch examples/hello/scenario.yaml --output json

# 启用 reporter
gimbal run launch examples/hello/scenario.yaml --reporter html --report-dir ./report
```

### 常用控制

```bash
# 失败立即终止
gimbal run launch examples/hello/scenario.yaml --fail-fast

# 只装配不真正执行
gimbal run launch examples/hello/scenario.yaml --dry-run

# 只收集不执行（run match）
gimbal run match "examples/**/*.yaml" --collect-only
```

### 调试技巧

- `--log-level debug` 查看 framework / plugin / executor 详细日志。
- `--output json` 获得结构化结果，便于接入外部 CI。
- `gimbal self-check` 在新环境先跑一次，确认基础设施（EventBus / Hook / Reporter）正常。
- 浏览器访问本机 `localhost:8765`（`gimbal run server`）可触发远程执行，适合做 webhook / 调度触发。
