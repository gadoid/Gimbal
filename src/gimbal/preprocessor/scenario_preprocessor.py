"""preprocessor/scenario_preprocessor.py

Scenario 预处理器：在执行链进入 StepRunner 之前，完成所有准备工作。

职责
----
1. 认证（原 ScenarioRunner._inject_config 的认证部分）
   - 从 scenario.config.users 构造 AuthSession，写入 AuthRegistry
   - 调用 AuthManager.get_auth() 触发登录，填充 token

2. 构建两段查询根对象
   - 第一段：scenario.config.services / users（用例自带，优先级高）
   - 第二段：BootstrapConfig.services + AuthRegistry（框架级，优先级低）
   - 不做 model_dump()，直接持有对象引用——AuthSession 刷新后 token 自动可见

3. 批量展开 steps 中的模板字段
   - 递归遍历 step.api / step.request / step.strategy 的所有字段
   - 将 "${auth.tag.token}"、"${service.name}" 等替换为实际值
   - 返回新的 step 列表，原始 schema 不变（immutable-safe）

4. 提取 base_url（原 ScenarioRunner._pick_base_url）

设计原则
--------
- 预处理器无副作用：不写入任何 Context，不触发事件
- 认证副作用（写 AuthRegistry）在此集中，后续执行链只读
- token 刷新由 AuthManager 在执行期按需触发，预处理不负责
- 两段查询顺序：scenario 级 > bootstrap 级（同名 key scenario 级覆盖）

历史：原代码把 AuthSession 写入 BootstrapConfig.users，但 BootstrapConfig 是
frozen=True，依赖 dict 内部可变性绕过。Issue 1 修复后 AuthSession 改由
独立的 AuthRegistry 持有，BootstrapConfig.users 字段已删除。
"""
from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.config.models import BootstrapConfig
    from gimbal.auth.registry import AuthRegistry
    from gimbal.repository import AssetStore
    from gimbal.schema.scenario import Scenario, Config
    from gimbal.schema.step import Step, StepUnion

from gimbal.log import get_logger
logger = get_logger(__name__)

# 引用物化器（懒导入避免循环）：
# AssetStore 仅在构造 preprocessor 时被使用；放 TYPE_CHECKING 是因为它只在
# Phase 0 才需要，Phase 0 是可选的（asset_store 为 None 时跳过）。

