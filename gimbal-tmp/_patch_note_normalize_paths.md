# 归一化 IOFieldBinding.path 实施方案

> 状态：**未改动 plate 源码**（遵循 read-only 约束）。本文件是迁移指南 + 外层
> 归一脚本 `_normalize_paths.py` 的说明，便于你或团队成员手动落地。

## 1. 问题

`IOFieldBinding.path` 接受两种合法形态：JSONPath（`$.order_id`）和短名（`order_id`）。
- `ResponseSpec.assertable_fields` 在加载时被 `normalize()` 收敛为 `$.xxx`。
- `IOFieldBinding.path` 自己**没有** normalize，导致 `request_fields` 与
  `response_fields` 在 platform dict 里出现风格混用（短名 vs `$.xxx`）。

## 2. 推荐修法（最小、零行为变更）

只需在 [io_spec.py:30-37](../src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py)
的 `_validate` 里追加一行：

```python
self.path = _path.normalize(self.path)  # 在 is_valid_path 通过之后
```

这一行带来的行为变化：
- ✅ `IOFieldBinding` 加载后 `path` 永远是 `$.xxx` 形态。
- ✅ `name == last_segment(path)` 校验逻辑不变（`normalize` 不动末段标识符）。
- ✅ platform / gimbal 输出端无需任何改动 —— `model_dump` 直接吃归一后的 path。
- ⚠️ 拒绝行为：`is_valid_path` 已通过的 path 不会再被 `normalize` 拒绝（设计上是同一套合法性定义），所以零误伤。
- ⚠️ 历史数据：已经 dump 出来的 JSON 文件不会被回溯修改；只需在下次加载时归一。

## 3. 已落地的外层归一工具

[_normalize_paths.py](_normalize_paths.py) —— 在不修改 plate 源码的前提下，
对 endpoint 模块做一次扫描 +（可选）原地归一：

```bash
# 只看 diff,不写
python gimbal-tmp/_normalize_paths.py systems.tidb.endpoints

# 原地归一（替换模块内 EndpointSpec 实例）
python gimbal-tmp/_normalize_paths.py systems.tidb.endpoints --write
```

适用场景：已经发布到端点库的 endpoint 定义文件，无法立刻升级 plate 版本时，
作为临时工具用。**正式方案仍是 §2 的一行 patch**。

## 4. 验证用例

修改后建议补以下单元测试（位于 `tests/`）：

```python
def test_io_field_binding_path_is_normalized_on_load():
    from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding

    # 短名应被归一为 JSONPath
    f = IOFieldBinding(name="order_id", path="order_id")
    assert f.path == "$.order_id"

    # JSONPath 原样保留
    f2 = IOFieldBinding(name="order_id", path="$.order_id")
    assert f2.path == "$.order_id"

    # 末段非 FIELD 时不强制 name 一致
    f3 = IOFieldBinding(name="first", path="$.items[0]")
    assert f3.path == "$.items[0]"
    assert f3.name == "first"  # 不抛错
```

## 5. 影响面盘点

| 位置 | 修改前 | 修改后 |
|---|---|---|
| `IOFieldBinding.path` 内存值 | `"order_id"` 或 `"$.order_id"` | 永远 `"$.order_id"` |
| `RequestSpec.fields[].path` dump | 短名 / JSONPath 混用 | 统一 JSONPath |
| `ResponseSpec.fields[].path` dump | 短名 / JSONPath 混用 | 统一 JSONPath |
| `PlatformScenarioExporter` 输出 | 短名 / JSONPath 混用 | 统一 JSONPath |
| `GimbalScenarioExporter` 输出 | 不涉及（gimbal 不读 IOFieldBinding.path） | 不变 |
| 端点定义文件 | 短名仍合法 | 仍合法（加载时归一） |