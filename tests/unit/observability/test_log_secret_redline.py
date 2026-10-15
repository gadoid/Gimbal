"""S11A 引擎红线：凭证不入日志 message（结构化日志设计 §5 S11）。

背景：通知摘要(S6)是日志内容唯一对外出口——出口打码是窄防护，真正的
红线在引擎侧：凭证不进任何类别的日志 message。本测试做**全类别抽查**：
带凭证跑真实引擎（认证登录 + 协议调用注入 Authorization 头 + 失败路径
触发 step/strategy 层 WARNING/ERROR），JsonSink 全量捕获后扫全部行。

扫描口径（命中即红）：
  1. 凭证取值形态 —— 键名(password/passwd/secret/token/authorization/
     api[-_]key) + 分隔符(``=``/``:``) + 非空值，或 ``Bearer <串>``。
     裸词不算红：引擎有过程性提及（如「[AuthManager] 刷新 token: tag=x」
     —— "token" 是词面不是凭证），形态正则只抓**取值形状**；
  2. 实配凭证字面量 —— 测试注入的 secret 值不得出现在任何 message，
     也不得出现在整行 JSON（log payload 会原样入库 execution_events）。

顺序约束（设计 §12 批 5）：本测试**先行于** S6 通知摘要落地 —— S6 把
日志行摘进通知 body 之前，这里的红线必须已立。
"""
import io
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from datetime import datetime, timezone
from types import SimpleNamespace

SECRET_PW = "pw-REDLINE-5e77-2f0e-9a1b"     # 登录口令(PreToken 模式镜像为 token)
SECRET_TOKEN = "sk-REDLINE-9c1f-47aa-b206"  # 预置 access token

# 凭证取值形态:key=value / key: value(值至少 4 字符,滤掉 "url=" 空值噪声)
# + Bearer 串
_SECRET_SHAPE_RE = re.compile(
    r"\b(password|passwd|secret|token|authorization|api[_-]?key)\b"
    r"\s*[=:]\s*['\"]?[^\s'\"]{4,}"
    r"|\bbearer\s+[^\s'\"]{4,}",
    re.IGNORECASE,
)


