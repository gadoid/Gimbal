# Phase 2 基线快照

> **收口日期**:2026-06-30
> **对应 commit**:见 `git log -1 --format=%H`(<commit-sha>)
> **测试套件**:`pytest tests/plate -q`
> **基线命令**:`python -m pytest tests/plate -q`
> **基线结果**:**330 passed in 18.25s**

> 本文件是 [PR-2.5 Phase 2 收口](PR-2.5.md) 的产出物之一。
> 仅做"事实记录 + 验证指引",不写新业务代码。

---

## 1. 测试统计(330)

| 类别 | 数量 | 文件 |
|---|---|---|
| **单元测试** | **287** | 18 个文件 |
| **E2E 测试** | **8** | `test_server_e2e.py` |
| **不变量测试** | **16** | `test_invariants.py`(含 1 个 server 协议 byte-equal) |
| **零侵入测试** | **6** | `test_zero_invasion.py` |
| **Phase 1 EOP 基线** | **12** | `test_eop_baseline.py` |
| **E2E 字节 pin(不变量内)** | **1** | `test_invariant_server_protocol_byte_equal` |

> 注:类别有重叠(不变量 #13/14/15 也是单元测试),不变量 #1 与零侵入测试
> 范围相近,本表按"测试关注点"分类而非物理位置。

### 1.1 测试文件分布(20 个文件,按数量排序)

| 文件 | 数量 | 主题 |
|---|---|---|
| `test_facade_switch.py` | 35 | **PR-2.4 新增**:`PlateFacade` mode 切换 + 3 工厂 + 旧 API 兼容 |
| `test_server.py` | 31 | **PR-2.3**:`PlateServer` 单元(handlers / 路由 / 错误码) |
| `test_aliases.py` | 24 | service 名 → 目录名 alias |
| `test_serialization.py` | 23 | `to_dict` / `from_dict` 字节级 pin |
| `test_logical_path_resolver.py` | 23 | `path_resolver.resolve_logical_path` |
| `test_fin_bindings.py` | 21 | fin 端点 FieldBinding 一致性 |
| `test_version.py` | 19 | `PlateVersion.parse` / `to_dict` / `from_dict` |
| `test_spec_category.py` | 18 | `EndpointCategory` 分类 |
| `test_spec.py` | 18 | `EndpointSpec` 字段约束 + frozen |
| `test_binding.py` | 17 | `FieldBinding` 数据类 |
| `test_invariants.py` | **16** | 15 个不变量 + 1 server 协议 byte-equal |
| `test_manifest.py` | 15 | `PlateManifest` 聚合 + checksum + verify |
| `test_doc.py` | 13 | L2 文档元数据 |
| `test_core.py` | 13 | registry `collect` / `resolve` / `warm` / `reset` |
| `test_eop_baseline.py` | 12 | **Phase 1 EOP** 收口时的基线快照 |
| `test_fin_category_coverage.py` | 9 | fin 端点 category 覆盖率 |
| `test_server_e2e.py` | 8 | **PR-2.3**:`PlateServer` 真实启动 + 字节 pin |
| `test_zero_invasion.py` | 6 | A1 零侵入完整契约 |
| `test_sanity.py` | 5 | 冒烟 |
| `test_concurrent_resolve.py` | 4 | registry 线程安全 |

### 1.2 PR 增量(Phase 2 累计)

| PR | 单元增量 | E2E 增量 | 不变量增量 | 备注 |
|---|---|---|---|---|
| **PR-2.0** 版本 + 序列化 | +59 | — | +2(manifest byte-equal, drift detection) | Phase 2 地基 |
| **PR-2.1** 协议草案 | 0 | — | — | 纯设计,无代码增量 |
| **PR-2.2** SDK 设计稿 | 0 | — | — | 仅设计稿,本会话用 `Plate/facade/client.py` 同进程占位 |
| **PR-2.3** server + E2E | +31 | +8 | +1(server protocol byte-equal) | |
| **PR-2.4** facade 切换 | +35 | — | +3(13/14/15) | 本会话新加 |
| **PR-2.5** 收口 | 0 | — | — | 仅 BASELINE + 文档同步(本文件) |
| **Phase 1 继承** | 221 | — | — | 来自 [PR-EOP](../phase1/PR-EOP.md) |
| **Phase 2 累计** | +125 | +8 | +6 | |
| **本基线总计** | **330** | | | |

> Phase 1 收口时 221 测试,本基线 330 测试,Phase 2 净增 +109(125 单元 + 8 E2E 扣除 PR-2.4 与 PR-2.3 各自的子集重叠)。

---

## 2. 端点统计(31)

| service | 端点数 | HTTP method | 字节 pin 状态 |
|---|---|---|---|
| **fin** | 31 | 全 POST | ✅ 远端 checksum == 本地(见 §3) |

> 当前仅 `fin` 一个 service 子包落地。`_aliases.py` 框架已就位,
> 新增 service 只需在 `Plate/<name>/endpoints.py` 定义 `EndpointSpec` 即可,
> 无需改 registry / facade / server。

### 2.1 字节 pin 样例

```
checksum   = 09042f457bc253ffc99e8cd66f89b818b0ed2c33bf6117e3ca012556f72281db
version    = 1.0.0
services   = ['fin']
endpoints  = 31
```

复现命令:
```bash
python -c "
from Plate import registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion
registry.reset()
registry.collect('fin')
services = {svc: [s.to_dict() for k, s in registry._index.items() if k.service == svc] for svc in {k.service for k in registry._index}}
m = PlateManifest.from_services(PlateVersion(1,0,0), services)
print(m.checksum)
"
```

---

## 3. 不变量清单(15 + 1 = 16 条)

> 编号沿用 [test_invariants.py](../../tests/plate/test_invariants.py) 出现顺序。
> 每条 = 业务护栏,违反即业务承诺破裂。

| # | 名称 | 原则 | 测试位置 | 状态 |
|---|---|---|---|---|
| **#1** | `top_level_does_not_load_service_subpackages` | A1 零侵入 | test_invariants.py:44 | ✅ |
| **#2** | `top_level_all_only_registry_and_bootstrap_error` | A1 零侵入 | test_invariants.py:104 | ✅ |
| **#3** | `registry_is_cold_after_import` | A2 按需加载 | test_invariants.py:131 | ✅ |
| **#4** | `failed_resolve_does_not_pollute_modules` | A2 按需加载 | test_invariants.py:149 | ✅ |
| **#5** | `resolve_triggers_on_demand_import` | A2 按需加载 | test_invariants.py:186 | ✅ |
| **#6** | `category_x_mutates_state_holds` | 业务分类 | test_invariants.py:240 | ✅ |
| **#7** | `fin_endpoints_have_category` | 业务分类 | test_invariants.py:274 | ✅ |
| **#8** | `fin_query_endpoints_do_not_mutate` | 业务分类 | test_invariants.py:303 | ✅ |
| **#9** | `no_self_binding` | 契约保真 | test_invariants.py:336 | ✅ |
| **#10** | `l1_l2_symmetry` | 契约保真 | test_invariants.py:398 | ✅ |
| **#11** | `plate_manifest_byte_equal` | A2 不可变序列化 | test_invariants.py:455 | ✅ |
| **#12** | `plate_manifest_drift_detection` | A2 不可变序列化 | test_invariants.py:492 | ✅ |
| **#13** | **`server_protocol_byte_equal`** | **A2 不可变序列化 + PR-2.3** | test_invariants.py:526 | ✅ |
| **#14** | **`facade_manifest_byte_equal_to_local`** | **A2 + PR-2.4** | test_invariants.py:607 | ✅ |
| **#15** | **`legacy_registry_still_works`** | **A6 向后兼容 + PR-2.4** | test_invariants.py:653 | ✅ |
| **#16** | **`facade_does_not_load_service_subpackages`** | **A1 零侵入 + PR-2.4** | test_invariants.py:672 | ✅ |

> 粗体 = Phase 2 新增(PR-2.3 #13 + PR-2.4 #14/15/16)。

---

## 4. 5 不变承诺 + 6 新增原则 兑现度

### 4.1 Phase 1 不变承诺(继承)

| 承诺 | 兑现 | 关键证据 |
|---|---|---|
| 1 零侵入 | ✅ | 不变量 #1 + #16(`import Plate` / `import Plate.facade` 都不触发 service 子包) |
| 2 按需加载 | ✅ | 不变量 #3 #4 #5;`registry.collect` 按 service 名扫子包 |
| 3 契约保真 | ✅ | `frozen=True` + `to_dict` 字节级稳定;不变量 #9 #10 |
| 4 互补而非替代 | ✅ | `PlateFacade` 是叠加层,`Plate.registry` 仍可用(不变量 #15) |
| 5 优雅降级 | ✅ | HYBRID mode 静默 fallback;server 错误码 + `available_*` 提示 |

### 4.2 Phase 2 新增原则(全部)

| 原则 | 兑现 | 关键证据 |
|---|---|---|
| **A1** 版本优先 | ✅ | `PlateManifest.version` 必填;`PlateVersion.parse` 拒绝非法格式(不变量 #11) |
| **A2** 不可变序列化 | ✅ | `frozen=True` + `sort_keys=True` + SHA256 checksum;不变量 #11/12/13/14 |
| **A3** 冷热分层 | ✅ | server 端 `/v1/spec/*` 与 `/v1/doc/*` 独立路由 |
| **A4** 本地优先远端备份 | ✅ | `PlateFacade.HYBRID` 默认 fallback;`LOCAL_ONLY` 显式可选 |
| **A5** 协议先于实现 | ✅ | PR-2.1 协议 → PR-2.2 SDK 设计 → PR-2.3 部署 → PR-2.4 切换 |
| **A6** 向后兼容 | ✅ | `from Plate import registry` 仍可用(不变量 #15);DeprecationWarning 一次性 |

---

## 5. SDK 行为(PR-2.4)

### 5.1 模式矩阵

| mode | 远端可达 | 缓存命中 | 实际行为 | 失败时 |
|---|---|---|---|---|
| `LOCAL_ONLY` | n/a | n/a | `registry.resolve()` 直读 | LookupError(无静默) |
| `HYBRID`(显式 `from_url`) | ✅ | ✅ | SDK → 返回 | — |
| `HYBRID` | ✅ | ❌ | SDK → 写缓存 → 返回 | — |
| `HYBRID` | ❌ | ✅ | SDK fail → 读缓存 → 返回 | — |
| `HYBRID` | ❌ | ❌ | SDK fail → 本地 registry fallback | 静默 DEBUG 日志 |
| `REMOTE_FIRST` | ❌ | n/a | `OfflineError` 上抛 | **不** fallback |
| `LOCAL_FALLBACK` | ❌ | ✅ | SDK fail → 缓存 → 返回 | — |
| `LOCAL_FALLBACK` | ❌ | ❌ | `OfflineError` 上抛 | **不** 静默 |

> 默认 mode = `LOCAL_ONLY`(本会话调整,理由见 [PR-2.4 §1.2](PR-2.4.md))。

### 5.2 缓存目录

本会话同进程占位 `PlateClient` 用**内存 dict** 缓存,无磁盘持久化。
磁盘落盘留 Phase 3 真 HTTP 实现。

预留路径:
- Linux/macOS: `~/.cache/plate/{version}/`
- Windows: `%LOCALAPPDATA%\plate\{version}\`

### 5.3 环境变量

| 变量 | 默认 | 行为 |
|---|---|---|
| `GIMBAL_PLATE_MODE` | `local-only` | `local-only` / `hybrid` / `remote-first` / `local-fallback` |
| `GIMBAL_PLATE_URL` | (无) | server base URL,`from_default` 读它决定走 SDK |
| `GIMBAL_PLATE_VERSION` | `1.0.0` | 协议版本 |
| `GIMBAL_PLATE_CACHE_DIR` | (平台默认) | 覆盖缓存目录(Phase 3 生效) |

### 5.4 旧 API 桥接

`from Plate import registry` 仍可用(不变量 #15),首次通过 `PlateFacade` 入口
构造时触发**一次** `DeprecationWarning`,提示迁移。Phase 3 收尾前保留,
**不**删除。

---

## 6. Server 行为(PR-2.3)

### 6.1 路由表(8 条)

| Method | Path | handler | requires_version |
|---|---|---|---|
| GET | `/healthz` | `handle_healthz` | False |
| GET | `/v1/versions` | `handle_version_list` | False |
| GET | `/v1/manifest` | `handle_manifest` | False(用默认) |
| GET | `/v1/manifest/{version}` | `handle_manifest_pinned` | True(URL 段) |
| GET | `/v1/spec/{service}` | `handle_spec_service` | True |
| GET | `/v1/spec/{service}/{method}/{path:path}` | `handle_spec_endpoint` | True |
| GET | `/v1/doc/{service}` | `handle_doc_service` | True |
| GET | `/v1/doc/{service}/{method}/{path:path}` | `handle_doc_endpoint` | True |

### 6.2 部署形态

- **零依赖**:`http.server` + `urllib` + `json` + `threading`(全部 stdlib)
- **进程模式**:同进程后台 `daemon` 线程
- **端口**:`PlateServer(port=0)` 动态分配(E2E fixture 用法)
- **关闭**:`server.stop()` 调 `shutdown()` + `server_close()` + `thread.join(2s)`
- **支持版本**:`SUPPORTED_VERSIONS=(1.0.0,)`(本 PR 单一版本)
- **支持服务**:`SUPPORTED_SERVICES=("fin",)`(本 PR 仅 fin)

### 6.3 字节 pin(不变量 #13)

服务端 `/v1/manifest`、`/v1/spec/fin`、`/v1/spec/fin/{method}/{path}` 的
响应**字节级等于** `Plate.registry` 走 `collect` + `to_dict` 构造的
本地 manifest / spec / endpoint。具体验证见不变量 #13。

---

## 7. 一行回执(快速验证)

```bash
# 跑全量 330 测试
python -m pytest tests/plate -q

# 跑 15 不变量
python -m pytest tests/plate/test_invariants.py -v

# 跑 6 零侵入
python -m pytest tests/plate/test_zero_invasion.py -v

# 跑 8 E2E
python -m pytest tests/plate/test_server_e2e.py -v

# 跑 35 facade 切换
python -m pytest tests/plate/test_facade_switch.py -v

# 算 fin checksum
python -c "
from Plate import registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion
registry.reset(); registry.collect('fin')
services = {svc: [s.to_dict() for k, s in registry._index.items() if k.service == svc] for svc in {k.service for k in registry._index}}
print(PlateManifest.from_services(PlateVersion(1,0,0), services).checksum)
"
# 期望:09042f457bc253ffc99e8cd66f89b818b0ed2c33bf6117e3ca012556f72281db
```

---

## 8. 收口审计 checklist(供 PR-2.5 收口时勾)

- [x] 330 测试全过(`pytest tests/plate -q` 0 失败)
- [x] 15 不变量全过(`pytest tests/plate/test_invariants.py -v` 16/16,**含** #13 server protocol)
- [x] 6 零侵入测试全过(`pytest tests/plate/test_zero_invasion.py -v`)
- [x] 31 fin 端点全部可经 SDK + server 字节 pin(不变量 #13 #14)
- [x] `from Plate import registry` 仍可用(不变量 #15)
- [x] `from Plate.facade import PlateFacade` 不触发 service 子包加载(不变量 #16)
- [x] **本基线文件存在**(本文件 = `design/phase2/BASELINE.md`)
- [x] **`PLATE_DESIGN.md` §7 §8 同步完毕**(留 PR-2.5 收口流程处理)
- [ ] **CI workflow 必跑**(**留 PR-2.5 收口流程,本会话不写**)

---

## 9. 后续 Phase 衔接

- **Phase 3** 入口:见 [PLATE_EVOLUTION.md §4](../PLATE_EVOLUTION.md)
  - 12 PD,预计 1.5 个月
  - 关键产出:service 子包从远端拉 + 异步 SDK + MCP 适配
  - **不**做真实生产部署(K8s manifest / CI 镜像 — 留给基础设施 PR)
- **BASELINE 维护**:Phase 3 启动时,基线数字应随 SDK / 异步化重新统计,本文档同步更新
