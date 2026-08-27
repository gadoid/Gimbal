# 服务别名 + 执行环境彻底退役 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地已拍板 spec 的四块改造 — ①引擎 per-step base_url 三触点 ②执行环境(execution env)彻底退役清理干净 ③服务别名前缀派生(纯前端) ④RunDialog 并集绑定行。

**Architecture:** 引擎侧把「场景级单一 base_url」升级为「per-step 按 `api.service` 查 `scenario.config.services` 声明 dict,回落兼容 base_url」;平台侧把执行环境模型(RunEnv/envs.yaml//api/envs/RunRequest.env/RunScheme.envId/ExportOverlay.envId/materialize env 补缺层)整链删除,URL 链收敛为「显式绑定 url > config.services 声明值」两层;别名特性零 schema 增 — 别名键 = `<目录服务名>-<后缀>` 编码在键名里,归属由前端按「最后一个 `-` 切分 + 目录名集合成员判定」派生,存储永远是全串键(引用 `steps[].api.service` + 声明 `config.services` 两个现有字段)。

**Tech Stack:** Python(FastAPI + pydantic v2 + pytest)/ Vue 3 `<script setup>` + TS + vitest / gimbal 引擎(pydantic 场景模型)。

**Spec:** [2026-08-27-service-alias-env-retirement-design.md](../specs/2026-08-27-service-alias-env-retirement-design.md)(拍板记录 D1-D8 是最高约束,实施不得偏离)

## Global Constraints

- **plate 零改动**;引擎 `config/env/*.yml` 零修改(spec D8)。平台唯一删除的配置文件是 `backend/app/core/envs.yaml`。
- **后端编排 schema 别名零新增**(spec §1.3):别名特性 = 纯前端 + 引擎;不得给 Orchestration/RunScheme/RunRequest 加任何别名字段。
- **api.service 契约禁令**(spec §1.6):任何 plate 拉取驱动的回写(适配 ops、未来契约同步、未来导入)不得触碰 `api.service`;导入按不透明键处理(禁目录存在性校验、禁按目录名规范化改写)。
- **命名约定**(spec §1.3):别名 = `<目录服务名>-<后缀>`,`-` 为唯一分隔符,后缀非空且不含 `-`;切分按**最后一个** `-`(固定切分点,不搜索前缀、不按最长)。
- **URL 优先级链**(spec §2.2):显式绑定 url > `config.services` 声明值,两层;未声明且未绑定 → 引擎现有显式报错语义不变。
- **校验全表警告级不阻塞**(spec D6):撞目录/跨服务/裸声明黄警,未声明红标但可现场救燃。
- **回归底线**(spec §8):现有测试套件只增不减全绿;`vue-tsc --noEmit` 绿;引擎单服务场景行为逐字节不变。
- 工作目录:引擎任务在仓库根 `d:/Gimbal/Gimbal`;后端任务在 `src/gimbal-platform/backend`;前端任务在 `src/gimbal-platform/frontend`。分支 `strbody_avaliable`。

---

### Task 1: 引擎 per-step base_url 三触点

**Files:**
- Modify: `src/gimbal/preprocessor/scenario_preprocessor.py:94-131`(`run()` 签名与 docstring)
- Modify: `src/gimbal/core/scenario_runner.py:100-114`(StepRunner 构造)、`149-157`(StepStateMachine 构造)、`261`(run() 解包)、`276-282`(StepRunner 构造点)
- Modify: `src/gimbal/statemachine/engine.py:96-112`(docstring 示例)、`114-135`(`__init__`)、`376-425`(`_do_http_call`)
- Modify: `pyproject.toml:70-77`(testpaths 增 `tests/unit/engine`)
- Create: `tests/unit/engine/test_per_step_service_url.py`

**Interfaces:**
- Consumes: 现有 `ScenarioPreprocessor._pick_base_url`(保留不动,B1 脚本测试继续绿)、`StepStateMachine._do_http_call` 现有错误语义(#6)。
- Produces: `ScenarioPreprocessor.run() -> tuple[list[StepUnion], str, dict[str, str]]`(第三项 = **仅场景声明**的 services dict,不合并 bootstrap);`StepRunner.__init__(..., service_base_url: str = "", services: Optional[dict] = None, ...)`;`StepStateMachine.__init__(..., service_base_url: str = "", services: Optional[dict[str, str]] = None, ...)`;engine 查表规则 `self._services.get(api.service) or self._service_base_url`。

- [ ] **Step 1: 写失败测试(新 pytest 文件)**

创建 `tests/unit/engine/test_per_step_service_url.py`(pytest 风格:sys.path 注入 + 真实 schema 构造,`__new__` 组装状态机 — 与 `tests/unit/test_defect_fixes.py` 的 `_make_sm_with_api` 同款手法,但 bus=None 即可,`_emit_http_request`/`_fire_hook` 均有 None 守卫):

```python
"""D7 per-step base_url:api.service 查 scenario.config.services 声明 dict,
未命中回落兼容 base_url,双缺失显式报错(spec 2026-08-27 §4)。

pytest 化子目录(testpaths 收录);手法与 tests/unit/test_defect_fixes.py
的 _make_sm_with_api 一致:StepStateMachine.__new__ 直填字段,dispatcher
用 MagicMock 捕获 call_spec.url。
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.schema.api import Api
from gimbal.schema.request import Request
from gimbal.schema.step import Step
from gimbal.schema.strategy import StrategyResult, StrategyStatus
from gimbal.statemachine import engine as sm_engine


def _make_sm(service: str, base_url: str, services: dict | None = None):
    """最小 StepStateMachine 替身:只填 _do_http_call 触达的字段。"""
    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "s1"
    sm._step_schema = Step(
        kind="step",
        api=Api(kind="api", service=service, method="GET", path="/x",
                headers={}, timeout=30.0),
        request=Request(kind="request", body={}),
        strategy=[],
    )
    sm._dispatcher = MagicMock()
    sm._dispatcher.dispatch.return_value = StrategyResult(
        status=StrategyStatus.PASSED, strategy_id="_call",
        message="mock ok", duration_ms=0.0,
    )
    sm._view = MagicMock()
    sm._service_base_url = base_url
    sm._services = services or {}
    sm._on_transition = None
    sm._hooks = None
    sm._bus = None
    sm._state = sm_engine.StepState.CALLING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None
    sm._handlers = {}
    return sm


def _called_url(sm) -> str:
    return sm._dispatcher.dispatch.call_args[0][0].url


def test_per_step_lookup_beats_fallback_base_url():
    """声明 dict 命中 → 用声明值,不用回落 base_url(D7 主路径)。"""
    sm = _make_sm("fin-service", base_url="https://fallback.example",
                  services={"fin-service": "https://fin.example"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://fin.example/x"


def test_two_services_route_independently():
    """多服务场景:两个 service 各自查表,不再共享一个 base_url(旧错路由修复)。"""
    sm_a = _make_sm("fin-service", base_url="https://fallback.example",
                    services={"fin-service": "https://a.example",
                              "order-svc": "https://b.example"})
    sm_b = _make_sm("order-svc", base_url="https://fallback.example",
                    services={"fin-service": "https://a.example",
                              "order-svc": "https://b.example"})
    assert sm_a._do_http_call().status == StrategyStatus.PASSED
    assert sm_b._do_http_call().status == StrategyStatus.PASSED
    assert _called_url(sm_a) == "https://a.example/x"
    assert _called_url(sm_b) == "https://b.example/x"


def test_missing_key_falls_back_to_base_url():
    """声明 dict 未含该键 → 回落 _service_base_url(兼容路径)。"""
    sm = _make_sm("unknown-svc", base_url="https://fallback.example",
                  services={"fin-service": "https://fin.example"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://fallback.example/x"


def test_both_missing_keeps_explicit_error():
    """dict 未命中且 base_url 为空 → 保留 #6 显式报错(消息不变)。"""
    sm = _make_sm("orphan-svc", base_url="", services={"fin-service": "https://x"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.ERROR
    assert "no service_base_url configured" in result.message
    assert "orphan-svc" in result.message
    assert sm._dispatcher.dispatch.call_count == 0


def test_empty_services_dict_identical_to_legacy():
    """services 空 dict → 行为与旧版逐字节一致(单服务回归底线)。"""
    sm = _make_sm("fin-service", base_url="https://only.example", services={})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://only.example/x"


def test_preprocessor_run_returns_declared_services():
    """run() 三元组:第三项 = 场景声明 dict 原样(不合并 bootstrap)。"""
    from datetime import datetime, timezone

    from gimbal.auth.registry import AuthRegistry
    from gimbal.config.models import BootstrapConfig
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.scenario import Config as ScenarioConfig
    from gimbal.schema.scenario import Meta, Scenario

    def _step(service_name: str):
        return Step(
            kind="step",
            api=Api(kind="api", service=service_name, method="GET", path="/x",
                    headers={}, timeout=30.0),
            request=Request(kind="request", body={}),
            strategy=[],
        )

    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(name="t", description="d", module="m", priority=1,
                  author="a", owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(services={
            "user-svc": "https://user.example.com",
            "order-svc": "https://order.example.com",
        }),
        resource={},
        steps=[_step("user-svc"), _step("order-svc")],
    )
    pre = ScenarioPreprocessor(
        scenario_schema=scenario,
        bootstrap_config=BootstrapConfig(env="dev", mode="local", log_level="info"),
        auth_registry=AuthRegistry(),
    )
    resolved, base_url, services = pre.run()
    assert services == {"user-svc": "https://user.example.com",
                        "order-svc": "https://order.example.com"}
    # base_url 兼容路径仍在(_pick_base_url 多键取第一个)
    assert base_url == "https://user.example.com"
    assert len(resolved) == 2
```

- [ ] **Step 2: 把新目录挂进 pytest testpaths**

`pyproject.toml` `[tool.pytest.ini_options]` testpaths 列表(`tests/unit/scenario`,条目后)追加一行:

```toml
    "tests/unit/engine",       # D7 per-step base_url(spec 2026-08-27)
```

- [ ] **Step 3: 跑测试确认失败**

Run(仓库根): `python -m pytest tests/unit/engine -q`
Expected: FAIL — `TypeError: StepStateMachine.__init__() got an unexpected keyword argument 'services'` 类错误 / `_services` AttributeError;`run()` 解包 3 元组处 ValueError。

- [ ] **Step 4: 实现三触点**

**4a. `src/gimbal/preprocessor/scenario_preprocessor.py`** — `run()`(L94)签名与返回改三元组;在 `base_url = self._pick_base_url()`(L123)后取声明 dict 并返回:

```python
    def run(self) -> tuple[list["StepUnion"], str, dict[str, str]]:
        """执行完整预处理入口,按顺序执行 0)引用物化、1)认证、2)构建查询根、3)批量展开 steps 模板、4)提取 base_url,返回 (resolved_steps, base_url, services) 元组。

        步骤:
          0. 引用物化（asset_store 不为 None 时）：递归替换 scenario 中所有
             Ref 节点（StepRef / ApiRef / RequestRef / StrategyRef / Ref）为
             仓库拉来的真实数据类对象。必须在认证 / 模板替换之前完成，
             否则执行器会碰到未解析的 Ref 节点。
          1. 认证（填充 token 到 AuthRegistry）
          2. 构建查询根对象
          3. 批量展开 steps 模板
          4. 提取 base_url + 场景声明 services（D7 per-step 查表用）
        """
```

return 前(L123-131)改为:

```python
        # 4. base_url + 场景声明 services(D7 per-step base_url)
        base_url = self._pick_base_url()
        # 仅场景声明 dict,不合并 bootstrap —— per-step 查表范围拍板 D7:
        # 只查 scenario.config.services(bootstrap 独有键进不了 URL 解析
        # = 现状保持)。模板解析 root["service"] 的合并语义不受影响。
        services = dict(getattr(self._schema.config, "services", None) or {})

        logger.info(
            "[Preprocessor] 预处理完成: scenario_id={} steps={} base_url={} services={}",
            self._schema.scenarioId,
            len(resolved_steps),
            base_url,
            sorted(services),
        )
        return resolved_steps, base_url, services
```

**4b. `src/gimbal/core/scenario_runner.py`** — StepRunner 构造(L100-114)增可选参:

```python
    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        service_base_url: str = "",
        hook_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        services: Optional[dict] = None,
    ) -> None:
        """初始化 StepRunner，保存 strategy dispatcher、ctx_manager、service_base_url/services 以及可选的 hook_registry 与 event_bus。"""
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._service_base_url = service_base_url
        # D7 per-step 查表:api.service → 场景声明 URL;空 dict 回落 base_url
        self._services = services or {}
        self._hooks = hook_registry
        self._bus = event_bus
        logger.debug("[StepRunner] 初始化: service_base_url={} services={}",
                     service_base_url, sorted(self._services))
```

StepStateMachine 构造点(L149-157)透传:

```python
        sm = StepStateMachine(
            step_id=step_id,
            step_schema=step_schema,
            dispatcher=self._dispatcher,
            view=StepContextAdapter(step_ctx),
            service_base_url=self._service_base_url,
            hook_registry=self._hooks,
            event_bus=self._bus,
            services=self._services,
        )
```

run() 调用点(L261)与 StepRunner 构造点(L276-282):

```python
        resolved_steps, base_url, services = preprocessor.run()
```

```python
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            service_base_url=base_url,
            hook_registry=self._hooks,
            event_bus=self._bus,
            services=services,
        )
```

**4c. `src/gimbal/statemachine/engine.py`** — `__init__`(L114-135)增 `services: Optional[dict[str, str]] = None` 参数并存储(在 `self._service_base_url = service_base_url` 后):

```python
        self._service_base_url = service_base_url
        # D7 per-step 路由:api.service → 声明 URL 查表;空/未命中回落 base_url
        self._services = services or {}
```

类 docstring 的使用示例(L96-112 一带)补一行 `services={"user-service": "http://user-service"},`。

`_do_http_call`(L376-425)的 URL 解析段重排 — 查表优先、空判后置(消息原文不动):

```python
        # D7 per-step 路由 + 修复 #6:先查场景声明 dict(api.service 是
        # config.services 的 key),未命中回落兼容 _service_base_url
        # (_pick_base_url 兼容路径);两者皆空 → 显式失败,不造幽灵 URL。
        service_url = self._services.get(api.service) or self._service_base_url
        if not service_url:
            logger.error(
                "[SM {}] 缺少 service_base_url: api.service={!r}，"
                "请在 scenario.config.services 或 bootstrap.services 中配置",
                self._step_id, api.service,
            )
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id="http_call",
                message=(
                    f"no service_base_url configured; api.service={api.service!r} "
                    "is a service key, not a URL. Configure scenario.config.services "
                    "or bootstrap.services with a real base URL."
                ),
            )
```

(原 L390-405 的 `if not self._service_base_url:` 块与 `service_url = self._service_base_url` 行由上段整体取代;`request = self._step_schema.request` 起的后续代码不变。)

- [ ] **Step 5: 跑新测试确认通过**

Run: `python -m pytest tests/unit/engine -q`
Expected: 6 passed。

- [ ] **Step 6: 引擎存量回归**

Run: `python -m pytest tests/plate tests/unit/reporter tests/unit/generator tests/unit/config tests/unit/scenario tests/unit/runtime_control -q && python tests/unit/test_defect_fixes.py`
Expected: pytest 全绿;脚本套件末尾 `ALL TESTS PASSED`(B1 直接测 `_pick_base_url`,未动,应保持绿;#6.1/#6.2 消息与行为不变)。

- [ ] **Step 7: Commit**

```bash
git add src/gimbal/preprocessor/scenario_preprocessor.py src/gimbal/core/scenario_runner.py src/gimbal/statemachine/engine.py tests/unit/engine pyproject.toml
git commit -m "feat(engine): per-step base_url — api.service 查场景声明 dict,回落兼容 base_url (D7)"
```

---

### Task 2: run_materialize env 补缺层退役(纯函数)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_materialize.py`
- Modify: `src/gimbal-platform/backend/tests/test_run_materialize.py`

**Interfaces:**
- Consumes: 无外部依赖(纯函数测试驱动)。
- Produces: `materialize_run_copy(converted, *, service_bindings=None, resolved_auths=None, built_in_users=None)`(**`env_base_url` 参数删除**);`_apply_services(cfg, *, steps, bindings)`(env 补缺分支删除;绑定优先语义不变)。Task 3 的 dispatcher/preview-plate 调用点按此签名跟进。

- [ ] **Step 1: 更新纯函数测试(先失败)**

`tests/test_run_materialize.py`:删除 `test_env_fills_missing_referenced_service` 与 `test_no_env_leaves_gap_visible` 中 env 相关用例的 `env_base_url=` 实参;模块 docstring 第 3 行优先级描述改为两层。新增锁两层链的用例(文件末追加;`_converted()` 为文件内既有 fixture 函数,步骤引用按需构造):

```python
def test_no_env_layer_binding_and_authored_only() -> None:
    """D2:env 补缺层删除后,URL 链只剩 显式绑定 > authored。"""
    # 已有声明(authored)+ 无绑定 → 原样保留
    out = materialize_run_copy(_converted())
    assert out["config"]["services"]["fin-service"] == "https://authored"

    # 显式绑定覆盖 authored(语义不变)
    out = materialize_run_copy(
        _converted(),
        service_bindings={"fin-service": {"url": "https://bound"}},
    )
    assert out["config"]["services"]["fin-service"] == "https://bound"

    # 未声明且未绑定 → 留空(引擎显式报错语义,RunDialog 并集行提前发现)
    out = materialize_run_copy(_converted())
    assert "svc-orphan" not in out["config"]["services"] or \
        not out["config"]["services"].get("svc-orphan")
```

(若 `_converted()` 现有步骤不引用 `fin-service`/`svc-orphan`,以文件内既有 `_converted` 的实际 services/steps 形状为准改写断言键名 — 断言意图保持:「绑定覆盖声明、env 层不存在、缺口留空」。)

- [ ] **Step 2: 跑测试确认失败**

Run(backend 目录): `python -m pytest tests/test_run_materialize.py -q`
Expected: FAIL — `TypeError: materialize_run_copy() got an unexpected keyword argument 'env_base_url'`(旧用例仍传该参)。

- [ ] **Step 3: 实现**

`run_materialize.py`:

- `materialize_run_copy` 签名删 `env_base_url: str = ""` 参数;docstring services 行改:`* services:显式绑定 url > 场景 authored(仅对 steps 实际引用的 service 键生效,未引用键原样保留;D2 env 补缺层已退役)`
- `_apply_services` 签名删 `env_base_url: str`,调用点(L37-38)同步;函数体 env 分支删除:

```python
def _apply_services(cfg: dict, *, steps: list,
                    bindings: dict[str, dict]) -> None:
    services: dict[str, Any] = cfg["services"]
    for svc in _referenced_services(steps):
        bound_url = (bindings.get(svc) or {}).get("url")
        if bound_url:
            services[svc] = bound_url                    # 显式绑定最优先
        # D2:env.baseUrl 补缺层退役 — 未绑定则留给 authored/缺口
        # (未声明缺口由引擎显式报错,RunDialog 并集行提前发现)
```

- 模块 docstring 优先级描述同步两层。

- [ ] **Step 4: 跑测试确认通过 + 后端存量状态确认**

Run: `python -m pytest tests/test_run_materialize.py -q`
Expected: PASS。(`test_run_m1_capabilities.py` 等调用方此刻会红 — 属 Task 3 范围,不在此修;本步只锁纯函数层。)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_materialize.py src/gimbal-platform/backend/tests/test_run_materialize.py
git commit -m "refactor(backend)!: materialize_run_copy 退役 env_base_url 补缺层 (D2)"
```

---

### Task 3: 后端执行环境彻底退役(schemas / dispatcher / routers / 端点 / 配置文件 / 测试清理)

> 「清理干净」任务:删模型、删端点、删文件、删校验、删留痕键,并同步全部测试。旧客户端多发的 env/envId 键由 pydantic v2 默认 extra=ignore 静默忽略(不 422 仅失效)— 加测试锁死该兼容行为。

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:185-191, 202-212, 226-233, 236-268`
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(env 校验 L366-383、config_json L444、_fanout env 参 L504/L468、日志行 env 键 L633、materialize 调用 L672-681)
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py`(import L45、preview-plate overlay L150-161、`_warn_dangling_refs` L329/L357-362)
- Modify: `src/gimbal-platform/backend/app/main.py:25,116`(envs router 注册)
- Delete: `src/gimbal-platform/backend/app/routers/envs.py`、`src/gimbal-platform/backend/app/services/env_store.py`、`src/gimbal-platform/backend/app/core/envs.yaml`
- Modify tests: `tests/helpers.py`(删 `test_env`)、`tests/test_run_baseline.py`、`tests/test_run_cancel.py`、`tests/test_run_capacity.py`、`tests/test_run_case_retention.py`、`tests/test_run_evidence.py`、`tests/test_run_log_integrity.py`、`tests/test_run_plate_resilience.py`、`tests/test_run_m1_capabilities.py`、`tests/test_scenario_composer_plate_integration.py`、`tests/test_run_schemes_endpoint.py`、`tests/test_export_overlay_equivalence.py`、`tests/test_scenario_composer_api.py`
- Delete test: `tests/test_run_env_authority.py`
- Modify: `src/gimbal-platform/backend/app/services/adaptation_ops.py`(契约禁令注释)

**Interfaces:**
- Consumes: Task 2 的 `materialize_run_copy` 新签名。
- Produces: `RunRequest`(无 env 字段:scenarioId/dataSetIds/serviceBindings/stepTo/nRuns/parallel);`RunScheme = {name, dataSetIds, serviceBindings, plugins, logSub}`;`ExportOverlay = {serviceBindings}`;`GET /api/envs` 端点不复存在;config_json 不再落 `envId` 键(历史行旧键由前端 RECIPE_LABELS 标签保留可读)。Task 4 前端按此契约跟进。

- [ ] **Step 1: 更新测试到目标契约(先失败)**

1. **删整文件**:`tests/test_run_env_authority.py`(P5 env 服务端权威 — 语义随 env 一并退役)、`git rm` 或删除。
2. `tests/helpers.py`:删除 `test_env()` 函数(L68-70 一带)。
3. **全部 /runs 投递体删 env 键**(逐文件 grep `"env":` 与 `test_env`):`test_run_baseline.py`(4 处 + import)、`test_run_cancel.py`(3 处)、`test_run_capacity.py`(2 处)、`test_run_case_retention.py`(1 处)、`test_run_evidence.py`(2 处)、`test_run_log_integrity.py`(1 处)、`test_run_plate_resilience.py`(2 处)、`test_run_m1_capabilities.py`(`_run_payload` 里的 env + import;顺带删除 `test_env_base_url_materializes_unmapped_services` 整个用例)、`test_scenario_composer_plate_integration.py`(3 处,L255 的内联 env dict 一并删)。改法一律是:

```python
# 改前
"scenarioId": "sc-base", "dataSetIds": [], "env": test_env(),
# 改后
"scenarioId": "sc-base", "dataSetIds": [],
```

4. `tests/test_run_baseline.py` 末尾追加旧客户端兼容锁:

```python
async def test_stale_env_key_silently_ignored(client, monkeypatch):
    """D2:RunRequest 删 env 后,旧客户端仍发 env 键 → 静默忽略不 422。"""
    from tests.helpers import make_draft, register_and_login, wait_until
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=make_draft("sc-stale-env"))
    monkeypatch.setattr(gl, "launch", lambda *a, **k: __import__(
        "tests.helpers", fromlist=["launch_ok"]).launch_ok())
    monkeypatch.setattr(pc, "convert", _fake_convert)
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-stale-env", "dataSetIds": [],
        "env": {"envId": "dev-local", "name": "dev-local", "baseUrl": "http://x"},
    })
    assert r.status_code == 201, r.text
    run_id = r.json()["runId"]
    await wait_until(
        lambda: list(run_dispatcher._run_dir(run_id).rglob("case.json"))
    )
    # config_json 不再留痕 envId
    exec_row = (await client.get("/api/executions", headers=headers)).json()
    assert all("envId" not in (e.get("config") or {}) for e in exec_row.get("items", []))
