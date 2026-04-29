"""
数据驱动测试框架 - 最小可跑骨架

架构分层：
  schema    → Pydantic 模型，定义 YAML 结构
  context   → 执行上下文，runner-plugin 数据契约
  events    → 事件类型，状态机产生、插件订阅
  bus       → 事件总线，订阅/发布
  dispatcher→ 动作分发器，按 type 路由到 handler
  handlers  → 4 个动作处理器（sql/extract/assign/assert）
  executor  → 状态机驱动器，按状态推进、调用 handler
  runner    → 顶层入口，加载 YAML、构造 step、跑 executor

设计纪律：
  1. 状态机不知道动作类型
  2. 处理器不知道状态
  3. 处理器之间不互相调用
  4. 失败累积，不断主流程
  5. 副作用都通过 ctx 可观测
"""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Callable, Literal, Union

import yaml
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# 1. 状态机：状态枚举
# =============================================================================

class StepState(str, Enum):
    BEFORE_REQUEST = "before_request"
    REQUESTING = "requesting"
    AFTER_REQUEST = "after_request"
    VERIFYING = "verifying"
    TEARDOWN = "teardown"


# =============================================================================
# 2. Schema：Pydantic 动作类型定义
# =============================================================================

class BaseAction(BaseModel):
    type: str
    name: str | None = None
    on_failure: Literal["abort", "continue", "ignore", "accumulate"] | None = None


class SqlAction(BaseAction):
    type: Literal["sql"]
    from_: str | None = Field(None, alias="from")
    inline: str | None = None
    inline_list: list[str] | None = None
    datasource: str = "default"
    params: dict = {}
    in_transaction: bool = False
    on_failure: Literal["abort", "continue", "ignore"] = "abort"

    @model_validator(mode="after")
    def check_source(self):
        sources = [self.from_, self.inline, self.inline_list]
        if sum(s is not None for s in sources) != 1:
            raise ValueError("sql action requires exactly one of: from / inline / inline_list")
        return self


class ExtractAction(BaseAction):
    type: Literal["extract"]
    key: str
    from_: Literal["response", "database", "variable"] = Field(alias="from")
    path: str | None = None
    sql: str | None = None
    sql_from: str | None = None
    expression: str | None = None
    params: dict = {}
    transform: str | None = None
    default: Any = None
    required: bool = True
    on_failure: Literal["abort", "continue", "ignore"] = "abort"


class AssignAction(BaseAction):
    type: Literal["assign"]
    target: Literal["body", "headers", "query", "path_params"]
    path: str | None = None
    value: Any = None
    expression: str | None = None
    fields: dict | None = None
    on_failure: Literal["abort", "continue", "ignore"] = "abort"


class AssertRule(BaseModel):
    path: str | None = None
    op: str = "eq"
    expected: Any = None
    message: str | None = None


class AssertAction(BaseAction):
    type: Literal["assert"]
    target: Literal["response", "database", "variable", "request_outcome"]
    from_: str | None = Field(None, alias="from")
    rules: list[AssertRule] | None = None
    path: str | None = None
    op: str | None = None
    expected: Any = None
    sql: str | None = None
    status_code: int | dict | None = None
    time_ms: dict | None = None
    on_failure: Literal["abort", "continue", "ignore", "accumulate"] = "accumulate"


Action = Annotated[
    Union[SqlAction, ExtractAction, AssignAction, AssertAction],
    Field(discriminator="type"),
]


# =============================================================================
# 3. Schema：Step / Scenario
# =============================================================================

class ApiSpec(BaseModel):
    method: str
    path: str
    headers: dict = {}


class RequestSpec(BaseModel):
    body: dict = {}
    headers: dict = {}
    query: dict = {}
    path_params: dict = {}


ALLOWED_ACTIONS_BY_STATE = {
    "before_request": {"sql", "extract", "assign"},
    "after_request": {"sql", "extract"},
    "verify": {"assert"},
    "teardown": {"sql"},
}


