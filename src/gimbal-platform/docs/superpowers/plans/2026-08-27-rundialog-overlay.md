# RunDialog 重构 + 运行方案(overlay)+ 执行可观测性 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 RunDialog(方案栏/主面板/折叠区/用户与服务绑定),落地场景级运行方案(orchestration.runSchemes sidecar + 窄端点),统一执行/导出两路的注入物化(`materialize_run_copy` + 黄金等价),并补齐行级实时跟踪与引擎日志流式落盘。

**Architecture:** 注入归一化为单一纯函数 `materialize_run_copy`(POST-convert 位点不变,明文凭证不过 plate),执行链(`_fanout`)与导出链(preview-plate 带 overlay)共同消费;注入清单由后端模板扫描(`${auth.<alias>.*}`)∪ serviceBindings 的 authAlias 得出;行状态走内存 registry(活跃)+ JSONL 回放(历史),引擎 stderr 逐行流式写 `case_dir/engine.log` 经白名单端点暴露。

**Tech Stack:** FastAPI + Pydantic v2(`populate_by_name` + alias 驼峰)+ SQLAlchemy async + pytest;Vue 3 `<script setup>` + Pinia + element-plus + vitest;plate /convert(gimbal-plate,零改动);gimbal CLI 子进程。

**Spec:** [docs/superpowers/specs/2026-08-27-rundialog-overlay-observability-design.md](../specs/2026-08-27-rundialog-overlay-observability-design.md)(本计划从 spec 立论,执行者两份都读)

## Global Constraints

- **路径根**:后端 `src/gimbal-platform/backend`,前端 `src/gimbal-platform/frontend`;以下所有相对路径以此为根。
- **测试命令 cwd**:后端 `cd src/gimbal-platform/backend && python -m pytest tests/<file> -v`;前端 `cd src/gimbal-platform/frontend && npx vitest run <path>`;类型检查 `npx vue-tsc --noEmit`。
- **零改动禁区**:`src/gimbal`、`src/gimbal-plate`(plate 与引擎);`probe_ui`(若存在)禁触。
- **回归底线**:现有测试套件只增不减全绿(语义退役的测试按任务指示删除/改写,其余不许动);`vue-tsc --noEmit` 绿。
- **凭证策略**:明文物化(内网部署 + 被测系统测试账户,用户决策 2026-08-27);明文只存在于 POST-convert 之后(run 副本/导出产物),PRE-convert 位点不带明文。
- **Pydantic 风格**:schema 一律 `_CAMEL = ConfigDict(populate_by_name=True, str_strip_whitespace=True)`,外部键驼峰 alias(见 `backend/app/schemas/scenario_composer.py` 现状)。
- **git 提交**:每任务一提交,消息格式 `feat|fix|refactor|test|docs(scope): 中文描述`,含 `Co-Authored-By: Claude <noreply@anthropic.com>` 尾行。
- **「上次运行」只取 overlay 三字段**(envId/dataSetIds/serviceBindings),base_config 不回填(spec §3.1)。

---

## Phase A — 后端执行链等价重构

### Task 1: 模板扫描器 `scan_auth_aliases`

**Files:**
- Create: `backend/app/services/auth_ref_scan.py`
- Test: `backend/tests/test_auth_ref_scan.py`

**Interfaces:**
- Produces: `scan_auth_aliases(steps: list) -> list[str]` — 递归扫 steps 内全部字符串值,返回 `${auth.<alias>.<field>}` 引用的去重 alias 列表(保持出现序)。Task 3 的 dispatch_run 消费。

- [ ] **Step 1: Write the failing test**

```python
"""scan_auth_aliases — 后端版 tpl-refs(语义对齐 frontend/src/utils/tpl-refs.ts)。"""
from app.services.auth_ref_scan import scan_auth_aliases


def test_headers_reference() -> None:
    steps = [{"api": {"headers": {"Authorization": "${auth.qa1.token}"}}}]
    assert scan_auth_aliases(steps) == ["qa1"]


def test_nested_body_and_list() -> None:
    steps = [{
        "api": {"path": "/x"},
        "request": {"body": {"creds": [{"u": "${auth.qa1.user}", "p": "${auth.qa1.pass}"}]}},
        "strategy": [{"message": "fail as ${auth.qa2.name}"}],
    }]
    assert scan_auth_aliases(steps) == ["qa1", "qa2"]


def test_dedup_keeps_first_seen_order() -> None:
    steps = [
        {"api": {"headers": {"a": "${auth.b.token}"}}},
        {"api": {"headers": {"b": "${auth.a.token}"}}},
        {"api": {"headers": {"c": "${auth.b.token}"}}},
    ]
    assert scan_auth_aliases(steps) == ["b", "a"]


def test_fieldless_reference_counts() -> None:
    steps = [{"api": {"headers": {"x": "${auth.qa1}"}}}]
    assert scan_auth_aliases(steps) == ["qa1"]


def test_non_auth_templates_ignored() -> None:
    steps = [{"api": {"headers": {"a": "${var.qty}", "b": "${service.fin.base}"}}}]
    assert scan_auth_aliases(steps) == []


def test_malformed_ignored() -> None:
    steps = [{"api": {"headers": {"a": "${auth.}", "b": "${auth.###}"}}}]
    assert scan_auth_aliases(steps) == []


def test_empty_steps() -> None:
    assert scan_auth_aliases([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_auth_ref_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.auth_ref_scan'`

- [ ] **Step 3: Write minimal implementation**

```python
"""平台侧 ${auth.<alias>.*} 模板引用扫描器。

语义对齐前端 tpl-refs(frontend/src/utils/tpl-refs.ts):递归扫 steps
的字符串值(headers/path/body/strategy 一网打尽),收集被引用的 auth
alias。注入清单的自动部分以此为准 — 场景内容是单一事实源(spec §5)。
"""
from __future__ import annotations

import re

# ${auth.<alias>} 或 ${auth.<alias>.<field>};alias 字符集与前端
# tpl-refs 一致:字母数字下划线连字符。
_AUTH_RE = re.compile(r"\$\{\s*auth\.([A-Za-z0-9_-]+)(?:\.[A-Za-z0-9_.-]+)?\s*\}")


def scan_auth_aliases(steps: list) -> list[str]:
    """收集 steps 里 ${auth.<alias>.*} 引用的去重 alias(保持出现序)。"""
    seen: dict[str, None] = {}  # dict 保序去重
    for found in _scan_value(steps):
        seen.setdefault(found, None)
    return list(seen)


def _scan_value(node: object) -> list[str]:
    if isinstance(node, str):
        return _AUTH_RE.findall(node)
    if isinstance(node, dict):
        out: list[str] = []
        for v in node.values():
            out.extend(_scan_value(v))
        return out
    if isinstance(node, list):
        out = []
        for v in node:
            out.extend(_scan_value(v))
        return out
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_auth_ref_scan.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/auth_ref_scan.py src/gimbal-platform/backend/tests/test_auth_ref_scan.py
git commit -m "feat(run): auth 模板引用扫描器 scan_auth_aliases"
```

---

### Task 2: 物化纯函数 `materialize_run_copy`

**Files:**
- Create: `backend/app/services/run_materialize.py`
- Test: `backend/tests/test_run_materialize.py`
- Read first: `backend/app/services/run_dispatcher.py` 的 `_inject_exec_users` / `_inject_services`(约 :1062-1106)——users 条目字段形状以现实现为准**搬迁**,本任务代码块即按其形状写出;若读后发现字段名有出入,以现实现为准修正本任务代码块再落地。

**Interfaces:**
- Consumes: 无(纯函数,不依赖 run_dispatcher)
- Produces: `materialize_run_copy(converted: dict, *, env_base_url: str = "", service_bindings: dict[str, dict] | None = None, resolved_auths: list | None = None, built_in_users: dict | None = None) -> dict` — 输入 plate /convert 产物,输出深拷贝物化副本。Task 3(dispatch)与 Task 4(preview-plate overlay)消费;`resolved_auths` 元素 duck-typed(`.alias/.url/.username/.password/.token_type/.expires_in`,即 run_dispatcher.ResolvedAuth);`built_in_users` = 场景 definition.config.users(**pre-convert 基座**,plate 会剥平台视图字段 — 见现 `_inject_exec_users` docstring,这是它独立于 converted 自带 users 的原因)。

- [ ] **Step 1: Write the failing test**

```python
"""materialize_run_copy — POST-convert 物化纯函数(执行/导出同源)。

绑定优先级(spec §5):显式绑定 url > 场景 authored > env.baseUrl 补缺。
users 合并固定 merge 语义(spec §10:merge_policy 退役)。
"""
from types import SimpleNamespace

from app.services.run_materialize import materialize_run_copy


def _converted() -> dict:
    return {
        "kind": "scenario",
        "config": {
            "services": {"fin-service": "https://authored"},
            "users": {"builtin": {"url": "https://u", "username": "b",
                                  "password": "p", "expires_in": 7200,
                                  "token_type": "Authorization"}},
            "vars": {},
        },
        "steps": [
            {"kind": "step", "api": {"service": "fin-service", "path": "/x",
                                     "headers": {"Authorization": "${auth.qa1.token}"}}},
            {"kind": "step", "api": {"service": "svc-orphan", "path": "/y"}},
        ],
    }


def _auth(alias: str, url="https://auth-url") -> SimpleNamespace:
    return SimpleNamespace(alias=alias, url=url, username="u1", password="p1",
                           token_type="Authorization", expires_in=7200)


def test_binding_url_overrides_authored() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env",
                               service_bindings={"fin-service": {"url": "https://bound"}})
    assert out["config"]["services"]["fin-service"] == "https://bound"


def test_authored_kept_when_no_binding() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env")
    assert out["config"]["services"]["fin-service"] == "https://authored"


def test_env_fills_missing_referenced_service() -> None:
    out = materialize_run_copy(_converted(), env_base_url="https://env")
    assert out["config"]["services"]["svc-orphan"] == "https://env"


def test_no_env_leaves_gap_visible() -> None:
    out = materialize_run_copy(_converted())
    assert "svc-orphan" not in out["config"]["services"]


def test_auths_merge_over_builtin() -> None:
    out = materialize_run_copy(_converted(), resolved_auths=[_auth("qa1")])
    users = out["config"]["users"]
    assert users["builtin"]["username"] == "b"          # 内置保留
    assert users["qa1"]["url"] == "https://auth-url"     # 注入覆盖同名
    assert users["qa1"]["username"] == "u1"
    assert users["qa1"]["token_type"] == "Authorization"
    assert users["qa1"]["expires_in"] == 7200


def test_built_in_users_base_precedes_converted_users() -> None:
    """merge 基座 = built_in_users(definition.config.users,pre-convert)
    先铺,converted 自带 users 后铺,auths 最后覆盖 — 与现 _inject_exec_users
    ``{**built_in, **cfg.users}`` 同构(内置认证以场景定义为唯一可信源)。"""
    src = _converted()
    src["config"]["users"]["from-converted"] = {"url": "https://c", "username": "c",
                                                "password": "c", "expires_in": 1,
                                                "token_type": "Bearer"}
    out = materialize_run_copy(src, resolved_auths=[_auth("qa1")],
                               built_in_users={"from-definition": {"url": "https://d"}})
    assert "from-definition" in out["config"]["users"]
    assert "from-converted" in out["config"]["users"]


def test_config_created_when_missing() -> None:
    """PlateMock ok 桩的 converted 无 config/steps — 物化不炸且注入可落。"""
    out = materialize_run_copy({"kind": "platform_scenario"},
                               service_bindings={"any": {"url": "https://x"}})
    assert out["config"]["services"] == {}   # 无 steps → 无 referenced → 绑定不落
    assert out["config"]["users"] == {}


def test_no_auths_leaves_users_untouched() -> None:
    out = materialize_run_copy(_converted())
    assert set(out["config"]["users"]) == {"builtin"}


def test_pure_function_input_not_mutated() -> None:
    src = _converted()
    snapshot = {"services": dict(src["config"]["services"]), "users": dict(src["config"]["users"])}
    materialize_run_copy(src, env_base_url="https://env",
                         service_bindings={"fin-service": {"url": "https://bound"}},
                         resolved_auths=[_auth("qa1")])
    assert src["config"]["services"] == snapshot["services"]
    assert src["config"]["users"] == snapshot["users"]


def test_unreferenced_service_keys_preserved() -> None:
    src = _converted()
    src["config"]["services"]["legacy-svc"] = "https://legacy"
    out = materialize_run_copy(src, env_base_url="https://env")
    assert out["config"]["services"]["legacy-svc"] == "https://legacy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_materialize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.run_materialize'`

