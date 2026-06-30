# PR-4.5 核心模块测试骨架建立

> Phase 4 / PR 5 of 9
> 优先级: 🟡 P1 测试
> 估计工作量: 2 PD
> 阻塞: PR-4.8

## 一句话目标

把 7+ 个"零覆盖"的核心模块拉到 ≥70% 行覆盖, 同时建立一个可复用的 pytest fixture 体系, 让后续 PR 落地即可"接入测试"。

---

## 背景与动机

### 现状 finding

`tests/` 共 51 个 `.py`, 其中 `tests/plate/*` (17 个) 属于 plate 项目; 余下 `tests/unit + integration` 共 34 个相关; 再筛出与本次核心模块相关:

| 模块 | 现有 unit test 文件 | 行覆盖估计 |
|---|---|---|
| `core/runner.py` (Engine) | 0 | <5% |
| `core/scenario_runner.py` | 0 | <5% |
| `statemachine/*` | 0 | <5% |
| `preprocessor/*` | 1 (`test_config_vars.py`) | ~5% |
| `strategy/*` | 0 | <5% |
| `context/*` | 0 | <2% |
| `events/*` | 0 | <5% |
| `core/hooks.py` | 0 | <5% |
| `plugins/*` | 0 | <5% |
| `repository/*` | 1 (`test_local_fs_store.py`) | ~10% |
| `auth/*` | 0 | <5% |
| `cli/*` | 0 | <2% |
| `schema/*` | 0 | <5% |
| `utils/jsonpath.py` | 0 | 0% |

→ **核心模块几乎"裸奔合并"**. 任何一个 `修复 #X` 注释都意味着没有 regression 保护.

## 范围与非目标

**In scope**:

- 建立 `tests/conftest.py` 的几个共享 fixture (`mock_asset_store`, `mock_event_bus`, `mock_reporter_runtime`, `scenario_factory`, ...)
- 为以下模块各加最小测试包:
  - statemachine / preprocessor / strategy / events / hooks / repository / auth / cli / schema / utils
- 加 pytest-cov + 阈值 (`pytest.ini` 设置 `--cov-fail-under=70`)
- 把 `tests/plate/*` 移出 pytest 默认 rootdir, 进 `addopts = --ignore=tests/plate`(让 plate CI 单独跑)

**Out of scope**:

- E2E 真实 HTTP 集成(只有 contract test 用 `respx` / `httpx_mock`)
- Hypothesis-style property-based 测试(后续 PR)

---

## 设计

### 1. conftest fixture 拓扑

```python
# tests/conftest.py (新增 / 重写)
@pytest.fixture
def tmp_assets(tmp_path):
    return tmp_path / "assets"

@pytest.fixture
def mock_asset_store(tmp_assets):
    return FilesystemAssetStore(root=str(tmp_assets))

@pytest.fixture
def mock_event_bus():
    return InMemoryEventBus(thread_pool_size=2)

@pytest.fixture
def mock_reporter_runtime():
    return ReporterRuntime(ReporterRegistry())

@pytest.fixture
def scenario_factory():
    """构造最小合法 scenario 的工厂, 支持覆写 steps / setup / teardown."""
    def _make(*, name="sc-1", steps=(), setup=None, teardown=None):
        return Scenario(name=name, steps=list(steps), setup=setup, teardown=teardown)
    return _make

@pytest.fixture
def cli_runner():
    """typer.testing.CliRunner, 自动 patch signal handler."""
    from typer.testing import CliRunner
    return CliRunner()
```

### 2. 各模块最小测试包

| 测试文件 | 覆盖范围 | 用例数(估计) |
|---|---|---|
| `tests/unit/test_statemachine/test_states.py` | VALID_TRANSITIONS 白名单 / 黑名单 | 12 |
| `tests/unit/test_statemachine/test_engine.py` | calling/verifying/teardown 三态 | 8 |
| `tests/unit/test_statemachine/test_exceptions.py` | InvalidTransition / AlreadyTerminal | 4 |
| `tests/unit/test_preprocessor/test_orchestrator.py` | 5 phase 串联 | 5 |
| `tests/unit/test_preprocessor/test_phase_service.py` | 单 service / 多 service 拒(配合 PR-4.4) | 4 |
| `tests/unit/test_strategy/test_dispatcher.py` | 注册 / 查找 / NotFound | 6 |
| `tests/unit/test_strategy/test_builtin_assertion.py` | eq / in / contains / 自定义失败信息 | 5 |
| `tests/unit/test_strategy/test_builtin_extract.py` | jsonpath 抽取 / 写入 context | 4 |
| `tests/unit/test_strategy/test_builtin_sleep.py` | happy / cancel 时立即返回 | 3 |
| `tests/unit/test_strategy/test_builtin_poll.py` | 成功 / 超时 / 错异常 | 4 |
| `tests/unit/test_strategy/test_builtin_composite.py` | all-pass / one-fail | 3 |
| `tests/unit/test_events/test_bus.py` | subscribe / unsubscribe / bus / error isolation | 6 |
| `tests/unit/test_events/test_subscription.py` | SYNC/ASYNC/BATCH 语义 | 4 |
| `tests/unit/test_core/test_hooks.py` | register / execute / STOP / payload 改写 | 6 |
| `tests/unit/test_repository/test_store_remove_gc.py` | refcount / 单 ref 后删 / 多 ref 后保留 | 5 |
| `tests/unit/test_repository/test_store_list_filter.py` | namespace_prefix / tag | 4 |
| `tests/unit/test_auth/test_auth_registry.py` | set / get / has / clear / snapshot | 4 |
| `tests/unit/test_auth/test_auth_manager.py` | get_auth 缓存 / refresh / 错误 wrap | 6 |
| `tests/unit/test_auth/test_authenticator_get.py` | URL 匹配三档 + 兜底 | 4 |
| `tests/unit/test_cli/test_run_launch.py` | 输入三种 / 干运行 / exit_code | 6 |
| `tests/unit/test_schema/test_scenario.py` | 最小 schema 反序列化 | 3 |
| `tests/unit/test_schema/test_ref.py` | Ref / Inline / Entity 三模式 | 4 |
| `tests/unit/test_utils/test_jsonpath.py` | 路径语法 + filter | 12 |
| `tests/unit/test_utils/test_template.py` | 整个 + 嵌入 + strict | 6 |
| **合计** | | **~140** |