class Step(BaseModel):
    action_name: str
    enabled: bool = True
    api: ApiSpec
    request: RequestSpec = RequestSpec()
    before_request: list[Action] = []
    after_request: list[Action] = []
    verify: list[Action] = []
    teardown: list[Action] = []

    def actions_at(self, state: StepState) -> list[Action]:
        mapping = {
            StepState.BEFORE_REQUEST: self.before_request,
            StepState.AFTER_REQUEST: self.after_request,
            StepState.VERIFYING: self.verify,
            StepState.TEARDOWN: self.teardown,
        }
        return mapping.get(state, [])

    @model_validator(mode="after")
    def validate_action_states(self):
        for state_name, actions in [
            ("before_request", self.before_request),
            ("after_request", self.after_request),
            ("verify", self.verify),
            ("teardown", self.teardown),
        ]:
            allowed = ALLOWED_ACTIONS_BY_STATE[state_name]
            for action in actions:
                if action.type not in allowed:
                    raise ValueError(
                        f"action type '{action.type}' not allowed in state '{state_name}'"
                    )
        return self


class Scenario(BaseModel):
    scenario_id: str
    flow: list[Step]


# =============================================================================
# 4. 上下文：runner-plugin 数据契约
# =============================================================================

@dataclass
class FailureRecord:
    state: StepState
    layer: str  # "machine" / "assertion" / "framework"
    severity: str  # "fatal" / "error" / "warning"
    source: str
    message: str
    detail: dict = field(default_factory=dict)


@dataclass
class AssertionResult:
    target: str
    path: str | None
    op: str
    expected: Any
    actual: Any
    passed: bool
    message: str | None = None


@dataclass
class ExecutionContext:
    # 静态身份
    scenario_id: str
    action_name: str
    step_index: int

    # 当前执行状态
    current_state: StepState | None = None

    # 输入数据（解析后）
    api: ApiSpec | None = None
    request: RequestSpec | None = None

    # 累积数据
    variables: dict = field(default_factory=dict)
    response: dict | None = None
    response_status: int | None = None
    state_timings: dict = field(default_factory=dict)
    request_outcome: str = "pending"  # "responded" / "network_error" / "timeout"

    # 副作用记录（供插件观测）
    sql_executions: list[dict] = field(default_factory=list)
    assignments: list[dict] = field(default_factory=list)
    extracts: dict = field(default_factory=dict)
    assertions: list[AssertionResult] = field(default_factory=list)

    # 失败累积
    failures: list[FailureRecord] = field(default_factory=list)


# =============================================================================
# 5. 事件 + 总线
# =============================================================================

@dataclass
class StateEntered:
    state: StepState
    timestamp: datetime
    context: ExecutionContext


@dataclass
class StateExited:
    state: StepState
    timestamp: datetime
    duration_ms: int
    context: ExecutionContext


@dataclass
class ActionStarted:
    action: Action
    state: StepState
    context: ExecutionContext


@dataclass
class ActionFinished:
    action: Action
    state: StepState
    duration_ms: int
    context: ExecutionContext


@dataclass
class StepFinished:
    passed: bool
    context: ExecutionContext


class EventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def on(self, event_type: type, handler: Callable):
        self._handlers[event_type].append(handler)

    def emit(self, event):
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception as e:
                print(f"  [bus] plugin handler {handler.__qualname__} failed: {e}")


# =============================================================================
# 6. 变量插值
# =============================================================================

VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def interpolate(value: Any, variables: dict) -> Any:
    """递归地对 dict/list/str 做 ${var} 替换"""
    if isinstance(value, str):
        # 完全匹配 ${xxx} 的情况，保留原值类型
        m = re.fullmatch(r"\$\{([^}]+)\}", value)
        if m:
            var_name = m.group(1)
            return variables.get(var_name, value)
        # 部分匹配 → 字符串替换
        return VAR_PATTERN.sub(lambda m: str(variables.get(m.group(1), m.group(0))), value)
    elif isinstance(value, dict):
        return {k: interpolate(v, variables) for k, v in value.items()}
    elif isinstance(value, list):
        return [interpolate(v, variables) for v in value]
    return value