```

(若该文件已有同款 `_fake_launch`/`_fake_convert` 局部定义,复用之,勿重复定义。)

5. `tests/test_run_schemes_endpoint.py`:`SCHEMES` 删 `"envId": "test-env-A",`;roundtrip 断言 L31 的 `["envId"]` 改为断言 `serviceBindings` 键;追加旧方案静默降级锁:

```python
async def test_legacy_envid_schemes_silently_dropped(client):
    """D2:旧存量方案含 envId → pydantic 忽略,存下的方案无该键。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=bob,
                            json={"schemes": [{
                                "name": "legacy", "envId": "dev-local",
                                "dataSetIds": [], "serviceBindings": {},
                            }]})
    assert resp.status_code == 200
    assert "envId" not in resp.json()[0]
```

6. `tests/test_export_overlay_equivalence.py`:`OVERLAY` 删 `"envId": "test-env-A",` 行(等价断言本体不动 — 两路同走无 env 的 materialize,黄金等价随两层链更新)。
7. `tests/test_scenario_composer_api.py`:删除 `test_list_envs` 用例与 `test_env` import(`# ── envs ──` 分节注释一并删)。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_run_materialize.py tests/test_run_baseline.py tests/test_run_schemes_endpoint.py tests/test_export_overlay_equivalence.py -q`
Expected: FAIL — dispatcher/preview-plate 仍引用 `env_base_url`/`req.env`/env_store(TypeError/AttributeError 系列)。

- [ ] **Step 3: 实现删除**

**3a. schemas(`app/schemas/scenario_composer.py`)**:
- 删 `RunEnv` 类(L186-191)。
- `RunScheme`:删 `env_id` 字段(L207),类 docstring 不变。
- `ExportOverlay`:删 `env_id` 字段(L231),docstring 补「envId 已随 D2 退役」。
- `RunRequest`:删 `env: RunEnv`(L260)。
- 文件内 `# ─── envs / runs ──` 分节注释改 `# ─── runs ──`。

**3b. run_dispatcher**:
- 删 env 校验块(L366-383:`server_env = next(...)` 到 mismatch warning 整段;步骤 2 注释一并清理为「2. Validate datasets」)。
- `_create_execution` 的 config_json 删 `"envId": req.env.env_id,` 行(L444),注释补「envId 已随 D2 退役;历史行旧键由前端 RECIPE_LABELS 保留可读」。
- `_fanout(...)` 调用(L462-475)删 `env=server_env.model_dump(...)` 行;`_fanout` 签名(L504)删 `env: dict,` 参;docstring 相应句删。
- `log_line`(L624-637)删 `"env": env,` 键。
- `materialize_run_copy` 调用(L672-681)删 `env_base_url=(env.get("baseUrl") or ""),` 行。
- import 行 L61 `from . import env_store, gimbal_launcher, plate_client` → `from . import gimbal_launcher, plate_client`。

**3c. routers/scenarios.py**:
- import L45 `from ..services import env_store, plate_client, run_dispatcher, scenario_store` → 去掉 `env_store`。
- preview-plate overlay(L150-161):`env_base_url = ""` 起到 `env_base_url = match[0].base_url or ""` 的整段删除;`materialize_run_copy(converted, env_base_url=env_base_url, ...)` 调用去该参。
- `_warn_dangling_refs`:删 `env_ids = ...`(L329)与 `if s.env_id and ...` 告警分支(L357-362);docstring 的 env 字样删。

**3d. main.py**:删 `envs,` import(L25)与 `app.include_router(envs.router, prefix="/api")`(L116)。

**3e. 删文件**:`app/routers/envs.py`、`app/services/env_store.py`、`app/core/envs.yaml`(`git rm`)。

**3f. adaptation_ops.py 契约禁令注释**(spec §9 首行对策)— 在 `check_step_addressable`(L93)函数 docstring 末尾追加:

```python
    """...

    契约禁令(spec 2026-08-27 §1.6):任何 plate 目录驱动的回写(适配 ops、
    未来契约同步/导入)不得触碰 ``api.service`` —— 它是用户引用键(可為
    别名全串),``view_hints.endpoint_id`` 才是目录锚点,两权分立。
    """
```

- [ ] **Step 4: 残留清扫(grep 验证「清理干净」)**

Run: `grep -rn "env_store\|RunEnv\|env_base_url\|list_envs\|envId\|envs.yaml\|/envs" src/gimbal-platform/backend/app --include="*.py"`
Expected: 0 命中(允许 `os.environ`/`CORS_ORIGINS` 等 .env 文件语义的无关命中 — 逐条人工核对为环境变量语义后放行)。

- [ ] **Step 5: 全量后端测试**

Run: `python -m pytest tests -q`
Expected: 全绿(被删用例不计;test_run_m1_capabilities 删 env 物化用例后其余通过)。

- [ ] **Step 6: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(backend)!: 执行环境彻底退役 — RunEnv//api/envs/envs.yaml/envId 整链删除,URL 链收敛两层 (D2)"
```

---

### Task 4: 前端执行环境退役 + RunDialog 并集绑定行

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunDialog.vue`
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`
- Modify: `src/gimbal-platform/frontend/src/types/scenario-composer.ts`(删 RunEnv)
- Modify: `src/gimbal-platform/frontend/src/stores/scenario-draft.ts`(`schemeToOverlay`)
- Modify: `src/gimbal-platform/frontend/src/components/ScenarioExportMenu.vue`(注释)
- Modify tests: `src/components/composer/__tests__/RunDialog.auths.test.ts`(重写)、`RunDialog.baseline.test.ts`、`RunDialog.createDataSet.test.ts`、`RunDialog.stepName.test.ts`、`RunDialog.totalRuns.test.ts`

**Interfaces:**
- Consumes: Task 3 的后端契约(RunRequest 无 env;RunScheme/RunOverlay 无 envId)。
- Produces: RunDialog props `serviceRows: Array<{ service: string; declaredUrl: string | null }>`(声明 ∪ 引用并集,父级算好;`declaredUrl === null` = 未声明引用行);emit `confirm(dataSetIds, opts)`(**去 envId 首参**)、`saveScheme(scheme)`(scheme 无 envId)。Task 6/7 不依赖本任务产出。

- [ ] **Step 1: 重写 RunDialog.auths.test.ts(先失败)**

整文件替换为:

```typescript
/**
 * RunDialog — 无环境版 + 并集绑定行(spec 2026-08-27 D2/D3)
 *
 * 锁死:
 * - 无环境语义:模板不含「执行环境」,confirm 无 envId,发起键不再被 env 门控
 * - serviceRows = 声明 ∪ 引用并集:声明行预填 URL、未声明行标红「未声明」
 * - 未声明行现场填 URL = 救燃绑定(confirm 携带该 url)
 * - 预填的声明值未改动时 confirm 不重复上送(非覆盖不进 serviceBindings)
 * - confirm 携带 serviceBindings(空绑定条目剔除)
 * - 存为方案快照无 envId
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'

const BASE_PROPS = {
  dataSets: [],
  schemes: [{ name: '冒烟-qa1', dataSetIds: [],
              serviceBindings: { 'fin-service': { authAlias: 'qa1' } } }],
  lastRunOverlay: null,
  serviceRows: [
    { service: 'fin-service', declaredUrl: 'https://authored.fin' },
    { service: 'order-svc', declaredUrl: null },          // 引用未声明 → 红
  ],
  authOptions: ['qa1', 'qa2'],
}

function mountDlg(props: Partial<typeof BASE_PROPS> = {}) {
  return mount(RunDialog, {
    props: { visible: true, ...BASE_PROPS, ...props },
    global: { stubs: { teleport: true } },
  })
}

describe('执行环境退役(D2)', () => {
  it('模板无环境区/无环境文案;confirm 无 envId', async () => {
    const w = mountDlg()
    expect(w.find('.env-grid').exists()).toBe(false)
    expect(w.text()).not.toContain('执行环境')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const evt = w.emitted('confirm')![0] as unknown[]
    expect(evt).toHaveLength(2)                       // (dataSetIds, opts)
  })

  it('存为方案快照无 envId', async () => {
    const w = mountDlg()
    await w.find('.rd-scheme-name').setValue('冒烟-新方案')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const s = w.emitted('saveScheme')![0][0] as any
    expect('envId' in s).toBe(false)
    expect(s.dataSetIds).toEqual([])
  })
})

describe('并集绑定行(D3)', () => {
  it('声明 ∪ 引用各一行;声明行 URL 预填、未声明行标红', () => {
    const w = mountDlg()
    expect(w.findAll('.rd-bind-row')).toHaveLength(2)
    expect(w.find('.rd-bind-row.is-undeclared').exists()).toBe(true)
    const urls = w.findAll('.rd-bind-url').map((i) => (i.element as HTMLInputElement).value)
    expect(urls[0]).toBe('https://authored.fin')      // 预填声明值
    expect(urls[1]).toBe('')                          // 未声明空,待救燃
  })

  it('未声明行现场填 URL → confirm 携带救燃绑定', async () => {
    const w = mountDlg()
    await w.findAll('.rd-bind-url')[1].setValue('https://rescue.example')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, { url?: string }>
    }
    expect(opts.serviceBindings).toEqual({ 'order-svc': { url: 'https://rescue.example' } })
  })

  it('声明值未改动不重复上送;改了才算覆盖绑定', async () => {
    const w = mountDlg()
    await w.find('[data-testid="run-confirm"]').trigger('click')
    let opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, unknown>
    }
    expect(opts.serviceBindings).toBeUndefined()       // 预填值 == 声明值
    await w.find('.rd-bind-url').setValue('https://override.example')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    opts = (w.emitted('confirm')![1] as unknown[])[1] as {
      serviceBindings?: Record<string, unknown>
    }
    expect(opts.serviceBindings).toEqual({ 'fin-service': { url: 'https://override.example' } })
  })
})
```

- [ ] **Step 2: 兄弟测试文件签名小调**

`RunDialog.baseline.test.ts` / `RunDialog.createDataSet.test.ts` / `RunDialog.stepName.test.ts` / `RunDialog.totalRuns.test.ts`:BASE_PROPS 去 `envs` 键、`referencedServices: [...]` 改 `serviceRows: [...(引用键).map(s => ({ service: s, declaredUrl: null }))]`;confirm 断言里 envId 下标引用(`evt[0]` 原是 envId,现在 `evt[0]` 是 dataSetIds)逐个对齐新签名。

- [ ] **Step 3: 跑测试确认失败**

Run(frontend 目录): `npx vitest run src/components/composer/__tests__/RunDialog.auths.test.ts`
Expected: FAIL — props 校验/模板仍含 env;`.rd-bind-url` 值语义未实现。

- [ ] **Step 4: 实现 RunDialog.vue**

**4a. props/emits**:

```typescript
import type { ServiceBinding, RunScheme, RunOverlay } from '@/api/scenario-composer'
import type { Scenario, DataSetSummary } from '@/types/scenario-composer'

export interface ServiceRow { service: string; declaredUrl: string | null }

const props = withDefaults(defineProps<{
  visible?: boolean
  scenario?: Scenario | null
  dataSets: DataSetSummary[]
  running?: boolean
  lastRunId?: string | null
  lastRunError?: string | null
  schemes: RunScheme[]
  lastRunOverlay: RunOverlay | null
  /** 绑定行 = 声明 ∪ 引用并集(D3);declaredUrl null = 未声明引用行(红,可救燃) */
  serviceRows: ServiceRow[]
  authOptions: string[]
  stepOrchestrationNames?: string[]
}>(), {
  visible: true, scenario: null, running: false,
  lastRunId: null, lastRunError: null, stepOrchestrationNames: () => [] as string[],
})
```

emits 的 confirm 改两参:

```typescript
const emit = defineEmits<{
  close: []
  confirm: [
    dataSetIds: string[],
    opts: {
      stepTo?: number
      nRuns?: number
      parallel?: number
      serviceBindings?: Record<string, ServiceBinding>
    },
  ]
  saveScheme: [scheme: RunScheme]
}>()
```

**4b. 删环境态**:`selectedEnv` ref、`watch(() => props.envs, ...)` 整块、`onConfirm` 的 `if (!selectedEnv.value) {...}` 守卫、selectedScheme watch 的 `if (src?.envId && ...) selectedEnv.value = src.envId` 行、`schemeDegraded` 中 env 条件(只剩 dataSetIds 失效)、footer env chip(`<span v-if="selectedEnv" class="summary-chip env">...`)、发起键 `:disabled="!selectedEnv || running"` → `:disabled="running"`、模板环境 `<section class="run-section">执行环境...</section>` 整块(L33-53)与 `.env-grid/.env-tile` CSS。

**4c. 绑定区改并集**(script):

```typescript
const bindings = ref<Record<string, ServiceBinding>>({})

function declaredUrlOf(svc: string): string | null {
  return props.serviceRows.find((r) => r.service === svc)?.declaredUrl ?? null
}

watch(() => props.serviceRows, (rows) => {
  const next = { ...bindings.value }
  for (const r of rows)
    if (!next[r.service]) next[r.service] = { url: r.declaredUrl ?? undefined }
  const keep = new Set(rows.map((r) => r.service))
  for (const k of Object.keys(next)) if (!keep.has(k)) delete next[k]
  bindings.value = next
}, { immediate: true })

watch(selectedScheme, (v) => {
  if (v === '__adhoc__') {
    bindings.value = Object.fromEntries(props.serviceRows.map(
      (r) => [r.service, { url: r.declaredUrl ?? undefined } as ServiceBinding]))
    return
  }
  const src = v === '__last__' ? props.lastRunOverlay : props.schemes.find((s) => s.name === v)
  const next: Record<string, ServiceBinding> = {}
  for (const r of props.serviceRows) {
    const b = src?.serviceBindings?.[r.service]
    next[r.service] = {
      ...(b?.authAlias ? { authAlias: b.authAlias } : {}),
      url: b?.url ?? r.declaredUrl ?? undefined,
    }
  }
  bindings.value = next
  selectedDatasets.value = (src?.dataSetIds ?? []).filter((id) =>
    props.dataSets.some((d) => d.datasetId === id))
})
```

`onConfirm` 的 serviceBindings 装配(预填值未改动不上送;未声明行任何非空 URL 都是救燃绑定):

```typescript
  const serviceBindings: Record<string, ServiceBinding> = {}
  for (const [svc, b] of Object.entries(bindings.value)) {
    const declared = declaredUrlOf(svc)
    const url = b.url?.trim()
    const effectiveUrl = url && url !== declared ? url : undefined
    const authAlias = b.authAlias || undefined
    if (authAlias || effectiveUrl)
      serviceBindings[svc] = {
        ...(authAlias ? { authAlias } : {}),
        ...(effectiveUrl ? { url: effectiveUrl } : {}),
      }
  }
  emit('confirm', selectedDatasets.value, {
    ...(stepTo.value !== null ? { stepTo: stepTo.value } : {}),
    ...(nRuns.value !== 1 ? { nRuns: nRuns.value } : {}),
    ...(parallel.value !== 1 ? { parallel: parallel.value } : {}),
    ...(Object.keys(serviceBindings).length ? { serviceBindings } : {}),
  })
```

`onSaveScheme` 快照去 `envId` 行;`bindingsSummary` 的 `props.referencedServices` 全部换 `props.serviceRows`。

**4d. 模板绑定区**(替换 L141-155 的 v-for 块):

```html
              <div
                v-for="row in serviceRows"
                :key="row.service"
                class="rd-bind-row"
                :class="{ 'is-degraded': degraded(row.service), 'is-undeclared': row.declaredUrl === null }"
              >
                <span class="rd-bind-svc">{{ row.service }}</span>
                <select class="rd-bind-user" v-model="bindings[row.service].authAlias">
                  <option :value="undefined">— 未绑定 —</option>
                  <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
                </select>
                <input
                  class="rd-bind-url"
                  v-model="bindings[row.service].url"
                  :placeholder="row.declaredUrl === null ? '未声明 — 现场填 URL 即可运行' : '覆盖 URL(可选,已预填声明值)'"
                />
                <span v-if="row.declaredUrl === null" class="rd-bind-warn undeclared">未声明</span>
                <span v-else-if="degraded(row.service)" class="rd-bind-warn">凭证已删,运行时该用户不注入</span>
              </div>
              <p v-if="!serviceRows.length" class="rd-empty">场景未声明且未引用任何 service</p>
```

CSS 追加:

```css
.rd-bind-row.is-undeclared .rd-bind-svc { color: #dc2626; font-weight: 600; }
.rd-bind-warn.undeclared { color: #dc2626; }
```

- [ ] **Step 5: 实现 CaseComposer / api / types / store**

**CaseComposer.vue**:
- 模板 `<RunDialog>`:`:envs="envs"` 行删;`:referenced-services="referencedServices"` → `:service-rows="serviceRows"`。
- script:`envs` ref(L282)、`loadEnvs`(L567-571)、onMounted 的 `await loadEnvs()`(L451)、`RunEnv` type import 全删;`referencedServices` computed(L405-410)替换为:

```typescript
/** 绑定行 = 声明 ∪ 引用并集(spec D3):声明行带 declaredUrl,
 *  引用未声明的键 declaredUrl=null(RunDialog 标红可救燃)。 */
const serviceRows = computed(() => {
  const declared = definition.value.config?.services ?? {}
  const rows = new Map<string, string | null>()
  for (const [k, v] of Object.entries(declared))
    rows.set(k, typeof v === 'string' ? v : null)
  for (const st of (draftStore.draft?.definition?.steps ?? []) as { api?: { service?: string } }[])
    if (st?.api?.service && !rows.has(st.api.service)) rows.set(st.api.service, null)
  return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
})
```

- `openRunDialog` 的 lastRunOverlay 派生(L360-366)去 envId:

```typescript
    lastRunOverlay.value = cfg && (cfg.dataSetIds?.length || cfg.serviceBindings)
      ? { dataSetIds: cfg.dataSetIds ?? [], serviceBindings: cfg.serviceBindings ?? {} }
      : null
```

- `onRunConfirm(dataSetIds, opts?)`(签名去 envId 首参):`const env = envs.value.find(...)` 行删;RunRequest body 去 `env` 键。
- 注释「Run dialog」节文案同步。

**api/scenario-composer.ts**:`RunEnv` 从 type import 删;`RunScheme` 删 `envId?` 行;`RunOverlay` 删 `envId?` 行;`RunRequest` 删 `env: RunEnv` 行;`listEnvs` 函数(L174-177)整删。

**types/scenario-composer.ts**:`RunEnv` interface(L105-109)删。

**stores/scenario-draft.ts**:`schemeToOverlay` 改:

```typescript
/** RunScheme → 导出 overlay(spec §8):只带 serviceBindings — envId 已随
 *  D2 退役,dataSetIds 有意不带(导出是场景级产物,v1 忽略行语义)。 */
export function schemeToOverlay(s: RunScheme): RunOverlay {
  return { serviceBindings: s.serviceBindings }
}
```

**ScenarioExportMenu.vue**:L40 注释「方案的 envId/serviceBindings 物化进导出」→「方案的 serviceBindings 物化进导出(envId 已退役)」。

- [ ] **Step 6: 跑测试 + 类型检查**

Run: `npx vitest run src/components/composer/__tests__/ && npx vue-tsc --noEmit`
Expected: RunDialog 5 文件全绿;vue-tsc 0 error。

- [ ] **Step 7: Commit**

```bash
git add -A src/gimbal-platform/frontend
git commit -m "feat(frontend)!: RunDialog 环境退役 + 声明∪引用并集绑定行(未声明红标救燃) (D2/D3)"
```

---

### Task 5: 前缀派生工具 deriveBase + 目录服务名加载器

**Files:**
- Create: `src/gimbal-platform/frontend/src/utils/service-alias.ts`
- Create: `src/gimbal-platform/frontend/src/utils/catalog-services.ts`
- Create: `src/gimbal-platform/frontend/src/utils/__tests__/service-alias.test.ts`

**Interfaces:**
- Consumes: `useAuthStore`(@/stores/auth)、plate 端点列表 `/plate/api/endpoint?per_page=500`(原生 fetch — axios baseURL=/api 会绕过 Vite 的 /plate 代理,与 CaseComposerCatalog 同款约束)。
- Produces(Task 6/7 消费,签名精确如下):
  - `deriveBase(key: string, catalogNames: ReadonlySet<string>): string | null` — key ∈ 目录名集合 → key 本身;否则按最后一个 `-` 切分,base ∈ 集合 → base;否则 null(裸声明,不猜)。
  - `loadCatalogServiceNames(): Promise<string[]>` — plate 目录服务名全串去重列表,模块级缓存(失败不缓存,可重试;失败静默由调用方降级)。

- [ ] **Step 1: 写失败测试**

`src/utils/__tests__/service-alias.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { deriveBase } from '../service-alias'

const CAT = new Set(['fin-service', 'fin-order-service', 'fin.tidb-test'])

describe('deriveBase — 最后一个 "-" 切分 + 目录名集合成员判定(spec D5)', () => {
  it('目录名直引:key ∈ 目录集合 → key 本身', () => {
    expect(deriveBase('fin-service', CAT)).toBe('fin-service')
  })
  it('别名:base = 目录名 → 归属 base(切分点固定,绝不切成 fin)', () => {
    expect(deriveBase('fin-service-2', CAT)).toBe('fin-service')
  })
  it('目录名含多个 "-":fin-order-service-x-1 → fin-order-service', () => {
    expect(deriveBase('fin-order-service-x-1', CAT)).toBe('fin-order-service')
  })
  it('目录名含 ".":fin.tidb-test-2 → fin.tidb-test', () => {
    expect(deriveBase('fin.tidb-test-2', CAT)).toBe('fin.tidb-test')
  })
  it('不搜索前缀:目录只有 fin-service 时 fin-x 的 base=fin 不在集合 → null', () => {
    expect(deriveBase('fin-x', CAT)).toBeNull()
  })
  it('base 不在集合(裸声明/违规键)→ null,不猜', () => {
    expect(deriveBase('whatever-key', CAT)).toBeNull()
  })
  it('无 "-" 且不在集合 → null;空串 → null', () => {
    expect(deriveBase('loose-name', CAT)).toBeNull()
    expect(deriveBase('', CAT)).toBeNull()
  })
  it('目录集合为空(目录不可达)→ 一律 null(派生是视图不是配置源)', () => {
    expect(deriveBase('fin-service', new Set())).toBeNull()
    expect(deriveBase('fin-service-2', new Set())).toBeNull()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/utils/__tests__/service-alias.test.ts`
Expected: FAIL — `Cannot find module '../service-alias'`。

- [ ] **Step 3: 实现两个工具**

`src/utils/service-alias.ts`:

```typescript
/**
 * service-alias.ts — 服务别名前缀派生(spec 2026-08-27 D5)
 *
 * 别名 = <目录服务名>-<后缀>,"-" 为唯一分隔符,后缀非空不含 "-"。
 * 切分点固定在最后一个 "-":不搜索前缀、不按最长匹配 — 目录名自身可含
 * "-"(如 fin-service、fin-order-service)或 "."(如 fin.tidb-test),
 * 最后一切分保证 base 永远是可能的最长目录名候选。
 *
 * deriveBase 是纯视图函数:目录名集合是唯一外部输入,集合清空 → 全部
 * 返回 null(裸声明降级),执行与导出零影响(酸性测试,spec §1.1)。
 */

/** key ∈ 目录集合 → key(目录名直引);否则最后 "-" 切分,base ∈ 集合 → base;
 *  否则 null(裸声明,不猜)。 */
export function deriveBase(key: string, catalogNames: ReadonlySet<string>): string | null {
  if (!key) return null
  if (catalogNames.has(key)) return key
  const i = key.lastIndexOf('-')
  if (i <= 0) return null
  const base = key.slice(0, i)
  return catalogNames.has(base) ? base : null
}
```

`src/utils/catalog-services.ts`:

```typescript
/**
 * catalog-services.ts — plate 目录服务名加载器(共享,模块级缓存)
 *
 * 目录服务名全串集合 = 别名派生(deriveBase)的唯一外部输入。数据源与
 * CaseComposerCatalog 相同:plate /api/endpoint?per_page=500 的 items[].service
 * (必须用原生 fetch — axios baseURL=/api 会把 /plate 拼成 /api/plate,
 * 绕过 Vite 的 /plate 代理)。消费方:Canvas 别名下拉 / Config 归属列 /
 * CaseComposer.checkSystemMismatch;失败静默降级为空集合(裸声明黄警)。
 */
import { useAuthStore } from '@/stores/auth'

let cached: Promise<string[]> | null = null

export function loadCatalogServiceNames(): Promise<string[]> {
  if (cached) return cached
  cached = (async () => {
    const token = useAuthStore().accessToken || ''
    const r = await fetch('/plate/api/endpoint?per_page=500', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!r.ok) throw new Error(`catalog endpoint list HTTP ${r.status}`)
    const data: any = await r.json()
    const items = data?.data?.items || data?.items || (Array.isArray(data) ? data : [])
    return [...new Set(items.map((e: any) => e.service).filter(Boolean))]
  })().catch((e) => {
    cached = null          // 失败不缓存,下次可重试
    throw e
  })
  return cached
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/utils/__tests__/service-alias.test.ts`
Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/service-alias.ts src/gimbal-platform/frontend/src/utils/catalog-services.ts src/gimbal-platform/frontend/src/utils/__tests__/service-alias.test.ts
git commit -m "feat(frontend): deriveBase 前缀派生工具 + 目录服务名共享加载器 (D5)"
```

---

### Task 6: Canvas 步骤面板双显 — 服务引用下拉 + 内联创建别名

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(props L438-447、api-summary 区 L91-97、propagation 不动)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(Canvas 绑定处)
- Modify tests: `src/components/composer/__tests__/CaseComposerCanvas.test.ts`(补用例)

**Interfaces:**
- Consumes: Task 5 的 `deriveBase` / `loadCatalogServiceNames`;既有 `/full` 会话缓存 `currentFull.value?.service`(endpoint 的目录服务权威名)。
- Produces: Canvas 新 props `services?: Record<string, string>`(场景声明 dict)与新 emit `'update:services': [Record<string, string>]`;`api.service` 仍在 Canvas 内 local 步骤上直改(既有 `watch([local, orch]) → emit('update:steps')` 传播,零新机制)。

- [ ] **Step 1: 写失败测试**

`CaseComposerCanvas.test.ts` 追加(沿用该文件既有 mount 手法;若其 props 形状不同,以文件内既有用例的装配方式为准对齐):

```typescript
import { vi, nextTick } from 'vitest'
// vi.mock 加在文件顶部 import 区:
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => ['fin-service', 'order-svc']),
}))

describe('服务引用下拉 + 内联创建别名(spec §1.4)', () => {
  it('下拉列出目录服务 + 本服务别名;其他声明键置底标跨服务', async () => {
    const w = mountCanvas({
      steps: [stepOf('fin-service')],
      services: { 'fin-service': 'https://a', 'fin-service-2': 'https://b', 'order-svc-1': 'https://c' },
    })
    await nextTick()
    const opts = w.find('.svc-ref-select').findAll('option').map(o => o.text())
    expect(opts.some(t => t.includes('fin-service') && t.includes('目录服务'))).toBe(true)
    expect(opts.some(t => t.includes('fin-service-2'))).toBe(true)
    expect(opts.some(t => t.includes('order-svc-1') && t.includes('跨服务'))).toBe(true)
  })

  it('内联创建:后缀+URL → 拼全串双写(update:services + api.service 切换);后缀含 - 拦截', async () => {
    const w = mountCanvas({
      steps: [stepOf('fin-service')],
      services: { 'fin-service': 'https://a' },
    })
    await w.find('.svc-ref-select').setValue('__create__')
    await w.find('.alias-suffix').setValue('qa2')
    await w.find('.alias-url').setValue('https://qa2.fin.local')
    await w.find('.alias-create-confirm').trigger('click')
    const svc = w.emitted('update:services')![0][0] as Record<string, string>
    expect(svc['fin-service-qa2']).toBe('https://qa2.fin.local')
    expect(svc['fin-service']).toBe('https://a')          // 既有声明保留
    // 拦截:后缀含 "-"
    await w.find('.svc-ref-select').setValue('__create__')
    await w.find('.alias-suffix').setValue('a-b')
    await w.find('.alias-create-confirm').trigger('click')
    expect(w.emitted('update:services')).toHaveLength(1)  // 未再发
  })
})

// 文件内辅助(若已有同款则复用):
function stepOf(service: string) {
  return {
    kind: 'step', description: 'ep',
    api: { kind: 'api', service, method: 'GET', path: '/x', headers: {}, view_hints: { endpoint_id: 'ep-1' } },
    request: { kind: 'request', body: {} },
    strategy: [],
  } as any
}
```

(`mountCanvas` = 文件既有的组件 mount 包装,加传 `services` prop;`/full` 拉取在该文件既有 mock 之下 — endpointFull 缓存 miss 时 `endpointService` 为 null,锚点回落 `deriveBase('fin-service')` = 'fin-service',用例不依赖 /full。)

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts`
Expected: FAIL — `.svc-ref-select` 不存在 / `update:services` 未发。

- [ ] **Step 3: 实现**

**3a. props/emit**(L438-447):

```typescript
const props = defineProps<{
  steps: StepView[]
  orchestration: Orchestration
  /** 场景服务声明 dict(config.services)—— 别名下拉/双写消费(spec §1.4) */
  services?: Record<string, string>
}>()
const emit = defineEmits<{
  'update:steps': [StepView[]]
  'update:orchestration': [Orchestration]
  /** 内联创建别名双写的声明面(config.services 整表替换) */
  'update:services': [Record<string, string>]
  'varPromote': [name: string, value: unknown]
  'seedVar': [name: string, spec: Record<string, unknown>],
}>()
```

**3b. script 追加**(import 区加 `import { deriveBase } from '@/utils/service-alias'` 与 `import { loadCatalogServiceNames } from '@/utils/catalog-services'`):

```typescript
// ── 服务引用(别名消费点,spec §1.4 双显)─────────────────────────
const catalogNames = ref<Set<string>>(new Set())
onMounted(() => {
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 派生降级裸声明黄警,不阻塞编排 */ })
})

/** 本 endpoint 的目录服务锚点:/full 的 service(权威)→ 派生当前引用 → null */
const serviceAnchor = computed<string | null>(() => {
  const fromFull = currentFull.value?.service
  if (fromFull && catalogNames.value.has(fromFull)) return fromFull
  return deriveBase(currentStep.value?.api?.service || '', catalogNames.value)
})

const serviceOptions = computed(() => {
  const anchor = serviceAnchor.value
  const declared = props.services ?? {}
  const opts: Array<{ value: string; label: string; dim?: boolean }> = []
  if (anchor) opts.push({ value: anchor, label: `${anchor}(目录服务)` })
  for (const key of Object.keys(declared)) {
    if (!anchor || key === anchor) continue
    if (deriveBase(key, catalogNames.value) === anchor)
      opts.push({ value: key, label: key })                    // 本服务别名
  }
  for (const key of Object.keys(declared)) {                   // 其他键置底
    if (anchor && (key === anchor || deriveBase(key, catalogNames.value) === anchor)) continue
    opts.push({ value: key, label: `${key}(跨服务)`, dim: true })
  }
  return opts
})

/** 引用告警(§1.5 全表警告级):裸声明黄 / 跨服务黄 / 未声明红 */
const refWarning = computed<{ text: string; level: 'warn' | 'error' } | null>(() => {
  const cur = currentStep.value?.api?.service || ''
  if (!cur) return null
  const anchor = serviceAnchor.value
  if (!anchor || deriveBase(cur, catalogNames.value) === null)
    return { text: '未挂目录服务(裸声明)', level: 'warn' }
  if (cur !== anchor && deriveBase(cur, catalogNames.value) !== anchor)
    return { text: '跨服务引用', level: 'warn' }
  if (!(cur in (props.services ?? {})))
    return { text: '未声明 — Config 或运行弹框补 URL 后可跑', level: 'error' }
  return null
})

const declaredUrlOf = (svc: string) => (props.services ?? {})[svc] || ''

function onServiceRefChange(step: StepView, value: string) {
  if (value === '__create__') { creatingAlias.value = true; return }
  creatingAlias.value = false
  step.api!.service = value          // local 直改,既有 watch 传播 update:steps
}

// 内联创建器:前缀(目录名)固定不可改,只收后缀 + URL(spec §1.3)
const creatingAlias = ref(false)
const aliasSuffix = ref('')
const aliasUrl = ref('')

function confirmAliasCreate(step: StepView) {
  const anchor = serviceAnchor.value
  const suffix = aliasSuffix.value.trim()
  const url = aliasUrl.value.trim()
  if (!anchor) { ElMessage.warning('未知目录服务,无法创建别名'); return }
  if (!suffix) { ElMessage.warning('后缀不能为空'); return }
  if (suffix.includes('-')) { ElMessage.warning('后缀不能含 "-"(分隔符保留)'); return }
  const full = `${anchor}-${suffix}`
  if (full in (props.services ?? {})) { ElMessage.warning(`别名 ${full} 已存在`); return }
  if (!url) { ElMessage.warning('baseUrl 不能为空'); return }
  // 一次动作双写 ①声明(config.services,经 emit 由父级落 definition)
  // ②引用(steps[k].api.service,local 直改经既有 watch 传播)
  emit('update:services', { ...(props.services ?? {}), [full]: url })
  step.api!.service = full
  creatingAlias.value = false
  aliasSuffix.value = ''
  aliasUrl.value = ''
  ElMessage.success(`已创建别名 ${full} 并切换引用`)
}
```

**3c. 模板**:`.api-summary`(L93-97)之后插入:

```html
            <!-- 运行引用(别名消费点,spec §1.4 双显):目录事实只读,引用可切 -->
            <div class="svc-ref">
              <span class="svc-ref-label">服务引用</span>
              <select
                class="svc-ref-select"
                :value="currentStep.api?.service"
                @change="onServiceRefChange(currentStep, ($event.target as HTMLSelectElement).value)"
              >
                <option
                  v-if="currentStep.api?.service && !serviceOptions.some(o => o.value === currentStep.api?.service)"
                  :value="currentStep.api.service"
                >{{ currentStep.api.service }}(未挂目录)</option>
                <option v-for="o in serviceOptions" :key="o.value" :value="o.value" :class="{ dim: o.dim }">{{ o.label }}</option>
                <option value="__create__">+ 为此服务新建别名…</option>
              </select>
              <span v-if="refWarning" class="svc-ref-warn" :class="refWarning.level">{{ refWarning.text }}</span>
              <div v-if="creatingAlias" class="alias-create">
                <span class="alias-prefix">{{ serviceAnchor }}-</span>
                <input v-model="aliasSuffix" placeholder="后缀(不含 -)" class="alias-suffix" />
                <input v-model="aliasUrl" placeholder="baseUrl(如 https://qa2.fin.local)" class="alias-url" />
                <button type="button" class="ghost-btn alias-create-confirm" @click="confirmAliasCreate(currentStep)">创建并切换</button>
                <button type="button" class="ghost-btn" @click="creatingAlias = false">取消</button>
              </div>
              <div class="svc-ref-url">URL: {{ declaredUrlOf(currentStep.api?.service || '') || '(未声明 — 运行前需补 URL)' }}</div>
            </div>
```

CSS 追加(svc-ref 区最小样式,`.dim { color: #94a3b8; }`、`.svc-ref-warn.warn { color: #b45309; } .svc-ref-warn.error { color: #dc2626; }` 等,对齐文件既有 token 用色)。

**3d. CaseComposer.vue** Canvas 绑定(模板 step-3 处 `<CaseComposerCanvas ...` 追加):

```html
          :services="definition.config?.services ?? {}"
          @update:services="onServicesUpdate"
```

script 追加:

```typescript
/** Canvas 内联创建别名双写的声明面落库(config.services 整表替换) */
function onServicesUpdate(services: Record<string, string>) {
  definition.value = {
    ...definition.value,
    config: { ...definition.value.config, services },
  }
}
```

**3e. onAddEndpoint 契约禁令注释**(L958 函数 docstring 处补一行):

```typescript
/**
 * ...既有注释...
 * 契约禁令(spec 2026-08-27 §1.6):目录插入只此一次写 api.service(初值
 * = 规范目录名);任何 plate 拉取驱动的回写不得再触碰该字段 — 它是用户
 * 引用键(可为别名全串),view_hints.endpoint_id 才是目录锚点。
 */
```

- [ ] **Step 4: 跑测试 + 类型检查**

Run: `npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts && npx vue-tsc --noEmit`
Expected: 新用例绿 + 既有 Canvas 用例不回归;vue-tsc 0 error。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts
git commit -m "feat(frontend): 步骤面板服务引用双显 — 别名下拉(前缀派生过滤)+ 内联创建双写 (D1/D4/D5)"
```

---

### Task 7: Config 归属列 + checkSystemMismatch 派生修复

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue`(服务卡 L199-237、script)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(`checkSystemMismatch` L470-490、onMounted)
- Modify tests: `src/components/composer/__tests__/CaseComposerConfig.test.ts`

**Interfaces:**
- Consumes: Task 5 的 `deriveBase` / `loadCatalogServiceNames`。
- Produces: 无跨任务接口(纯展示/告警修复)。Config `namespaceOf` 分组逻辑不动(spec §1.6 拍板:别名与 base 共享首 `.` 前缀,分组天然一致)。

- [ ] **Step 1: 写失败测试**

`CaseComposerConfig.test.ts` 追加(vi.mock 同 Task 6 手法):

```typescript
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => ['fin-service']),
}))

it('归属列:别名行显示派生 base;违规键显示未挂目录(spec §1.4)', async () => {
  const w = mountConfig({
    services: { 'fin-service': 'https://a', 'fin-service-2': 'https://b', 'loose-key': 'https://c' },
  })
  await nextTick()
  const owners = w.findAll('.svc-owner').map(n => n.text())
  expect(owners).toContain('fin-service')       // 直引
  expect(owners).toContain('fin-service')       // 别名派生(同值出现两次)
  expect(owners).toContain('未挂目录')
})
```

`CaseComposer` 侧若无组件级测试文件,则新增轻量单测到 `src/utils/__tests__/service-alias.test.ts` 之外不另建 — checkSystemMismatch 的修复由派生函数测试 + 手工验证覆盖(该函数内联在 .vue,无既有测试文件;改动最小化)。

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/components/composer/__tests__/CaseComposerConfig.test.ts`
Expected: FAIL — `.svc-owner` 不存在。

- [ ] **Step 3: 实现**

**3a. CaseComposerConfig.vue** — import 区加 `deriveBase` / `loadCatalogServiceNames`、`ref/onMounted` 补齐;script 追加:

```typescript
// ── 别名归属列(spec §1.4/§1.3):前缀派生只读标签,无手填 ──────────
const catalogNames = ref<Set<string>>(new Set())
onMounted(() => {
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 全部显示未挂目录,不阻塞编辑 */ })
})
function ownerLabel(alias: string): string {
  return deriveBase(alias, catalogNames.value) ?? '未挂目录'
}
```

模板 svc-row(L217-233)alias 输入后追加一列:

```html
            <span class="svc-owner" :title="ownerLabel(s.alias)">{{ ownerLabel(s.alias) }}</span>
```

(注:最后一切分使「后缀含 -」结构上不可能出现 — Config 自由输入的违规形态只剩 base 不在目录集合,归属列「未挂目录」即创建期可见的拦截展示;结构性拦截在内联创建器(Task 6)。)

**3b. CaseComposer.vue `checkSystemMismatch`** — 先派生 base 再比对(spec §1.6:别名全串会被整串当系统,逐别名步骤误报):

```typescript
const catalogNames = ref<Set<string>>(new Set())
onMounted(async () => {
  // ...既有步骤(loadScenario 等)...
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 派生降级为整串(现状行为) */ })
  // ...既有 checkSystemMismatch 调用等...
})
```

函数内循环体替换为:

```typescript
  for (const s of scenario.value.steps as any[]) {
    const svc = (s.api && s.api.service) || ''
    if (!svc) continue
    // 先派生 base(别名 fin-service-2 → fin-service)再取系统前缀;
    // 不派生则别名全串被当系统名,每个别名步骤都误报(spec §1.6)
    const base = deriveBase(svc, catalogNames.value) ?? svc
    actual.add(base.includes('.') ? base.split('.')[0] : base)
  }
```

import 区加 `import { deriveBase } from '@/utils/service-alias'`、`import { loadCatalogServiceNames } from '@/utils/catalog-services'`。

- [ ] **Step 4: 跑测试 + 类型检查**

Run: `npx vitest run src/components/composer/__tests__/CaseComposerConfig.test.ts && npx vue-tsc --noEmit`
Expected: 新用例绿、既有 Config 用例不回归;vue-tsc 0 error。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerConfig.test.ts
git commit -m "feat(frontend): Config 服务卡归属列 + checkSystemMismatch 先派生 base 再比对 (D5/§1.6)"
```

---

### Task 8: 收尾 — 全量回归 + 残留清扫

**Files:**
- 无新增(只验证与清扫;若清扫发现残留,修复归属对应文件)

**Interfaces:**
- Consumes: Task 1-7 全部产出。
- Produces: 全绿的仓库状态(spec §8 回归底线)。

- [ ] **Step 1: 三层全量回归**

```bash
# 引擎(仓库根)
python -m pytest tests/plate tests/unit/engine tests/unit/reporter tests/unit/generator tests/unit/config tests/unit/scenario tests/unit/runtime_control -q
python tests/unit/test_defect_fixes.py
# 后端
cd src/gimbal-platform/backend && python -m pytest tests -q
# 前端
cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit
```

Expected: 三层全绿(被退役语义删除的用例不计入)。

- [ ] **Step 2: 残留清扫 grep(「清理干净」验收)**

```bash
# 前端:env 语义残留(Executions.vue RECIPE_LABELS 的 envId 标签是刻意保留 — 历史行可读)
cd src/gimbal-platform/frontend && grep -rn "listEnvs\|RunEnv\|selectedEnv\|envs\.yaml" src --include="*.ts" --include="*.vue" | grep -v RECIPE_LABELS
# 后端:Task 3 Step 4 同款 grep 复跑
# 引擎:bootstrap/config/env 零改动确认
cd d:/Gimbal/Gimbal && git diff --stat src/gimbal/config
```

Expected: 前端 grep 仅允许 Executions.vue 的 `envId: '环境'` 标签行(RECIPE_LABELS);后端 0 命中;引擎 `src/gimbal/config` 零 diff。

- [ ] **Step 3: spec §8 验收清单逐项核对**

- 引擎:per-step 命中/回落/双缺失 ✓(Task 1 测试);单服务逐字节不变 ✓(`test_empty_services_dict_identical_to_legacy` + test_defect_fixes #6);旧多服务断言改正确路由 ✓(`test_two_services_route_independently`)。
- 后端:RunScheme 去 envId 往返 ✓;旧 envId 静默降级 ✓;materialize 去 env 层等价 ✓;preview-plate 无 env 路径 ✓(overlay 仅 serviceBindings);黄金等价随两层链更新 ✓。
- 前端:派生单元 ✓;checkSystemMismatch 别名不误报 ✓(Task 7);下拉过滤/内联创建拼串双写/跨服务黄警/未声明红 ✓(Task 6);Config 归属 ✓;RunDialog 无环境版 ✓;并集行救燃 ✓;方案栏回填新签名 ✓(Task 4)。

- [ ] **Step 4: Commit(如有清扫修复)**

```bash
git add -A
git commit -m "chore: 服务别名+环境退役 收尾清扫与全量回归"
```

(无修复则跳过本步,直接交付。)

---

## 自检记录(writing-plans Self-Review)

1. **Spec coverage**:D1(步骤粒度别名)= Task 6;D2(环境彻底退役)= Task 2+3+4(清单 §2.1 逐行:前端 tiles/loadEnvs/回填 → Task 4;schemas 四项 → Task 3a;router /api/envs + run-schemes 校验 → Task 3c/d;dispatcher 比对告警/config_json envId → Task 3b;materialize env 层 → Task 2;envs.yaml → Task 3e;上次运行派生 → Task 4 Step 5);D3(并集)= Task 4;D4(直写)= Task 6(local 直改 + update:services 双写);D5(前缀派生)= Task 5+6+7;D6(警告级)= Task 6 refWarning/Task 4 未声明红不阻塞;D7(引擎三触点)= Task 1;D8(配置文件)= Task 3e + Task 8 引擎 config 零 diff 验证。§1.6 存量点切(checkSystemMismatch 改/namespaceOf 不改)= Task 7;契约禁令注释 = Task 3f + Task 6 Step 3e;§5 导出 = 既有 materialize 语义 + Task 3/4 调整,零新增合并 ✓。
2. **Placeholder scan**:无 TBD/TODO;所有代码步骤带实码;两处「以文件内既有形状为准」的测试适配(test_run_materialize 的 _converted 键名、Canvas 测试的 mountCanvas 包装)是对既有测试文件的适配指引,不是实现占位。
3. **Type consistency**:`deriveBase(key, catalogNames: ReadonlySet<string>): string | null` 在 Task 5/6/7 一致;`serviceRows: Array<{service, declaredUrl: string|null}>` 在 Task 4 的 props/测试/父级 computed 一致;`update:services` emit 在 Task 6 的 Canvas/CaseComposer 两侧一致;`materialize_run_copy` 新签名在 Task 2(定义)/Task 3(两处调用)一致;引擎 `services` 参数链 preprocessor→StepRunner→StepStateMachine 一致。
