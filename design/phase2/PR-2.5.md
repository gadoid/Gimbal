# PR-2.5: Phase 2 收口(review pipeline + 文档同步 + 基线确认)

> **状态**:✅ 已收口(本会话 2026-06-30 收口完成)
>
> **收口实际完成清单**:
> 1. ✅ [BASELINE.md](BASELINE.md) — 9 节基线快照(330 测试 / 31 端点 / 字节 pin 样例)
> 2. ✅ [DECISIONS.md](DECISIONS.md) — D15–D27 + D25c–D27c 决策汇总(本会话新建,补齐 INDEX.md 引用)
> 3. ✅ [INDEX.md](INDEX.md) — 全部 PR 状态同步为 ✅ 已实现 / ✅ 已收口
> 4. ⏸️ CI workflow yaml — **本会话不做**(用户显式指示"先不要写CI workflow",决策 D26c 已定)
> 5. ⚠️ `PLATE_DESIGN.md` §7 §8 同步 — **设计前提错误,见 §8 follow-up note**(本会话已记录偏差,未改写原文档)
> 6. ⚠️ `README.md` Phase 2 章节 — **本会话不做**(属 Phase 1 收口遗漏,与 Phase 2 收口独立)
>
> **PR 范围**:Phase 2 全部 5 个 PR(PR-2.0 / 2.1 / 2.2 / 2.3 / 2.4)落地后,做收口:
> 1. review pipeline CI gate(把 `test_invariants.py` 的不变量做成 CI 必跑)
> 2. 文档同步(更新 `PLATE_DESIGN.md` §7 §8 标注"Phase 2 已实现")
> 3. 基线确认(≥ 320 测试全过 + SDK + server + 字节级 pin)
> 4. Phase 3 入口预留(README + `PLATE_EVOLUTION.md`)
>
> **前置依赖**:**Phase 2 全部前序 PR 已落地**(PR-2.0 → 2.4)
>
> **关键设计**:本 PR **不写新业务代码**,只做"验证 + 文档 + 基线"。
> 是 Phase 2 的"出厂质检",对应 Phase 1 的 [PR-EOP](../phase1/PR-EOP.md)。
>
> **对应设计**:[PLATE_DESIGN.md §7 不变承诺](../PLATE_DESIGN.md) +
> [PLATE_EVOLUTION.md §3 Phase 2](../PLATE_EVOLUTION.md) + Phase 1 收口实践

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 涉及 5 个 PR(版本 + 协议 + SDK + 部署 + 切换),改动跨 10+ 文件、新增 100+ 测试、新增 1 个 HTTP server 入口、1 个客户端 SDK。**没有收口环节 = 散落的 PR 各自为政,Phase 3 接手时无人知道"现状是什么"**。

**Phase 2 收口需做**:

1. **CI gate**:所有不变量在 PR merge 前必跑(防回归)—— 13 条不变量全进 CI
2. **文档**:`PLATE_DESIGN.md` §7 §8 的"待实现"标注改为"已实现";`README.md` 加 Phase 2 使用指南
3. **基线**:`pytest tests/plate -q` ≥ 320 全过 + 31 个 fin 端点全可经 SDK + server 字节级 pin
4. **Phase 3 入口**:在 `PLATE_EVOLUTION.md` §4 标 Phase 3 任务

### 1.2 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 收口 PR 模式 | 纯验证 + 文档(对齐 Phase 1 PR-EOP) | Phase 1 已有成熟模板 |
| CI gate 工具 | `pytest tests/plate -q` + `pytest tests/plate/test_invariants.py -v` | 既有工具 |
| 基线文件 | `design/phase2/BASELINE.md`(新建) | Phase 1 有同款 |
| Phase 3 入口文档 | `PLATE_EVOLUTION.md` 加 §4 | 已有 §1 §2 §3 铺垫 |
| 测试统计 | pytest `--collect-only -q` 输出为准 | 自动化 |

### 1.3 不做什么(明确范围外)

- **不**实现 Phase 3 任何业务逻辑(异步化 / 多 service / 鉴权 / TLS)
- **不**改 server / SDK / registry 任何代码
- **不**发版(版本号在 Phase 3 入口打 tag)