- [ ] **Step 3: Write minimal implementation**

```python
"""run 副本物化(POST-convert 注入,执行与导出同源)。

materialize_run_copy 是执行链(run_dispatcher._fanout)与导出链
(preview-plate overlay)共用的唯一物化点 — 相同输入逐字段相同输出,
黄金等价测试锁死不漂移(spec §7)。PRE/POST convert 是刻意安全缝:
明文凭证不过 plate。
"""
from __future__ import annotations

import copy
from typing import Any


def materialize_run_copy(
    converted: dict[str, Any],
    *,
    env_base_url: str = "",
    service_bindings: dict[str, dict[str, Any]] | None = None,
    resolved_auths: list[Any] | None = None,
    built_in_users: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回物化后的深拷贝;入参不可变(纯函数)。

    * users:merge 基座 ``{**built_in_users, **converted.config.users}``
      (内置认证以场景定义为唯一可信源),resolved_auths 按别名覆盖/追加
    * services:显式绑定 url > 场景 authored > env.baseUrl 补缺(仅对
      steps 实际引用的 service 键生效,未引用键原样保留)
    """
    out = copy.deepcopy(converted)
    cfg = out.setdefault("config", {})
    if not isinstance(cfg, dict):        # 防御:converted.config 非 dict(与
        cfg = {}                          # _inject_* 现防御一致)
        out["config"] = cfg
    cfg["services"] = dict(cfg.get("services") or {})
    cfg["users"] = dict(cfg.get("users") or {})

    _apply_services(cfg, steps=out.get("steps") or [],
                    env_base_url=env_base_url, bindings=service_bindings or {})
    _apply_users(cfg, resolved_auths or [], built_in_users=built_in_users or {})
    return out


def _referenced_services(steps: list) -> list[str]:
    seen: dict[str, None] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        api = step.get("api")
        svc = api.get("service") if isinstance(api, dict) else None
        if svc:
            seen.setdefault(svc, None)
    return list(seen)


def _apply_services(cfg: dict, *, steps: list, env_base_url: str,
                    bindings: dict[str, dict]) -> None:
    services: dict[str, Any] = cfg["services"]
    for svc in _referenced_services(steps):
        bound_url = (bindings.get(svc) or {}).get("url")
        if bound_url:
            services[svc] = bound_url                    # 显式绑定最优先
        elif not services.get(svc) and env_base_url:
            services[svc] = env_base_url                 # env 补缺(authored 已有则不动)


def _apply_users(cfg: dict, resolved_auths: list, *, built_in_users: dict) -> None:
    if not resolved_auths:
        return                       # 无 auths:users 原样(同现 _inject_exec_users)
    users: dict[str, Any] = {**built_in_users, **cfg["users"]}
    for r in resolved_auths:
        users[r.alias] = {
            "url": r.url,
            "username": r.username,
            "password": r.password,
            "token_type": r.token_type,
            "expires_in": r.expires_in,
        }
    cfg["users"] = users
```

(实现已按现 `_inject_exec_users`(:1062-1106)/`_inject_services`(:1025-1059)原文搬移语义:merge 基座 `{**built_in, **cfg.users}`、users 条目五字段取自 ResolvedAuth、无 auths 返回原样、referenced 扫描 `steps[*].api.service`、env 只补缺口。)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_materialize.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_materialize.py src/gimbal-platform/backend/tests/test_run_materialize.py
git commit -m "feat(run): materialize_run_copy 物化纯函数(执行/导出同源)"
```

---

### Task 3: RunRequest 改造 + dispatch_run 重接(注入清单 = 扫描 ∪ 绑定)

**Files:**
- Modify: `backend/app/schemas/scenario_composer.py`(RunRequest :187-230;新增 ServiceBinding)
- Modify: `backend/app/services/run_dispatcher.py`(dispatch_run 预检/config_json/_fanout;删 `_inject_prefix_vars`/`_inject_exec_users`/`_inject_services`)
- Modify: `backend/tests/test_scenario_composer_plate_integration.py`(PlateMock 增 echo 行为,测试基建)
- Modify: `backend/tests/test_run_m1_capabilities.py`、`backend/tests/test_scenario_visibility_and_copy.py`
- Test: `backend/tests/test_run_bindings_injection.py`(新增)

**Interfaces:**
- Consumes: Task 1 `scan_auth_aliases(steps) -> list[str]`;Task 2 `materialize_run_copy(converted, *, env_base_url, service_bindings, resolved_auths, built_in_users)`
- Produces:
  - `class ServiceBinding(BaseModel)`:`auth_alias: str | None = Field(default=None, alias="authAlias", max_length=128)`、`url: str | None = Field(default=None, alias="url", max_length=512)`,`model_config = _CAMEL`(Task 5/4 复用)
  - `RunRequest` 新字段 `service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict, alias="serviceBindings")`;**删除** `auths`/`inject_credentials`/`prefix`/`merge_policy`
  - `config_json` 新键 `serviceBindings`(dict 驼峰 dump)/`injectedAuths`(实际注入清单 list[str]);**删除** `exec_auth_alias`/`prefix`/`mergePolicy`/`injectCredentials`
  - 测试基建:PlateMock 新行为 `echo`(convert 请求里的 scenario 原样回为 converted)—— services/扫描类断言的前提(默认 ok 桩 converted 无 steps)

- [ ] **Step 1: PlateMock 增 echo 行为(测试基建)**

`test_scenario_composer_plate_integration.py` 的 `PlateMock.install` handler 里,`behaviour == "ok"` 分支旁增:

```python
if self.behaviour == "echo":
    # scenario 原样回灌为 converted — 供 services/users 物化断言用
    # (默认 ok 桩的 converted 是 {"kind": "platform_scenario"},无 steps)
    body = json.loads(request.content)
    return httpx.Response(200, json={
        "ok": True, "dim": "scenario",
        "data": {"consumer": "gimbal", "converted": body["scenario"]},
    })
```

(`__init__` 的 behaviour 注释改为 `ok | echo | 4xx | 5xx | unavailable`;默认仍 ok,既有测试零影响。)

- [ ] **Step 2: Write the failing test**

新增 `backend/tests/test_run_bindings_injection.py`。helpers 全部 import 复用(不复制):`_run_payload`/`_patch_launch_capture` from `test_run_m1_capabilities`,`_member`/`_seed_ds` from `test_scenario_visibility_and_copy`,`_draft` from `helpers`。注意三个事实:`_member(client, "bob")` 返回 **headers dict**;`_run_payload(**extra)` 的 extra 直接并进顶层 JSON(驼峰键);POST /api/runs 返 **201**;capture sink 是 **list**(完成序);config_json 查 DB(M1 现行做法)。

```python
"""serviceBindings 注入 + 模板扫描驱动注入清单(spec §5/§6)。

capture 读 case.json(_patch_launch_capture),断言物化结果:绑定 url
覆盖 services、绑定 authAlias 注入 users、steps 里的 ${auth.*} 引用
即使无绑定也进注入清单。PlateMock 用 echo 行为(converted 带 steps)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


_AUTH_STEP = {
    "kind": "step",
    "api": {"service": "fin-service", "path": "/x",
            "headers": {"Authorization": "${auth.qa1.token}"}},
}


async def _seed_scenario(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=_draft(steps=[_AUTH_STEP]))
    assert r.status_code in (200, 201), r.text


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(Execution.id.desc()))
              ).scalars().first()
        return ex.config_json


async def test_binding_url_and_auth_materialized(client, plate_mock: PlateMock,
                                                 monkeypatch):
    """serviceBindings {url, authAlias} → case.json services 物化 +
    config_json 留痕 injectedAuths/serviceBindings。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"authAlias": "qa1", "url": "https://bound"}},
    ))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    cfg = cases[0]["config"]
    assert cfg["services"]["fin-service"] == "https://bound"
    # qa1 不在 bob 凭证池 → _resolve_exec_auths 告警继续,users 不含 qa1 明文
    assert "qa1" not in (cfg.get("users") or {})

    config_json = await _last_config_json()
    assert config_json["serviceBindings"]["fin-service"]["authAlias"] == "qa1"
    assert config_json["injectedAuths"] == ["qa1"]      # 扫描 ∪ 绑定
    # 旧键退役(两种历史写法都兜住;实际键名以 :368-383 现码为准,删除后均过)
    for gone in ("prefix", "mergePolicy", "injectCredentials",
                 "execAuthAlias", "exec_auth_alias"):
        assert gone not in config_json


