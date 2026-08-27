# Gimbal 执行过程调用关系图

> 本文以 `gimbal run launch <file>`（单 scenario 文件直执行）为主线，
> 描述从命令行入口到 `StepStateMachine` 终态的完整调用链，
> 标注每个环节对应的 **模块 / 文件 / 方法**，以及
> **配置 / 参数加载路径**与**文件来源**。
>
> 其它子命令（suite / scenario / match / server）共用同一套
> `bootstrap() → Engine.run() → ScenarioRunner.run() → StepStateMachine.run()` 链，
> 差异仅在「参数注入」与「Suite 循环遍历」两点，详见末尾"差异点"一节。

---

## 1. 全景总览

```
                                 ┌─────────────────────────────────────┐
                                 │   python -m gimbal  (或 gimbal CLI) │
                                 │  src/gimbal/__main__.py:3 starter() │
                                 └────────────────┬────────────────────┘
                                                  │
                       Typer callback (main)     ▼
       ┌────────────────────────────────────────────────────────────┐
       │  src/gimbal/cli/main.py:71  main()                         │
       │   ├─ _install_sigint_handler()  [cli/main.py:57]           │
       │   └─ ctx.obj = CLIContext(config_file, no_color, log_level)│
       │                                                            │
       │  派发到子命令 (run/asset/self-check)  src/gimbal/cli/params.py:40-44
       └────────────────────────┬───────────────────────────────────┘
                                │
        run launch <file>       ▼
       ┌────────────────────────────────────────────────────────────┐
       │  src/gimbal/cli/commands/run_launch.py:152  launch()      │
       │  1) 互斥校验 (step_to/breakpoint)         [run_launch.py:212]
       │  2) 写入 cli_ctx.{env,mode,log_level}     [run_launch.py:227-235]
       │  3) configuration = bootstrap(cli_ctx)    [run_launch.py:239] ★
       │  4) _publish_run_meta(configuration)      [run_launch.py:241]
       │  5) payload = normalize_input(source,..)  [run_launch.py:245]
       │  6) scenario = Scenario.model_validate()  [run_launch.py:255]
       │  7) 构造 RuntimeControl (--step-to/--breakpoint) [run_launch.py:264-273]
       │  8) asset_store = _build_default_asset_store() [run_launch.py:284]
       │  9) engine = Engine(configuration, asset_store) [run_launch.py:286]
       │ 10) result = engine.run(scenario, runtime_control) [run_launch.py:288]
       │ 11) shutdown(configuration)                [run_launch.py:291]
       │ 12) _print_run_report(result, output,..)  [run_launch.py:292]
       └────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
```

---

## 2. 框架启动阶段：`bootstrap(cli_ctx)`

> 职责：把"配置"从多源收集 + 校验，初始化所有基础设施，返回不可变的 `Configuration`。

