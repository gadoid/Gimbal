# Phase 1 实施计划索引

> 配套设计文档:
> - [PLATE_DESIGN.md](../PLATE_DESIGN.md) —— 数据模型设计
> - [PLATE_EVOLUTION.md](../PLATE_EVOLUTION.md) —— 演进路径(4 阶段)
>
> 本目录是 **Phase 1 (Plate 静态模块内部改造)** 的逐 PR 实施计划。
> 配套维护 [DECISIONS.md](DECISIONS.md) 记录实施过程中的关键决策与权衡。

---

## 阶段总览

```
Plate Phase 1 演进 —— "建护栏 → 做改造 → 收口验证" 三段式
═══════════════════════════════════════════════════════════════════════════════

PR-0  基线约束
  ├─ PR-0.1  pytest 基线                  [DONE 2026-06-25]
  └─ PR-0.2  model_registry pytest 化 + 改名  [下一步]
  ↓
PR-A  纯重命名 ModelRegistry → Plate       [按用户决策:与 PR-0.2 合并]
  ↓
PR-B  EndpointSpec 引入 category 字段
  ↓
PR-C  fin 31 端点:从 PATH_MODELS 双轨切到 EndpointSpec 单轨 + 业务标注
  ↓
PR-D  字段依赖边与 L2 物理解耦
  ├─ PR-D1  路径解析器(独立基建)
  ├─ PR-D2  FieldBinding 收编进 EndpointSpec
  ├─ PR-D3  EndpointDoc L2 物理解耦
  └─ PR-D4  首批 field_bindings 批量化
  ↓
收口  review pipeline 全链路验证 + 文档同步
```

---

## 文档清单

| PR | 文件 | 状态 | 关键产出 |
|---|---|---|---|
| (前置) | [PR-0.1.md](PR-0.1.md) | **已完成** | pytest 基线 + collect_ignore + 5 个 sanity 测试 |
| (前置) | [PR-0.2.md](PR-0.2.md) | **已完成** | model_registry 4 测试 pytest 化 + 改名 |
| 1 | [PR-A.md](PR-A.md) | **已完成** | 纯重命名(目录/import/错误信息) |
| 2 | [PR-B.md](PR-B.md) | **已完成** | `EndpointCategory` enum + `mutates_state` + `__post_init__` 强校 |
| 3 | [PR-C.md](PR-C.md) | **已完成** | fin 31 端点单轨化 + 业务标注(15 BUSINESS + 16 QUERY) |
| 4 | [PR-D1.md](PR-D1.md) | **已完成** | 路径解析器(独立基建, ≥20 单测) |
| 5 | [PR-D2.md](PR-D2.md) | **已完成** | `FieldBinding` dataclass + `EndpointSpec.bindings` |
| 6 | [PR-D3.md](PR-D3.md) | **已完成** | `EndpointDoc` + 独立 L2 存储(零侵入) |
| 7 | [PR-D4.md](PR-D4.md) | **已完成** | 首批 `field_bindings` 批量化(5 个 binding) + referential integrity check |
| 收口 | [PR-EOP.md](PR-EOP.md) | **已完成** | review pipeline 串联 + 文档同步 + 基线 ≥300 测试 |
| 配套 | [REVIEW-CHECKLIST.md](REVIEW-CHECKLIST.md) | 已建立 | reviewer 统一视角(每 PR 重点 + 反模式) |
| 配套 | [DECISIONS.md](DECISIONS.md) | 已建立 | D1-D14 已确认决策 |

---

## 工作量估计

| PR | 估计工作量 | 状态 |
|---|---|---|
| PR-0.1 | 0.5 PD | ✅ 已完成 |
| PR-0.2 + PR-A | 1.5 PD | ✅ 已完成 |
| PR-B | 0.5 PD | ✅ 已完成 |
| PR-C | 2–3 PD | ✅ 已完成(最大单 PR) |
| PR-D1 | 1 PD | ✅ 已完成 |
| PR-D2 | 0.5 PD | ✅ 已完成 |
| PR-D3 | 0.5 PD | ✅ 已完成 |
| PR-D4 | 2–3 PD | ✅ 已完成 |
| 收口 | 1 PD | ✅ 已完成 |
| **总计** | **9–12 PD** | **Phase 1 全部完成** |

---

## 关键设计原则(每 PR 通用)

### 1. "建护栏 → 做改造 → 收口验证" 三段式

任何 PR 内部都遵循这个流程:
- **建护栏**:先把"什么是禁止的、什么是合法的"用测试/检查器锁死
- **做改造**:在护栏允许的范围内推数据/重构
- **收口验证**:跑全套场景 + 跑 review pipeline,确保不破现有承诺

### 2. 测试用例面向业务需求,不验证功能

按用户明确指示:测试用例必须回答"**这个业务承诺有没有被破坏**",不是"代码能不能跑"。

例如:
- ✅ `test_endpoint_spec_constructible` —— 验证"31 个 fin 端点必须能成功构造,否则 service 加载链断"
- ❌ `test_endpoint_spec_init_does_not_crash` —— 验证"代码能跑"(无业务含义)

### 3. 零侵入 / 按需加载 / 契约保真(设计 §7)

5 条不变承诺,每 PR review 时显式校验:
1. **零侵入**:import Plate 顶层不 import 任何子包
2. **按需加载**:未引用的 service 不 import;执行态不加载 L2
3. **契约保真**:模型不改写 wire 格式(extra=forbid + 禁用清单全关)
4. **互补而非替代**:Plate 提供静态契约级真值,流量挖掘提供动态实例级值流向
5. **优雅降级**:服务化后,Plate 不可达时消费方退回本地缓存/流量挖掘

---

## 已确认的决策

详见 [DECISIONS.md](DECISIONS.md)。

---

## reviewer 检查清单

详见 [REVIEW-CHECKLIST.md](REVIEW-CHECKLIST.md)。