async def test_template_scan_without_binding_injects(client, plate_mock: PlateMock,
                                                     monkeypatch):
    """steps 引用 ${auth.qa1.token}(无绑定)→ qa1 仍进注入清单留痕。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["qa1"]
    assert config_json["serviceBindings"] == {}


async def test_legacy_payload_fields_silently_ignored(client, plate_mock: PlateMock,
                                                      monkeypatch):
    """旧客户端发 auths/prefix/mergePolicy → 不 422,仅失效(spec §6)。"""
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    payload = _run_payload(dataSetIds=[])
    payload.update({"auths": ["qa1"], "prefix": "T-1",
                    "mergePolicy": "override", "injectCredentials": False})
    r = await client.post("/api/runs", headers=bob, json=payload)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert (cfg.get("vars") or {}).get("order_no_prefix") is None   # prefix 失效
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_bindings_injection.py -v`
Expected: FAIL — `serviceBindings` 被 pydantic 忽略后 services 断言不等 / config_json 无新键

- [ ] **Step 4: Schema 改造(scenario_composer.py)**

在 RunRequest 附近新增:

```python
class ServiceBinding(BaseModel):
    """service → {authAlias?, url?} 绑定(spec §3.1/§5)。"""
    model_config = _CAMEL

    auth_alias: str | None = Field(default=None, alias="authAlias", max_length=128)
    url: str | None = Field(default=None, alias="url", max_length=512)
```

RunRequest:`service_bindings` 新增(放在 `data_set_ids` 之后);删除 `auths`(:207)/`inject_credentials`(:212)/`prefix`(:220)/`merge_policy`(:228)四字段及其注释;`step_to`/`n_runs`/`parallel`/`env`/`scenario_id`/`data_set_ids` 不动。

- [ ] **Step 5: dispatch_run 重接(run_dispatcher.py)**

1. **删 append 冲突预检块**(dispatch_run 内,原 merge_policy 分支)。
2. 注入清单与绑定传递 — 扫描源是**存储的 definition steps**( authored 模板所在处),取法与 `_compose_scenario` 的 `definition_from_payload(raw)` 一致:

```python
from .auth_ref_scan import scan_auth_aliases
from .run_materialize import materialize_run_copy

# dispatch_run 内,原 auth_aliases 计算处替换为:
scanned = scan_auth_aliases(definition_from_payload(payload).get("steps") or [])
bound = [b.auth_alias for b in req.service_bindings.values() if b.auth_alias]
auth_aliases: list[str] = list(dict.fromkeys([*scanned, *bound]))  # 去重保序
```

(`payload` = dispatch_run 里已加载的场景 payload 变量名,以现码为准。)

3. `config_json` 配方写入处(:368-383)删 `exec_auth_alias`/`prefix`/`mergePolicy`/`injectCredentials` 四键,新增:

```python
"injectedAuths": auth_aliases,
"serviceBindings": {
    k: b.model_dump(by_alias=True, exclude_none=True)
    for k, b in req.service_bindings.items()
},
```

4. `_fanout` 签名:`merge_policy`/`prefix` 参数删除,`service_bindings` 新增(调用点同步)。`_row` 内 `_inject_exec_users` + `_inject_prefix_vars` + `_inject_services` 三连调用替换为(`built_in` 沿用现有 `_built_in_users(definition)` 结果,执行前算一次):

```python
composed_exec = materialize_run_copy(
    converted,
    env_base_url=(env.get("baseUrl") or ""),
    service_bindings={k: b.model_dump(by_alias=True) for k, b in service_bindings.items()},
    resolved_auths=exec_auths,
    built_in_users=built_in,
)
```

5. 删除 `_inject_prefix_vars`/`_inject_exec_users`/`_inject_services` 三函数体(`_built_in_users`/`_resolve_exec_auths`/`_compose_scenario`/`_coerce_row_value` 保留)。

- [ ] **Step 6: 既有测试按新语义改造**

- `test_run_m1_capabilities.py`:删除 `test_prefix_injects_order_no_vars`、merge_policy 的 override/append-conflict-409/default-merge 三测;`test_merge_policy_merge_keeps_built_in_users` 改写为:

```python
async def test_service_binding_auth_merge_keeps_built_in(client, owner, ...):
    """绑定 authAlias 注入 users,场景内置 users 保留(固定 merge)。"""
    # 场景 config.users 带 builtin 别名(构造法抄原测试),payload:
    payload = _run_payload(data_set_ids=[], service_bindings={"svc": {"authAlias": "qa1"}})
    # 断言 case.json: users 同含 builtin 与 qa1(builtin 值未变)
```

- `test_scenario_visibility_and_copy.py`:删除 `test_run_inject_credentials_false_skips_auth_resolution`。
- `test_scenario_composer_plate_integration.py`:跑一遍,凡 payload 带 `auths=`/`mergePolicy`/`prefix` 的用例,改为 `serviceBindings={"<svc>": {"authAlias": "<alias>"}}` 形式(注入断言不变)。

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_bindings_injection.py tests/test_run_m1_capabilities.py tests/test_scenario_visibility_and_copy.py tests/test_scenario_composer_plate_integration.py tests/test_run_auth_resolution.py -v`
Expected: 全 PASS

- [ ] **Step 8: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "refactor(run): RunRequest 收敛 serviceBindings,注入清单=扫描∪绑定,materialize 接管 _fanout"
```

---

### Task 4: preview-plate overlay + 黄金等价测试

**Files:**
- Modify: `backend/app/schemas/scenario_composer.py`(ExportOverlay)
- Modify: `backend/app/routers/scenarios.py`(preview_plate :97-142)
- Test: `backend/tests/test_export_overlay_equivalence.py`(新增)

**Interfaces:**
- Consumes: Task 2 `materialize_run_copy`;Task 3 `ServiceBinding`;`run_dispatcher._resolve_exec_auths(db_factory, owner_id=, aliases=)` 与 `run_dispatcher.session_factory`;`env_store` 的环境读取(preview 内现成用法)
- Produces: `POST /api/scenarios/preview-plate` body 增**可选** `overlay: {envId?: str, serviceBindings?: dict[str, ServiceBinding]}` — 传入则 convert 后物化(明文)返回;不传行为不变(向后兼容,spec §8)

- [ ] **Step 1: Write the failing test**

等价成立的两条前提,测试内显式钉死:①场景 meta 带 `owner` 与 `createTime`(否则两路 `fill_plate_defaults` 各自打不同时间戳/不同 owner,等价被非实质差异打破);②PlateMock 用 `echo` 行为(converted 携带 steps/config,绑定物化可观察)。

```python
"""导出 overlay + 黄金等价(spec §7.3/§8)。

同一场景、同一 overlay 下:preview-plate(带 overlay)产物 ≡ 基线单行
执行 case.json(逐字段相等)。无数据集 → 行 vars 无差异;stepTo/nRuns
不进 case.json → 无需模掉任何字段(spec §7.3 的「模掉行 vars/halt」
在基线单行下自然退化为零差)。
"""
from __future__ import annotations

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member

OVERLAY = {
    "envId": "test-env-A",
    "serviceBindings": {"fin-service": {"authAlias": "qa1", "url": "https://bound"}},
}
# meta 钉死 owner/createTime:两路 fill_plate_defaults 全 setdefault 无增量;
# vars_map={} 显式带上 config.vars — _compose_scenario 恒定写回 vars(空 dict),
# 缺省 draft 无 vars 键会让两路差一个键
_META = {"owner": "bob", "createTime": "2026-08-27T00:00:00Z"}
_STEP = {"kind": "step",
         "api": {"service": "fin-service", "path": "/x",
                 "headers": {"Authorization": "${auth.qa1.token}"}}}


def _eq_draft() -> dict:
    return _draft(steps=[_STEP], vars_map={}, **_META)


async def _seed(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers, json=_eq_draft())
    assert r.status_code in (200, 201), r.text


async def test_preview_plate_without_overlay_unchanged(client, plate_mock: PlateMock):
    """不传 overlay → convert 原样(向后兼容,无绑定注入痕迹)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json=_eq_draft())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    services = (body.get("config") or {}).get("services") or {}
    assert services.get("fin-service") != "https://bound"


async def test_preview_plate_with_overlay_materializes(client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)
    resp = await client.post("/api/scenarios/preview-plate", headers=bob,
                             json={**_eq_draft(), "overlay": OVERLAY})
    assert resp.status_code == 200, resp.text
    assert resp.json()["config"]["services"]["fin-service"] == "https://bound"
    # qa1 无凭证池会话 → 告警继续,users 不含 qa1(与 dispatch 同语义)
    assert "qa1" not in (resp.json()["config"].get("users") or {})


async def test_golden_equivalence_export_equals_baseline_case_json(
        client, plate_mock: PlateMock, monkeypatch):
    """黄金等价:导出产物 ≡ 基线单行 case.json,逐字段相等。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob)

    exported = (await client.post(
        "/api/scenarios/preview-plate", headers=bob,
        json={**_eq_draft(), "overlay": OVERLAY})).json()

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings=OVERLAY["serviceBindings"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    assert cases[0] == exported
```

(preview-plate 的 body 形态以现路由为准:它现吃 ScenarioDraft(`definition`+`orchestration`)— `_draft()` 即此形态;`_draft(steps=[...], **_META)` 的 meta_over 落在 `definition.meta`。若 preview 响应外层还有包裹,断言取 `resp.json()["converted"]` 一类 — 以 `routers/scenarios.py` preview_plate 现返回为准对齐。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_export_overlay_equivalence.py -v`
Expected: FAIL — overlay 字段被忽略(services 断言不等)/422

- [ ] **Step 3: Implement**

`scenario_composer.py` 新增:

```python
class ExportOverlay(BaseModel):
    """导出/预览的运行方案覆盖层(spec §8)。dataSetIds 有意不收 —
    导出是场景级产物,行级展开是非目标。"""
    model_config = _CAMEL

    env_id: str | None = Field(default=None, alias="envId", min_length=1, max_length=64)
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")
```

preview-plate 的请求模型(现 body 为 ScenarioDraft)改为继承扩展:

```python
class PreviewPlateIn(ScenarioDraft):
    overlay: ExportOverlay | None = None
```

`routers/scenarios.py` preview_plate:

```python
# convert 之后、返回之前插入(明文物化不过 plate,POST-convert 位点):
if body.overlay is not None:
    env_base_url = ""
    if body.overlay.env_id:
        envs = await env_store.list_envs()          # 与 dispatch 同源的环境读取
        match = [e for e in envs if e.env_id == body.overlay.env_id]
        if not match:
            raise HTTPException(404, detail={"code": "env_not_found",
                                             "message": body.overlay.env_id})
        env_base_url = match[0].base_url or ""
    aliases = sorted({b.auth_alias for b in body.overlay.service_bindings.values()
                      if b.auth_alias})
    exec_auths = await run_dispatcher._resolve_exec_auths(
        run_dispatcher.session_factory, owner_id=user.id, aliases=aliases)
    # built_in 基座与 dispatch 同源:场景 definition.config.users
    # (plate 会剥平台视图字段,内置认证以场景定义为唯一可信源)
    def_cfg = (body.definition.get("config") or {})
    built_in = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    converted = materialize_run_copy(
        converted,
        env_base_url=env_base_url,
        service_bindings={k: b.model_dump(by_alias=True)
                          for k, b in body.overlay.service_bindings.items()},
        resolved_auths=exec_auths,
        built_in_users=dict(built_in or {}),
    )
```

(preview_plate 现有函数体内 `user`/`env_store`/owner 变量名以实际代码为准对齐;`_resolve_exec_auths` 对未知 alias 告警继续的语义与 dispatch 一致。)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_export_overlay_equivalence.py tests/test_scenario_composer_plate_integration.py -v`
Expected: 全 PASS(黄金等价逐字段相等)

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(export): preview-plate 可选 overlay 物化 + 黄金等价测试"
```

---

## Phase B — 方案存储(runSchemes sidecar)

### Task 5: RunScheme 模型 + 透传保留 + PUT /run-schemes 端点

**Files:**
- Modify: `backend/app/schemas/scenario_composer.py`(RunScheme/RunSchemesIn;Orchestration 增 runSchemes)
- Modify: `backend/app/services/scenario_store.py`(update :134-137 透传保留;新增 put_run_schemes)
- Modify: `backend/app/routers/scenarios.py`(PUT 端点)
- Test: `backend/tests/test_run_schemes_endpoint.py`(新增)

**Interfaces:**
- Consumes: Task 3 `ServiceBinding`
- Produces:
  - `class RunScheme(BaseModel)`:`name: str = Field(min_length=1, max_length=64)`、`env_id: str | None = Field(default=None, alias="envId", max_length=64)`、`data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")`、`service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict, alias="serviceBindings")`、`plugins: Any = None`、`log_sub: Any = Field(default=None, alias="logSub")`
  - `Orchestration.run_schemes: list[RunScheme] = Field(default_factory=list, alias="runSchemes")`
  - `PUT /api/scenarios/{scenario_id}/run-schemes`,body `RunSchemesIn {schemes: list[RunScheme]}` → 200 `list[RunScheme]`;404 scenario_not_found;403 非-owner;409 `run_scheme_name_conflict`
  - `scenario_store.put_run_schemes(db, scenario_id, schemes) -> list[RunScheme]`

- [ ] **Step 1: Write the failing test**

```python
"""PUT /run-schemes 窄端点 + runSchemes 键所有权(spec §3.2/§11)。