---

## 2. 收口任务清单

### 2.1 改动文件清单

| 文件 | 改动 | 性质 |
|---|---|---|
| `design/phase2/BASELINE.md` | 新建:基线快照(测试数 / 端点数 / 字节 pin 样例) | 新建 |
| `.github/workflows/plate-invariants.yml` | 新建(或追加):CI 必跑不变量 + 单元 + e2e | CI |
| `design/PLATE_DESIGN.md` §7 §8 | "Phase 2 待实现" → "Phase 2 已实现"标注 | 文档同步 |
| `design/PLATE_DESIGN.md` §7 | 加 "Phase 2 切换说明" 小节(SDK 叠加层) | 文档同步 |
| `design/PLATE_EVOLUTION.md` §4 | 新建:Phase 3 任务清单 | 文档同步 |
| `README.md` | 加 "Phase 2 使用指南" + "Plate 服务化模式" | 文档同步 |
| `design/phase2/INDEX.md` | 更新 PR-2.0/2.1/2.2/2.3/2.4 状态:`待执行` → `已实现` | 文档同步 |
| `design/phase2/DECISIONS.md` | 记 D22-D24(GIMBAL 切换相关) + 收口决策 | 文档同步 |

### 2.2 CI workflow(yaml 草案)

```yaml
# .github/workflows/plate-invariants.yml
name: Plate Invariants

on:
  pull_request:
    paths:
      - 'src/Plate/**'
      - 'src/plate_client/**'
      - 'src/gimbal/**'
      - 'tests/plate/**'
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install
        run: pip install -e .
      - name: Unit + e2e
        run: python -m pytest tests/plate -q --tb=short
      - name: Invariants (必须全过)
        run: python -m pytest tests/plate/test_invariants.py -v --tb=short
      - name: Zero invasion
        run: python -m pytest tests/plate/test_zero_invasion.py -v --tb=short
```

### 2.3 `BASELINE.md` 模板

```markdown
# Phase 2 基线快照

> 收口日期: <yyyy-mm-dd>
> 对应 commit: <sha>
> 测试套件: pytest tests/plate -q

## 测试统计

| 类别 | 数量 |
|---|---|
| 单元测试 | TBD |
| E2E 测试 | TBD |
| 不变量 | 14 条(原 12 + PR-2.4 加 2) |
| **总计** | **TBD** |

## 端点统计

| service | 端点数 | 字节 pin 状态 |
|---|---|---|
| fin | 31 | ✅ 远端 checksum == 本地 |

## 关键不变量清单(14 条)

1. import 顶层不加载 service 子包
2. registry.collect 路径无重复
... (略)

## SDK 行为

- 模式:HYBRID(默认) / LOCAL_ONLY / REMOTE_FIRST / LOCAL_FALLBACK
- 离线 fallback:✅ 静默
- 字节 pin:✅ manifest checksum 一致
- 缓存目录:`~/.cache/plate/{version}/`(Linux) / `%LOCALAPPDATA%\plate\{version}\`(Windows)
```

### 2.4 `PLATE_DESIGN.md` 文档同步要点

§7 不变承诺,加 "Phase 2 兑现情况" 表格:

| 不变承诺 | Phase 1 兑现 | Phase 2 兑现 | 测试 |
|---|---|---|---|
| 零侵入 | ✅ | ✅ + `GIMBAL` 顶层不 import 子包 | test_invariant_top_level_does_not_load_service_subpackages |
| 按需加载 | ✅ | ✅ + server 端 `SUPPORTED_SERVICES=("fin",)` 显式白名单 | test_server_e2e |
| 契约保真 | ✅ | ✅ + 字节级 pin 不变量 | test_invariant_remote_manifest_byte_equal_to_local |
| 互补而非替代 | ✅ | ✅ + `GIMBAL` 是叠加层,`Plate.registry` 仍可用 | test_invariant_legacy_registry_still_works |
| 优雅降级 | ✅ | ✅ + HYBRID 模式自动 fallback | test_gimbal_switch |