# =============================================================================
# 7. 简单的路径取值/设值
# =============================================================================

def get_by_path(data: Any, path: str) -> Any:
    """简化版 JSONPath：支持 $.a.b / a.b / a[0].b"""
    if not path or path == "$":
        return data
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]

    cur = data
    # 简单解析：a.b[0].c
    parts = re.split(r"\.|\[(\d+)\]", path)
    parts = [p for p in parts if p is not None and p != ""]
    for part in parts:
        if cur is None:
            return None
        if part.isdigit():
            cur = cur[int(part)] if isinstance(cur, list) else None
        else:
            cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def set_by_path(data: dict, path: str, value: Any):
    """简化版路径设值：a.b.c"""
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


# =============================================================================
# 8. 处理器
# =============================================================================

class ActionHandler(ABC):
    @abstractmethod
    def handle(self, action: Action, ctx: ExecutionContext) -> None: ...


class SqlHandler(ActionHandler):
    """演示用 mock SQL 执行——真实环境换成 SQLAlchemy/asyncpg 等"""

    def __init__(self, mock_db: dict):
        self.mock_db = mock_db

    def handle(self, action: SqlAction, ctx: ExecutionContext):
        sqls = self._resolve(action, ctx)
        for sql in sqls:
            interpolated = interpolate(sql, ctx.variables)
            print(f"      [sql] EXECUTE: {interpolated}")
            ctx.sql_executions.append({
                "datasource": action.datasource,
                "sql": interpolated,
                "state": ctx.current_state.value,
            })

    def _resolve(self, action, ctx) -> list[str]:
        if action.inline:
            return [action.inline]
        if action.inline_list:
            return action.inline_list
        if action.from_:
            # 真实场景从模板注册表加载，这里简化
            return [f"-- template:{action.from_}"]
        return []


class ExtractHandler(ActionHandler):
    """从 response/database/variable 取值，写入变量池"""

    def __init__(self, mock_db: dict):
        self.mock_db = mock_db

    def handle(self, action: ExtractAction, ctx: ExecutionContext):
        try:
            if action.from_ == "response":
                value = get_by_path(ctx.response, action.path)
            elif action.from_ == "database":
                # mock：根据 sql 查 mock_db
                sql = interpolate(action.sql, ctx.variables) if action.sql else ""
                value = self._mock_query(sql)
            elif action.from_ == "variable":
                expr = interpolate(action.expression, ctx.variables)
                value = expr  # 简化：不做真表达式求值
            else:
                value = None
        except Exception as e:
            value = None
            print(f"      [extract] error fetching: {e}")

        if value is None:
            if action.required:
                raise RuntimeError(f"extract '{action.key}' got None and required=True")
            value = action.default

        if action.transform:
            value = self._transform(value, action.transform)

        ctx.variables[action.key] = value
        ctx.extracts[action.key] = {
            "from": action.from_,
            "value": value,
        }
        print(f"      [extract] {action.key} = {value!r}")

    def _mock_query(self, sql: str) -> Any:
        # demo 用：根据 mock_db 模拟 SQL 返回单值
        for key, val in self.mock_db.items():
            if key in sql.lower():
                return val
        return None

    def _transform(self, value, transform):
        if transform == "to_int":
            return int(value)
        if transform == "to_str":
            return str(value)
        if transform == "lower":
            return str(value).lower()
        return value


class AssignHandler(ActionHandler):
    """修改当次 request"""

    def handle(self, action: AssignAction, ctx: ExecutionContext):
        target = self._get_target(action.target, ctx.request)

        if action.fields:
            for path, raw_val in action.fields.items():
                value = interpolate(raw_val, ctx.variables)
                set_by_path(target, path, value)
                self._record(ctx, action.target, path, value)
        else:
            value = self._compute_value(action, ctx)
            set_by_path(target, action.path, value)
            self._record(ctx, action.target, action.path, value)

    def _get_target(self, target_name: str, request: RequestSpec) -> dict:
        return getattr(request, target_name)

    def _compute_value(self, action, ctx):
        if action.value is not None:
            return interpolate(action.value, ctx.variables)
        if action.expression is not None:
            return interpolate(action.expression, ctx.variables)
        return None

    def _record(self, ctx, target, path, value):
        ctx.assignments.append({
            "target": target,
            "path": path,
            "value": value,
            "state": ctx.current_state.value,
        })
        print(f"      [assign] {target}.{path} = {value!r}")


