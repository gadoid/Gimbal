# PR-A: 纯重命名 ModelRegistry → Plate

> **状态**:⏸️ **被 [PR-0.2](PR-0.2.md) 合并执行**
>
> **说明**:按用户决策 D2=A,纯重命名与"model_registry 测试 pytest 化"在**同一 PR(PR-0.2)**完成。本文件保留作为**单独执行场景的参考**(若 PR-0.2 拆分回两个 PR,本文件可直接执行)。
>
> **关联**:完整细节见 [PR-0.2.md §2.1](PR-0.2.md#21-改动文件清单) 的 "A. 重命名" 段。

---

## 1. 适用范围

如果未来某个会话需要"只做改名,不动测试",本文件提供独立可执行的工作清单。

## 2. 改动清单(独立执行版)

| 操作 | 路径 |
|---|---|
| `git mv` | `src/ModelRegistry/` → `src/Plate/` |
| 改字符串 | `src/Plate/__init__.py`(import + 错误信息) |
| 改字符串 | `src/Plate/core.py`(importlib + 错误信息) |
| 改字符串 | `src/Plate/_aliases.py`(错误信息 + docstring) |
| 改字符串 | `src/Plate/spec.py`(docstring) |
| 改字符串 | `src/Plate/fin/__init__.py`(docstring) |
| 改字符串 | `src/Plate/fin/models.py`(docstring) |
| 改字符串 | `pyproject.toml` (若有 `packages` 列表) |
| 改字符串 | 仓库根 `README.md`、 `docs/`(若有) |
| 改字符串 | `tests/plate/test_sanity.py`(`from ModelRegistry` → `from Plate`) |
| 改字符串 | 任何 e2e / scenarios / scripts 目录下的引用 |

## 3. 验收

```bash
# 1. 物理改名
git mv src/ModelRegistry src/Plate

# 2. 内部 import 改
grep -rl "ModelRegistry" src/ | xargs sed -i 's/ModelRegistry/Plate/g'

# 3. importlib 字符串改
grep -rln '"ModelRegistry' src/ | xargs sed -i 's/"ModelRegistry/"Plate/g'

# 4. 错误信息改
grep -rln '\[ModelRegistry\]' src/ | xargs sed -i 's/\[ModelRegistry\]/[Plate]/g'

# 5. 跑基线
pytest tests/plate/ -v
```

## 4. 风险

| 风险 | 缓解 |
|---|---|
| 漏改 `importlib.import_module("ModelRegistry.xxx")` | grep `'ModelRegistry\.'` 字面字符串 |
| 漏改错误信息前缀 `[ModelRegistry]` | grep `\[ModelRegistry\]` |
| 漏改 docstring | grep `ModelRegistry` 在 `.py` 文件里 |
| 外部消费者断链 | PR 描述明确 migration note;可选 shim(`src/ModelRegistry/__init__.py` 转发到 `src/Plate`) |
| `pyproject.toml` 的 `packages` 列表漏改 | `pip install -e .` 验证 |

## 5. 与 PR-0.2 的关系

如果本次**不与 PR-0.2 合并**(例如 D2 改判),本 PR 是先决条件:
- 顺序:PR-A(改名) → PR-0.2(model_registry 测试 pytest 化,改完名字后的 import 路径)
- 二者必须保持一致(要么都 `Plate`,要么都 `ModelRegistry`)
