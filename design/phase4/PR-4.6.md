# PR-4.6 空壳子包治理决策

> Phase 4 / PR 6 of 9
> 优先级: 🟡 P1 结构
> 估计工作量: 1 PD
> 阻塞: PR-4.7 (docs)

## 一句话目标

对 5 个 ~100% 空壳化的子包 (`compiler/`, `scheduler/`, `observability/`, `resource/`, `ai/`) 做出 **"delete / fill / move-to-roadmap" 三选一** 决策, 落地统一规范(`__stub__` 标签或彻底删除或文档迁移)。

---

## 背景与动机

### 现状 finding (HIGHEST IMPACT — 文档债)

| 子包 | 文件数 | 实际代码 | 文档 |
|---|---|---|---|
| `compiler/` | 5 | 0 行(全部 1 行 docstring) | `README.md` 大段 |
| `suite/` | 4 | 0 行 | `README.md` |
| `scheduler/` | 5 | 0 行 | `README.md` |
| `observability/` | 5 + 4 (backends) | 0 行 | `README.md` 多样(SkyWalking/Prometheus/Graylog) |
| `resource/` | 3 + 4 (providers) | 0 行 | `README.md` |
| `ai/` | 2 + 1 (anthropic) | 0 行 | `README.md` |
| `repository/backends/mysql.py` | 1 | 0 行 | `README.md` |
| `repository/backends/python_module.py` | 1 | 0 行 | (无) |

后果:
1. 开发者被目录树误导, 以为能力已就绪
2. README 中提到接口但 `import` 不到 `AttributeError`
3. `__init__.py` 若误 re-export, 会运行时炸
4. 仓库体积变大但承载空承诺
5. "修复 #X" 类注释满天飞说明项目一直想实现但没实现

## 范围与非目标

**In scope**:

- 5 个子包 (compiler / suite / scheduler / observability / resource / ai) 分别决策
- 2 个空 backend (`mysql / python_module`) 一并决策
- 给出统一规范: 哪类目录用 `__stub__ = True` 标注; 哪类删除; 哪类移到 `docs/roadmap.md`
- `src/gimbal/__init__.py` 的 `__all__` 不 re-export 这些子包
- README 同步更新

**Out of scope**:

- 实际实现任何能力
- 删除第三方插件可能用到的接口

---

## 决策矩阵 (建议由 reviewer 拍板)

按"项目当前节奏"打分:

| 子包 | 决策 | 理由 |
|---|---|---|
| `compiler/` | **删除目录 → 移到 `docs/roadmap.md` "Future: Asset Compiler"** | 团队内 no active owner; 重整在 phase2 之后已可被 SDK 替代 |
| `suite/` | **保留为 stub, 加 `__stub__ = True`, README 显式标 `(planned)`** | Phase 1–4 都用到 suite 概念名, 但实现只在 `core/runner.py` 上, 单独建子包为时尚早 |
| `scheduler/` | **保留 stub, 加 `__stub__ = True`** | PR-4.3 引入 Serial / Parallel; 完整 scheduler 接口留 phase5 |
| `observability/` | **保留 stub + `__stub__ = True`** | tracer/metrics 需独立 PR; 当前用 EventBus 够用 |
| `resource/` | **保留 stub + `__stub__ = True`** | 当前 suite/setup 用的 providers 用 fixture 写即可 |
| `ai/` | **保留 stub + `__stub__ = True`** | 仅 1 个 provider, 与外部 API 依赖强耦合, 不在 phase4 范围 |
| `repository/backends/mysql.py` | **保留 stub + 在 store.py 接 MySQLContentStore 工厂默认备选项走 `NotImplementedError`** | MySQL 后端在 Phase 2 引入后没补完, 可以保留接口但显式 raise |
| `repository/backends/python_module.py` | **保留 stub + 同上** | 同上 |

> **`__stub__ = True`** 标记规范:

```python
# file: src/gimbal/observability/__init__.py
"""
gimbal/observability —— OpenTelemetry 风格的 trace / metrics.

[STUB] This subpackage is at planning stage; functionality is provided
through EventBus currently. See docs/roadmap.md for the implementation plan.

Imports return objects with NotImplementedError on method call, OR raise
ImportError on direct usage. See __stub__ check below.
"""

__stub__: bool = True
```

```python
# 在每个公开类 / 函数:
def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    raise NotImplementedError(
        f"gimbal.observability.{name} is not implemented yet; see roadmap.md.",
    )
```

---

## 范围与非目标

**In scope**:

- 5 个子包 (compiler / suite / scheduler / observability / resource / ai) 分别决策
- 2 个空 backend (`mysql / python_module`) 一并决策
- 给出统一规范: 哪类目录用 `__stub__ = True` 标注; 哪类删除; 哪类移到 `docs/roadmap.md`
- `src/gimbal/__init__.py` 的 `__all__` 不 re-export 这些子包
- README 同步更新