### 3. pytest 配置

`pytest.ini`:

```ini
[pytest]
addopts =
    --strict-markers
    --cov=gimbal
    --cov-report=term-missing
    --cov-report=html:reports/coverage/html
    --cov-fail-under=70
    --ignore=tests/plate
markers =
    integration: 集成测试(需要外部资源)
    slow: 长时跑
filterwarnings =
    ignore::DeprecationWarning:pydantic
    ignore::DeprecationWarning:yaml
```

> reviewer 决定阈值; 起始可设 `--cov-fail-under=40`, 每个 PR 提升 5%, 直到 70.

### 4. 覆盖率门槛策略

- 每完成一个 PR, 期望覆盖率 净增 ≥ +2%
- PR 模板"模块改动清单"必须附"对应 test 文件路径"
- `tests/plate/*` 移出 coverage 统计

### 5. 排除 `tests/plate/`

`tests/conftest.py` 加 `collect_ignore_glob`:

```python
collect_ignore_glob = ["plate/*"]
```

让 plate 项目单独跑 (e.g. `pytest tests/plate -p tests/plate/conftest.py`).

### 6. CI 配置

`.github/workflows/ci.yml`(或现有 CI) 增:

```yaml
- name: Unit tests
  run: |
    pytest tests/ -x -q --cov
- name: Coverage report
  if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v4
  with:
    name: coverage-html
    path: reports/coverage/html
```

> 若 CI 失败, 临时降阈值, 但必须留 TODO.

---

## 验收 (DoD)

### 必须

- [ ] `tests/conftest.py` 含至少 5 个共享 fixture
- [ ] 新增 ≥ 80 个 unit test case(覆盖上表 24 个测试文件)
- [ ] 覆盖率阈值 ≥ 40%(起步), CI 失败时阻断 merge
- [ ] `pytest tests/unit` 全部通过(忽略 plate)
- [ ] `tests/plate/*` 不再被默认 pytest collection
- [ ] DECISIONS D33 / CHANGELOG

### 应有

- [ ] `pytest --cov` HTML 报告链接到 PR comment
- [ ] Phase 4 完结时, 阈值提升到 70%

### Nice to have

- [ ] mutmut / mutpy 给 statemachine + strategy 各跑一次 mutation testing
- [ ] hypothesis 跑 jsonpath + template

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 老 scenario/json 格式让 fixture 工厂不兼容 | fixture 工厂支持 kwargs 覆盖 | 不回滚; 旧用法继续 |
| 阈值 40% 一刀切会让现有 PR 失败 | 阈值从 30 起步, 每 PR +5% | 临时阈值 |
| plate 隔离让 plate 的 regression 无人盯 | 在 CI 中加 `pytest tests/plate -p ...` 独立 job | 调整 collect_ignore_glob |

---

## 任务清单

- [ ] T1 conftest.py 重写, fixture 工厂
- [ ] T2 pytest.ini + CI 配置
- [ ] T3 statsmachine (3 文件)
- [ ] T4 preprocessor (2 文件)
- [ ] T5 strategy (6 文件)
- [ ] T6 events (2 文件)
- [ ] T7 hooks (1 文件)
- [ ] T8 repository (2 文件)
- [ ] T9 auth (3 文件)
- [ ] T10 cli (1 文件)
- [ ] T11 schema (2 文件)
- [ ] T12 utils (2 文件)
- [ ] T13 DECISIONS D33 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.0 (auth 测试), PR-4.1 (repo 测试)
- **被依赖**: PR-4.6 (空壳决策看测试覆盖率), PR-4.7 (docs)
- **可并行**: PR-4.4 (preprocessor 重构期间同步测试)