class AssertHandler(ActionHandler):
    """断言。失败累积到 ctx，不抛异常"""

    OPS = {
        "eq": lambda a, e: a == e,
        "ne": lambda a, e: a != e,
        "gt": lambda a, e: a > e,
        "gte": lambda a, e: a >= e,
        "lt": lambda a, e: a < e,
        "lte": lambda a, e: a <= e,
        "in": lambda a, e: a in e,
        "not_in": lambda a, e: a not in e,
        "contains": lambda a, e: e in a,
        "is_null": lambda a, e: a is None,
        "not_null": lambda a, e: a is not None,
    }

    def __init__(self, mock_db: dict):
        self.mock_db = mock_db

    def handle(self, action: AssertAction, ctx: ExecutionContext):
        rules = self._resolve_rules(action)
        target_data = self._fetch_target(action, ctx)

        for rule in rules:
            actual = self._extract(target_data, rule.path) if rule.path else target_data
            expected = interpolate(rule.expected, ctx.variables)
            try:
                passed = self.OPS[rule.op](actual, expected)
                err = None
            except Exception as e:
                passed = False
                err = str(e)

            result = AssertionResult(
                target=action.target,
                path=rule.path,
                op=rule.op,
                expected=expected,
                actual=actual,
                passed=passed,
                message=err,
            )
            ctx.assertions.append(result)

            mark = "✓" if passed else "✗"
            print(f"      [assert] {mark} {action.target}.{rule.path} {rule.op} {expected!r} (actual: {actual!r})")

        # 状态码快捷断言
        if action.status_code is not None and action.target == "response":
            expected_code = action.status_code
            actual_code = ctx.response_status
            passed = actual_code == expected_code
            ctx.assertions.append(AssertionResult(
                target="response", path="status_code", op="eq",
                expected=expected_code, actual=actual_code, passed=passed,
            ))
            mark = "✓" if passed else "✗"
            print(f"      [assert] {mark} response.status_code eq {expected_code} (actual: {actual_code})")

    def _resolve_rules(self, action) -> list[AssertRule]:
        if action.rules:
            return action.rules
        if action.path or action.op:
            return [AssertRule(path=action.path, op=action.op or "eq", expected=action.expected)]
        return []

    def _fetch_target(self, action, ctx):
        if action.target == "response":
            return ctx.response
        if action.target == "variable":
            return ctx.variables
        if action.target == "database":
            sql = interpolate(action.sql, ctx.variables) if action.sql else ""
            return {"_value": self._mock_query(sql)}
        if action.target == "request_outcome":
            return ctx.request_outcome
        return None

    def _extract(self, data, path):
        if path is None:
            return data
        return get_by_path(data, path)

    def _mock_query(self, sql: str):
        for key, val in self.mock_db.items():
            if key in sql.lower():
                return val
        return None


# =============================================================================
# 9. 分发器
# =============================================================================

class ActionDispatcher:
    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_type: str, handler: ActionHandler):
        self._handlers[action_type] = handler

    def dispatch(self, action: Action, ctx: ExecutionContext, bus: EventBus):
        handler = self._handlers.get(action.type)
        if handler is None:
            raise RuntimeError(f"no handler for action type: {action.type}")

        bus.emit(ActionStarted(action=action, state=ctx.current_state, context=ctx))
        start = time.time()
        try:
            handler.handle(action, ctx)
        except Exception as e:
            ctx.failures.append(FailureRecord(
                state=ctx.current_state,
                layer="machine",
                severity="error",
                source=action.type,
                message=str(e),
                detail={"action_type": action.type},
            ))
            if action.on_failure == "abort":
                raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            bus.emit(ActionFinished(
                action=action, state=ctx.current_state,
                duration_ms=duration_ms, context=ctx,
            ))


