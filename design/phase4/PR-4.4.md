# PR-4.4 Preprocessor 拆分：5 个 Phase Handler

> Phase 4 / PR 4 of 9
> 优先级: 🟡 P1 重构
> 估计工作量: 1.5 PD
> 阻塞: 无

## 一句话目标

把 ~1500 行的 `ScenarioPreprocessor` 单类拆成 **Orchestrator + 5 个 Phase handler**, 每个 phase handler 有独立接口 (`run(plan, ctx) -> PhaseResult`) 与单测入口。

---

## 背景与动机

### 现状 finding

`src/gimbal/preprocessor/scenario_preprocessor.py` 单文件 ~1500 行, 单类 `ScenarioPreprocessor`. **公开 5 个 phase 职责**:

1. **Phase 0**: RefBase 物化(从 asset store 拉内容 → 实例化)
2. **Phase 1**: 模板变量解析 (`resolve_template_strict`)
3. **Phase 2**: 默认值 + 类型转换 (Pydantic 模型变换)
4. **Phase 3**: Service 编排(step.api → request body)
5. **Phase 4**: 验证 & 输出 `ExecutionPlan`

造成后果:

- **单元测试只能整段跑**: 任何一 phase 行为变更都需要构造完整 scenario fixture
- **多 service 静默降级** ([scenario_preprocessor.py:565-575]): schema 没禁, 报错不友好
- **Phase 1 模板解析栈深无界**: `vars` 内引用 `vars` 可爆栈, 无显式深度限制
- **Phase 间错误**：一个 phase fail 整个 preprocessor 死, 无法"先 Phase 0/1/2 都跑, 再 Phase 3/4 报错"

## 范围与非目标

**In scope**:

- 把 5 个 phase 拆成独立模块 `preprocessor/phase/{ref,template,defaults,service,validate}.py`
- `ScenarioPreprocessor` 退化为 `Orchestrator`, 仅协调 phases
- 单类接口稳定(同名 phase 仍按顺序跑), 行为对外一致
- 给每个 phase 加独立单测(原 Phase 0 全 happy path 测试需扩)
- 加 "phase 跳过 / phase 重试" 配置,可后续 PR 用

**Out of scope**:

- phase 间真正并发(单 thread per scenario 已够用)
- phase 输出 ablation(被 Engine 接入即可)

---

## 设计

### 1. 模块结构

```
preprocessor/
  __init__.py
  orchestrator.py        # 新: ScenarioPreprocessor
  phase/
    __init__.py
    base.py              # BasePhase[Input, Output], PhaseContext
    ref.py               # Phase 0: Ref 物化
    template.py          # Phase 1: 模板
    defaults.py          # Phase 2: 默认值 + 类型
    service.py           # Phase 3: service / step 编排
    validate.py          # Phase 4: 验证
  result.py              # PhaseResult / PlanArtifact
```

### 2. BasePhase

```python
class PhaseContext:
    asset_store: AssetStore
    variables: dict[str, Any]                    # CLI --vars / Generator
    cancel_token: CancellationToken | None
    config: BootstrapConfig
    logger: Logger

class PhaseResult(Generic[T]):
    ok: bool
    data: T
    errors: list[PreprocessError]
    warnings: list[str]

T = TypeVar("T")
class BasePhase(Protocol[T]):
    name: ClassVar[str]
    def run(self, input: Any, ctx: PhaseContext) -> PhaseResult[T]: ...
```

### 3. Orchestrator

```python
class ScenarioPreprocessor:
    def __init__(self, phases: list[BasePhase] | None = None):
        self.phases = phases or [
            Phase0_Ref(),
            Phase1_Template(),
            Phase2_Defaults(),
            Phase3_Service(),
            Phase4_Validate(),
        ]

    def execute(
        self,
        scenario: Scenario,
        ctx: PhaseContext,
    ) -> PlanArtifact:
        current = scenario
        all_errors: list[PreprocessError] = []
        for phase in self.phases:
            result = phase.run(current, ctx)
            all_errors.extend(result.errors)
            ctx.logger.info(
                f"[preprocessor] {phase.name} → errors={len(result.errors)} warnings={len(result.warnings)}",
            )
            if not result.ok and phase.required:
                raise PreprocessError(...)
            current = result.data
        return PlanArtifact(current, all_errors)
```

> `phase.required` 默认 True; 后续可由 Policy 控制.

### 4. 各 phase 接口契约