```
bootstrap(cli_ctx)                                          src/gimbal/core/bootstrap.py:52
├── 1. 日志系统 (在 logger 调用前)
│      configure_logging_from_cli(cli_ctx)                  src/gimbal/log/integration.py
│      configure_logging_from_bootstrap(cfg)                src/gimbal/log/integration.py
│
├── 2. 配置合并                                           ── 详见 §3 ──
│      cfg = ConfigLoader().load(cli_ctx)                   src/gimbal/config/loader.py:76
│
├── 3. 基础设施 (按需懒导入)
│      event_bus       = InMemoryEventBus()                 src/gimbal/events/bus.py
│      archive         = InMemoryArchive()                  src/gimbal/context/archive.py
│      hook_registry   = HookRegistry()                     src/gimbal/core/hooks.py
│      plugin_registry = PluginRegistry()                   src/gimbal/plugins/registry.py
│      auth_registry   = AuthRegistry()                     src/gimbal/auth/registry.py
│      ctx_manager     = ContextManager(archive, event_bus) src/gimbal/context/manager.py:22
│      dispatcher      = build_default_dispatcher(...)      src/gimbal/strategy/dispatcher.py
│                        └─ 内部自注册 Extract/Assign/Assertion 等 Executor
│
├── 4. 插件发现 / 加载 / 激活                              [bootstrap.py:105, _load_plugins]
│      loader = PluginLoader(plugins_dir, enabled_filter)   src/gimbal/plugins/loader.py
│      specs  = loader.discover()                            ← 扫描 manifest / entry_point
│      specs  = loader.resolve_deps(specs)                   ← 拓扑排序
│      loader.load_all(specs)                                ← 实例化
│      loader.activate_all(plugins, event_bus, hook_registry, plugin_registry, auth_registry,
│                           user_configs=cfg.plugin_configs) ← 触发 on_activate
│
├── 5. 触发 FRAMEWORK_INIT 钩子                            [bootstrap.py:116]
│      hook_registry.trigger(HookPoint.FRAMEWORK_INIT, {...}) src/gimbal/core/hooks.py
│
├── 6. 装配 Reporter runtime                               [bootstrap.py:127-135]
│      reporter_registry = ReporterRegistry()                src/gimbal/reporter/registry.py
│      register_builtin_reporters(registry)                  src/gimbal/reporter/builtin.py
│      reporter_runtime = ReporterRuntime(registry)          src/gimbal/reporter/runtime.py
│      reporter_runtime.setup(bus=event_bus, config=cfg)     ← 订阅 bus 事件
│
├── 7. 变量生成器注入                                      [bootstrap.py:138-141]
│      generator = Generator(build_default_registry())       src/gimbal/generator/__init__.py
│      cfg = cfg.model_copy(update={"generator": generator}) ← BootstrapConfig frozen
│
└── return Configuration(cfg, auth_registry, ctx_manager,
                         dispatcher, event_bus, archive,
                         hook_registry, plugin_registry,
                         plugins, reporter_runtime)         [bootstrap.py:143-154]
```

`shutdown(configuration)` 流程（`bootstrap.py:213`）按相反顺序清理：
`FRAMEWORK_TEARDOWN` 钩子 → `PluginLoader.deactivate_all()` → `hook_registry.clear()` → `event_bus.stop()`。

---

## 3. 配置 / 参数加载路径

> 来源优先级（低 → 高，后写覆盖前写）：
> **内置默认值 → gimbal.yaml → env 配置文件 → mode 配置文件 → 环境变量 → CLI 参数**

入口：`ConfigLoader.load(cli_ctx)`  [src/gimbal/config/loader.py:76]

```
ConfigLoader.load(cli_ctx)                                  src/gimbal/config/loader.py:76
│
├── BASE_DIR = _find_base_dir()                              src/gimbal/config/loader.py:252
│     └─ 从 cwd 向上查找 pyproject.toml 所在目录（项目根）
│
├── Step 1: defaults = _load_defaults()                     src/gimbal/config/loader.py:121
│     └─ BootstrapConfig.model_validate(self._defaults())    [loader.py:213]
│         env="dev" mode="local" log_level="info" plugins=() ...
│
├── Step 2: merged = _load_yaml_file(BASE_DIR/.../gimbal.yaml, "gimbal.yaml")
│                                                          [loader.py:130]
│     └─ 文件: src/gimbal/config/gimbal.yaml
│         - 写入 services / users / execution / timeout / scope / reporter / poll / plugin_configs ...
│
├── 提前收集 effective_env / effective_mode
│     env_vars = _load_env()                                 [loader.py:146]
│       └─ _ENV_MAP: GIMBAL_ENV / MODE / LOG_LEVEL / MONGO_URI / MINIO_ENDPOINT / REPORT_DIR
│     cli_cfg  = _from_cli(cli_ctx)                           [loader.py:156]
│       └─ 提取 cli_ctx.{env,mode,log_level,no_color}
│       └─ 提取 cli_ctx.extras.{fail_fast,reporters,report_dir,default_timeout,default_retry,vars}
│
├── Step 3: env 配置文件                                    [loader.py:104]
│     merged += _load_yaml_file(BASE_DIR/config/env/gimbal_<env>.yml, env)
│     └─ 文件: src/gimbal/config/env/
│            gimbal_dev.yml / gimbal_test.yml / gimbal_staging.yml / gimbal_prod.yml
│
├── Step 4: mode 配置文件                                   [loader.py:109]
│     merged += _load_yaml_file(BASE_DIR/config/mode/<mode>.yml, mode)
│     └─ 文件: src/gimbal/config/mode/
│            local.yml / server.yml / service.yml
│
├── Step 5: merged += env_vars                              [loader.py:114]
├── Step 6: merged += cli_cfg                               [loader.py:116]
│
└── return _merge(merged, {"base_dir": BASE_DIR}) → BootstrapConfig (frozen)
```