# =============================================================================
# 10. 状态机执行器
# =============================================================================

class StepAborted(Exception):
    pass


class HttpClient:
    """演示用：根据 api+request 返回 mock 响应"""

    def __init__(self, mock_responses: dict):
        self.mock_responses = mock_responses

    def request(self, api: ApiSpec, request: RequestSpec) -> tuple[int, dict]:
        key = f"{api.method} {api.path}"
        resp = self.mock_responses.get(key, {"code": 0, "data": {}})
        return 200, resp


class StepExecutor:
    MAIN_FLOW = [
        StepState.BEFORE_REQUEST,
        StepState.REQUESTING,
        StepState.AFTER_REQUEST,
        StepState.VERIFYING,
    ]

    def __init__(self, step: Step, ctx: ExecutionContext,
                 dispatcher: ActionDispatcher, bus: EventBus, http: HttpClient):
        self.step = step
        self.ctx = ctx
        self.dispatcher = dispatcher
        self.bus = bus
        self.http = http

    def run(self) -> bool:
        # 把声明的 api / request 设到 ctx
        self.ctx.api = self.step.api
        # 拷贝一份，避免污染原始 step
        self.ctx.request = RequestSpec(**self.step.request.model_dump())

        try:
            for state in self.MAIN_FLOW:
                self._enter(state)
        except StepAborted:
            pass
        finally:
            try:
                self._enter(StepState.TEARDOWN)
            except StepAborted:
                pass
            self._finalize()

        return self._compute_passed()

    def _enter(self, state: StepState):
        self.ctx.current_state = state
        enter_ts = time.time()
        print(f"  → enter {state.value}")
        self.bus.emit(StateEntered(state=state, timestamp=datetime.now(), context=self.ctx))

        try:
            if state == StepState.REQUESTING:
                self._do_request()
            else:
                self._run_hooks(state)
        except StepAborted:
            raise
        except Exception as e:
            self.ctx.failures.append(FailureRecord(
                state=state, layer="machine", severity="error",
                source="executor", message=str(e),
            ))
            if state == StepState.BEFORE_REQUEST:
                # setup 失败 → 跳到 teardown
                raise StepAborted()
        finally:
            duration_ms = int((time.time() - enter_ts) * 1000)
            self.ctx.state_timings[state.value] = duration_ms
            print(f"  ← exit  {state.value} ({duration_ms}ms)")
            self.bus.emit(StateExited(
                state=state, timestamp=datetime.now(),
                duration_ms=duration_ms, context=self.ctx,
            ))

    def _run_hooks(self, state: StepState):
        for action in self.step.actions_at(state):
            try:
                self.dispatcher.dispatch(action, self.ctx, self.bus)
            except Exception:
                # dispatcher 已经记录失败,这里决定是否 abort
                if state == StepState.BEFORE_REQUEST:
                    raise StepAborted()

    def _do_request(self):
        try:
            status, body = self.http.request(self.ctx.api, self.ctx.request)
            self.ctx.response_status = status
            self.ctx.response = body
            self.ctx.request_outcome = "responded"
            print(f"      [http] {self.ctx.api.method} {self.ctx.api.path} → {status}")
            print(f"      [http] body = {body}")
        except Exception as e:
            self.ctx.request_outcome = "network_error"
            self.ctx.failures.append(FailureRecord(
                state=StepState.REQUESTING, layer="machine",
                severity="error", source="http", message=str(e),
            ))

    def _finalize(self):
        passed = self._compute_passed()
        self.bus.emit(StepFinished(passed=passed, context=self.ctx))

    def _compute_passed(self) -> bool:
        blocking = [
            f for f in self.ctx.failures
            if f.severity in ("error", "fatal")
        ]
        if blocking:
            return False
        if any(not a.passed for a in self.ctx.assertions):
            return False
        return True


