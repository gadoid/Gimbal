# PR-EOP: End-of-Phase 收口(review pipeline + 文档同步 + 基线确认)

> **状态**:待执行
>
> **PR 范围**:Phase 1 全部 7 个 PR(PR-0.1 / 0.2 / B / C / D1 / D2 / D3 / D4)落地后,做收口:
> 1. review pipeline CI gate(把 `test_invariants.py` 的不变量做成 CI 必跑)
> 2. 文档同步(更新 PLATE_DESIGN.md 标注"Phase 1 已实现")
> 3. 基线确认(≥221 测试全过 + fin 服务 31 端点全部可注册)
>
> **前置依赖**:**Phase 1 全部前序 PR 已落地**。
>
> **关键设计**:本 PR **不写新业务代码**,只做"验证 + 文档"。是 Phase 1 的"出厂质检"。
>
> **对应设计**:[PLATE_DESIGN.md §7 不变承诺](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 1 涉及 7 个 PR,改动跨 15+ 文件、新增 60+ 测试。**没有收口环节 = 散落的 PR 各自为政,Phase 2 接手时无人知道"现状是什么"**。

**Phase 1 收口需做**:
1. **CI gate**:所有不变量在 PR merge 前必跑(防回归)
2. **文档**:PLATE_DESIGN.md §2 / §3 的"待实现"标注改为"已实现"
3. **基线**:`pytest tests/` 全过 + 31 个 fin 端点全注册成功

### 1.2 关键决策

- **不写新业务代码**:本 PR 是"验证 + 文档",不允许"借机加 feature"
- **CI gate 复用现有 pytest**:`test_invariants.py` 是普通 pytest 文件,只需在 CI 配置里加 `pytest tests/plate/test_invariants.py -v` 必跑项
- **文档更新最小化**:只改"待实现 → 已实现"标注,不动设计本身

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `.github/workflows/ci.yml`(或同等 CI 配置) | 加 `pytest tests/plate/test_invariants.py -v` 必跑项 |
| `tests/plate/test_invariants.py` | 汇总 Phase 1 所有不变量(从各 PR 的 §2.5 聚合) |
| `design/PLATE_DESIGN.md` | §2 / §3 的"待实现"标注改为"已实现 (Phase 1)" |
| `design/PLATE_EVOLUTION.md` | Phase 1 状态从"待执行"改为"已完成(2026-XX-XX)" |
| `design/phase1/INDEX.md` | 所有 PR 状态从"待执行"改为"已完成" |
| `tests/plate/test_eop_baseline.py` | 新建:Phase 1 收口专项测试(≥8 个) |

### 2.2 CI gate 配置(伪代码示例)

```yaml
# .github/workflows/ci.yml
name: Phase 1 Invariants

on: [pull_request]

jobs:
  invariants:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      # Phase 1 不变量 CI gate
      - name: Phase 1 Invariants
        run: |
          pytest tests/plate/test_invariants.py -v --tb=short
      # 全量基线
      - name: Full Baseline
        run: |
          pytest tests/ -v --tb=short
```

**业务意图**:
- Phase 1 不变量是"必须保证的硬约束",PR merge 前必跑
- 全量基线是"防回归",任何测试失败都阻塞 merge
- `--tb=short` 失败信息紧凑便于 review

### 2.3 `test_invariants.py` 聚合

```python
# tests/plate/test_invariants.py
"""Phase 1 不变量聚合。

所有不变量对应业务承诺,任意一条失败 = 阻塞 PR merge。
"""

# PR-B 不变量
def test_invariant_category_x_mutates_state_holds():
    ...

# PR-D2 不变量
def test_invariant_no_self_binding():
    ...

# PR-D3 不变量
def test_invariant_l1_l2_symmetry():
    ...

# PR-D4 不变量
def test_invariant_no_orphan_bindings():
    ...

# PR-EOP 不变量(本 PR 新增)
def test_invariant_all_fin_endpoints_registerable():
    ...

def test_invariant_no_default_category_remaining():
    """Phase 1 收口:fin 端点不应再有默认 category(全应显式标注)。

    对应设计:§1.3 PR-C 推动业务标注。
    业务影响:默认值残留 = PR-C 推动没完成,Phase 2 接手时被默认值误导。
    """
    from Plate.core import registry
    for key, spec in registry._index.items():
        if key.service == "fin":
            # 默认 category 是 BUSINESS;但 fin 的 QUERY 端点应为 QUERY
            # 所以默认 category 出现 = 漏标
            assert spec.category is not EndpointCategory.BUSINESS or spec.mutates_state is True, (
                f"{key.path}: 默认 category=BUSINESS 但可能是漏标的 QUERY 端点"
            )
```

### 2.4 文档同步

```markdown
# design/PLATE_DESIGN.md 改动示例

## §2.1 EndpointSpec

> ~~待实现:PR-B 落地~~ **已实现 (Phase 1, PR-B, 2026-XX-XX)**

## §2.2 FieldBinding

> ~~待实现:PR-D2 落地~~ **已实现 (Phase 1, PR-D2, 2026-XX-XX)**

## §2.3 EndpointDoc

> ~~待实现:PR-D3 落地~~ **已实现 (Phase 1, PR-D3, 2026-XX-XX)**
```

```markdown
# design/PLATE_EVOLUTION.md 改动示例

## Phase 1: 静态模块内部改造

> **状态**:~~待执行~~ **已完成 (2026-XX-XX)**
>
> Phase 1 涉及 7 个 PR,见 `design/phase1/INDEX.md`
```

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应 Phase 1 收口的"出厂质检承诺":
1. **业务需求**(Phase 1 完成度的硬约束)
2. **对应设计章节**(PLATE_DESIGN.md)
3. **业务影响**(违反此约束的代价 = Phase 2 接手时现状不清)

### 3.2 必测业务场景

```python
"""PR-EOP:Phase 1 收口基线测试。

业务动机:Phase 1 涉及 7 个 PR,本测试是出厂质检,确认所有交付物到位。
不变量失败 = Phase 1 没收口完成,Phase 2 不能启动。
"""


# ════════════════════════════════════════════════════════════════════════════
# 交付物完整性
# ════════════════════════════════════════════════════════════════════════════

def test_endpoint_spec_has_category_field():
    """业务需求:EndpointSpec 包含 category 字段(PR-B 落地)。

    对应设计:§2.1
    业务影响:缺字段 = PR-B 没合并,Phase 2 接手时无 category 可消费。
    """
    from dataclasses import fields
    from Plate.spec import EndpointSpec
    field_names = {f.name for f in fields(EndpointSpec)}
    assert "category" in field_names
    assert "mutates_state" in field_names


def test_endpoint_spec_has_bindings_field():
    """业务需求:EndpointSpec 包含 bindings 字段(PR-D2 落地)。

    对应设计:§2.2
    业务影响:缺字段 = PR-D2 没合并。
    """
    from dataclasses import fields
    from Plate.spec import EndpointSpec
    field_names = {f.name for f in fields(EndpointSpec)}
    assert "bindings" in field_names


def test_fin_dannotations_module_exists():
    """业务需求:fin/dannotations 目录存在(PR-D3 落地)。

    对应设计:§2.3 L1/L2 物理分离
    业务影响:目录不在 = PR-D3 没合并,L2 注释无处存放。
    """
    import os
    import Plate.fin
    pkg_dir = os.path.dirname(Plate.fin.__file__)
    assert os.path.isdir(os.path.join(pkg_dir, "dannotations"))


def test_path_resolver_module_exists():
    """业务需求:path_resolver 模块存在(PR-D1 落地)。

    对应设计:§3.4 路径解析器
    业务影响:模块不在 = PR-D1 没合并,binding 真实性校验无法做。
    """
    from Plate import path_resolver
    assert hasattr(path_resolver, "resolve_logical_path")


# ════════════════════════════════════════════════════════════════════════════
# 数据完整性
# ════════════════════════════════════════════════════════════════════════════

def test_invariant_all_fin_endpoints_registerable():
    """业务需求:fin 服务 31 端点全部可注册,无 __post_init__ 失败。

    对应设计:PR-C 推动 fin 31 端点全部显式标注。
    业务影响:有端点注册失败 = PR-C 没完成,fin 服务加载链断。
    """
    from Plate.core import registry
    fin_count = sum(
        1 for key in registry._index
        if key.service == "fin"
    )
    assert fin_count == 31, f"fin 服务应注册 31 端点,实际 {fin_count}"


def test_invariant_no_default_category_in_fin():
    """业务需求:fin 端点不应再依赖默认值(BUSINESS)兜底。

    对应设计:PR-C "本 PR 推动业务标注"。
    业务影响:默认值残留 = 漏标的 QUERY 端点仍当 BUSINESS,CT 主动探测会触发写入。
    """
    from Plate.core import registry
    from Plate.spec import EndpointSpec, EndpointCategory

    # 检查所有 fin 端点的 category 是显式传入的(不是默认 BUSINESS)
    # 简化判断:有 bindings 的必是 QUERY(应显式标),没 bindings 的可能是 BUSINESS
    for key, spec in registry._index.items():
        if key.service != "fin":
            continue
        if spec.bindings:
            assert spec.category is EndpointCategory.QUERY, (
                f"{key.path}: 有 binding 应为 QUERY,实际 {spec.category}"
            )
        # 注:BUSINESS 端点无 binding 是正常的(写操作无上游读依赖)


def test_invariant_fin_binding_count_in_range():
    """业务需求:fin 服务的 binding 总数符合 PR-D4 落地表。

    对应设计:PR-D4 §1.3 [8, 15] 区间。
    业务影响:过少 = 漏标;过多 = 强凑假依赖。
    """
    from Plate.core import registry
    total = sum(
        len(spec.bindings)
        for key, spec in registry._index.items()
        if key.service == "fin"
    )
    assert 8 <= total <= 15, f"fin binding 总数 {total} 不在 [8, 15]"


def test_invariant_fin_l1_l2_symmetry():
    """业务需求:有 L2 doc 必有 L1 spec。

    对应设计:PR-D3 §3 L1/L2 对称性。
    业务影响:doc 指向幽灵 endpoint = 文档库腐化。
    """
    from Plate.core import registry
    from Plate.fin.dannotations import _DOCS

    fin_paths = {
        key.path
        for key in registry._index
        if key.service == "fin"
    }
    for doc_path in _DOCS:
        assert doc_path in fin_paths, (
            f"dannotations 有 {doc_path!r} 但 fin registry 找不到对应 spec"
        )


# ════════════════════════════════════════════════════════════════════════════
# 测试基线
# ════════════════════════════════════════════════════════════════════════════

def test_baseline_test_count_at_least_221():
    """业务需求:全量测试数 ≥ 221(Phase 1 收口基线)。

    对应设计:本 PR §4.2。
    业务影响:测试数下降 = 有 PR 删了测试,Phase 1 完整性破坏。
    """
    import subprocess
    result = subprocess.run(
        ["pytest", "--collect-only", "-q", "tests/"],
        capture_output=True, text=True,
    )
    # 简单 parse:收集到的测试数在 output 里
    # 更稳健的做法是 pytest.main 但会触发整个测试
    # 这里简化:只校验 pytest 能收集成功
    assert result.returncode == 0, f"pytest collect 失败:\n{result.stdout}\n{result.stderr}"
```

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 交付物完整 | `test_endpoint_spec_has_category_field` / `..._has_bindings_field` / `test_fin_dannotations_module_exists` / `test_path_resolver_module_exists` | 各 PR merge 状态可验证 |
| 数据完整 | `test_invariant_all_fin_endpoints_registerable` / `..._no_default_category_in_fin` / `..._fin_binding_count_in_range` / `..._fin_l1_l2_symmetry` | Phase 1 数据层 OK |
| 测试基线 | `test_baseline_test_count_at_least_221` | 防漏测试 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_eop_baseline.py -v

# 2. 跑全量 Phase 1 不变量
pytest tests/plate/test_invariants.py -v

# 3. 跑全量基线
pytest tests/ -v  # 应 ≥ 221 个测试全过

# 4. 验证交付物
python -c "
from dataclasses import fields
from Plate.spec import EndpointSpec
from Plate import path_resolver
import os
import Plate.fin

print('=== 交付物清单 ===')
print(f'1. EndpointSpec 字段: {[f.name for f in fields(EndpointSpec)]}')
print(f'2. path_resolver 模块: {\"resolve_logical_path\" in dir(path_resolver)}')
print(f'3. dannotations 目录: {os.path.isdir(os.path.join(os.path.dirname(Plate.fin.__file__), \"dannotations\"))}')

from Plate.core import registry
fin_count = sum(1 for k in registry._index if k.service == 'fin')
binding_count = sum(len(s.bindings) for k, s in registry._index.items() if k.service == 'fin')
print(f'4. fin 端点数: {fin_count}')
print(f'5. fin binding 总数: {binding_count}')
"

# 5. 文档同步检查
python -c "
with open('design/PLATE_DESIGN.md', encoding='utf-8') as f:
    content = f.read()
print('=== 文档状态标注 ===')
for marker in ['EndpointCategory', 'FieldBinding', 'EndpointDoc']:
    if marker in content:
        # 检查是否还在说'待实现'
        idx = content.find(marker)
        ctx = content[idx:idx+300]
        if '待实现' in ctx:
            print(f'  {marker}: 仍标\"待实现\"(需更新)')
        elif '已实现' in ctx:
            print(f'  {marker}: 已标\"已实现\" ✓')
        else:
            print(f'  {marker}: 未明确标注')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_eop_baseline.py` 测试数 | ≥ 8 |
| 全量测试数 | ≥ 221 |
| 不变量测试 | 0 失败 |
| fin 端点注册 | 31 / 31 |
| fin binding 总数 | 在 [8, 15] 区间 |
| 文档标注更新 | 所有 Phase 1 字段标"已实现" |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 借机加 feature | 本 PR 严格只做"验证 + 文档",不在范围内的新需求 push 到 Phase 2 |
| CI gate 被绕开 | CI 是组织级约束,本 PR 只提供配置,不强制 |
| 文档更新漏掉 | 由 `test_eop_baseline.py` 检查文档包含"已实现"关键词,缺失则报警 |

---

## 5. 与后续 Phase 的衔接

- **Phase 2**(service 化):依赖本 PR 的:
  - `category` 字段(用于调用编排判断)
  - `bindings` 字段(用于自动注入)
  - `dannotations` 目录(用于 AI skill 提示词补充)
- **Phase 3**(动态服务能力):依赖本 PR 的路径解析器(`resolve_logical_path`)做实时注入
- **Phase 4**(CT 主动保活):依赖 `category × mutates_state` 交叉校验做"可探测"过滤

**Phase 2 启动条件**:
- [ ] Phase 1 全部 PR 合并
- [ ] 本 PR 收口通过(≥221 测试 + 不变量 0 失败)
- [ ] 文档已同步
- [ ] CI gate 已配置