**关键文件清单**

| 类型       | 路径                                                | 作用                                  |
|------------|-----------------------------------------------------|---------------------------------------|
| 默认值     | `ConfigLoader._defaults()`        [loader.py:213]   | 兜底硬编码                            |
| 项目配置   | `src/gimbal/config/gimbal.yaml`                     | 全局基础配置（services/users/exec）   |
| 环境配置   | `src/gimbal/config/env/gimbal_{dev,test,staging,prod}.yml` | 按 env 覆盖 services/users    |
| 模式配置   | `src/gimbal/config/mode/{local,server,service}.yml` | 按 mode 覆盖 execution/timeout/plugins |
| 环境变量   | `os.environ[GIMBAL_*]`  映射见 `_ENV_MAP`            | CI/CD 注入                            |
| CLI 参数   | `CLIContext` from `gimbal/cli/context.py:13`        | 用户显式传入（最高权威）              |
| Schema     | `BootstrapConfig` in `src/gimbal/config/models.py:9` | frozen=True 的 Pydantic 模型          |

> 备注：`gimbal.yaml` 中存在不少 legacy 字段（`execution`/`timeout`/`scope`/`reporter`/
> `chaos`/`database`），`BootstrapConfig` 当前只识别扁平字段
> （`fail_fast`/`request_timeout`/`scenario_timeout`/`suite_timeout`/
> `poll_timeout`/`poll_interval`/`reporters`/`report_dir`/`plugin_configs` …）。
> 未识别字段被 Pydantic 默认忽略（无 `extra="forbid"`），因此旧字段不会报错，但也不生效。

---

## 4. CLI 子命令参数注入

各子命令把执行控制参数塞进 `cli_ctx.extras`，
由 `ConfigLoader._from_cli()` 提取为 `BootstrapConfig` 字段：

| 注入位置 (文件:行)                                              | 注入到 `cli_ctx.extras`            | 最终落到 `BootstrapConfig` 字段  |
|------------------------------------------------------------------|-------------------------------------|----------------------------------|
| `cli/commands/run_launch.py:232` `--report-dir`                | `extras["report_dir"]`              | `report_dir`                     |
| `cli/commands/run_launch.py:235` `--reporter`                  | `extras["reporters"]`               | `reporters`                      |
| `cli/commands/run_suite.py`  `--fail-fast / --var / --var-file` | `extras["fail_fast"]` / `vars`      | `fail_fast` / `vars`             |

`Engine.run()` 之后还会从 `Configuration` 里读 `cfg.fail_fast` 决定 suite 失败是否提前终止
[runner.py:354]。

---

## 5. 输入归一化（仅 `run launch` 走这条路）

`normalize_input(source, inline, fmt)`  [run_launch.py:132]

```
_read_source(source, inline)               → (raw, source_hint)
    ├─ inline:    返回 inline 字面量
    ├─ source=='-':  sys.stdin.read()
    └─ 其它:       Path(source).read_text(utf-8)

_detect_format(fmt, raw, hint)             → InputFormat
    ├─ fmt != auto: 直接透传
    ├─ 扩展名 .yaml/.yml: yaml
    ├─ 扩展名 .json: json
    └─ 嗅探: 首字符 {/[ → json；否则 yaml

_parse_json(raw) / _parse_yaml(raw)        → dict   (顶层必须 dict)
_parse_text(raw)                            → {"__raw_text__": raw, "__pending_parse__": True}
```

随后 `Scenario.model_validate(payload)`  [run_launch.py:255] 把 dict 绑定为 Pydantic 模型
（`src/gimbal/schema/scenario.py:41`），校验失败立即 `typer.Exit(code=2)`。

---

## 6. 执行阶段：`Engine.run(scenario)`