# =============================================================================
# 11. 示例插件：响应时间统计
# =============================================================================

class ResponseTimePlugin:
    """订阅 StateExited，统计 REQUESTING 状态耗时"""

    def __init__(self):
        self.records = []

    def subscribe(self, bus: EventBus):
        bus.on(StateExited, self._on_exit)

    def _on_exit(self, event: StateExited):
        if event.state == StepState.REQUESTING:
            self.records.append({
                "action_name": event.context.action_name,
                "response_time_ms": event.duration_ms,
            })


# =============================================================================
# 12. 顶层 Runner
# =============================================================================

def normalize_action(raw: dict) -> dict:
    """{ sql: { from: x } } → { type: "sql", from: x }"""
    if len(raw) != 1:
        raise ValueError(f"action dict must have exactly one key: {raw}")
    type_, body = next(iter(raw.items()))
    if not isinstance(body, dict):
        raise ValueError(f"action body must be dict: {raw}")
    return {"type": type_, **body}


def normalize_step(raw: dict) -> dict:
    """递归把每个 hook 列表里的动作 normalize"""
    out = dict(raw)
    for hook in ["before_request", "after_request", "verify", "teardown"]:
        if hook in out:
            out[hook] = [normalize_action(a) for a in out[hook]]
    return out


def load_scenario(path: str) -> Scenario:
    with open(path) as f:
        raw = yaml.safe_load(f)
    raw["flow"] = [normalize_step(s) for s in raw.get("flow", [])]
    return Scenario.model_validate(raw)


class TestRunner:
    def __init__(self, mock_db: dict, mock_responses: dict):
        self.mock_db = mock_db
        self.bus = EventBus()
        self.dispatcher = ActionDispatcher()
        self.dispatcher.register("sql", SqlHandler(mock_db))
        self.dispatcher.register("extract", ExtractHandler(mock_db))
        self.dispatcher.register("assign", AssignHandler())
        self.dispatcher.register("assert", AssertHandler(mock_db))
        self.http = HttpClient(mock_responses)

        # 注册插件
        self.response_time_plugin = ResponseTimePlugin()
        self.response_time_plugin.subscribe(self.bus)

    def run(self, scenario: Scenario):
        print(f"\n{'='*70}")
        print(f"Scenario: {scenario.scenario_id}")
        print(f"{'='*70}")
        results = []
        for idx, step in enumerate(scenario.flow):
            if not step.enabled:
                continue
            print(f"\n[step {idx}] {step.action_name}")
            print("-" * 70)
            ctx = ExecutionContext(
                scenario_id=scenario.scenario_id,
                action_name=step.action_name,
                step_index=idx,
            )
            executor = StepExecutor(step, ctx, self.dispatcher, self.bus, self.http)
            passed = executor.run()
            results.append((step.action_name, passed, ctx))
            print(f"\n  result: {'PASSED' if passed else 'FAILED'}")
            if ctx.failures:
                print(f"  failures: {len(ctx.failures)}")
                for f in ctx.failures:
                    print(f"    [{f.severity}/{f.layer}] {f.state.value}: {f.message}")

        # 总结
        print(f"\n{'='*70}")
        print(f"Summary: {sum(1 for _,p,_ in results if p)}/{len(results)} passed")
        print(f"\nResponseTimePlugin records:")
        for r in self.response_time_plugin.records:
            print(f"  {r['action_name']}: {r['response_time_ms']}ms")
        print(f"{'='*70}\n")
        return results


# =============================================================================
# 13. main
# =============================================================================

if __name__ == "__main__":
    import sys
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "scenario.yaml"

    # mock 后端
    mock_db = {
        "select id from customers": 16,
        "select count(*) from orders": 1,
        "select status from orders": 1,
    }
    mock_responses = {
        "POST /api/order/create": {
            "code": 0,
            "data": {"id": 12345, "bl_no": "AutoTest_xxx", "status": 1},
        },
    }

    scenario = load_scenario(yaml_path)
    runner = TestRunner(mock_db, mock_responses)
    runner.run(scenario)
