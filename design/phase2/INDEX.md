# Phase 2 实施计划索引

> 配套设计文档:
> - [PLATE_DESIGN.md](../PLATE_DESIGN.md) —— 数据模型设计
> - [PLATE_EVOLUTION.md](../PLATE_EVOLUTION.md) —— 演进路径(4 阶段)
> - [phase1/INDEX.md](../phase1/INDEX.md) —— Phase 1 收口(已完成)
>
> 本目录是 **Phase 2 (Plate 服务化基础设施)** 的逐 PR 实施计划。
> 配套维护 [DECISIONS.md](DECISIONS.md) 记录实施过程中的关键决策与权衡。

---

## 阶段总览

```
Plate Phase 2 演进 —— "打地基 → 立协议 → 建 SDK → 切换 → 收口" 五段式
═══════════════════════════════════════════════════════════════════════════════

Phase 1 基础(已完成)
  ├─ L1/L2 物理解耦
  ├─ EndpointCategory × mutates_state
  ├─ FieldBinding + path_resolver
  └─ EndpointDoc 空壳
  ↓
PR-2.0  版本机制 + L1 序列化           [地基]
  ↓
PR-2.1  远端服务契约(HTTP 协议草案)    [协议]
  ↓
PR-2.2  客户端 SDK(plate_client)       [SDK]
  ↓
PR-2.3  服务部署形态 + E2E 验证        [部署]
  ↓
PR-2.4  GIMBAL 切换到 SDK(向后兼容)    [切换]
  ↓
PR-2.5  Phase 2 收口(review pipeline + 文档同步 + 基线)
```

---

## 架构原则(Phase 2 全部 PR 通用)

继承 Phase 1 不变承诺(PLATE_DESIGN §7)+ Phase 2 特有:

### Phase 1 继承(不变承诺)

1. **零侵入**:任何包顶层 `import` 不破坏现有行为
2. **按需加载**:未引用 service 不 import
3. **契约保真**:序列化不改写 wire 语义
4. **互补而非替代**:服务与流量挖掘互补
5. **优雅降级**:Plate 不可达时退回本地缓存/流量挖掘

### Phase 2 新增

| 编号 | 原则 | 落地 |
|---|---|---|
| **A1** | 版本优先于功能 | `PlateManifest.version` 必填,无版本不服务化 |
| **A2** | 不可变序列化 | 反序列化 `__eq__` 字节级一致(排序无关字段先排序) |
| **A3** | 冷热分层在两个端点 | `/spec` 与 `/doc` 独立路由 |
| **A4** | 本地优先,远端备份 | `import Plate` 仍可用;SDK 是叠加层 |
| **A5** | 协议先于实现 | PR-2.1 协议草案 → PR-2.2 SDK 并行实现 |
| **A6** | 向后兼容 | PR-2.4 切换期间,旧 `from Plate import registry` 持续可用 |

---

## 文档清单

| PR | 文件 | 状态 | 关键产出 |
|---|---|---|---|
| 1 | [PR-2.0.md](PR-2.0.md) | 待执行 | `PlateManifest` + `to_dict`/`from_dict` + 字节级 pin |
| 2 | [PR-2.1.md](PR-2.1.md) | 待执行 | HTTP 协议草案(URL 形态 + JSON schema + 错误码) |
| 3 | [PR-2.2.md](PR-2.2.md) | 待执行 | `plate_client` 子包:fetch + cache + resolver + 离线 fallback |
| 4 | [PR-2.3.md](PR-2.3.md) | 待执行 | 服务部署形态(进程模式 / 端口 / health check) |
| 5 | [PR-2.4.md](PR-2.4.md) | 待执行 | GIMBAL 切换到 SDK(向后兼容的双轨期间) |
| 6 | [PR-2.5.md](PR-2.5.md) | 待执行 | review pipeline 串联 + 文档同步 + 基线 |
| 配套 | [DECISIONS.md](DECISIONS.md) | 已建立 | D15+ Phase 2 决策 |

---

## 工作量估计

| PR | 估计工作量 | 状态 |
|---|---|---|
| PR-2.0 | 1.5 PD | 待执行(地基,必须最先做) |
| PR-2.1 | 1 PD | 待执行(协议,后续 SDK 与服务端并行) |
| PR-2.2 | 2 PD | 待执行(SDK,最复杂) |
| PR-2.3 | 1 PD | 待执行(部署 + E2E) |
| PR-2.4 | 1.5 PD | 待执行(GIMBAL 切换,真风险点) |
| PR-2.5 | 1 PD | 待执行(收口) |
| **总计** | **8 PD** | |

---

## PR 间依赖图

```
PR-2.0(版本 + 序列化)
   │
   ├──> PR-2.1(协议草案)──> PR-2.3(部署) ──┐
   │                                       │
   └──> PR-2.2(SDK) ────────────────────┐  │
                                         ▼  ▼
                                    PR-2.4(切换)
                                         │
                                         ▼
                                    PR-2.5(收口)
```

**关键依赖**:
- **PR-2.0 阻塞所有后续** —— 没版本机制就没字节级 pin
- **PR-2.1 与 PR-2.2 可并行** —— 协议先定,SDK 按协议实现
- **PR-2.3 阻塞 PR-2.4** —— 没真实部署,GIMBAL 切换无法验证

---

## reviewer 检查清单

继承 Phase 1 的 [REVIEW-CHECKLIST](../phase1/REVIEW-CHECKLIST.md),Phase 2
重点关注:

| 项 | 检查 |
|---|---|
| 序列化 byte-equal | `from_dict(to_dict(x)) == x` 对 31 端点全成立 |
| 离线 fallback | 拔网后 GIMBAL 执行不挂(走本地缓存) |
| 协议版本独立 | 协议升级不破坏旧客户端(版本字段在 URL) |
| 双轨期间 | `from Plate import registry` 与 `from plate_client import PlateClient` 同时可用 |
| L1/L2 端点分离 | `/spec` 与 `/doc` 路由独立,响应 schema 不混 |
| 缓存命中可观测 | `cache_stats()` 返回 hit/miss 计数 |

---

## 已确认的决策

详见 [DECISIONS.md](DECISIONS.md)。

---

## Phase 1 → Phase 2 衔接

Phase 1 已为 Phase 2 铺路的设计:
- L1/L2 物理解耦(`spec.py` 与 `doc.py` 独立模块)→ 服务化后两个端点对应物理目录
- `path_resolver` 是纯函数 → 客户端 SDK 可重写,无状态依赖
- `EndpointSpec` 是 `frozen=True` dataclass → 序列化无须特殊处理
- `FieldBinding` 是 `frozen=True` dataclass → 同上
- `EndpointCategory` 是 `str, Enum` → JSON 序列化天然支持

Phase 2 不需重构 Phase 1 任何模块,**纯叠加**。