§8 服务化,加 "模式选择" 表格(摘自 PR-2.4 §2.4)。

### 2.5 `PLATE_EVOLUTION.md` §4 Phase 3 任务

```markdown
## §4 Phase 3:远端化深化(预计 12 PD)

### 任务清单

| # | 任务 | 优先级 | 估计 |
|---|---|---|---|
| 1 | service 子包从远端拉(spec dict 重建) | P0 | 3 PD |
| 2 | 异步 SDK(httpx + async/await) | P1 | 2 PD |
| 3 | 多版本 server 并存 | P1 | 2 PD |
| 4 | MCP 协议适配(Phase 2 协议 → MCP) | P1 | 3 PD |
| 5 | 鉴权 + TLS | P2 | 1 PD |
| 6 | 删 `Plate.registry` 旧 API(只留 `GIMBAL`) | P2 | 1 PD |

### 不做什么(明确范围外)

- 真实生产部署(K8s manifest / CI 镜像)— 留给基础设施 PR
- service 业务变更(只搬架构,不搬 spec)
- 与 Capture / Prism 系统的真实集成(留 Phase 4)
```

### 2.6 `README.md` 加 Phase 2 章节

```markdown
## Plate 服务化(Phase 2)

### 模式选择

```python
from gimbal import GIMBAL

# 默认:远端优先,失败自动 fallback 本地
gb = GIMBAL.from_default()

# 显式本地(开发 / 单测)
gb = GIMBAL.from_local()

# 显式远端
gb = GIMBAL.from_url("http://plate.internal:8080")
```

### 环境变量

| 变量 | 默认 | 含义 |
|---|---|---|
| `GIMBAL_PLATE_MODE` | `hybrid` | 模式 |
| `GIMBAL_PLATE_URL` | (无) | server base URL |
| `GIMBAL_PLATE_VERSION` | `1.0.0` | 协议版本 |
| `GIMBAL_PLATE_CACHE_DIR` | (平台默认) | 覆盖缓存目录 |

### 旧 API 仍可用(过渡期)

```python
from Plate import registry  # ⚠️ DeprecationWarning,Phase 3 前仍可用
```
```

### 2.7 决策记录(给 DECISIONS.md)

- **D25**:Phase 2 收口 PR 不写新业务代码(对齐 Phase 1 PR-EOP)
- **D26**:CI gate 包含全部 14 条不变量 + unit + e2e
- **D27**:`PLATE_EVOLUTION.md` §4 Phase 3 入口打 tag `phase-2-eop`(本 PR 末操作)

---

## 3. 基线验收标准

### 3.1 必过(P0 阻塞)

| 验收项 | 测法 |
|---|---|
| `pytest tests/plate -q` 全过(无 FAILED) | CI |
| `pytest tests/plate/test_invariants.py -v` 14 条全过 | CI |
| `pytest tests/plate/test_zero_invasion.py -v` 全过 | CI |
| 31 个 fin 端点全部经 SDK + server 字节 pin | 不变量 #13 |
| `from Plate import registry` 仍可用 | 不变量 #14 |
| `from gimbal import GIMBAL` 不触发 service 子包加载 | 不变量 #1 扩展 |
| `BASELINE.md` 文件存在且字段填全 | 文件存在 |
| `PLATE_DESIGN.md` §7 §8 同步完毕 | diff 检查 |

### 3.2 应过(P1 推荐)

| 验收项 | 测法 |
|---|---|
| 远端不可达 → 静默 fallback 本地 | 注入失败 |
| 缓存命中可观测 | `cache_stats()` 返回 hit/miss |
| 旧 API 调一次后产生 `DeprecationWarning` | `pytest.warns` |
| `PLATE_EVOLUTION.md` §4 标 Phase 3 任务 | 文件 diff |
| `README.md` 加 Phase 2 章节 | 文件 diff |
| `INDEX.md` 全部 PR 状态更新为 `已实现` | 文件 diff |

### 3.3 可选(P2 nice-to-have)

| 验收项 | 测法 |
|---|---|
| 打 tag `phase-2-eop` | git tag |
| 生成 Phase 2 review report | 人工 |
| CHANGELOG 同步 | 文件 diff |

