# GIMBAL 流量过滤策略参考文档

> 在配置或调试 **capture 白名单** 时加载本文档——决定 `gimbal capture` 录制哪些请求、丢弃哪些。
>
> `gimbal capture` 是基于 mitmproxy 的流量录制器；本文档描述 `gimbal/capture/loader.py` 消费的 v0.4 YAML 策略格式，**不涉及**"如何把录制结果转成场景用例"（那是 `gimbal-traffic-to-scenario` 的职责）。

**所有路径均相对于 GIMBAL 仓库根目录**。源码指针使用**符号（类/函数）而非行号**，便于长期演进——需要定位具体代码时请 `grep` 该符号。

---

## 0. 文件位置与查找顺序

`loader.py` 通过 `_default_search_paths` 按以下顺序解析策略文件：

1. `./.gimbal/filters.yaml` — 项目内，**推荐用于团队共享**
2. `./filters.yaml` — 项目根目录
3. `~/.gimbal/filters.yaml` — 个人级，跨项目
4. `$GIMBAL_FILTERS` — 环境变量，指向任意路径

`--filter-file <path>` 覆盖以上所有路径（**最高优先级**，跳过自动查找）。配合 `--strict-files-only` 时，文件缺失将**硬失败**（不降级到自动查找）。

---

## 0.5 最少必填基线（生成 filters.yaml 时必须满足）

| 层级 | 必填条件 |
|---|---|
| **根节点** | `mode`（`include` 或 `exclude` 二选一） |
| **profiles** | 至少 1 个 profile |
| **每个 profile** | 至少 1 条 rule |
| **每条 rule** | 至少 1 个 `host` / `host_glob` / `host_regex` / `path` / `path_glob` / `path_regex` / `methods` 字段 |

> AI 自检：生成完成后对照上表逐项校验，缺失即补全。

---

## 0.6 常用取值约定

AI 生成时直接套用以下约定，避免任意编造：

| 字段 | 约定值 / 格式 |
|---|---|
| `mode` | 默认 `include`（白名单）；仅在"少量路径要排除"时用 `exclude` |
| `default_profile` | 默认值 `smoke`；通过 `--filter-profile` 可覆盖 |
| `host` | 精确域名（如 `api.example.com`），不含协议与端口 |
| `path` | **前缀匹配**（注意：`/api/order` 也会匹配 `/api/orderlist`） |
| `path_glob` | fnmatch 风格（`*` 跨段、`?` 单字符），最常用 |
| `path_regex` | 标准正则；**YAML 中反斜杠需双转义**（`\\d` 而非 `\d`） |
| `methods` | HTTP 方法大写列表（`GET` / `POST` / `PUT` / `DELETE` / `PATCH`）；空 = 匹配所有方法 |

---

## 0.7 黄金生成规则

按重要性从高到低，AI 须无条件遵守：

1. **mode 必填**：`include` 与 `exclude` 二选一，不可省略。
2. **profile 不可空**：每个 profile 必须至少有 1 条 rule，否则抛 `EmptyRulesError`。
3. **rule 不可空字段**：每条 rule 至少 1 个匹配字段；`extra="forbid"`，**未知字段会报错**。
4. **regex 必须双转义**：YAML 中的 `\d` 写成 `\\d`、`\s` 写成 `\\s`。
5. **includes 无循环**：`includes:` 形成的引用链必须是有向无环图（`IncludeCycleError`）。
6. **优先 path_glob**：人易读且不易错；仅在需要精确控制时使用 `path_regex`。
7. **谨慎使用 path 前缀**：`path: /api/order` 会同时匹配 `/api/orderlist`；需精确控制时改用 `path_regex`。
8. **团队共享优先用 `./.gimbal/filters.yaml`**：提交到仓库；个人配置用 `~/.gimbal/filters.yaml`。

---

## 1. YAML 结构

```yaml
mode: include              # 根模式；未匹配的请求 → 默认 exclude
default_profile: smoke     # 省略 --filter-profile 时使用

profiles:
  smoke:
    description: smoke 录制 — 仅核心订单/查询接口
    rules:
      - path: /api/order               # 前缀 + 方法白名单
        methods: [GET, POST]
      - path_glob: "/api/v*/order/**"  # fnmatch 风格 glob
      - path_glob: "/api/payment/*"
      - path_regex: "^/api/(user|account)/[0-9]+/?$"
```

`includes:`（相对于主 YAML 所在目录）可引入共享 profile；循环引用将被拒绝（`IncludeCycleError`）。

---

## 2. 规则字段

数据模型：`Rule` / `Profile` / `StrategyFile`，定义于 `gimbal/capture/strategy.py`。

| 字段 | 类型 | 含义 |
|---|---|---|
| `host` | string | 精确主机名（与 `host_glob`/`host_regex` 三选一） |
| `host_glob` | string | fnmatch 主机匹配 |
| `host_regex` | string | 正则主机匹配 |
| `path` | string | **前缀匹配**（`/api/order` 匹配 `/api/order/123`） |
| `path_glob` | string | fnmatch（`*` 跨段、`?` 单字符） |
| `path_regex` | string | 正则（YAML 中反斜杠需双转义：`\\d`） |
| `methods` | list[string] | HTTP 方法白名单；大写；空 = 匹配所有方法 |

---

## 3. 匹配语义

由 `CompiledMatcher.match` 实现（`strategy.py`）。

- **单条规则内**：`host` / `path` / `methods` 是 **AND 关系**——所有出现的字段都必须匹配。
- **多条规则间**：**OR 关系**——任意一条规则匹配即视为请求匹配。
- **无规则匹配**：根 `mode: include` → 默认 **exclude**（丢弃）；根 `mode: exclude` → 默认 **include**（保留）。
- 每条规则至少需要 **1 个**匹配字段。未知字段将报错（`extra="forbid"`）。