| Phase | Input | Output | 关键依赖 |
|---|---|---|---|
| `Phase 0 Ref` | Scenario | Scenario(Resolution-failed 标 error) | AssetStore |
| `Phase 1 Template` | Scenario | Scenario(模板已替换) | variables, jsonpath |
| `Phase 2 Defaults` | Scenario | Scenario(所有字段有默认值) | Pydantic |
| `Phase 3 Service` | Scenario | Scenario(api → request 已编排) | services dict |
| `Phase 4 Validate` | Scenario | PlanArtifact | engine contract |

### 5. 多 service 行为变更 (强制)

`Phase 3 Service` 改为:

```python
def run(self, scenario, ctx):
    services = list(_collect_service_refs(scenario))
    if len(services) > 1:
        if not ctx.config.allow_multi_service:
            return PhaseResult(ok=False, errors=[
                PreprocessError(code="MULTI_SERVICE_NOT_SUPPORTED",
                                message=f"scenario 引用的 service 数量={len(services)}"),
            ])
        # 否则多 service 当前仍是 warn-only, 不报错
```

> 完整 multi-service 实现仍需 Engine 重构(phase5), 本 PR 至少把"静默降级"换成"明确报错/明确允许".

### 6. 异常与 Phase status

引入 preprocessor 异常层级, 把原 `preprocessor.scenario_preprocessor` 内的所有`raise XYZError` 转为 `PhaseResult.errors`:

```python
class PreprocessError:
    code: str                  # REF_NOT_FOUND / TEMPLATE_MISSING / ...
    message: str
    phase: str                 # 当前 phase.name
    context: dict              # 可 trace 反查
    suggestion: str | None
```

reporter 通过 `phase.name + code` 渲染.

### 7. 测试

每个 phase 一个文件:

| 文件 | 用例 |
|---|---|
| `test_phase_ref.py` | 5 case: happy / cycle / max_depth / not_found / type mismatch |
| `test_phase_template.py` | 8 case: 单变量 / 嵌套 / missing / None / 合法空 / 性能(100 var) |
| `test_phase_defaults.py` | 4 case: 字段默认值 / type coerce / extra forbid / Pydantic 错 |
| `test_phase_service.py` | 4 case: 单 service / multi service 拒 / multi service allow / 缺 service warn |
| `test_phase_validate.py` | 3 case: 合法输出 / 缺字段报错 / 错误尝试 num assert |
| `test_orchestrator.py` | 5 case: 全部 happy / phase 0 错不继续(若 required) / phase 顺序 / 整合 |

---

## 验收 (DoD)

### 必须

- [ ] 5 个 phase 文件独立(单文件 ≤ 350 行)
- [ ] `ScenarioPreprocessor` 退化为 orchestrator(单类 ≤ 100 行)
- [ ] 现有 scenario 行为完全不变(regression: 跑 e2e `tests/integration/test_defect_6_integration.py` 通过)
- [ ] 多 service 场景不再静默降级, 而是明确报错或 allow
- [ ] 6 个测试文件落地, 共 30+ 用例
- [ ] DECISIONS D32 / CHANGELOG

### 应有

- [ ] `phase.name` 出现在 reporter 的 step 前缀中, 增强 diagnostic
- [ ] phase 间断点可恢复(scenario 中断后重入)

### Nice to have

- [ ] `phase.required` / `phase.skip_conditions` 策略化

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 拆分引入新 bug | 保留旧 `ScenarioPreprocessor` 作为 compat shim 一个 release | 删 shim 完整切换 |
| PhaseResult 错误 vs raise Exception 的行为差异 | orchestrator 显式 raise, 文档化 | 不回滚, 这是设计 |
| 多 service 报错让现有用户场景不再可跑 | `BootstrapConfig.allow_multi_service=True` 默认 False, 但发 deprecation | 不回滚 |

---

## 任务清单

- [ ] T1 preprocessor/phase/base.py (PhaseContext / PhaseResult / BasePhase)
- [ ] T2 phase/ref.py + 单测
- [ ] T3 phase/template.py + 单测
- [ ] T4 phase/defaults.py + 单测
- [ ] T5 phase/service.py + 单测 + 多 service 改造
- [ ] T6 phase/validate.py + 单测
- [ ] T7 orchestrator 重写
- [ ] T8 PreprocessError 异常类
- [ ] T9 DECISIONS D32 / CHANGELOG

---

## 依赖与并行

- **依赖**: 无
- **被依赖**: PR-4.3 (Engine 用 plan 输出), PR-4.7 (docs)
- **可并行**: PR-4.5 (test skeleton)