```
Engine.run(target, runtime_control)                              src/gimbal/core/runner.py:88
│
├── 1. framework_ctx = ctx_manager.create_framework_context(    [runner.py:104]
│         run_id=uuid4(),
│         cfg=configuration)                                    [context/manager.py:29]
│     └─ channels=Channels(framework_locked policy) + promotion listener
│
├── 2. _emit_run_start(framework_ctx)                            [runner.py:112, 152]
│     └─ bus.publish(RunStartEvent(...))                         src/gimbal/events/types.py
│
├── 3. reporter_runtime.begin_all(                                [runner.py:118]
│         framework_ctx,
│         reporter_names=cfg.reporters,
│         report_dir=cfg.report_dir,
│         plugin_configs=cfg.plugin_configs)
│
├── 4. if isinstance(target, Scenario): _run_scenario(...)       [runner.py:200]
│     elif isinstance(target, Suite):    _run_suite(...)         [runner.py:272]
│     else: result = RunResult(exit_code=3, error=1)
│
├── 5. _emit_run_end(framework_ctx, result)                      [runner.py:141, 173]
│     └─ bus.publish(RunEndEvent(...))
│
└── 6. self._artifacts = reporter_runtime.finalize_all(result)   [runner.py:147]
    return result
```

### 6.1 `_run_scenario`（单 scenario 路径）

```
Engine._run_scenario(scenario, framework_ctx, runtime_control)   [runner.py:200]
│
├── suite_ctx = framework_ctx.ctx_manager.derive_suite_context(  [context/manager.py:56]
│         suite_id="__default__", suite_name="Default Suite",
│         tags=[], plugins={})
│
└── ScenarioRunner(                                              [scenario_runner.py:178]
        dispatcher=framework_ctx.dispatcher,
        ctx_manager=framework_ctx.ctx_manager,
        hook_registry, event_bus, auth_registry, asset_store
    ).run(scenario, suite_ctx, runtime_control=runtime_control)  ─► 见 §7
```

### 6.2 `_run_suite`（Suite 循环路径）

```
Engine._run_suite(suite, framework_ctx, runtime_control)         [runner.py:272]
│
├── suite_ctx = derive_suite_context(suite_id, suite_name, ...)  [context/manager.py:56]
│
└── for idx, scenario in enumerate(suite.suite):
        result = ScenarioRunner(...).run(scenario, suite_ctx, runtime_control)
        accum: total / passed / failed / error / halted
        if cfg.fail_fast and not result.passed: break            [runner.py:354]
```

---

## 7. Scenario 执行：`ScenarioRunner.run`

```
ScenarioRunner.run(scenario_schema, suite_ctx, runtime_control)   src/gimbal/core/scenario_runner.py:216
│
├── 1. scenario_ctx = ctx_manager.derive_scenario_context(        [context/manager.py:92]
│         suite_ctx, scenario_id, scenario_name, description)
│     └─ 发布 scenario.start 事件                                [scenario.py:scenario_started]
│
├── 2. 预处理 (Phase 0/1/1.5/2/3/4)                              ── 详见 §8 ──
│     preprocessor = ScenarioPreprocessor(                        [preprocessor/scenario_preprocessor.py:53]
│         scenario_schema,
│         bootstrap_config=scenario_ctx.config,
│         auth_registry=self._auth_registry,
│         asset_store=self._asset_store)
│     resolved_steps, base_url = preprocessor.run()               [scenario_preprocessor.py:94]
│
├── 3. _emit_scenario_start(scenario, sid, executable_count)      [scenario_runner.py:273, 421]
│     └─ bus.publish(ScenarioStartEvent(...))                     src/gimbal/events/types.py
│
├── 4. step_runner = StepRunner(                                  [scenario_runner.py:276]
│         dispatcher, ctx_manager, service_base_url=base_url,
│         hook_registry, event_bus)
│
├── 5. for idx, step_union in enumerate(resolved_steps):         [scenario_runner.py:326]
│       ├─ 阶段 1 最小子集: runtime halt 检查                      [scenario_runner.py:329]
│       ├─ B3:  cooperative timeout (cfg.scenario_timeout)        [scenario_runner.py:347]
│       ├─ B8:  cancel flag (gimbal.cli.main.is_cancelled)        [scenario_runner.py:364]
│       ├─ 跳过 StepRef (not hasattr(step_union, "api"))         [scenario_runner.py:375]
│       └─ result = step_runner.run(step_union, scenario_ctx, idx) ─► 见 §9
│
├── 6. ctx_manager.finalize_scenario(scenario_ctx, status)        [context/manager.py]
│
└── 7. _emit_scenario_end(scenario, sid, status, step_count)      [scenario_runner.py:408, 443]
    └─ bus.publish(ScenarioEndEvent(...))
    return ScenarioRunResult(...)
```