**Out of scope**:

- 实际实现任何能力
- 删除第三方插件可能用到的接口

---

## 设计

### 1. `__stub__` 模式

```python
# src/gimbal/scheduler/__init__.py
"""Scheduler —— 多 scenario 调度的并发/重试/优先级抽象.

[STUB] 当前暂未实现; 见 docs/roadmap.md 第 X 节.
"""

__stub__: bool = True
__all__: list[str] = []   # 显式空, 不 re-export

def __getattr__(name: str):
    raise NotImplementedError(
        f"gimbal.scheduler.{name} is a planned but unimplemented API. "
        f"See docs/roadmap.md and PR-4.3 (which provides SerialScheduler / ParallelScheduler in core/).",
    )
```

### 2. deleted 子包流程

对 `compiler/`:

```
1. 删除 src/gimbal/compiler/ 全部文件
2. 删除 docs 中引用 compiler 的 link
3. 在 docs/roadmap.md 加 "Future: Asset Compiler (priority: low)"
4. 删 DESIGN.md 中任何 compiler 示意
5. 加 changelog 注明 "compiler/ 实装未达, 已迁出"
```

### 3. 校验工具 `check_stub_consistency`

`tools/check_stub_consistency.py`:

- 对每个 `__stub__ = True` 的子包, 检查:
  - 该子包的 README 是否标 `[STUB]`
  - 父级 `__init__.py` 是否 raise NotImplementedError
- 对每个**未声明** `__stub__` 但实际 0 行的子包, **告警** "考虑加 stub"

CI 跑该工具, 失败阻断 merge.

### 4. 文档 migration

`docs/roadmap.md` 新文件, 包含:

```
# Roadmap

## Status Matrix

| 子包        | 状态          | 计划实现 PR | 优先级 |
|-------------|---------------|-------------|--------|
| compiler/   | DELETED       | phase5?     | P3     |
| suite/      | STUB          | phase5      | P2     |
| scheduler/  | STUB          | PR-4.3 done | P1     |
| observability/ | STUB        | phase5      | P2     |
| resource/   | STUB          | phase5      | P3     |
| ai/         | STUB          | phase5      | P3     |

## History

- PR-4.6 (phase4): 治理空壳
```

### 5. README sync

README 主段落加一段:

```
### 实验 / 计划中 子包

下列子包仅作目录占位, 当前不提供功能。开发者请勿依赖它们的公共符号:
- gimbal.scheduler.*: 见 docs/roadmap.md (待 phase5 规划)
- gimbal.observability.*: 同上
- gimbal.resource.*: 同上
- gimbal.ai.*: 同上
- gimbal.suite.*: 同上
- repository.backends.mysql: 部分实现
- repository.backends.python_module: 部分实现

这些子包导入可能成功, 但调用会 raise NotImplementedError.
```

---

## 验收 (DoD)

### 必须

- [ ] 5 个空壳子包 (compiler/scheduler/suite/observability/resource/ai) 决策落地(delete / stub)
- [ ] 2 个空 backend (mysql / python_module) 决策落地
- [ ] `__stub__ = True` 模式在保留子包中实现统一
- [ ] `tools/check_stub_consistency.py` 落地并接入 CI
- [ ] `docs/roadmap.md` 创建
- [ ] README / 各子包 README 加 [STUB] 标记
- [ ] 1 个单元测试: `test_stub_subpackages.py` 验证 raise NotImplementedError
- [ ] DECISIONS D34 / CHANGELOG

### Nice to have

- [ ] 欢迎第三方 plugin 作者贡献某个 stub(独立 issue / mailing)

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 删除 `compiler/` 后, 旧文档中 `@compiler.register` 引用炸 | `git grep compiler` 全扫; 文档替换 placeholder | 恢复前 commit |
| `__stub__` raise NotImplementedError 让 import 仍成功 | 用 PEP 562 `__getattr__` 实现; 不破坏 import | 退出 `__getattr__`, 改用 `__init__.py` raise ImportError |
| 某 stub 子包对插件有用, 删了破坏生态 | 全 audit 一遍 plugin 名册再决策 | 保留 stub, 推到 phase5 决策 |

---

## 任务清单

- [ ] T1 选定 5 子包决策(在本 PR 上 ticket 写明)
- [ ] T2 `compiler/` 删除 + docs 迁移
- [ ] T3 余 5 子包 `__stub__` 化
- [ ] T4 MySQL / python_module 显式 NotImplementedError
- [ ] T5 `docs/roadmap.md` 新建
- [ ] T6 `tools/check_stub_consistency.py` 落地 + CI
- [ ] T7 tests/unit/test_stub_subpackages.py
- [ ] T8 README 同步
- [ ] T9 DECISIONS D34 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.5 (知道哪些子包有测试覆盖)
- **被依赖**: PR-4.7 (docs 同步)
- **可并行**: 无