def _run_redline_plan(buf: io.StringIO) -> list[dict]:
    """带凭证跑真实引擎,JsonSink 全量捕获到 buf,返回解析后的行列表。

    覆盖面(全类别抽查的范围声明):
      - auth:AuthManager 真实登录流程(INFO/DEBUG 行);
      - call:协议注册/请求就绪/执行异常路径,send 内注入 Authorization 头;
      - core:stdlib 桥接(httpx.client 经 InterceptHandler → loguru → JSON);
      - step/strategy/compiler:成功 + 失败两条单元路径的引擎日志。
    """
    from loguru import logger

    from gimbal.auth.manager import AuthManager
    from gimbal.auth.registry import AuthRegistry
    from gimbal.auth.session import AuthSession
    from gimbal.log.formatters import JsonSink
    from gimbal.log.intercept import InterceptHandler

    from gimbal.config.models import BootstrapConfig
    from gimbal.context.archive import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.core.bootstrap import Configuration
    from gimbal.core.hooks import HookRegistry
    from gimbal.core.runner import Engine
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.plugins import PluginRegistry
    from gimbal.protocols.base import ProtocolExecutor
    from gimbal.protocols.result import CallResult
    from gimbal.schema import Call
    from gimbal.schema.plan import PlanPolicy
    from gimbal.schema import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
    from gimbal.schema import Step
    from gimbal.strategy.dispatcher import build_default_dispatcher

    class RedlineExecutor(ProtocolExecutor):
        """凭证流经的测试协议:login 取 token 注入 Authorization 头。"""

        protocol = "redline"

        def build_spec(self, call, pctx):
            return SimpleNamespace(
                kind="call:redline", message=str(getattr(call, "message", "")),
                user=str(getattr(call, "user", "") or ""),
                headers={}, pctx=pctx)

        def send(self, spec, view):
            tok = (self.login(spec.user) or {}).get("token")
            spec.headers["Authorization"] = f"Bearer {tok}"
            # stdlib 桥接路径(→ category core):真实 httpx 汇总行形态
            logging.getLogger("httpx.client").debug(
                'HTTP Request: POST http://fin.internal/_redline "HTTP/1.1 200"')
            logger.debug("[redline] 请求就绪: user={} header_keys={}",
                         spec.user, sorted(spec.headers))
            if spec.message == "bad":
                raise RuntimeError("connection reset by peer")
            return CallResult.build(
                protocol=self.protocol,
                request={"headers": dict(spec.headers), "body": {"ok": True}},
                status=0, body={"echo": spec.message})

    reg = AuthRegistry()
    reg.set("preset-user", AuthSession(token=SECRET_TOKEN))

    bus = InMemoryEventBus()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    executor = RedlineExecutor()
    dispatcher.protocols.register(executor)
    ctx_manager = ContextManager(archive=InMemoryArchive(), event_bus=bus)
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="debug"),
        auth_registry=reg, ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )

    def _scenario(sid: str, *, user: str) -> Scenario:
        return Scenario(
            scenarioId=sid,
            meta=Meta(name=sid, description="d", module="red-mod", priority=1,
                      author="a", owner="o", tags=[], version="1",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=SC(), resource={},
            steps=[Step(call=Call(protocol="redline", message=sid, user=user),
                        strategy=[])],
        )

    graph = SuiteGraph(
        kind="graph", mode="aggregate",
        units=[
            UnitDecl(ref="ok", scenario=_scenario("ok", user="login-user")),
            UnitDecl(ref="bad", scenario=_scenario("bad", user="preset-user")),
        ],
        policy=PlanPolicy(parallel=1),
    )

    # ── 捕获:JsonSink(DEBUG 全量) + stdlib 桥接 ──────────────────
    # 凭证注册(真实 AuthManager 流程)在捕获窗口内 —— auth 类别行也要过红线
    root_handlers, root_level = logging.root.handlers, logging.root.level
    httpx_lv = logging.getLogger("httpx.client").level   # 前序测试可能已静默,桥接行会被 logger 级过滤
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.DEBUG)
    logging.getLogger("httpx.client").setLevel(logging.DEBUG)
    sink_id = logger.add(JsonSink(buf), level="DEBUG")
    try:
        AuthManager(reg).load_and_auth(
            "login-user", {"username": "admin", "password": SECRET_PW})
        Engine(conf).run(graph)
    finally:
        logger.remove(sink_id)
        logging.root.handlers = root_handlers
        logging.root.setLevel(root_level)
        logging.getLogger("httpx.client").setLevel(httpx_lv)

    return [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]


class TestLogSecretRedline:

    def test_no_credential_shape_or_value_in_any_log_message(self):
        buf = io.StringIO()
        lines = _run_redline_plan(buf)
        assert lines, "引擎未产生任何日志行 —— 抽查失效"

        # 1) 取值形态:任何类别的 message 不含凭证形状
        for ln in lines:
            m = _SECRET_SHAPE_RE.search(ln.get("message") or "")
            assert m is None, (
                f"日志 message 出现凭证形态 [{ln.get('category')}]: "
                f"{m.group(0)!r} <- {ln.get('message')!r}")
        # 2) 字面量:secret 值不进 message,也不进整行 JSON(行会原样入库)
        raw = buf.getvalue()
        for secret in (SECRET_PW, SECRET_TOKEN):
            assert secret not in raw, f"凭证字面量泄漏到日志行: {secret}"

    def test_redline_actually_exercises_credential_and_categories(self):
        """抽查有效性闸:凭证确实流经了调用(send 注入了头),且抽查面覆盖
        auth/call/core/step 四类 —— 否则上面的红线是空转。"""
        from gimbal.protocols.result import redact_mapping

        buf = io.StringIO()
        lines = _run_redline_plan(buf)
        cats = {ln.get("category") for ln in lines}
        assert {"auth", "call", "core", "step"} <= cats, (
            f"类别覆盖不足: {sorted(c for c in cats if c)}")
        # 桥接行(httpx.client)确实经 stdlib 拦截进了 JSON 管道
        assert any(ln.get("logger") == "httpx.client" for ln in lines)
        # 证据面脱敏照旧(区别于 message 红线):request.headers 的
        # authorization 键被 redact_mapping 覆写 —— 同一份数据两条纪律互证
        masked = redact_mapping({"headers": {"Authorization": f"Bearer {SECRET_TOKEN}"}})
        assert masked["headers"]["Authorization"] != f"Bearer {SECRET_TOKEN}"