class ScenarioPreprocessor:
    """Scenario 预处理器。

    用法::

        pre = ScenarioPreprocessor(scenario_schema, bootstrap_config, auth_registry)
        resolved_steps, base_url, services = pre.run()

        # resolved_steps 中所有 ${} 模板已展开
        # base_url 供 StepRunner 构造完整 URL
        # services 为场景声明服务表(D7 per-step 查表,未命中回落 base_url)
    """

    def __init__(
        self,
        scenario_schema: "Scenario",
        bootstrap_config: "BootstrapConfig",
        auth_registry: Optional["AuthRegistry"] = None,
        asset_store: Optional["AssetStore"] = None,
    ) -> None:
        """
        Args:
            scenario_schema:  待预处理的 scenario
            bootstrap_config: 框架级配置
            auth_registry:    认证 session 容器（None 时构造空 registry）
            asset_store:      资产仓库（None 时跳过 Phase 0 物化）。
                              传入即启用引用物化：把所有 RefBase 子类节点
                              替换为从仓库拉来的真实数据类对象。
        """
        self._schema = scenario_schema
        self._cfg = bootstrap_config
        # 缺省时构造一个空的 registry（仅当 scenario 不需要认证时安全）
        if auth_registry is None:
            from gimbal.auth.registry import AuthRegistry
            auth_registry = AuthRegistry()
        self._auth_registry = auth_registry
        self._asset_store = asset_store
        self._generator = self._cfg.generator
        self._resolved_vars: dict[str, Any] = {}   # Phase 1.5 填充

    # ── 公开入口 ──────────────────────────────────────────────────────────────

    def run(self) -> tuple[list["StepUnion"], str, dict[str, str]]:
        """执行完整预处理入口，按顺序执行 0)引用物化、1)认证、2)构建查询根、3)批量展开 steps 模板、4)提取 base_url，返回 (resolved_steps, base_url, services) 元组。

        步骤：
          0. 引用物化（asset_store 不为 None 时）：递归替换 scenario 中所有
             Ref 节点（StepRef / ApiRef / RequestRef / StrategyRef / Ref）为
             仓库拉来的真实数据类对象。必须在认证 / 模板替换之前完成，
             否则执行器会碰到未解析的 Ref 节点。
          1. 认证（填充 token 到 AuthRegistry）
          2. 构建查询根对象
          3. 批量展开 steps 模板
          4. 提取 base_url + 场景声明 services（D7 per-step 查表用）
        """
        # 0. 引用物化
        self._materialize_refs()

        # 1. 认证
        self._setup_auth()

        # 1.5 变量生成
        self._generate_vars()

        # 2. 构建查询根
        root = self._build_resolve_root()

        # 3. 展开 steps
        resolved_steps = self._resolve_steps(root)

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

    # ── 第零段：引用物化（Phase 0）────────────────────────────────────────────

    def _materialize_refs(self) -> None:
        """物化 scenario 中所有 Ref 节点。

        仅在构造时传入了 asset_store 才执行；
        否则此方法为空（保持向后兼容）。

        注意：
          - 直接修改 self._schema（Pydantic v2 默认非 frozen 即可 setattr）
          - 物化后的 scenario.steps 中应该全部是 Step，不再含 StepRef
          - 物化后 step 内 body 等 free-form dict 中的内联 Ref 也会被替换
        """
        if self._asset_store is None:
            logger.debug(
                "[Preprocessor] 未提供 asset_store，跳过 Phase 0 物化",
            )
            return

        from gimbal.core.asset_materializer import AssetMaterializer

        materializer = AssetMaterializer(self._asset_store)
        # 物化整个 scenario 图（包括 steps、api、request、strategy、body）
        materializer.materialize(self._schema)
        logger.info(
            "[Preprocessor] Phase 0 物化完成: scenario_id={}",
            self._schema.scenarioId,
        )

    # ── 第一段：认证 ──────────────────────────────────────────────────────────

    def _setup_auth(self) -> None:
        """从 scenario.config.users 构造 AuthSession 并触发认证。

        回滚 B4 → template 引用的 user 在 preprocess 阶段登录（eager）。
        原因：模板替换（_resolve_steps）依赖 token 字段值——
        模板 ${auth.<tag>.token} 必须解析为真实 token 字符串，
        而非 lazy 模式的 None。

        优化（避免原 B4 修复前的 25min startup）：
          - 扫描所有 step 模板，提取实际引用的 auth tag
          - 只登录被引用的 user，未引用的 skip
        """
        from gimbal.schema.auth import AuthSession
        from gimbal.auth import AuthManager

        auth_dict = getattr(self._schema.config, "users", None) or {}
        if not auth_dict:
            logger.debug("[Preprocessor] 无 users，跳过认证")
            return

        # 1. 先把 AuthSession 注入 registry
        for tag, entry in auth_dict.items():
            if isinstance(entry, AuthSession):
                self._auth_registry.set(tag, entry)
            elif isinstance(entry, dict):
                self._auth_registry.set(tag, AuthSession(**entry))
            else:
                logger.warning(
                    "[Preprocessor] 未知的 users entry 类型: tag={} type={}",
                    tag, type(entry).__name__,
                )

        # 2. 扫描模板找出实际引用的 auth tags
        # 模板格式: ${auth.<tag>.token} / ${auth.<tag>.*}
        # Fix 2+4：用公共 helper 递归扫描，自动覆盖嵌套 body / 自定义 strategy 字段。
        from gimbal.utils.jsonpath import find_template_var_refs

        referenced_tags: set[str] = set()
        for step_union in self._schema.steps:
            for tag in find_template_var_refs(step_union, prefix="auth"):
                referenced_tags.add(tag)

        # 3. 登录：只登录模板引用的（未引用的 skip）
        auth_manager = AuthManager(self._auth_registry)
        for tag in auth_dict:
            if tag in referenced_tags:
                try:
                    auth_manager.get_auth(tag)
                    logger.info(
                        "[Preprocessor] 认证成功（模板引用）: tag={}", tag,
                    )
                except Exception as exc:
                    logger.error(
                        "[Preprocessor] 认证失败: tag={} error={}", tag, exc,
                    )
                    raise
            else:
                logger.debug(
                    "[Preprocessor] tag={} 未在模板中引用，skip 登录", tag,
                )

        logger.info(
            "[Preprocessor] auth 配置完成: 共 {} 个 user, 引用 {} 个, 实际登录 {} 个",
            len(auth_dict), len(referenced_tags), len(referenced_tags),
        )

    # ── 第一段半：变量生成（Phase 1.5）───────────────────────────────────────

    def _generate_vars(self) -> None:
        """Phase 1.5: 合并 scenario + CLI vars，生成或保留字面量。

        合并规则（CLI 赢）：
            merged = {**scenario_vars, **cli_vars}

        每一项运行时判定：
            - dict 且含 'kind'：作为生成式，调用 self._generator.generate
            - str / int / float / bool / None：作为字面量，原样保留
            - 其它类型：抛 ValueError
        """
        from gimbal.generator import VarSpec  # 局部导入避免循环

        cli_vars = self._cfg.vars or {}
        scenario_vars = getattr(self._schema.config, "vars", None) or {}
        merged: dict[str, Any] = {**scenario_vars, **cli_vars}

        result: dict[str, Any] = {}
        for name, spec in merged.items():
            if isinstance(spec, dict) and "kind" in spec:
                var_spec = VarSpec.model_validate(spec)
                result[name] = self._generator.generate(var_spec)
            elif isinstance(spec, (str, int, float, bool, type(None))):
                result[name] = spec
            else:
                raise ValueError(
                    f"[Preprocessor] invalid var spec for '{name}': {spec!r} "
                    f"(expected dict with 'kind' or a primitive literal)"
                )
        self._resolved_vars = result

    # ── 第二段：构建查询根 ────────────────────────────────────────────────────

    def _build_resolve_root(self) -> dict[str, Any]:
        """构建两段查询根对象。

        优先级（高 → 低）：
          scenario.config.services  >  bootstrap.services
          AuthRegistry.snapshot()（含已认证的 AuthSession）

        不做 model_dump()，直接持有对象引用：
          - AuthSession.token 是普通字段，认证后已填充
          - AuthSession.auth_header 是 @property，实时计算
          - token 刷新后无需重建 root，下次模板解析自动拿到新值
        """
        root: dict[str, Any] = {}

        # --- service ---
        # 先放 bootstrap 级（低优先级）
        if self._cfg.services:
            root["service"] = dict(self._cfg.services)
        else:
            root["service"] = {}

        # scenario 级覆盖（高优先级）
        service_dict = getattr(self._schema.config, "services", None) or {}
        if service_dict:
            root["service"].update(service_dict)

        # --- auth ---
        # AuthRegistry.snapshot() 返回浅拷贝字典，下游模板解析只读
        root["auth"] = self._auth_registry.snapshot()

        # --- var（修复 #52 完整链路 + Phase 1.5 生成式变量） ---
        # Phase 1.5 合并 scenario + CLI vars，已生成式变量 / 字面量均落到 _resolved_vars
        # 模板里 ${var.foo} 引用
        if self._resolved_vars:
            root["var"] = dict(self._resolved_vars)

        logger.debug(
            "[Preprocessor] 查询根构建完成: service_keys={} auth_tags={} var_keys={}",
            list(root["service"].keys()),
            list(root["auth"].keys()),
            list(root.get("var", {}).keys()),
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
                logger.debug("[Preprocessor] step[{}] 是 StepRef，跳过展开", idx)
                resolved.append(step_union)
                continue
            resolved.append(self._resolve_step(step_union, root, idx))
        return resolved

    def _resolve_step(self, step: "Step", root: dict, idx: int) -> "Step":
        """展开单个 Step 的所有模板字段，返回新 Step 实例。"""
        from gimbal.schema.step import Step

        resolved = Step(
            kind=step.kind,
            description=step.description,
            api=self._resolve_api(step.api, root),
            request=self._resolve_request(step.request, root),
            strategy=[self._resolve_strategy(s, root) for s in step.strategy],
        )
        logger.debug("[Preprocessor] step[{}] 展开完成", idx)
        return resolved

    def _resolve_api(self, api, root: dict):
        """展开 Api 中的模板字段：解析 path 和 headers 中的 ${} 占位符。

        任一模板变量缺失由 _resolve_value 内部 fail-fast 抛 ValueError（与 body/strategy 一致）。
        因此不再做"先收集所有缺失再统一报错"的 B5 逻辑——单点失败直接上抛。
        """
        from gimbal.schema.api import Api, ApiRef

        if isinstance(api, ApiRef):
            return api

        resolved_headers = {
            k: self._resolve_value(v, root)
            for k, v in (api.headers or {}).items()
        }
        resolved_path = self._resolve_value(api.path, root)

        return Api(
            kind=api.kind,
            service=api.service,
            method=api.method,
            path=resolved_path,
            headers=resolved_headers,
            timeout=api.timeout,
        )

    def _resolve_request(self, request, root: dict):
        """展开 Request 中的模板字段：递归解析 body 嵌套结构中的所有 ${} 占位符，返回新的 Request 实例（RequestRef 原样返回）。"""
        from gimbal.schema.request import Request, RequestRef

        if isinstance(request, RequestRef):
            return request

        return Request(
            kind=request.kind,
            # 修复 falsy 兜底：request.body or {} 会把空字符串 "" 误判为 falsy
            # 并替换成 {} —— 引入 str body 后这是显性问题（str 不再保证 truthy）。
            # 改成 `is None` 才是正确的"body 未提供"语义。
            body=self._resolve_nested(
                request.body if request.body is not None else {}, root
            ),
        )

    def _resolve_strategy(self, strategy, root: dict):
        """展开单条策略（Extract/Assign/Assertion）的模板字段，模板变量缺失时 fail-fast（避免 expected=None 误导），返回新的策略实例（StrategyRef 原样返回，未知类型原样返回）。

        修复 #5：与 `_resolve_api` 一致——模板变量缺失时 fail-fast，
        避免 expected=None 这类误导性断言失败信息。
        """
        from gimbal.schema.strategy import Extract, Assign, Assertion, StrategyRef

        if isinstance(strategy, StrategyRef):
            return strategy

        base = self._base_strategy_fields(strategy)
        owner = f"{type(strategy).__name__}#{strategy.name or '?'}"

        if isinstance(strategy, Extract):
            return Extract(
                **base,
                expression=self._resolve_or_fail(
                    strategy.expression, root, owner=owner, field="expression",
                ),
                target=strategy.target,
                scope=strategy.scope,
                default=self._resolve_or_fail(
                    strategy.default, root, owner=owner, field="default",
                ),
                required=strategy.required,
            )

        if isinstance(strategy, Assign):
            return Assign(
                **base,
                source=self._resolve_or_fail(
                    strategy.source, root, owner=owner, field="source",
                ),
                target=strategy.target,
                scope=strategy.scope,
                default=self._resolve_or_fail(
                    strategy.default, root, owner=owner, field="default",
                ),
                required=strategy.required,
            )

        if isinstance(strategy, Assertion):
            return Assertion(
                **base,
                target=self._resolve_or_fail(
                    strategy.target, root, owner=owner, field="target",
                ),
                operator=strategy.operator,
                expected=self._resolve_or_fail(
                    strategy.expected, root, owner=owner, field="expected",
                ),
                message=strategy.message,
                soft=strategy.soft,
            )

        # 未知策略类型，原样返回
        return strategy

    # ── 核心：单值模板解析（fail-fast 包装）─────────────────────────────────

    def _resolve_or_fail(self, value: Any, root: dict, *, owner: str, field: str) -> Any:
        """解析模板值；缺失则抛 ValueError（fail-fast），与 `_resolve_api` 一致。

        触发条件（必须同时满足）：
          - value 是字符串
          - value 含 ${} 模板（is_template(value)）
          - resolve_template_strict 返回 _MISSING 哨兵（路径真不存在）

        不触发的情况：
          - 非字符串 → 原样返回
          - 无模板字符串 → 原样返回
          - 合法 None 值（key 存在但值是 None） → 返回 None
          - 模板解析成功 → 返回解析值

        注意：必须直接调用 resolve_template_strict，不能走 _resolve_value 包装，
        否则 _resolve_value 会把 _MISSING 折叠成 None，与"合法 None 值"混淆，
        误报 fail-fast。
        """
        from gimbal.utils.jsonpath import is_template, resolve_template_strict, is_missing

        if not isinstance(value, str) or not is_template(value):
            return value

        resolved = resolve_template_strict(value, root)
        if is_missing(resolved):
            raise ValueError(
                f"[Preprocessor] {owner}.{field} 模板变量未找到: {value!r}。"
                "请检查变量名拼写或 vars 注入"
            )
        return resolved

    # ── 核心：单值模板解析 ────────────────────────────────────────────────────

    def _resolve_value(self, value: Any, root: dict) -> Any:
        """解析单个值中的 ${} 模板。

        - 非字符串 / 不含模板 → 原样返回
        - 整体是单个 ${} → 保留原始类型（int / dict / AuthSession）
        - 嵌入式 ${} → 字符串拼接
        - 解析失败（变量不存在） → 抛 ValueError（fail-fast，与 _resolve_or_fail 一致）
        - 合法 None 值（key 存在但值为 None） → 正常返回 None / 空串

        Fix 3 修正：
          区分"路径不存在"（_Missing，触发 fail-fast）与"合法 None 值"
          （key 存在但值为 None，渲染为空串 / 返回 None）。

        Phase 1.5 修正：
          body 模板（经 _resolve_nested → _resolve_value）也走 fail-fast，
          防止静默把变量缺失渲染为 None 进入请求体。
        """
        from gimbal.utils.jsonpath import is_template, resolve_template_strict, is_missing

        if not isinstance(value, str) or not is_template(value):
            return value

        # 修复 B5 + Fix 3：用 strict 版本
        # - 路径不存在 → _Missing（fail-fast 抛 ValueError）
        # - 合法 None → 嵌入式渲染为空串、整体模板返回 None
        resolved = resolve_template_strict(value, root)

        if is_missing(resolved):
            # 路径真不存在 → fail-fast，避免静默渲染为 None 进入请求体
            raise ValueError(
                f"[Preprocessor] 模板变量未找到: {value!r}。"
                "请检查变量名拼写或 vars 注入"
            )

        logger.debug("[Preprocessor] 模板展开: {!r} → {!r}", value, resolved)
        return resolved

    def _resolve_nested(self, data: Any, root: dict) -> Any:
        """递归展开嵌套结构（dict / list）中的所有模板字段：dict 递归每个 value、list 递归每个 item、scalar 走 _resolve_value，返回结构（dict/list）或解析后的标量值。"""
        if isinstance(data, dict):
            return {k: self._resolve_nested(v, root) for k, v in data.items()}
        if isinstance(data, list):
            return [self._resolve_nested(item, root) for item in data]
        return self._resolve_value(data, root)

    # ── 第四段：提取 base_url ──────────────────────────────────────────────────

    def _pick_base_url(self) -> str:
        """按 step 实际引用的 service 提取 base_url（修复 B1）。

        解析策略：
          1. 收集所有 step 引用了哪些 service key
          2. 如果只有一个 service 被引用：用它（精确匹配）
          3. 如果多个 service 被引用：当前架构只支持一个 base_url per scenario，
             取第一个并 warn（让用户知道是 multi-service 降级）
          4. 如果 step 未引用任何 service：fallback 到 services dict 的第一个
             （保留旧行为，向后兼容）
          5. 优先取 scenario.config.services，找不到再查 bootstrap.services

        注：完全多服务支持需要 per-step base_url（架构层面变更），本次
        修复仅消除"静默错路由"——最坏情况是 warn 而非 silent misroute。
        """
        sd = getattr(self._schema.config, "services", None) or {}
        if not sd:
            sd = self._cfg.services or {}

        if not sd:
            logger.debug("[Preprocessor] 未找到 base_url，使用空字符串")
            return ""

        # 收集 step 实际引用的 service key
        referenced: set[str] = set()
        for step_union in self._schema.steps:
            if hasattr(step_union, "api") and hasattr(step_union.api, "service"):
                ref = step_union.api.service
                if ref in sd:
                    referenced.add(ref)
                elif ref:
                    # step 引用了 service，但不在 services dict 中
                    logger.warning(
                        "[Preprocessor] step api.service={!r} 不在 services dict 中，"
                        "该 step 将发到空 base_url（触发 #6 修复的 error 报告）",
                        ref,
                    )

        if len(referenced) == 1:
            chosen = next(iter(referenced))
            url = sd[chosen]
            logger.debug(
                "[Preprocessor] base_url（按 step 引用解析）: service={} url={}",
                chosen, url,
            )
            return url
        elif len(referenced) > 1:
            # 当前架构不支持 per-step base_url，降级并 warn
            chosen = next(iter(referenced))
            url = sd[chosen]
            logger.warning(
                "[Preprocessor] multi-service scenario detected: 引用了 {} 个 "
                "service keys ({})。当前架构只支持一个 base_url per scenario，"
                "使用 '{}' 作为 fallback。其他 service 的 step 会失败。",
                len(referenced), sorted(referenced), chosen,
            )
            return url
        else:
            # step 未引用任何 service（旧行为 fallback）
            url = next(iter(sd.values()), "")
            logger.debug(
                "[Preprocessor] base_url（无 step 引用，fallback 到 dict 第一个）: {}",
                url,
            )
            return url

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