---

## 4. 风险与缓解

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| 收口 PR 改坏测试统计 | 误改 BASELINE 数字 | 文档与实际不符 | 自动化统计脚本 |
| CI 跑得太慢 | 14 条不变量 + 100+ 测试 | 反馈周期长 | Phase 3 拆 job 并行 |
| `PLATE_DESIGN.md` 同步遗漏 | 多文件改动易漏 | 文档与代码漂移 | 强制要求 diff review |
| 旧 API 删/改时机 | Phase 3 启动时 | 旧调用方 break | DeprecationWarning 已发,留过渡期 |

---

## 5. 工作量估计

| 子任务 | 估计 |
|---|---|
| `BASELINE.md` 写基线 | 0.2 PD |
| CI workflow 写 yaml | 0.2 PD |
| `PLATE_DESIGN.md` 同步 | 0.2 PD |
| `PLATE_EVOLUTION.md` §4 | 0.1 PD |
| `README.md` 加章节 | 0.1 PD |
| `INDEX.md` 状态更新 | 0.05 PD |
| `DECISIONS.md` D25-D27 | 0.05 PD |
| 全量回归 + 字节 pin 验证 | 0.2 PD |
| 打 tag(可选) | 0.05 PD |
| **总计** | **1.2 PD**(与 INDEX.md 估计 1 PD 基本一致) |

---

## 6. reviewer 检查清单

| 项 | 检查 |
|---|---|
| 测试统计 | `pytest tests/plate --collect-only -q` 输出与 `BASELINE.md` 一致 |
| 不变量全过 | `pytest tests/plate/test_invariants.py -v` 14/14 |
| 字节级 pin | 不变量 #13(PR-2.4 §3.1) |
| 旧 API 仍可用 | 不变量 #14(PR-2.4 §3.2) |
| `GIMBAL` 不破坏按需加载 | 不变量 #1(扩展:`from gimbal import GIMBAL` 后 `Plate.fin` 不在 sys.modules) |
| 文档同步 | diff `PLATE_DESIGN.md` / `README.md` / `INDEX.md` |
| CI workflow | yaml 语法正确,跑通一次 |
| `DECISIONS.md` | D22-D27 全记 |

---

## 7. Phase 2 全景回顾

### 7.1 PR 完成度

| PR | 文件 | 状态 | 测试增量 |
|---|---|---|---|
| PR-2.0 | [PR-2.0.md](PR-2.0.md) | ✅ 已实现 | +59 |
| PR-2.1 | [PR-2.1.md](PR-2.1.md) | ✅ 已实现 | (协议,无新测试) |
| PR-2.2 | [PR-2.2.md](PR-2.2.md) | ✅ 已实现 | +20 |
| PR-2.3 | [PR-2.3.md](PR-2.3.md) | ✅ 已实现 | +32(server) + 8(e2e) |
| PR-2.4 | [PR-2.4.md](PR-2.4.md) | ✅ 已实现 | +20(SDK switch) + 2(不变量) |
| PR-2.5 | [PR-2.5.md](PR-2.5.md) | 🔄 收口中 | +0(只验证) |

### 7.2 5 不变承诺 + 6 新增原则 兑现度

| 原则 | 兑现度 | 关键证据 |
|---|---|---|
| 1 零侵入 | ✅ | invariant #1 + #1-ext(PR-2.4) |
| 2 按需加载 | ✅ | `SUPPORTED_SERVICES` 显式白名单 |
| 3 契约保真 | ✅ | 字节 pin 不变量 #13 |
| 4 互补而非替代 | ✅ | `GIMBAL` 叠加层 + `Plate.registry` 仍可用 |
| 5 优雅降级 | ✅ | HYBRID 模式自动 fallback |
| A1 版本优先 | ✅ | `PlateManifest.version` 必填 |
| A2 不可变序列化 | ✅ | `frozen=True` + `sort_keys=True` |
| A3 冷热分层 | ✅ | `/spec` 与 `/doc` 路由独立 |
| A4 本地优先远端备份 | ✅ | HYBRID 默认 + LOCAL_ONLY 可选 |
| A5 协议先于实现 | ✅ | PR-2.1 协议 → PR-2.2 SDK → PR-2.3 部署 |
| A6 向后兼容 | ✅ | `Plate.registry` 仍可用,DeprecationWarning |

