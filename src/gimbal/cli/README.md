# CLI 模块

命令行接口，使用 Typer + Rich 构建。

## 设计理念

### 1. 命令树结构

```
gimbal [全局选项]
├── run
│   ├── suite     # 按 ID 执行已注册的 Suite 资产
│   ├── scenario  # 按 ID 执行已注册的 Scenario 资产
│   ├── match     # 按路径/模式匹配本地未注册的用例文件
│   ├── server    # 作为服务监听端口接收任务
│   └── launch    # 直接接收文件/stdin/inline 内容执行
├── resolve       # 解析资产引用
├── compile-case  # 编译用例
├── validate      # 验证配置
└── list-assets  # 列出资产
```

### 2. 分层设计

- **main.py**: 主入口，统一参数解析和命令注册
- **common.py**: 公共选项定义（复用逻辑）
- **commands/**: 各子命令具体实现
- **context.py**: CLI 上下文对象

### 3. RunRequest 契约

CLI 层只负责构造 `RunRequest`，具体执行委托给 `Runner`：

```
CLI → RunRequest → Runner → RunResult → CLI
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `main.py` | 主入口，Typer 应用 |
| `common.py` | 公共选项定义 |
| `context.py` | CLIContext 上下文 |
| `engine.py` | GIMBAL Engine 主控类 |

### Commands

| 文件 | 命令 | 说明 |
|------|------|------|
| `run.py` | `gimbal run` | run 子命令组（五种执行模式） |
| `run_suite.py` | `gimbal run suite` | 执行 Suite |
| `run_scenario.py` | `gimbal run scenario` | 执行 Scenario |
| `run_match.py` | `gimbal run match` | 按模式匹配执行 |
| `run_server.py` | `gimbal run server` | 服务模式 |
| `run_launch.py` | `gimbal run launch` | 直接加载文件/stdin/inline 执行 |
| `resolve.py` | `gimbal resolve` | 解析引用 |
| `compile_case.py` | `gimbal compile-case` | 编译用例 |
| `validate.py` | `gimbal validate` | 验证配置 |
| `list_assets.py` | `gimbal list-assets` | 列出资产 |

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `-c, --config <path>` | 配置文件路径 |
| `--no-color` | 关闭彩色输出 |
| `-v, --verbose` | 详细输出（等同于 `--log-level=debug`） |
| `--version` | 显示版本 |

---

## run suite 命令

### 用法

```bash
gimbal run suite <suite_id...> [选项]
```

### 示例

```bash
# 执行单个 Suite
gimbal run suite customs-declare

# 执行多个 Suite
gimbal run suite customs-declare forex-settle --order=parallel

# 通配符匹配
gimbal run suite "customs/*" --yes

# 指定版本
gimbal run suite customs/declare:v1.2 --source=remote
```

### 选项

**资产来源**
| 选项 | 说明 |
|------|------|
| `--source [auto\|local\|remote]` | 资产来源，默认 auto |
| `--registry <url>` | 远程资产库地址 |
| `--version <ver>` | 资产版本，默认 latest |
| `--no-cache` | 强制远程获取 |
| `--cache-only` | 只读缓存 |

**执行控制**
| 选项 | 说明 |
|------|------|
| `--order [sequential\|parallel\|as-given]` | 执行顺序，默认 as-given |
| `--parallel <num>` | 并发数，默认 1 |
| `--timeout <seconds>` | 超时时间，默认 300 |
| `--retry <num>` | 重试次数，默认 0 |
| `--fail-fast` | 首个失败即停止 |
| `--dry-run` | 只组装不执行 |

**项目过滤**
| 选项 | 说明 |
|------|------|
| `--include-scenario <pattern>` | 只执行匹配的 scenario |
| `--exclude-scenario <pattern>` | 排除匹配的 scenario |
| `-t, --tag <tag>` | 按标签过滤 |

**报告输出**
| 选项 | 说明 |
|------|------|
| `--reporter <name>` | 报告器名称 |
| `--report-dir <path>` | 报告目录，默认 ./reports |
| `-o, --output [console\|json\|junit]` | 输出格式，默认 console |

---

## run scenario 命令

### 用法

```bash
gimbal run scenario <scenario_id...> [选项]
```

### 选项

同 `run suite`，增加：
| 选项 | 说明 |
|------|------|
| `--env <env>` | 目标环境，默认 dev |
| `--profile <name>` | 使用的 profile，默认 default |

---

## run match 命令

### 用法

```bash
gimbal run match [pattern...] [选项]
```

按本地文件路径/模式匹配，直接执行未注册的资产文件。

---

## run server 命令

### 用法

```bash
gimbal run server [选项]
```

将 GIMBAL 作为服务监听，支持远程任务调度。

### 选项
| 选项 | 说明 |
|------|------|
| `--port <port>` | 监听端口，默认 8765 |
| `--host <host>` | 监听地址，默认 0.0.0.0 |

---

## run launch 命令

### 用法

```bash
gimbal run launch [SOURCE] [选项]
```

直接接收文件路径、stdin 或 inline 内容，加载并执行。

### 输入来源

| 来源 | 用法 |
|------|------|
| 文件路径 | `gimbal run launch ./debug.yaml` |
| stdin | `cat case.yaml \| gimbal run launch - -f yaml` |
| inline | `gimbal run launch --inline '{"name":"x"}' -f json` |

### 选项
| 选项 | 说明 |
|------|------|
| `SOURCE` | 文件路径，`-` 表示 stdin |
| `--inline <text>` | 直接传内容 |
| `-f, --format [auto\|json\|yaml\|text]` | 输入格式，默认 auto |

### 示例

```bash
# 文件路径
gimbal run launch ./debug.yaml

# stdin
cat case.yaml | gimbal run launch - -f yaml

# inline JSON
gimbal run launch --inline '{"name":"test"}' -f json

# auto 检测格式
gimbal run launch ./case.json
```

---

## 其他命令

### validate

```bash
gimbal validate <path>
```

验证 YAML/JSON 文件的 Schema 合规性。

### compile-case

```bash
gimbal compile-case <source> -o <output>
```

将 Markdown/Text 格式的用例编译为 JSON/YAML。

### list-assets

```bash
gimbal list-assets [--source local|remote] [--type suite|scenario]
```

列出资产库中的资产。

### resolve

```bash
gimbal resolve <ref>
```

解析资产引用的完整路径。

---

## 核心类

### CLIContext

```python
class CLIContext:
    config_path: Optional[str]
    no_color: bool
    verbose: bool
    env: str
    profile: str
```

---

## 运行测试

```bash
# 查看帮助
python -m gimbal --help

# 查看 run 命令帮助
python -m gimbal run --help

# 查看 run suite 帮助
python -m gimbal run suite --help

# 查看 run launch 帮助
python -m gimbal run launch --help
```