### 三种 `path` 形式的区别——必须牢记

| 形式 | 行为 | 示例 |
|---|---|---|
| `path` | `request.path.startswith(rule.path)` | `/api/order` **也会**匹配 `/api/orderlist` |
| `path_glob` | `fnmatch(request.path, rule.path_glob)` | `/api/v*/order/**` —— `*` 跨段 |
| `path_regex` | `re.search(rule.path_regex, request.path)` | `^/api/order/[0-9]+$` —— 精确 |

**前缀陷阱**：`path: /api/order` 会同时匹配 `/api/orderlist`。若只想匹配 `/api/order` 及其子路径，请使用 `path_regex: "^/api/order(/.*)?$"`。

---

## 4. 按场景的规则模式

**严格前缀 + 方法**

```yaml
- path: /api/order
  methods: [POST, PUT]    # 仅创建/更新
- path: /api/user
  methods: [GET]          # 仅用户读取
```

**多版本 glob**

```yaml
- path_glob: "/api/v*/order/**"   # 任意 v1/v2/v3 订单子路径
- path_glob: "/api/payment/*"     # 单段（不含斜杠）
```

**正则精确 ID 匹配**

```yaml
- path_regex: "^/api/order/[0-9]+$"
  methods: [GET, DELETE]
- path_regex: "^/api/user/profile/?$"
```

**锁定主机**（省略 `host` 表示匹配任意主机）

```yaml
- host: api.example.com
  path_glob: "/api/order/**"
  methods: [POST]
```

---

## 5. CLI 调用

**自动查找 + 默认 profile**：

```bash
gimbal capture start --session dev-1
```

**显式文件 + profile**：

```bash
gimbal capture start --session dev-1 \
  --filter-file ./.gimbal/filters.yaml \
  --filter-profile smoke
```

**旧版 CSV 前缀追加**（向后兼容；`--filter` = 逗号分隔的路径前缀，`--filter-mode` 控制 include/exclude，默认为 include）：

```bash
gimbal capture start --session dev-1 \
  --filter-file ./.gimbal/filters.yaml --filter-profile smoke \
  --filter "/api/debug" --filter-mode include
```

**强制要求文件存在**（不自动降级）：

```bash
gimbal capture start --session dev-1 --strict-files-only
```

CLI 实现：`gimbal/capture/cli.py` 的 `start_cmd`。

---

## 6. 启动前校验——必须通过 mitmdump 才能启动

以下检查在父进程中执行；失败 → **退出码 5**，mitmdump 不会启动。`capture start` 之前请逐项确认：

- YAML 可解析：`python -c "import yaml; yaml.safe_load(open('./.gimbal/filters.yaml'))"`
- 每条 rule 至少有 1 个 `host` / `path` / `method` 字段
- 所有 `path_regex` / `host_regex` 可编译（`re.compile` 不抛异常）
- `--filter-profile` 指定的名称存在于 `profiles:` 下
- `includes:` 路径可解析（相对于主 YAML 所在目录）且无循环

---

## 7. 运行时验证——capture 启动后

- `gimbal capture list --session dev-1` 展示会话已建立
- 浏览器/客户端代理设置为 `127.0.0.1:8080`
- 白名单内的请求写入 `$GIMBAL_HOME/captures/active/<sid>.ndjson`
- `gimbal capture show --session dev-1 --tail` 实时显示预期的 method/path
- **不在**白名单的请求**不会**出现在 NDJSON 中

---

## 8. 推荐实践（软建议，不强制）

- 将复杂正则以单元测试形式固化到 `tests/test_loader_yaml.py` / `tests/test_loader_profile.py`，避免静默腐化。
- 团队依赖的配置**优先**使用 `./.gimbal/filters.yaml`（提交到仓库），而非个人 `~/.gimbal/` 文件。

---

## 9. 故障排查

| 症状 | 原因 | 修复 |
|---|---|---|
| `FilterFileNotFound` | 自动查找路径上无文件 | 添加 `--filter-file` 或创建 `./.gimbal/filters.yaml` |
| `EmptyRulesError` | profile 的 `rules: []` 为空 | 至少添加 1 条 rule |
| `RuleCompileError` | 正则非法 | 用 `re.compile` 测试；YAML 中 `\\d` 而非 `\d` |
| `ProfileNotFound` | `--filter-profile` 拼写错误 | 对照 `profiles:` 下的 key 检查 |
| `IncludeCycleError` | `includes:` 形成循环 | 打断 include 链 |
| 未捕获任何请求 | `mode: include` + 无规则匹配 → 全部排除 | 录制已知匹配的路径；或临时用 `path_glob: "/**"` 调试 |
| 全部请求都被录制 | 规则太宽，或 mode 反转 | 复核三种 `path` 形式（见上表） |

---

## 10. 源码指针（只读）

| 关注点 | 位置 |
|---|---|
| 数据模型（Rule/Profile/StrategyFile） | `gimbal/capture/strategy.py` |
| 运行时匹配器 | `gimbal/capture/strategy.py` → `CompiledMatcher` |
| 加载器（查找路径、includes、profile 选择） | `gimbal/capture/loader.py` → `_default_search_paths` |
| 旧版 CSV 过滤器 | `gimbal/capture/filter.py` |
| mitmproxy addon → 匹配器 | `gimbal/capture/proxy.py` |
| CLI 装配 | `gimbal/capture/cli.py` → `start_cmd` |
| 用户手册（过滤章节） | `USER_MANUAL.md` |
| 设计文档（完整语义） | `gimbal-design/07-filter-strategy.md` |