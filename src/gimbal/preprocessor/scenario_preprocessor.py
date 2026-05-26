"""preprocessor/scenario_preprocessor.py

Scenario 预处理器：在执行链进入 StepRunner 之前，完成所有准备工作。

职责
----
1. 认证（原 ScenarioRunner._inject_config 的认证部分）
   - 从 scenario.config.authDict 构造 AuthSession，写入 users_pool
   - 调用 AuthManager.get_auth() 触发登录，填充 token

2. 构建两段查询根对象
   - 第一段：scenario.config.serviceDict / authDict（用例自带，优先级高）
   - 第二段：BootstrapConfig.services_pool / users_pool（框架级，优先级低）
   - 不做 model_dump()，直接持有对象引用——AuthSession 刷新后 token 自动可见

3. 批量展开 steps 中的模板字段
   - 递归遍历 step.api / step.request / step.strategy 的所有字段
   - 将 "${auth.tag.token}"、"${service.name}" 等替换为实际值
   - 返回新的 step 列表，原始 schema 不变（immutable-safe）

4. 提取 base_url（原 ScenarioRunner._pick_base_url）

设计原则
--------
- 预处理器无副作用：不写入任何 Context，不触发事件
- 认证副作用（写 users_pool）在此集中，后续执行链只读
- token 刷新由 AuthManager 在执行期按需触发，预处理不负责
- 两段查询顺序：scenario 级 > bootstrap 级（同名 key scenario 级覆盖）
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.config.models import BootstrapConfig
    from gimbal.schema.scenario import Scenario, Config
    from gimbal.schema.step import Step, StepUnion

logger = logging.getLogger(__name__)


class ScenarioPreprocessor:
    """Scenario 预处理器。

    用法::

        pre = ScenarioPreprocessor(scenario_schema, bootstrap_config)
        resolved_steps, base_url = pre.run()

        # resolved_steps 中所有 ${} 模板已展开
        # base_url 供 StepRunner 构造完整 URL
    """

    def __init__(
        self,
        scenario_schema: "Scenario",
        bootstrap_config: "BootstrapConfig",
    ) -> None:
        self._schema = scenario_schema
        self._cfg = bootstrap_config

    # ── 公开入口 ──────────────────────────────────────────────────────────────

    def run(self) -> tuple[list["StepUnion"], str]:
        """执行完整预处理，返回 (resolved_steps, base_url)。

        步骤：
          1. 认证（填充 token 到 users_pool）
          2. 构建查询根对象
          3. 批量展开 steps 模板
          4. 提取 base_url
        """
        # 1. 认证
        self._setup_auth()

        # 2. 构建查询根
        root = self._build_resolve_root()

        # 3. 展开 steps
        resolved_steps = self._resolve_steps(root)

        # 4. base_url
        base_url = self._pick_base_url()

        logger.info(
            "[Preprocessor] 预处理完成: scenario_id=%s steps=%d base_url=%s",
            self._schema.scenarioId,
            len(resolved_steps),
            base_url,
        )
        return resolved_steps, base_url

    # ── 第一段：认证 ──────────────────────────────────────────────────────────

    def _setup_auth(self) -> None:
        """从 scenario.config.authDict 构造 AuthSession 并触发认证。

        认证结果（token）写入 BootstrapConfig.users_pool，
        后续 _build_resolve_root() 直接从 users_pool 拿对象引用。

        BootstrapConfig 本身是 frozen 的，但 users_pool 是 dict，
        dict 内容可变——这里直接操作 dict，不违反 frozen 约束。
        """
        from gimbal.schema.auth import AuthSession
        from gimbal.auth import AuthManager

        auth_dict = getattr(self._schema.config, "authDict", None) or {}
        if not auth_dict:
            logger.debug("[Preprocessor] 无 authDict，跳过认证")
            return

        for tag, entry in auth_dict.items():
            if isinstance(entry, AuthSession):
                # 已经是 AuthSession 对象，直接认证
                self._authenticate_one(tag, entry)
            elif isinstance(entry, dict):
                # 是 dict，先转成 AuthSession
                self._authenticate_one(tag, AuthSession(**entry))
            else:
                logger.warning("[Preprocessor] 未知的 authDict entry 类型: tag=%s type=%s", tag, type(entry).__name__)

    def _authenticate_one(self, tag: str, auth_session) -> None:
        from gimbal.auth import AuthManager

        self._cfg.users_pool[tag] = auth_session
        logger.debug("[Preprocessor] AuthSession 注入 users_pool: tag=%s", tag)

        auth_manager = AuthManager(self._cfg)
        try:
            auth_manager.get_auth(tag)
            session = self._cfg.users_pool.get(tag)
            logger.info(
                "[Preprocessor] 认证成功: tag=%s token=%s token_type=%s",
                tag,
                session.token if session else "?",
                session.token_type if session else "?",
            )
        except Exception as exc:
            logger.error("[Preprocessor] 认证失败: tag=%s error=%s", tag, exc)
            raise

    # ── 第二段：构建查询根 ────────────────────────────────────────────────────

    def _build_resolve_root(self) -> dict[str, Any]:
        """构建两段查询根对象。

        优先级（高 → 低）：
          scenario.config.serviceDict  >  bootstrap.services_pool
          bootstrap.users_pool（含已认证的 AuthSession）

        不做 model_dump()，直接持有对象引用：
          - AuthSession.token 是普通字段，认证后已填充
          - AuthSession.auth_header 是 @property，实时计算
          - token 刷新后无需重建 root，下次模板解析自动拿到新值
        """
        root: dict[str, Any] = {}

        # --- service ---
        # 先放 bootstrap 级（低优先级）
        if self._cfg.services_pool:
            root["service"] = dict(self._cfg.services_pool)
        else:
            root["service"] = {}

        # scenario 级覆盖（高优先级）
        service_dict = getattr(self._schema.config, "serviceDict", None) or {}
        if service_dict:
            root["service"].update(service_dict)

        # --- auth ---
        # users_pool 已包含刚认证好的 AuthSession 对象
        root["auth"] = self._cfg.users_pool

        logger.debug(
            "[Preprocessor] 查询根构建完成: service_keys=%s auth_tags=%s",
            list(root["service"].keys()),
            list(root["auth"].keys()),
        )
        return root

    # ── 第三段：批量展开 steps ────────────────────────────────────────────────

    def _resolve_steps(self, root: dict[str, Any]) -> list["StepUnion"]:
        """遍历所有 steps，对每个 Step 做模板展开，返回新列表。

        StepRef 不做展开（未解析的引用，跳过）。
        """
        resolved: list[Any] = []
        for idx, step_union in enumerate(self._schema.steps):
            if not hasattr(step_union, "api"):
                # StepRef，原样保留
                logger.debug("[Preprocessor] step[%d] 是 StepRef，跳过展开", idx)
                resolved.append(step_union)
                continue
            resolved.append(self._resolve_step(step_union, root, idx))
        return resolved

    def _resolve_step(self, step: "Step", root: dict, idx: int) -> "Step":
        """展开单个 Step 的所有模板字段，返回新 Step 实例。"""
        from gimbal.schema.step import Step

        resolved = Step(
            kind=step.kind,
            api=self._resolve_api(step.api, root),
            request=self._resolve_request(step.request, root),
            strategy=[self._resolve_strategy(s, root) for s in step.strategy],
        )
        logger.debug("[Preprocessor] step[%d] 展开完成", idx)
        return resolved

    def _resolve_api(self, api, root: dict):
        """展开 Api 中的模板字段。"""
        from gimbal.schema.api import Api, ApiRef

        if isinstance(api, ApiRef):
            return api

        resolved_headers = {
            k: self._resolve_value(v, root)
            for k, v in (api.headers or {}).items()
        }
        # 过滤掉解析失败的 None（模板变量不存在时）
        resolved_headers = {k: v for k, v in resolved_headers.items() if v is not None}

        return Api(
            kind=api.kind,
            service=api.service,
            method=api.method,
            path=self._resolve_value(api.path, root),
            headers=resolved_headers,
            timeout=api.timeout,
        )

    def _resolve_request(self, request, root: dict):
        """展开 Request 中的模板字段。"""
        from gimbal.schema.request import Request, RequestRef

        if isinstance(request, RequestRef):
            return request

        return Request(
            kind=request.kind,
            body=self._resolve_nested(request.body or {}, root),
        )

    def _resolve_strategy(self, strategy, root: dict):
        """展开单条策略的模板字段。"""
        from gimbal.schema.strategy import Extract, Assign, Assertion, StrategyRef

        if isinstance(strategy, StrategyRef):
            return strategy

        base = self._base_strategy_fields(strategy)

        if isinstance(strategy, Extract):
            return Extract(
                **base,
                source=strategy.source,
                expression=self._resolve_value(strategy.expression, root),
                target=strategy.target,
                scope=strategy.scope,
                default=self._resolve_value(strategy.default, root),
                required=strategy.required,
            )

        if isinstance(strategy, Assign):
            return Assign(
                **base,
                source=self._resolve_value(strategy.source, root),
                target=strategy.target,
                scope=strategy.scope,
                default=self._resolve_value(strategy.default, root),
                required=strategy.required,
            )

        if isinstance(strategy, Assertion):
            return Assertion(
                **base,
                target=self._resolve_value(strategy.target, root),
                operator=strategy.operator,
                expected=self._resolve_value(strategy.expected, root),
                message=strategy.message,
                soft=strategy.soft,
            )

        # 未知策略类型，原样返回
        return strategy

    # ── 核心：单值模板解析 ────────────────────────────────────────────────────

    def _resolve_value(self, value: Any, root: dict) -> Any:
        """解析单个值中的 ${} 模板。

        - 非字符串 / 不含模板 → 原样返回
        - 整体是单个 ${} → 保留原始类型（int / dict / AuthSession）
        - 嵌入式 ${} → 字符串拼接
        - 解析失败（变量不存在） → 返回原始字符串，记录 warning
        """
        from gimbal.utils.jsonpath import is_template, resolve_template

        if not isinstance(value, str) or not is_template(value):
            return value

        resolved = resolve_template(value, root)

        if resolved is None:
            logger.warning("[Preprocessor] 模板变量未找到: %s", value)
            return value  # 保留原始占位符，不返回 None，避免意外空值

        logger.debug("[Preprocessor] 模板展开: %r → %r", value, resolved)
        return resolved

    def _resolve_nested(self, data: Any, root: dict) -> Any:
        """递归展开嵌套结构（dict / list）中的所有模板字段。"""
        if isinstance(data, dict):
            return {k: self._resolve_nested(v, root) for k, v in data.items()}
        if isinstance(data, list):
            return [self._resolve_nested(item, root) for item in data]
        return self._resolve_value(data, root)

    # ── 第四段：提取 base_url ──────────────────────────────────────────────────

    def _pick_base_url(self) -> str:
        """从 serviceDict 取第一个 URL 作为 base_url。

        优先取 scenario.config.serviceDict，找不到再查 bootstrap.services_pool。
        """
        sd = getattr(self._schema.config, "serviceDict", None) or {}
        if sd:
            url = next(iter(sd.values()), "")
            logger.debug("[Preprocessor] base_url（来自 serviceDict）: %s", url)
            return url

        if self._cfg.services_pool:
            url = next(iter(self._cfg.services_pool.values()), "")
            logger.debug("[Preprocessor] base_url（来自 services_pool）: %s", url)
            return url

        logger.debug("[Preprocessor] 未找到 base_url，使用空字符串")
        return ""

    # ── 辅助 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _base_strategy_fields(strategy) -> dict:
        """提取 StrategyBase 的公共字段，用于构造子类实例。"""
        return {
            "kind":      strategy.kind,
            "name":      strategy.name,
            "phase":     strategy.phase,
            "order":     strategy.order,
            "enabled":   strategy.enabled,
            "onFailure": strategy.onFailure,
            "timeout":   strategy.timeout,
            "tags":      strategy.tags,
        }