核心断言:composer 的 PUT /scenarios/{id}(整体替换)永不覆盖 runSchemes
— 键归窄端点专管,scenario_store.update 透传保留。
"""
from __future__ import annotations

from .helpers import make_draft as _draft
from .test_scenario_visibility_and_copy import _member

SCHEMES = [{"name": "冒烟-qa1", "envId": "test-env-A", "dataSetIds": [],
            "serviceBindings": {"fin-service": {"authAlias": "qa1"}},
            "plugins": None, "logSub": None}]


async def _saved_scenario(client, headers) -> str:
    r = await client.post("/api/scenarios", headers=headers, json=_draft())
    assert r.status_code in (200, 201), r.text
    return "sc-test"                       # _draft 缺省 scenario_id


async def test_put_and_get_roundtrip(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=bob, json={"schemes": SCHEMES})
    assert resp.status_code == 200, resp.text
    assert [s["name"] for s in resp.json()] == ["冒烟-qa1"]
    # 保存后 GET 场景:orchestration.runSchemes 可见
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert got["orchestration"]["runSchemes"][0]["envId"] == "test-env-A"


async def test_duplicate_name_409(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=bob, json={"schemes": SCHEMES + [SCHEMES[0]]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "run_scheme_name_conflict"


async def test_composer_save_never_overwrites_schemes(client):
    """并发保护:整体 PUT 场景(不带 runSchemes)后方案仍在。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    assert (await client.put(f"/api/scenarios/{sid}/run-schemes",
                             headers=bob, json={"schemes": SCHEMES})).status_code == 200
    # composer 保存:GET → PUT 回写(orchestration 无 runSchemes 键)
    cur = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    cur["orchestration"].pop("runSchemes", None)
    resp = await client.put(f"/api/scenarios/{sid}", headers=bob, json=cur)
    assert resp.status_code == 200
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert [s["name"] for s in got["orchestration"]["runSchemes"]] == ["冒烟-qa1"]


async def test_invalid_refs_accepted_warn_level(client):
    """envId/datasetId/authAlias 失效 → 接受不拒(降级预填由前端标红)。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=bob,
                            json={"schemes": [{
                                "name": "ghost", "envId": "env-gone",
                                "dataSetIds": ["ds-gone"],
                                "serviceBindings": {"fin-service": {"authAlias": "ghost-alias"}},
                            }]})
    assert resp.status_code == 200


async def test_owner_enforced(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    eve = await _member(client, "eve")     # 第二用户(_member 即建用户返 headers)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=eve, json={"schemes": SCHEMES})
    assert resp.status_code == 403
```

(`_member(client, "eve")` 会新建第二个用户并返回其 headers — 它就是「其他用户」fixture,无需另建。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_schemes_endpoint.py -v`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: Implement**

schemas(`Orchestration` 后追加):

```python
class RunScheme(BaseModel):
    """场景级运行方案(orchestration sidecar,plate 零感知,spec §3.1)。"""
    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=64)
    env_id: str | None = Field(default=None, alias="envId", max_length=64)
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")
    plugins: Any = None        # 预埋,gimbal 就绪前 no-op
    log_sub: Any = Field(default=None, alias="logSub")  # 预埋,同上


class RunSchemesIn(BaseModel):
    model_config = _CAMEL

    schemes: list[RunScheme]
```

`Orchestration` 增:`run_schemes: list[RunScheme] = Field(default_factory=list, alias="runSchemes")`。

`scenario_store.update`(:134-137)— 整体替换前透传保留(编辑器不管理该键):

```python
stored_orch = ((row.payload or {}).get("orchestration") or {})
orch_data = draft.orchestration.model_dump(by_alias=True, mode="json")
orch_data["runSchemes"] = stored_orch.get("runSchemes") or []   # 窄端点专管键
row.payload = ScenarioDraft(
    definition=stored_definition,
    orchestration=Orchestration.model_validate(orch_data),
).model_dump(by_alias=True, mode="json")
```

`scenario_store` 新增:

```python
async def put_run_schemes(db: AsyncSession, scenario_id: str,
                          schemes: list[RunScheme]) -> list[RunScheme]:
    row = await get_row(db, scenario_id)          # None → 调用方 404
    payload = dict(row.payload or {})
    orch = dict(payload.get("orchestration") or {})
    orch["runSchemes"] = [s.model_dump(by_alias=True, mode="json") for s in schemes]
    payload["orchestration"] = orch
    row.payload = payload
    await db.commit()
    return schemes
```

`routers/scenarios.py` 新增(所有权校验与相邻端点同款写法):

```python
@router.put("/{scenario_id}/run-schemes", response_model=list[RunScheme])
async def put_run_schemes(user: CurrentUser, session: DbSession,
                          scenario_id: str, body: RunSchemesIn) -> list[RunScheme]:
    row = await scenario_store.get_row(session, scenario_id)
    if row is None:
        raise HTTPException(404, detail={"code": "scenario_not_found",
                                         "message": scenario_id})
    if row.owner_id != user.id:                    # 与既有场景端点同款拒绝
        raise HTTPException(403, detail={"code": "not_owner",
                                         "message": scenario_id})
    names = [s.name for s in body.schemes]
    if len(names) != len(set(names)):
        raise HTTPException(409, detail={"code": "run_scheme_name_conflict",
                                         "message": "方案名场景内唯一"})
    # 警告级校验(不拒,降级预填原则):envId 存在性 / dataSetIds 归属 /
    # authAlias ∈ owner 凭证池 ∪ 场景内置 users — 仅 logger.warning
    return await scenario_store.put_run_schemes(session, scenario_id, body.schemes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_schemes_endpoint.py tests/test_scenario_visibility_and_copy.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(run-schemes): orchestration.runSchemes sidecar + 窄端点 + update 透传保留"
```

---

### Task 6: executions list 加 scenario_id 过滤

**Files:**
- Modify: `backend/app/routers/executions.py`(list :39-61)
- Test: `backend/tests/test_executions_scenario_filter.py`(新增)

**Interfaces:**
- Produces: `GET /api/executions?scenario_id=<id>` — 只返回该场景的执行(owner 过滤之上叠加);不传行为不变。Task 12(前端「上次运行」)消费。

- [ ] **Step 1: Write the failing test**

```python
"""list executions 的 scenario_id 过滤(「上次运行」数据源,spec §3.1)。"""
from __future__ import annotations

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


async def test_list_filters_by_scenario(client, plate_mock: PlateMock, monkeypatch):
    bob = await _member(client, "bob")
    for sid in ("sc-a", "sc-b"):
        r = await client.post("/api/scenarios", headers=bob,
                              json=_draft(scenario_id=sid))
        assert r.status_code in (200, 201), r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    for sid in ("sc-a", "sc-b"):
        r = await client.post("/api/runs", headers=bob,
                              json=_run_payload(scenarioId=sid, dataSetIds=[]))
        assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)

    resp = await client.get("/api/executions", headers=bob,
                            params={"scenario_id": "sc-a"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["scenarioId"] == "sc-a"
```

(`scenarioId` 字段名以 `execution_store.execution_out` 现投影为准 — 若叫 `scenario_id` 按实际改断言键。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_executions_scenario_filter.py -v`
Expected: FAIL — 过滤参数被忽略,len(items) == 2

- [ ] **Step 3: Implement**

```python
async def list_executions(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
    scenario_id: Annotated[str | None, Query(max_length=64)] = None,
) -> ExecutionListOut:
    base = select(Execution).where(Execution.owner_id == user.id)
    if scenario_id:
        base = base.where(Execution.scenario_id == scenario_id)
    ...
```

(其余行不动。)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_executions_scenario_filter.py tests/test_executions_api.py -v`
(`test_executions_api.py` 若不存在,跑 `python -m pytest tests/ -k executions -v`)

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(executions): list 支持 scenario_id 过滤"
```

---

## Phase C — 可观测性(行状态 + 流式日志 + 工件端点)

### Task 7: 行状态 registry + JSONL 回放 + GET /rows

**Files:**
- Modify: `backend/app/services/run_dispatcher.py`(RowState/registry/写点/execution_rows;finalize 后 pop registry)
- Modify: `backend/app/schemas/execution.py`(ExecutionRowOut/ExecutionRowsOut)
- Modify: `backend/app/routers/executions.py`(GET /rows)
- Test: `backend/tests/test_execution_rows.py`(新增)

**Interfaces:**
- Produces:
  - `run_dispatcher.execution_rows(execution_id: int) -> list[dict]` — 活跃读内存 registry,历史读 JSONL 回放(dispatched+final 两行/row,final 覆盖);元素形如 `{"seq": 0, "datasetId": None, "rowIndex": 0, "rep": 0, "status": "passed", "caseDir": "case-000-...", "startedAt": "...", "finishedAt": "..."}`
  - `GET /api/executions/{id}/rows` → `{"items": [...]}`;Task 13 前端消费
  - JSONL 行形状不变(已有 `executionId/seq/status/casePath` 键 — 回放只读不写)

- [ ] **Step 1: Write the failing test**

```python
"""行级状态:registry(活跃)+ JSONL 回放(历史)(spec §9.1)。"""
from __future__ import annotations

import asyncio

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member, _seed_ds

# 执行终态(models/execution.py:done/failed/canceled;queued/running 非终态)
_EXEC_FINAL = {"done", "failed", "canceled"}


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


async def test_rows_live_then_replay(client, plate_mock: PlateMock, monkeypatch):
    """执行完成后 registry 已 pop → rows 端点走 JSONL 回放,结果一致。"""
    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}], vars_map={"qty": 1}))
    assert r.status_code in (200, 201), r.text
    await _seed_ds(client, bob)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=["ds-001"], nRuns=1))
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 2)              # baseline + 1 数据行
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert [r["seq"] for r in rows] == [0, 1]
    assert all(r["status"] and r["status"] != "queued" for r in rows)
    assert all(r["caseDir"] for r in rows)            # case stem 非空(供工件端点)


async def test_registry_popped_after_finalize(client, plate_mock: PlateMock,
                                              monkeypatch):
    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}]))
    assert r.status_code in (200, 201), r.text
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    await _await_final(client, bob, exec_id)

    from app.services import run_dispatcher
    assert exec_id not in run_dispatcher._row_states   # 活跃表不泄漏


async def test_rows_unknown_execution_404(client):
    bob = await _member(client, "bob")
    resp = await client.get("/api/executions/99999999/rows", headers=bob)
    assert resp.status_code == 404
```

(行终态字符串集合以 `_fanout` 现 JSONL 终态行为准 — 实现时把它提为 `run_dispatcher._FINAL_STATUSES` 模块常量,回放与测试共用;`_seed_ds` 落库的 ds-001 行数以其实现为准,若 >1 行则相应调整 `len(rows)` 期望为 `1 + 行数`。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_execution_rows.py -v`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: Implement**

run_dispatcher:

```python
from dataclasses import asdict, dataclass

@dataclass
class RowState:
    seq: int
    dataset_id: str | None
    row_index: int
    rep: int
    status: str
    case_dir: str = ""                 # case stem(非全路径,不泄漏服务端布局)
    started_at: str | None = None
    finished_at: str | None = None

_row_states: dict[int, list[RowState]] = {}   # 活跃执行;finalize 后 pop
```

写点:`_fanout` 组完全部行任务后初始化(全部 `status="queued"`);`_row` 开头改 `dispatched` + `started_at`;结束时改终态 + `finished_at` + `case_dir=case_dir.name`;`_finalize`(或执行终态化处)`_row_states.pop(execution_id, None)`。

```python
def execution_rows(execution_id: int) -> list[dict]:
    live = _row_states.get(execution_id)
    if live is not None:
        return [asdict(r) for r in live]
    return _replay_rows(execution_id)


def _replay_rows(execution_id: int) -> list[dict]:
    """按天 JSONL 回放:同 (executionId, seq) 后行覆盖前行(final 覆盖 dispatched)。"""
    rows: dict[int, dict] = {}
    for path in sorted((DATA_DIR / "runs").glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("executionId") != execution_id:
                    continue
                seq = rec.get("seq")
                if seq is None:
                    continue
                cur = rows.setdefault(seq, {"seq": seq,
                                            "datasetId": rec.get("datasetId"),
                                            "rowIndex": rec.get("rowIndex", 0),
                                            "rep": rec.get("rep", 0),
                                            "status": rec.get("status", ""),
                                            "caseDir": "",
                                            "startedAt": None, "finishedAt": None})
                cur["status"] = rec.get("status", cur["status"])
                if rec.get("casePath"):
                    cur["caseDir"] = Path(rec["casePath"]).name
                ts = rec.get("ts")
                if rec.get("status") in _FINAL_STATUSES:
                    cur["finishedAt"] = ts
                else:
                    cur["startedAt"] = ts or cur["startedAt"]
    return [rows[k] for k in sorted(rows)]
```

(`DATA_DIR`/`_FINAL_STATUSES`/JSONL 记录键名(`datasetId/rowIndex/rep/ts/casePath`)以 run_dispatcher 现有 `_log_line`/写 JSONL 的实现为准对齐 — 本块是回放器,不改 JSONL 写侧;若现记录缺某键,回放侧给默认值即可。)

schemas/execution.py:

```python
class ExecutionRowOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    seq: int
    dataset_id: str | None = Field(default=None, alias="datasetId")
    row_index: int = Field(default=0, alias="rowIndex")
    rep: int = 0
    status: str
    case_dir: str = Field(default="", alias="caseDir")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")


class ExecutionRowsOut(BaseModel):
    items: list[ExecutionRowOut]
```

routers/executions.py:

```python
@router.get("/{execution_id}/rows", response_model=ExecutionRowsOut)
async def get_execution_rows(ex: OwnedExecution) -> ExecutionRowsOut:
    return ExecutionRowsOut(items=run_dispatcher.execution_rows(ex.id))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_execution_rows.py tests/test_run_m1_capabilities.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(observability): 行状态 registry + JSONL 回放 + GET /executions/{id}/rows"
```

---

### Task 8: launcher 流式 stderr → engine.log

**Files:**
- Modify: `backend/app/services/gimbal_launcher.py`(`launch()` :145 起,`communicate()` 替换)
- Test: `backend/tests/test_launcher_streaming_log.py`(新增)

**Interfaces:**
- Produces: `launch(..., engine_log_path: Path | None = None)` — stderr 逐行流式写入该文件(边读边写),stdout JSON 解析语义不变,`LaunchResult` 形状不变;超时 kill / spawn 失败保留已读部分。Task 9 消费(dispatcher 传 `case_dir/"engine.log"`)。

- [ ] **Step 1: Write the failing test**

launch 签名现状:`launch(case_path, *, step_to=None, report_dir=None, cwd=None, timeout=None) -> LaunchResult`,argv 由 `build_argv(case_path, ...)` 生成 — 测试 monkeypatch `build_argv` 换成 `python -c` 假引擎,stdout 打一行 JSON(成功路径),stderr 打日志行;超时路径 stderr 后 `time.sleep(30)`。`LaunchResult.launch_status`(docstring:超时为 `"timeout"`)。

```python
"""流式 stderr 落盘:正常完成与超时两条路径(spec §9.2)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services import gimbal_launcher