---

## 8. 预处理：引用物化 / 认证 / 模板展开 / base_url

`ScenarioPreprocessor.run()`  [src/gimbal/preprocessor/scenario_preprocessor.py:94]

```
ScenarioPreprocessor.run()
│
├── Phase 0 引用物化 (asset_store != None)                        [scenario_preprocessor.py:108, 135]
│     materializer = AssetMaterializer(self._asset_store)          src/gimbal/core/asset_materializer.py
│     materializer.materialize(self._schema)
│       └─ 递归替换 scenario.{steps,api,request,strategy,body} 中所有
│          StepRef/ApiRef/RequestRef/StrategyRef/RefBase 节点，
│          从 AssetStore 拉取真实数据类对象
│
├── Phase 1 认证                                                  [scenario_preprocessor.py:111, 164]
│     for tag, entry in scenario.config.users.items():
│         AuthRegistry.set(tag, AuthSession(**entry))
│     扫描模板 ${auth.<tag>.*} 的引用（utils.jsonpath.find_template_var_refs）
│     for tag in referenced_tags:
│         AuthManager(auth_registry).get_auth(tag)                src/gimbal/auth/manager.py
│           └─ authenticators[auth_type].authenticate()           src/gimbal/auth/builtin/
│           └─ 把 token 写回 AuthSession（registry 持有引用）
│
├── Phase 1.5 变量生成                                            [scenario_preprocessor.py:114, 232]
│     merged = {**scenario.config.vars, **cfg.vars}                ← CLI --var 胜出
│     for name, spec in merged.items():
│       ├─ dict 且含 'kind': Generator(registry).generate(VarSpec)  src/gimbal/generator/
│       └─ str/int/float/bool/None: 原样保留
│     self._resolved_vars = result
│
├── Phase 2 构建查询根                                            [scenario_preprocessor.py:117, 265]
│     root = {
│         "service":  {**cfg.services, **scenario.config.services},   ← scenario 覆盖
│         "auth":     AuthRegistry.snapshot(),                         ← 已含 token
│         "var":      self._resolved_vars,
│     }
│
├── Phase 3 批量展开 steps 模板                                   [scenario_preprocessor.py:120, 311]
│     for step in scenario.steps:
│         Step(api=_resolve_api(...), request=_resolve_request(...),
│               strategy=[_resolve_strategy(s) for s in step.strategy])
│         _resolve_value/_resolve_nested 调用 utils.template 解析 ${service.x}/${auth.x.token}/${var.x}
│
└── Phase 4 base_url                                              [scenario_preprocessor.py:123]
    base_url = scenario.config.services[scenario.steps[0].api.service] or cfg.services[...]
    return resolved_steps, base_url
```

---

## 9. Step 执行：`StepRunner.run` → `StepStateMachine.run`

```
StepRunner.run(step_schema, scenario_ctx, step_index)             src/gimbal/core/scenario_runner.py:116
│
├── step_ctx = ctx_manager.derive_step_context(                   [context/manager.py]
│         scenario_ctx, step_id="step-{idx:03d}", step_name=...,
│         strategy_kind="multi", strategy_spec=step.model_dump(),
│         resolved_vars={}, description=step.description)
│
├── sm = StepStateMachine(                                        src/gimbal/statemachine/engine.py:97
│         step_id, step_schema, dispatcher,
│         view=StepContextAdapter(step_ctx),                       src/gimbal/context/views.py
│         service_base_url, hook_registry, event_bus)
│
├── result = sm.run()                                             [engine.py:164]  ─► 见 §10
│
├── ctx_manager.finalize_step(step_ctx, StepStatus(result.status)) [context/manager.py]
│
└── return result
```