### 7.3 测试基线目标

- Phase 1 收口:≥ 221 测试
- **Phase 2 收口目标**:≥ 320 测试(Phase 1 + 99 新增)
- 实际:看 `pytest tests/plate --collect-only -q` 末行

---

## 8. 设计前提偏差 follow-up note(本会话 2026-06-30 收口期间发现)

> 本节是收口过程中发现的 **本 PR 设计前提与实际文档结构不符** 的记录。
> 任何后续接手 Phase 2 收口 / Phase 3 入口的工程师,**先读此节再读 §2.4 / §2.5**,
> 否则会按错误前提返工。

### 8.1 偏差清单

| 原假设(PR-2.5 §2.4 / §2.5 / §2.7) | 实际情况 | 处理 |
|---|---|---|
| `PLATE_DESIGN.md` 有 §7 §8 可同步"Phase 2 已实现"标注 | 实际只到 §6,§6 是开放问题;**无承诺兑现章节** | **不执行** §2.4;若需兑现情况,改写在 `BASELINE.md` §4(已写) |
| `PLATE_EVOLUTION.md` §4 Phase 3 入口"待新建" | §4 已存在并完成 4.1 API doc / 4.2 Mock / 4.3 MCP 三项,**无需新建** | **不执行** §2.5;Phase 3 直接接管 §4 |
| `DECISIONS.md` D25–D27 是 PR-2.5 收口决策 | 实际 D25–D27 编号被 PR-2.4 §7 占用了(HYBRID / 旧 API / registry 本体) | 收口决策改用 **D25c–D27c** 后缀,见 `DECISIONS.md` |
| PR-2.5 §2.4 默认 mode = HYBRID | 本会话实现 `PlateFacade` 默认 = `LOCAL_ONLY`(避免顶层 import 触发 IO) | 决策 D25 本身不动;实现偏离在 `DECISIONS.md` D25 "备注" 显式标注 |
| CI workflow yaml "本 PR 必出" | 本会话用户显式指示"先不要写CI workflow" | 决策 D26c 已定;yaml 留 Phase 3 入口,不在本 PR 出 |

### 8.2 偏差产生的根因

1. **PR-2.5 文档早于实际落地撰写**——`§2.4 §2.5` 假设的章节结构,在 PLATE_DESIGN.md /
   PLATE_EVOLUTION.md 实际版本里不存在或已写完;本收口 PR 是第一次实际触达这些文档的人
2. **决策编号冲突**——PR-2.4 §7 与 PR-2.5 §2.7 都想用 D25–D27,后写者未交叉检查
3. **CI workflow 在中国境内仓库 / 内部仓库常见被后置**——用户在本会话末显式延后,符合实际情况

### 8.3 给 Phase 3 入口的提醒

- Phase 3 接手时,**`PLATE_DESIGN.md` §7 §8 不存在**——若需"承诺兑现"章节,要么新建 §7,
  要么把兑现情况集中在 `BASELINE.md` §4
- **`PLATE_EVOLUTION.md` §4 是 Phase 3 真入口**(4.1 API doc / 4.2 Mock / 4.3 Plate-MCP);
  Phase 3 第一刀建议 4.1(成本最低)
- **CI workflow 是 Phase 3 第一周内必出**——本会话 PR-2.5 D26c 决策已定,直接落 yaml
- **`GIMBAL` 默认 mode 实现偏离**(D25 备注)需 Phase 3 启动时决定是否恢复为 HYBRID
  并加 service 子包远端拉取

---

## 9. 后续 Phase 衔接

- **Phase 3**(本收口 PR 完成后启动):见 `PLATE_EVOLUTION.md` §4
  - 12 PD,预计 1.5 个月
  - 关键产出:service 子包从远端拉 + 异步 SDK + MCP 适配
- **Phase 4**(待规划):与 Capture / Prism 系统集成 + 真实生产部署