def _fake_engine_argv(lines: int, *, hang: bool = False) -> list[str]:
    stmt = ";".join(
        ["import sys"]
        + [f"sys.stderr.write('engine line {i}\\n'); sys.stderr.flush()"
           for i in range(lines)]
        + (["import time; time.sleep(30)"] if hang else
           ["sys.stdout.write('{\"status\": \"ok\"}')"])
    )
    return [sys.executable, "-c", stmt]


@pytest.fixture
def patch_argv(monkeypatch: pytest.MonkeyPatch):
    def _install(argv: list[str]) -> None:
        monkeypatch.setattr(gimbal_launcher, "build_argv",
                            lambda *a, **k: argv)
    return _install


async def test_stderr_streamed_to_log(tmp_path: Path, patch_argv) -> None:
    patch_argv(_fake_engine_argv(3))
    log = tmp_path / "engine.log"
    await gimbal_launcher.launch(tmp_path / "case.json",
                                 timeout=15, engine_log_path=log)
    assert log.read_text(encoding="utf-8").splitlines() == [
        "engine line 0", "engine line 1", "engine line 2"]


async def test_timeout_preserves_partial_log(tmp_path: Path, patch_argv) -> None:
    patch_argv(_fake_engine_argv(2, hang=True))
    log = tmp_path / "engine.log"
    result = await gimbal_launcher.launch(tmp_path / "case.json",
                                          timeout=1.0, engine_log_path=log)
    assert result.launch_status == "timeout"
    assert log.read_text(encoding="utf-8").splitlines() == [
        "engine line 0", "engine line 1"]        # 已读部分保留
```

(case.json 不需要真实存在 — build_argv 被 patch 后 case_path 仅作 argv 占位参数。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_launcher_streaming_log.py -v`
Expected: FAIL — `engine_log_path` 参数不存在(TypeError)

- [ ] **Step 3: Implement**

`launch()` 签名加 `engine_log_path: Path | None = None`;子进程创建后:

```python
log_fh = engine_log_path.open("w", encoding="utf-8") if engine_log_path else None

async def _drain_stderr() -> None:
    assert proc.stderr is not None
    while True:
        raw = await proc.stderr.readline()
        if not raw:
            break
        text = raw.decode("utf-8", errors="replace")
        if log_fh:
            log_fh.write(text)

try:
    stdout_task = asyncio.create_task(proc.stdout.read())
    stderr_task = asyncio.create_task(_drain_stderr())
    await asyncio.wait_for(
        asyncio.gather(stdout_task, stderr_task, proc.wait()), timeout=timeout)
    stdout_bytes = stdout_task.result()
finally:
    if log_fh:
        log_fh.flush()
        log_fh.close()
    for t in (stdout_task, stderr_task):
        if not t.done():
            t.cancel()
```