---

## 10. 状态机：`StepStateMachine.run`

> 状态流转（`src/gimbal/statemachine/states.py`）：

```
PENDING ─► BEFORE_REQUEST ─► CALLING ─► AFTER_REQUEST ─► VERIFYING ─► (TEARDOWN ─►) PASSED / FAILED / ERROR
                          └─ hard_fail ─► TEARDOWN ─────► FAILED
                                                                                └ ERROR 兜底
```

`StepStateMachine.run()`  [src/gimbal/statemachine/engine.py:164]

```
StepStateMachine.run()
│
├── 初始化: request_body → view.write_scratch("request_body", body)
├── _advance(BEFORE_REQUEST, reason="start")                       [engine.py:181]
│
├── while not _state.is_terminal:                                 [engine.py:184]
│     handler = _handlers[_state]
│     next_state = handler()
│     _advance(next_state, reason="...")
│
├── _handle_before_request()                                       [engine.py:220]
│     _run_phase(BEFORE_REQUEST)   ← 跑 Assign 类策略
│     if pr.hard_failed → TEARDOWN
│     else              → CALLING
│
├── _handle_calling()                                              [engine.py:234]
│     self._do_http_call()                                         [engine.py:~`CALLING 阶段内部`]
│       ├─ 合成 _CallSpec(method, url, headers, body, timeout)
│       ├─ dispatcher.dispatch(CallSpec, view)                    src/gimbal/strategy/dispatcher.py:51
│       │     ├─ 跳过 disabled 的策略
│       │     ├─ 触发 STRATEGY_BEFORE hook
│       │     ├─ executor.execute()                                src/gimbal/strategy/builtin/call.py
│       │     ├─ 触发 STRATEGY_AFTER hook
│       │     └─ return StrategyResult
│       └─ 写入 view.last_response / view.scratch
│     if result.failed → error_phase="calling", → TEARDOWN
│     else              → AFTER_REQUEST
│
├── _handle_after_request()                                        [engine.py:251]
│     _run_phase(AFTER_REQUEST)   ← 跑 Extract 类策略（提取字段写 context）
│     if pr.hard_failed → TEARDOWN
│     else              → VERIFYING
│
├── _handle_verifying()                                            [engine.py:265]
│     _run_phase(VERIFYING)   ← 跑 Assertion 类策略
│     if has TEARDOWN phase: → TEARDOWN
│     if pr.hard_failed: → FAILED (error_phase="verifying")
│     else:               → PASSED
│
└── _handle_teardown()                                             [engine.py:298]
    _run_phase(TEARDOWN)
    if 前序阶段有 hard_fail → FAILED
    if teardown hard_fail  → PASSED with teardown_failure  (B6: 不污染业务结果)
    else                   → PASSED
```

`_run_phase(phase)` 内部对 `step.strategy` 按 `phase` 过滤后逐条
`dispatcher.dispatch(strategy, view)` [strategy/dispatcher.py:51]。

埋点：
- 入口 `_emit_step_start()` / 出口 `_emit_step_end()` / `_emit_step_failed()` 走 `event_bus`
  [engine.py 内部]；
- 框架还可在 `strategy.dispatcher` 上注册 `STRATEGY_BEFORE/AFTER` 钩子。

---

## 11. 事件 / 钩子 / 报告

```
event_bus:   InMemoryEventBus()                                   src/gimbal/events/bus.py
├─ RunStartEvent          publish @ Engine._emit_run_start        runner.py:165
├─ RunEndEvent            publish @ Engine._emit_run_end          runner.py:187
├─ RunMetaEvent           publish @ CLI._publish_run_meta         cli/common.py:405
├─ ScenarioStartEvent     publish @ ScenarioRunner._emit_scenario_start  scenario_runner.py:435
├─ ScenarioEndEvent       publish @ ScenarioRunner._emit_scenario_end    scenario_runner.py:472
├─ StepStartEvent         publish @ StepStateMachine._emit_step_start
├─ StepEndEvent           publish @ StepStateMachine._emit_step_end
├─ StepFailedEvent        publish @ StepStateMachine._emit_step_failed
└─ StrategyBefore/After   publish @ StrategyDispatcher.dispatch   strategy/dispatcher.py

hook_registry:  HookRegistry()                                    src/gimbal/core/hooks.py
├─ FRAMEWORK_INIT      trigger @ bootstrap step 5                bootstrap.py:116
├─ FRAMEWORK_TEARDOWN  trigger @ shutdown step 1                  bootstrap.py:237
├─ STRATEGY_BEFORE     trigger @ dispatcher.dispatch              strategy/dispatcher.py
├─ STRATEGY_AFTER      trigger @ dispatcher.dispatch
└─ 其它扩展点: 详见 src/gimbal/core/hooks.py:HookPoint

reporter_runtime:  ReporterRuntime                                 src/gimbal/reporter/runtime.py
├─ setup(bus, config)            @ bootstrap step 6               bootstrap.py:134
├─ begin_all(framework_ctx, names, report_dir, plugin_configs)   runner.py:118
├─ (订阅 event_bus 事件 → 边写边落盘)
└─ finalize_all(run_result)      → list[ReportArtifact]           runner.py:147
```

---

## 12. 资产仓库 / 插件加载路径（补充）

```
asset_store (仅 run launch 走)                                    src/gimbal/repository/
└─ _build_default_asset_store(Path(registry))                      cli/common.py:363
   ├─ root = (registry or ~/.gimbal/registry).expanduser()
   └─ AssetStore(backend=LocalFsContentStore(root=root))
         └─ Phase 0 物化时调用 AssetMaterializer.materialize()     core/asset_materializer.py

plugin loading                                                      src/gimbal/plugins/loader.py
└─ _load_plugins(cfg, event_bus, hook_registry, plugin_registry, auth_registry)
   ├─ loader.discover()            扫描 {cfg.base_dir}/{cfg.plugins_dir} 与 entry_point
   ├─ loader.resolve_deps(specs)   拓扑排序（ValueError=循环依赖=致命）
   ├─ loader.load_all(specs)       实例化插件类
   └─ loader.activate_all(plugins, bus, hooks, registry, auth_registry, user_configs)
         └─ 对每个插件 on_activate(ctx) + register_hook/bus/registry
```

---

## 13. 文件 → 方法 一览速查

| 阶段            | 文件 / 行号                                                | 关键方法                                        |
|-----------------|------------------------------------------------------------|-------------------------------------------------|
| 入口            | `src/gimbal/__main__.py:3`                                 | `starter()`                                     |
| Typer 回调      | `src/gimbal/cli/main.py:71`                                | `main(ctx, config, no_color, version, log_level)`|
| 子命令注册      | `src/gimbal/cli/params.py:40-44`                           | `starter.add_typer(...)`                        |
| run launch      | `src/gimbal/cli/commands/run_launch.py:152`                | `launch()`                                      |
| 输入归一化      | `run_launch.py:132`                                        | `normalize_input` / `_read_source` / `_detect_format` / `_parse_yaml` / `_parse_json` |
| 资产仓库        | `src/gimbal/cli/common.py:363`                             | `_build_default_asset_store`                    |
| 元数据发布      | `src/gimbal/cli/common.py:405`                             | `_publish_run_meta`                             |
| 报告打印        | `src/gimbal/cli/common.py:432`                             | `_print_run_report`                             |
| 框架启动        | `src/gimbal/core/bootstrap.py:52`                          | `bootstrap` / `_load_plugins` / `shutdown`      |
| 配置加载        | `src/gimbal/config/loader.py:76`                           | `ConfigLoader.load` / `_load_defaults` / `_load_yaml_file` / `_load_env` / `_from_cli` / `_merge` / `_find_base_dir` |
| 插件加载        | `src/gimbal/plugins/loader.py`                             | `PluginLoader.discover/resolve_deps/load_all/activate_all/deactivate_all` |
| 执行引擎        | `src/gimbal/core/runner.py:88`                             | `Engine.run` / `_run_scenario` / `_run_suite` / `_emit_run_start` / `_emit_run_end` |
| 上下文工厂      | `src/gimbal/context/manager.py:29/56/92/...`               | `create_framework_context` / `derive_suite_context` / `derive_scenario_context` / `derive_step_context` / `finalize_*` |
| Scenario 执行   | `src/gimbal/core/scenario_runner.py:216`                   | `ScenarioRunner.run` / `_emit_scenario_start/end` |
| Step 执行       | `src/gimbal/core/scenario_runner.py:116`                   | `StepRunner.run`                                |
| 状态机          | `src/gimbal/statemachine/engine.py:164`                    | `StepStateMachine.run` / `_handle_before_request/calling/after_request/verifying/teardown` |
| 策略分发        | `src/gimbal/strategy/dispatcher.py:51`                     | `StrategyDispatcher.dispatch`                   |
| 预处理          | `src/gimbal/preprocessor/scenario_preprocessor.py:94`      | `ScenarioPreprocessor.run` / `_materialize_refs` / `_setup_auth` / `_generate_vars` / `_build_resolve_root` / `_resolve_steps` / `_pick_base_url` |
| 引用物化        | `src/gimbal/core/asset_materializer.py`                    | `AssetMaterializer.materialize`                 |
| 认证            | `src/gimbal/auth/manager.py`                               | `AuthManager.get_auth`                          |
| 变量生成        | `src/gimbal/generator/__init__.py`                         | `Generator.generate` / `build_default_registry` |
| 模板解析        | `src/gimbal/utils/template.py` (经由 `_resolve_value`)     | resolve `${service.x}` / `${auth.x.token}` / `${var.x}` |
| 报告            | `src/gimbal/reporter/runtime.py`                           | `ReporterRuntime.setup` / `begin_all` / `finalize_all` |
| 事件总线        | `src/gimbal/events/bus.py`                                 | `InMemoryEventBus.publish/subscribe/stop`       |