超时分支(原 `except asyncio.TimeoutError`):kill 后 reap(`await proc.wait()`),走现有 timeout 结果构造 — `_drain_stderr` 在管道关闭后自然收敛,finally 已落盘已读部分。spawn 失败分支不动(log 文件可为空文件)。**dispatch 调用点**(run_dispatcher `_row` 内 launch 调用)加 `engine_log_path=case_dir / "engine.log"`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_launcher_streaming_log.py -v && python -m pytest tests/ -k launch -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(observability): launcher stderr 流式落盘 engine.log(超时保留已读)"
```

---

### Task 9: case-artifact 白名单端点

**Files:**
- Modify: `backend/app/routers/executions.py`
- Test: `backend/tests/test_case_artifact.py`(新增)

**Interfaces:**
- Consumes: Task 8(`engine.log` 落盘);`run_dispatcher` 的 run 目录定位(现 `_run_dir`/`DATA_DIR`)
- Produces: `GET /api/executions/{id}/case-artifact?case=<stem>&file=engine-log|result` → `text/plain`;400 `bad_artifact_kind`(file 非法)、404(`runId` 缺失/工件不存在)。**case.json 不暴露**(含明文凭证,spec §9.1)。Task 13 前端消费。

- [ ] **Step 1: Write the failing test**

```python
"""case 工件白名单端点:engine.log / result.json 可读,其余一律拒(spec §9.1)。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from .helpers import launch_ok as _ok, make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


@pytest.fixture
async def finished_run(client, plate_mock: PlateMock, monkeypatch):
    """单行执行完成;launch 假实现同时落 engine.log/result.json 工件。"""
    from app.services import gimbal_launcher as gl

    case_dirs: list[Path] = []

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None):
        case_dir = Path(case_path).parent
        (case_dir / "engine.log").write_text("engine says hi\n", encoding="utf-8")
        (case_dir / "result.json").write_text('{"steps": []}', encoding="utf-8")
        case_dirs.append(case_dir)
        return _ok()

    monkeypatch.setattr(gl, "launch", _capture)

    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json=_draft(steps=[{"id": "s1"}]))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(case_dirs) >= 1)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    return bob, exec_id, rows[0]["caseDir"]       # stem


async def test_engine_log_and_result_readable(client, finished_run):
    bob, exec_id, stem = finished_run
    r1 = await client.get(f"/api/executions/{exec_id}/case-artifact",
                          headers=bob, params={"case": stem, "file": "engine-log"})
    assert r1.status_code == 200
    assert "text/plain" in r1.headers["content-type"]
    assert r1.text == "engine says hi\n"
    r2 = await client.get(f"/api/executions/{exec_id}/case-artifact",
                          headers=bob, params={"case": stem, "file": "result"})
    assert r2.status_code == 200 and r2.text == '{"steps": []}'


async def test_case_json_never_exposed(client, finished_run):
    bob, exec_id, stem = finished_run
    for f in ("case", "case-json", "case.json"):
        resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                                headers=bob, params={"case": stem, "file": f})
        assert resp.status_code == 400


async def test_path_traversal_rejected(client, finished_run):
    bob, exec_id, _ = finished_run
    resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                            headers=bob,
                            params={"case": "..%2Fevil", "file": "engine-log"})
    assert resp.status_code in (400, 404)


async def test_missing_artifact_404(client, finished_run):
    bob, exec_id, _ = finished_run
    resp = await client.get(f"/api/executions/{exec_id}/case-artifact",
                            headers=bob,
                            params={"case": "case-999-none-r0-n0", "file": "engine-log"})
    assert resp.status_code == 404
```

(依赖 Task 7 的 rows 端点取 stem — 本任务排在 Task 7/8 之后。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_case_artifact.py -v`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: Implement**

```python
import re
from fastapi.responses import PlainTextResponse

_CASE_STEM_RE = re.compile(r"[A-Za-z0-9._-]+")
_ARTIFACTS = {"engine-log": "engine.log", "result": "result.json"}


@router.get("/{execution_id}/case-artifact", response_class=PlainTextResponse)
async def get_case_artifact(
    ex: OwnedExecution,
    case: Annotated[str, Query(max_length=128)],
    file: Annotated[str, Query(max_length=32)],
) -> PlainTextResponse:
    """白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。
    case.json 刻意不暴露 — 含明文凭证,无前端消费场景。"""
    name = _ARTIFACTS.get(file)
    if name is None or not _CASE_STEM_RE.fullmatch(case):
        raise HTTPException(400, detail={"code": "bad_artifact_kind",
                                         "message": f"file ∈ {sorted(_ARTIFACTS)}"})
    run_id = (ex.config_json or {}).get("runId")
    if not run_id:
        raise HTTPException(404, detail={"code": "artifact_not_found", "message": name})
    path = run_dispatcher.run_dir(str(run_id)) / case / name   # run_dir = 公开别名
    if path.parent != run_dispatcher.run_dir(str(run_id)) or not path.is_file():
        raise HTTPException(404, detail={"code": "artifact_not_found", "message": name})
    return PlainTextResponse(path.read_text(encoding="utf-8"))
```

run_dispatcher 侧:把现有 `_run_dir`(模块内函数)加公开别名 `run_dir = _run_dir`(或直接改端点调 `_run_dir` — 与 run_dispatcher 现有导出风格一致即可)。**注意**:`run_dir` 必须按 runId 定位(防跨执行读),且 `config_json.runId` 由 Task 3 的配方写入保留。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_case_artifact.py tests/test_execution_rows.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(observability): case-artifact 白名单端点(engine.log/result.json)"
```

---

## Phase D — 前端 RunDialog 重构

### Task 10: 前端 types + api 层同步

**Files:**
- Modify: `frontend/src/api/scenario-composer.ts`(RunRequest 接口 :117-136;putRunSchemes 新增;previewPlateDraft 加 overlay)
- Modify: `frontend/src/api/executions.ts`(MergePolicy :4 删;config 键类型;list 参数;getExecutionRows/getCaseArtifact 新增)
- Test: `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit`(类型层验证;无新单测 — 纯类型/透传)

**Interfaces:**
- Produces(Task 11-14 消费):
  - `interface ServiceBinding { authAlias?: string; url?: string }`
  - `interface RunScheme { name: string; envId?: string | null; dataSetIds: string[]; serviceBindings: Record<string, ServiceBinding>; plugins?: unknown; logSub?: unknown }`
  - `interface RunOverlay { envId?: string | null; dataSetIds?: string[]; serviceBindings?: Record<string, ServiceBinding> }`
  - `RunRequest` 接口:删 `auths/injectCredentials/prefix/mergePolicy`,增 `serviceBindings?: Record<string, ServiceBinding>`
  - `putRunSchemes(scenarioId: string, schemes: RunScheme[]): Promise<RunScheme[]>`
  - `previewPlateDraft(draft: unknown, overlay?: RunOverlay): Promise<unknown>`
  - `listExecutions(params?: { scenarioId?: string; limit?: number })`;`getExecutionRows(id: number): Promise<{ items: ExecutionRow[] }>`;`ExecutionRow = { seq: number; datasetId: string | null; rowIndex: number; rep: number; status: string; caseDir: string; startedAt: string | null; finishedAt: string | null }`;`getCaseArtifact(id: number, caseStem: string, file: 'engine-log' | 'result'): Promise<string>`

- [ ] **Step 1: Implement api/types(先改后验 — 类型层无独立测试)**

`api/scenario-composer.ts`:在 RunRequest 接口上方加三个 interface(代码见 Produces);RunRequest 删四字段、增 `serviceBindings?: Record<string, ServiceBinding>`;新增:

```ts
export async function putRunSchemes(scenarioId: string, schemes: RunScheme[]): Promise<RunScheme[]> {
  return http.put(`/scenarios/${scenarioId}/run-schemes`, { schemes })
}

export async function previewPlateDraft(draft: unknown, overlay?: RunOverlay): Promise<unknown> {
  return http.post('/scenarios/preview-plate', overlay ? { ...wrapDraft(draft), overlay } : wrapDraft(draft))
}
```

(`wrapDraft` = 现有 previewPlateDraft 的 body 组装逻辑保持不变,只是包一层 overlay 条件;http 客户端引用抄本文件现有函数的写法。)

`api/executions.ts`:删 `MergePolicy` 类型及双处 import;`Execution.config` 配方键改为 `serviceBindings?: Record<string, ServiceBinding>` / `injectedAuths?: string[]`(旧键 `prefix/mergePolicy/execAuthAlias/injectCredentials` 从接口删,RECIPE_LABELS 在 Task 13 保留旧键标签);`list` 加可选 params;新增 rows/case-artifact 两个调用(http 用法抄本文件现有函数)。

- [ ] **Step 2: Type-check(此时 RunDialog 还没改,vue-tsc 可能报旧字段 — 允许只与 api 层相关的错误)**

Run: `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit`
Expected: api 层自身无错误(RunDialog/CaseComposer 引用旧字段的错误留给 Task 11/12 清零)

- [ ] **Step 3: Commit**

```bash
git add src/gimbal-platform/frontend/src/api
git commit -m "refactor(frontend-api): ServiceBinding/RunScheme 类型,RunRequest 收敛,rows/case-artifact 调用"
```

---

### Task 11: RunDialog 重构(方案栏 + 用户与服务 + 折叠区)

**Files:**
- Rewrite: `frontend/src/components/composer/RunDialog.vue`
- Test: 改写 `frontend/src/components/composer/__tests__/RunDialog.auths.test.ts`;跑既有 `RunDialog.baseline/createDataSet/stepName/totalRuns.test.ts` 并按新签名修 fixtures

**Interfaces:**
- Consumes: Task 10 类型;props 由 CaseComposer 供给(Task 12)
- Produces:
  - props:`visible, envs, dataSets`(既有)+ `schemes: RunScheme[]`、`lastRunOverlay: RunOverlay | null`、`referencedServices: string[]`、`authOptions: string[]`(owner 凭证池 ∪ 场景内置 users 别名)
  - emits:`confirm(envId: string, dataSetIds: string[], opts: { stepTo?: string; nRuns?: number; parallel?: number; serviceBindings?: Record<string, ServiceBinding> })`、`saveScheme(scheme: RunScheme)`(存为方案)、既有 close/createDataSet 等不动
  - **删除**:PRESETS/POLICIES/policyHint/prefix 输入/authOptions 多选 chips/append 预检(spec §10 清理表)

- [ ] **Step 1: 改写 RunDialog.auths.test.ts 为 failing test(用户与服务区)**

```ts
// RunDialog.auths.test.ts — 重写:用户与服务绑定区(spec §4)
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'

const BASE_PROPS = {
  envs: [{ envId: 'dev', name: 'dev', baseUrl: 'https://dev' }],
  dataSets: [],
  schemes: [{ name: '冒烟-qa1', envId: 'dev', dataSetIds: [],
              serviceBindings: { 'fin-service': { authAlias: 'qa1' } } }],
  lastRunOverlay: null,
  referencedServices: ['fin-service'],
  authOptions: ['qa1', 'qa2'],
}

function mountDlg(props: Partial<typeof BASE_PROPS> = {}) {
  return mount(RunDialog, { props: { visible: true, ...BASE_PROPS, ...props } })
}

describe('用户与服务绑定区', () => {
  it('referencedServices 每服务一行,默认无绑定', () => {
    const w = mountDlg()
    expect(w.findAll('.rd-bind-row')).toHaveLength(1)
  })

  it('选方案 → 绑定 authAlias 预填;alias 不在 authOptions → 标红降级', async () => {
    const w = mountDlg({ schemes: [BASE_PROPS.schemes[0]], authOptions: [] })
    await w.find('.rd-scheme-select').setValue('冒烟-qa1')     // 或触发选择 handler
    expect(w.find('.rd-bind-row.is-degraded').exists()).toBe(true)
  })

  it('confirm 携带 serviceBindings', async () => {
    const w = mountDlg()
    await w.find('.rd-bind-user').setValue('qa1')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const evt = w.emitted('confirm')![0]
    expect(evt[2].serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa1' } })
  })

  it('存为方案 → emit saveScheme,携带当前 env/ds/bindings', async () => {
    const w = mountDlg()
    await w.find('.rd-bind-user').setValue('qa1')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const s = w.emitted('saveScheme')![0][0] as any
    expect(s.serviceBindings['fin-service'].authAlias).toBe('qa1')
    expect(s.envId).toBe('dev')
  })

  it('退役语义不存在:无 prefix 输入/无 policy 选择', () => {
    const w = mountDlg()
    expect(w.find('.rd-prefix').exists()).toBe(false)
    expect(w.find('.rd-policy').exists()).toBe(false)
    expect(w.text()).not.toContain('合并策略')
  })
})
```

(选择器类名以实现为准对齐;既有四个 RunDialog 测试文件的 mount props 需补 `schemes/lastRunOverlay/referencedServices/authOptions` 必填 props — 逐个文件补默认值。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/RunDialog.auths.test.ts`
Expected: FAIL — 新 props/类不存在

- [ ] **Step 3: Rewrite RunDialog.vue**

结构(spec §4):方案栏 → 主面板(环境 tiles / 数据集多选+基线 / 基础设置 nRuns×parallel+stepTo)→ 折叠区(用户与服务 / 插件列表预埋只读 / 日志订阅预埋只读)→ footer chips + 发起运行。script 核心(完整替换原 setup 中退役部分;环境 tiles/数据集/总量闸 MAX_TOTAL_RUNS=200/钳位逻辑保留):

```ts
const selectedScheme = ref<string>('__adhoc__')          // '__adhoc__' | '__last__' | scheme.name
const schemeOptions = computed(() => [
  { value: '__adhoc__', label: '临时手填' },
  ...(props.lastRunOverlay ? [{ value: '__last__', label: '上次运行' }] : []),
  ...props.schemes.map(s => ({ value: s.name, label: s.name })),
])

// 绑定态:service → { authAlias?, url? };方案/上次运行选择时整体替换
const bindings = ref<Record<string, ServiceBinding>>({})

watch(selectedScheme, (v) => {
  if (v === '__adhoc__') { bindings.value = {}; return }
  const src = v === '__last__'
    ? props.lastRunOverlay
    : props.schemes.find(s => s.name === v)
  const next: Record<string, ServiceBinding> = {}
  for (const svc of props.referencedServices)
    next[svc] = src?.serviceBindings?.[svc] ? { ...src.serviceBindings[svc] } : {}
  bindings.value = next
  if (src?.envId && props.envs.some(e => e.envId === src.envId)) envId.value = src.envId
  if (src?.dataSetIds?.length) selectedDs.value = src.dataSetIds.filter(id =>
    props.dataSets.some(d => d.id === id))
})

// 降级:绑定引用的 alias / 方案的 env / ds 已删 → 标红不报废
const degraded = (svc: string) => {
  const a = bindings.value[svc]?.authAlias
  return !!a && !props.authOptions.includes(a)
}
const schemeDegraded = computed(() =>
  props.schemes.filter(s =>
    (s.envId && !props.envs.some(e => e.envId === s.envId)) ||
    s.dataSetIds.some(id => !props.dataSets.some(d => d.id === id))).map(s => s.name))

function onConfirm() {
  // 总量闸(既有 MAX_TOTAL_RUNS 钳位逻辑保留)后:
  const serviceBindings = Object.fromEntries(Object.entries(bindings.value)
    .filter(([, b]) => b.authAlias || b.url))
  emit('confirm', envId.value, selectedDs.value, {
    ...(stepTo.value ? { stepTo: stepTo.value } : {}),
    ...(nRuns.value !== 1 ? { nRuns: nRuns.value } : {}),
    ...(parallel.value !== 1 ? { parallel: parallel.value } : {}),
    ...(Object.keys(serviceBindings).length ? { serviceBindings } : {}),
  })
}

async function onSaveScheme() {
  const name = schemeNameDraft.value.trim()
  if (!name) return
  emit('saveScheme', {
    name,
    envId: envId.value || null,
    dataSetIds: [...selectedDs.value],
    serviceBindings: { ...bindings.value },
    plugins: null, logSub: null,
  })
}
```

模板关键段(其余沿现状保留段落):

```html
<!-- 方案栏 -->
<div class="rd-scheme-bar">
  <select class="rd-scheme-select" v-model="selectedScheme">
    <option v-for="o in schemeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
  </select>
  <input class="rd-scheme-name" v-model="schemeNameDraft" placeholder="方案名" />
  <button data-testid="save-scheme" @click="onSaveScheme">存为方案</button>
</div>

<!-- 折叠区:用户与服务 -->
<section class="rd-fold" :class="{ 'is-open': foldBindings }">
  <button class="rd-fold-head" @click="foldBindings = !foldBindings">
    用户与服务
    <span class="rd-fold-summary">{{ bindingsSummary }}</span>
  </button>
  <div v-show="foldBindings">
    <div v-for="svc in referencedServices" :key="svc"
         class="rd-bind-row" :class="{ 'is-degraded': degraded(svc) }">
      <span class="rd-bind-svc">{{ svc }}</span>
      <select class="rd-bind-user" v-model="bindings[svc].authAlias">
        <option :value="undefined">— 未绑定 —</option>
        <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
      </select>
      <input class="rd-bind-url" v-model="bindings[svc].url"
             placeholder="覆盖 URL(可选)" />
      <span v-if="degraded(svc)" class="rd-bind-warn">凭证已删,运行时该用户不注入</span>
    </div>
    <p v-if="!referencedServices.length" class="rd-empty">场景未引用任何 service</p>
  </div>
</section>

<!-- 预埋:插件列表 / 日志订阅(只读) -->
<section class="rd-fold">
  <button class="rd-fold-head">插件列表 <span class="rd-fold-summary">待 gimbal 侧支持</span></button>
</section>
<section class="rd-fold">
  <button class="rd-fold-head">日志订阅 <span class="rd-fold-summary">待 gimbal 侧支持</span></button>
</section>
```

CSS:删 policy/preset 相关样式类;新增 `.rd-scheme-bar/.rd-scheme-select/.rd-scheme-name/.rd-bind-row/.rd-bind-svc/.rd-bind-user/.rd-bind-url/.rd-bind-warn/.rd-fold*` 基础样式(对齐组件内现有 token:16px 块距、既有圆角/边框变量写法 — 抄本文件 env tiles 的样式变量)。折叠区默认折叠,`bindingsSummary` = 已绑定计数 `2/3 已绑定`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/ && npx vue-tsc --noEmit`
Expected: RunDialog 五测全绿(其余组件测可能因 CaseComposer 未接而失败 — 只允许 `views/__tests__/CaseComposer*` 与 Executions 相关失败,Task 12/13 清零)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer
git commit -m "feat(rundialog): 方案栏+用户与服务绑定+折叠区,退役 prefix/policy/preset"
```

---

### Task 12: CaseComposer 对接(新 confirm 签名 + 方案拉取 + 上次运行)

**Files:**
- Modify: `frontend/src/views/CaseComposer.vue`(onRunConfirm :681-739;openRunDialog :330-337;RunDialog 挂载 :210-222)
- Test: `frontend/src/views/__tests__/CaseComposer.run.test.ts`(新增,或并入现有 CaseComposer 测试)

**Interfaces:**
- Consumes: Task 10 api(`putRunSchemes/listExecutions`)、Task 11 RunDialog props/emits
- Produces: 打开 RunDialog 时装配 `schemes`(store.draft.orchestration.runSchemes)/`lastRunOverlay`(`GET /executions?scenario_id&limit=1` → config 只取 overlay 三字段)/`referencedServices`(draft steps 派生)/`authOptions`(现有 ownerAuthAliases ∪ 场景 users 键);`saveScheme` → `putRunSchemes(scenarioId, [...现有, 新方案])` → 更新 store draft orchestration.runSchemes

- [ ] **Step 1: Write the failing test**

```ts
// CaseComposer.run.test.ts — onRunConfirm 新签名 + 方案装配
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CaseComposer from '../CaseComposer.vue'

vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({ items: [{ id: 7, config: {
    envId: 'dev', dataSetIds: ['ds-1'],
    serviceBindings: { 'fin-service': { authAlias: 'qa1' } } } }], total: 1 }),
  // ...其余用到的导出补空实现
}))
vi.mock('@/api/scenario-composer', () => ({
  putRunSchemes: vi.fn().mockResolvedValue([]),
  // ...其余用到的导出补空实现
}))

it('上次运行只回填 overlay 三字段(base_config 不回填)', async () => {
  const w = await mountComposerWithDraft()      // 抄现有 CaseComposer 测试的建件方式
  await w.vm.openRunDialog()
  await flushPromises()
  const dlg = w.findComponent({ name: 'RunDialog' })
  expect(dlg.props('lastRunOverlay')).toEqual({
    envId: 'dev', dataSetIds: ['ds-1'],
    serviceBindings: { 'fin-service': { authAlias: 'qa1' } } })
})

it('onRunConfirm 转发 serviceBindings,不含退役键', async () => {
  const runScenario = vi.fn().mockResolvedValue({ executionId: 1 })
  const w = await mountComposerWithDraft({ runScenario })
  await w.vm.onRunConfirm('dev', ['ds-1'], { serviceBindings: { 'fin-service': { authAlias: 'qa1' } } })
  const body = runScenario.mock.calls[0][0]
  expect(body.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa1' } })
  expect('prefix' in body || 'mergePolicy' in body || 'auths' in body).toBe(false)
})
```

(建件方式抄 `views/__tests__/CaseComposer.poolrail.test.ts`/`CaseComposer.expire.test.ts` 现有 mock 结构。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseComposer.run.test.ts`
Expected: FAIL — openRunDialog 未装配 lastRunOverlay / onRunConfirm 旧签名

- [ ] **Step 3: Implement CaseComposer.vue**

`openRunDialog`(:330-337 附近,保留 ownerAuthAliases 懒加载):

```ts
const runSchemes = computed<RunScheme[]>(() =>
  (draftStore.draft?.orchestration?.runSchemes ?? []) as RunScheme[])
const referencedServices = computed(() => {
  const seen = new Set<string>()
  for (const st of (draftStore.draft?.definition?.steps ?? []) as any[])
    if (st?.api?.service) seen.add(st.api.service)
  return [...seen]
})

async function openRunDialog() {
  if (!scenarioId.value) return
  // ownerAuthAliases 既有懒加载保留 …
  try {
    const res = await listExecutions({ scenarioId: scenarioId.value, limit: 1 })
    const cfg = res.items[0]?.config
    lastRunOverlay.value = cfg && (cfg.envId || cfg.dataSetIds?.length || cfg.serviceBindings)
      ? { envId: cfg.envId ?? null, dataSetIds: cfg.dataSetIds ?? [],
          serviceBindings: cfg.serviceBindings ?? {} } : null
  } catch { lastRunOverlay.value = null }
  runVisible.value = true
}

async function onRunConfirm(envId: string, dataSetIds: string[],
                            opts: { stepTo?: string; nRuns?: number; parallel?: number;
                                    serviceBindings?: Record<string, ServiceBinding> }) {
  const body: RunRequest = { scenarioId: scenarioId.value, envId, dataSetIds,
    ...(opts.stepTo ? { stepTo: opts.stepTo } : {}),
    ...(opts.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
    ...(opts.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
    ...(opts.serviceBindings && Object.keys(opts.serviceBindings).length
      ? { serviceBindings: opts.serviceBindings } : {}) }
  await runScenario(body)
  runVisible.value = false
  // 既有 800ms 跳转 Executions 逻辑保留 …
}

async function onSaveScheme(scheme: RunScheme) {
  if (!scenarioId.value) return
  const next = [...runSchemes.value.filter(s => s.name !== scheme.name), scheme]
  const saved = await putRunSchemes(scenarioId.value, next)
  draftStore.draft && (draftStore.draft.orchestration.runSchemes = saved)
}
```

模板挂载处补四个 props 与 `@save-scheme="onSaveScheme"`;`authOptions` = ownerAuthAliases ∪ `Object.keys(draft.definition.config.users ?? {})`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/ src/components/composer/__tests__/ && npx vue-tsc --noEmit`
Expected: 全绿(Executions 相关测试留给 Task 13)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src
git commit -m "feat(composer): RunDialog 对接 — 方案/上次运行装配,serviceBindings 上送"
```

---

## Phase E — 前端可观测 + 按方案导出

### Task 13: Executions 行级表格 + 日志查看

**Files:**
- Modify: `frontend/src/stores/executions.ts`(rows 状态 + 拉取)
- Modify: `frontend/src/views/Executions.vue`(行级表格/展开工件查看/RECIPE_LABELS/JSONL 提示删)
- Test: `frontend/src/views/__tests__/Executions.test.ts`(扩展)

**Interfaces:**
- Consumes: Task 10 `getExecutionRows/getCaseArtifact`、Task 7/9 端点
- Produces: store 增 `rowsByExecution: Record<number, ExecutionRow[]>`、`fetchRows(id)`、`fetchArtifact(id, stem, file)`;Executions.vue 执行详情行级表格(展开行 → 引擎日志/步骤明细两个 tab 或分区);RECIPE_LABELS 增 `serviceBindings/injectedAuths` 标签,**保留**旧键(`prefix:"提单号前缀"`/`mergePolicy`/`execAuthAlias`/`injectCredentials`)标签;删「明细只能服务端检索 JSONL」提示

- [ ] **Step 1: Write the failing test(扩展 Executions.test.ts)**

```ts
it('行级表格:拉取 rows 并渲染;展开可读 engine-log', async () => {
  const { getExecutionRows, getCaseArtifact } = await import('@/api/executions')
  vi.mocked(getExecutionRows).mockResolvedValue({ items: [
    { seq: 0, datasetId: null, rowIndex: 0, rep: 0, status: 'passed',
      caseDir: 'case-000-baseline-r0-n0', startedAt: 't1', finishedAt: 't2' },
    { seq: 1, datasetId: 'ds-1', rowIndex: 0, rep: 0, status: 'failed',
      caseDir: 'case-001-ds-1-r0-n0', startedAt: 't1', finishedAt: 't3' } ] })
  vi.mocked(getCaseArtifact).mockResolvedValue('engine says hi')
  const w = await mountExecutions()          // 抄本文件现有建件方式
  await w.find('[data-testid="exec-row-7"]').trigger('click')   // 展开执行 7
  await flushPromises()
  expect(w.findAll('.ex-table-row')).toHaveLength(2)
  expect(w.text()).toContain('ds-1')
  await w.find('[data-testid="row-artifact-1-engine-log"]').trigger('click')
  await flushPromises()
  expect(w.text()).toContain('engine says hi')
})

it('配方 chips:serviceBindings 显示新标签,旧键 prefix 仍有人读得懂的标签', async () => {
  vi.mocked(listExecutions).mockResolvedValue({ items: [{
    id: 8, status: 'done', config: {
      serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
      injectedAuths: ['qa1'],
      prefix: 'T-1' } }], total: 1 })
  const w = await mountExecutions()
  await flushPromises()
  expect(w.text()).toContain('服务绑定')        // 新键标签
  expect(w.text()).toContain('提单号前缀')      // 旧键标签保留(历史记录可读)
})
```

(建件/mock 方式抄 `Executions.test.ts` 现有结构 — 该文件已有 listExecutions 的 mock 与挂载骨架,直接在其内部追加这两个用例;`config` 键名与 Execution 接口对齐。)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/Executions.test.ts`
Expected: FAIL — rows 表格/工件查看不存在

- [ ] **Step 3: Implement**

store(沿用既有 1s 轮询模式,rows 只对「已展开」执行拉,避免列表 N+1):

```ts
const rowsByExecution = ref<Record<number, ExecutionRow[]>>({})
const expanded = ref<Set<number>>(new Set())

async function fetchRows(id: number) {
  try { rowsByExecution.value = { ...rowsByExecution.value, [id]: (await getExecutionRows(id)).items } }
  catch { /* 软失败:沿用既有软失败预算思路,不计密 */ }
}
// 既有 poll tick 内追加:for (const id of expanded.value) await fetchRows(id)
```

Executions.vue:执行行点击 → `expanded` 切换 + 立即 fetchRows;展开区渲染行级表格(seq/数据集/rep/状态/耗时)每行「引擎日志 | 步骤明细」按钮 → `fetchArtifact` → `<pre>` 展示;状态色沿用现有 status 样式;删除 JSONL 运维提示文案;RECIPE_LABELS 增删按 Interfaces。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/Executions.test.ts && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src
git commit -m "feat(executions): 行级实时表格 + engine.log/步骤明细查看"
```

---

### Task 14: 按方案导出(顶栏菜单 + 场景库行级)

**Files:**
- Modify: `frontend/src/stores/scenario-draft.ts`(exportJson/exportYaml 增 overlay 参数)
- Modify: `frontend/src/components/ScenarioExportMenu.vue`
- Modify: `frontend/src/views/Scenarios.vue`(exportRow)
- Test: `frontend/src/components/__tests__/ScenarioExportMenu.scheme.test.ts`(新增)

**Interfaces:**
- Consumes: Task 10 `previewPlateDraft(draft, overlay?)`、`RunScheme/RunOverlay` 类型
- Produces: 两入口均可「按方案导出」— 选方案 → overlay `{envId, serviceBindings}`(dataSetIds 有意不带,spec §7.3)→ preview-plate → 下载;无方案时行为不变

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ScenarioExportMenu from '../ScenarioExportMenu.vue'

vi.mock('@/stores/scenario-draft', () => ({
  useScenarioDraftStore: () => ({
    draft: { orchestration: { runSchemes: [
      { name: '冒烟-qa1', envId: 'dev', dataSetIds: [],
        serviceBindings: { 'fin-service': { authAlias: 'qa1' } } }] } },
    exportJson: vi.fn().mockResolvedValue(undefined),
    exportYaml: vi.fn().mockResolvedValue(undefined),
    copyJson: vi.fn(),
  }),
}))

it('方案子项走 exportJson(overlay)', async () => {
  const w = mount(ScenarioExportMenu)
  await w.find('.se-trigger').trigger('click')
  await flushPromises()
  const item = w.findAll('.el-dropdown-menu__item').find(i => i.text().includes('冒烟-qa1'))
  expect(item).toBeTruthy()
  await item!.trigger('click')
  const { useScenarioDraftStore } = await import('@/stores/scenario-draft')
  expect(useScenarioDraftStore().exportJson).toHaveBeenCalledWith({
    envId: 'dev', serviceBindings: { 'fin-service': { authAlias: 'qa1' } } })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/__tests__/ScenarioExportMenu.scheme.test.ts`
Expected: FAIL — 方案子项不存在

- [ ] **Step 3: Implement**

`stores/scenario-draft.ts`(先读现有 exportJson/exportYaml 的下载实现,保持不变,只把 previewPlateDraft 调用点加第二参):

```ts
async function exportJson(overlay?: RunOverlay) {
  // 现有流程,仅此行变化:
  const converted = await previewPlateDraft(draftPayload(), overlay)
  // …下载逻辑原样
}
async function exportYaml(overlay?: RunOverlay) { /* 同上 */ }
```

`ScenarioExportMenu.vue`(element-plus dropdown,现有三动作后追加 divided 分组):

```vue
<el-dropdown-item v-for="s in schemes" :key="s.name" :command="`scheme:${s.name}`"
                  :disabled="exporting" divided>
  按方案导出 · {{ s.name }}
</el-dropdown-item>
```

```ts
const schemes = computed(() => (store.draft?.orchestration?.runSchemes ?? []) as RunScheme[])

// onCommand 内追加:
if (cmd.startsWith('scheme:')) {
  const s = schemes.value.find(x => x.name === cmd.slice(7))
  const overlay = s ? { envId: s.envId, serviceBindings: s.serviceBindings } : undefined
  await store.exportJson(overlay)      // YAML 入口同理:菜单再分 JSON/YAML 或默认 JSON — 按
}                                      // 现有菜单形态最小扩展:方案项统一走 exportJson(overlay)
```

`Scenarios.vue` exportRow(先读现函数):行级导出在拉取 draft 后,若 `orchestration.runSchemes.length` 则弹出方案选择(`ElMessageBox`/简易下拉,按本文件现有交互风格),选中后以 `{envId, serviceBindings}` 调 `previewPlateDraft(draft, overlay)` 走既有下载代码;无方案走原路径。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/__tests__/ScenarioExportMenu.scheme.test.ts src/views/__tests__/Scenarios.expire.test.ts && npx vue-tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src
git commit -m "feat(export): 顶栏与场景库按方案导出(overlay 物化)"
```

---

## Phase F — 收尾

### Task 15: 清理校验 + 全量回归

**Files:**
- Verify: 全仓(无新文件)

**Interfaces:**
- Consumes: 全部前序任务
- Produces: spec §10 清理表逐项勾销 + 全绿基线

- [ ] **Step 1: 清理残留 grep 校验(spec §10 清理表)**

```bash
cd src/gimbal-platform
grep -rn "inject_prefix_vars\|_inject_exec_users\|_inject_services" backend/app || echo OK
grep -rn "merge_policy\|mergePolicy" backend/app || echo OK
grep -rn "PRESETS\|policyHint\|rd-prefix\|rd-policy" frontend/src/components/composer/RunDialog.vue || echo OK
grep -rn "MergePolicy" frontend/src || echo OK
grep -rn "服务端检索\|JSONL" frontend/src/views/Executions.vue || echo OK
```

Expected: 全部 OK(Executions.vue 中 RECIPE_LABELS 保留的旧键标签除外 — `mergePolicy` 作为历史留痕标签键允许出现在标签映射里,grep 命中时人工确认仅为标签)。

- [ ] **Step 2: 后端全量**

Run: `cd src/gimbal-platform/backend && python -m pytest -v`
Expected: 全 PASS

- [ ] **Step 3: 前端全量 + 类型**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全 PASS / 0 error

- [ ] **Step 4: 禁区零改动校验**

```bash
git diff --stat main...HEAD -- src/gimbal src/gimbal-plate || true
```
Expected: 空(或仅本分支既有提交,无本轮任务触碰)

- [ ] **Step 5: Commit(如有残留清理)+ 收尾**

```bash
git add -A
git commit -m "chore(run): RunDialog/overlay/可观测性 收尾清理与全量回归"
```

---

## 任务依赖图

```
T1 ─┬─► T3 ─► T4(黄金等价)
T2 ─┘   │
        ├─► T5(ServiceBinding 复用)
        └─► T6 ────────────┐
T7 ◄── (独立)              ├─► T12 ─► T13 ─► T14 ─► T15
T8 ─► T9(依赖 engine.log) ┘
T10 ─► T11 ─► T12
```

串行执行顺序 T1→T15 即可(每任务独立可测、独立提交)。