---

## 14. 各子命令差异点

| 子命令                                | 输入来源                          | 执行分发                                                                 |
|---------------------------------------|-----------------------------------|--------------------------------------------------------------------------|
| `run launch <file>`                   | 文件路径 / stdin / `--inline`     | 解析→`Scenario`→`Engine._run_scenario`                                   |
| `run scenario <id> [id...]`           | 资产仓库 (AssetStore)              | 查仓库→`Scenario`→`Engine._run_scenario`；`--order` 决定顺序            |
| `run suite <id> [id...]`              | 资产仓库                          | 查仓库→`Suite`→`Engine._run_suite`（循环 `_run_scenario`）              |
| `run match <pattern>`                 | glob 匹配本地文件                  | 遍历 → 各文件 `Engine._run_scenario`                                     |
| `run server --port=...`               | HTTP/gRPC/WS 任务                  | `core/server.py` 长驻监听，分发到 `Engine.run`                          |
| `run show <id>`                       | 资产仓库                          | 只读打印 steps 索引，不执行                                                |

所有 run 子命令都共用 `bootstrap(cli_ctx)` + `Engine.run()` 这两个核心入口，
差异仅在「如何把目标 schema 喂进 `Engine.run()`」以及「`Suite` 还是 `Scenario`」。

---

## 15. 关键不变量 / 注意事项

1. **配置不可变**：`BootstrapConfig` (`config/models.py:9`) `frozen=True`，
   bootstrap 阶段用 `cfg.model_copy(update=...)` 注入 `generator`。
2. **运行期状态分离**：可变状态（token、scratch、context）放在
   `AuthRegistry` / `Context` / `StepContext` 中，**不污染** `BootstrapConfig`。
3. **资源懒加载**：`Configuration` 只持引用，**不持任何层级 Context**；
   Context 在 `Engine.run()` 内部按 framework → suite → scenario → step 派生。
4. **plugin 容错**：单插件失败被 loader 内部隔离；只有结构性故障（`OSError`/
   `ImportError`/`ValueError` 循环依赖）才回退空列表。
5. **状态机终态**：`PASSED` / `FAILED` / `ERROR`；`B6 修复` 后 `teardown`
   失败不会让业务通过的 step 退化为 FAILED。
6. **halt 语义**：`RuntimeControl.halt_at` 走 Python `range(stop)` 语义，
   与现有 timeout/cancel 路径**正交**。
