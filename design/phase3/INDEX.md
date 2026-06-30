# Phase 3 实施计划索引

> 配套设计文档:
> - [PLATE_DESIGN.md](../PLATE_DESIGN.md) —— 数据模型设计
> - [PLATE_EVOLUTION.md](../PLATE_EVOLUTION.md) —— 演进路径(4 阶段)
> - [phase1/INDEX.md](../phase1/INDEX.md) —— Phase 1 收口(已完成)
> - [phase2/INDEX.md](../phase2/INDEX.md) —— Phase 2 收口(已完成)
>
> 本目录是 **Phase 3 (Plate 动态服务能力)** 的逐 PR 实施计划。
> 配套维护 [DECISIONS.md](DECISIONS.md) 记录实施过程中的关键决策与权衡。

---

## 阶段总览

```
Plate Phase 3 演进 —— "低成本 doc → 中成本 mock → 高成本 MCP" 三段式
═══════════════════════════════════════════════════════════════════════════════

Phase 2 收口(已完成)
  ├─ 远端服务 + 客户端 SDK
  ├─ GIMBAL 切换到 facade
  └─ 基线快照(BASELINE.md + DECISIONS.md)
  ↓
PR-3.1  API doc 服务(L1+L2 Markdown 渲染)     [低成本,最先做]
  ↓
PR-3.2  Mock server(responses 填充 + hook)     [中成本]
  ↓
PR-3.3  Plate-MCP(库 + MCP 双形态,按消费者分) [高成本,需前两 PR 稳定]
  ↓
PR-3.4  Phase 3 收口(review pipeline + docs + baseline,可选)
```

---

## 架构原则(Phase 3 全部 PR 通用)

继承 Phase 1+2 不变承诺(PLATE_DESIGN §7)+ Phase 2 新增(A1–A6)+ Phase 3 特有:

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
| **A2** | 不可变序列化 | 反序列化 `__eq__` 字节级一致 |
| **A3** | 冷热分层在两个端点 | `/spec` 与 `/doc` 独立路由 |
| **A4** | 本地优先,远端备份 | `import Plate` 仍可用;SDK 是叠加层 |
| **A5** | 协议先于实现 | PR-2.1 协议草案 → PR-2.2 SDK 并行实现 |
| **A6** | 向后兼容 | `from Plate import registry` 持续可用,DeprecationWarning |

### Phase 3 新增

| 编号 | 原则 | 落地 |
|---|---|---|
| **B1** | 库形态优先,MCP 后置 | 确定性脚本用 `import`,agent 交互才用 MCP(PLATE_EVOLUTION §4.3 论证) |
| **B2** | 渲染层零副作用 | API doc / Mock 输出**只读**,不改 L1/L2 任何字段 |
| **B3** | L2 注释渐进补 | 不强绑 L2 完备性,L2 缺失时静默降级显示 |

---

## 文档清单

| PR | 文件 | 状态 | 关键产出 |
|---|---|---|---|
| 1 | [PR-3.1.md](PR-3.1.md) | 🆕 已设计(本会话 2026-06-30) | `Plate/api_doc/` 子包 + `plate doc <service>` CLI |
| 2 | [PR-3.2.md](PR-3.2.md) | 📋 待启动 | Mock server(响应填充 + hook 调用) |
| 3 | [PR-3.3.md](PR-3.3.md) | 📋 待启动 | Plate-MCP(库 + MCP 双形态) |
| 4 | [PR-3.4.md](PR-3.4.md) | 📋 可选 | Phase 3 收口(对齐 PR-2.5) |
| 配套 | [DECISIONS.md](DECISIONS.md) | 📋 待建 | D28–D30 PR-3.1 决策,后续 PR 决策汇总 |

---

## 工作量估计

| PR | 估计工作量 | 状态 |
|---|---|---|
| PR-3.1 | 1.1 PD | 🆕 设计完成,本会话可启动实装 |
| PR-3.2 | 2 PD | 📋 待启动 |
| PR-3.3 | 3 PD | 📋 待启动 |
| PR-3.4 | 1 PD(可选) | 📋 待启动 |
| **总计** | **7.1 PD** | PR-3.1 本会话先做;其余按需启动 |

---

## PR 间依赖图

```
PR-3.1 (API doc)
   │
   ├──> PR-3.2 (Mock server) ──┐
   │                           │
   └──> PR-3.3 (Plate-MCP) ───┤
                               │
                            PR-3.4 (收口)
```

**关键依赖**:
- **PR-3.1 不阻塞 PR-3.2 / PR-3.3**——三条独立战线,Phase 3 §4.1/4.2/4.3 本就是按成本排序
- **PR-3.3 依赖 PR-3.1 + PR-3.2 稳定**——MCP 查询到的数据模型必须稳定(PLATE_EVOLUTION §4.3 论证)

---

## reviewer 检查清单

继承 Phase 1/2 的评审清单,Phase 3 重点关注:

| 项 | 检查 |
|---|---|
| 库形态优先 | `Plate.api_doc.render.render_service()` 库函数可用,CLI 是薄包装 |
| 渲染层零副作用 | API doc 输出**只读** `EndpointSpec` / `EndpointDoc`,不改任何字段 |
| L2 渐进补容忍 | L2 doc 缺失时静默显示"(无 L2 注释)",不抛错 |
| L1/L2 物理解耦 | `Plate/api_doc/__init__.py` **不** import `Plate.fin` 等服务子包 |
| Markdown git diff 友好 | 同类端点格式一致,diff 只显示差异 |

---

## 已确认的决策

详见 [DECISIONS.md](DECISIONS.md)。

---

## Phase 2 → Phase 3 衔接

Phase 2 已为 Phase 3 铺路的设计/实装:

- **HTTP 协议**(PR-2.1):MCP 适配可复用 URL 形态与 JSON schema 模式
- **客户端 SDK**(PR-2.2):`plate_client` 可在 MCP 适配时升级为 httpx async
- **服务部署**(PR-2.3):`http.server` 可在 Mock server 阶段升级为 FastAPI/Starlette
- **GIMBAL 切换**(PR-2.4):`PlateFacade` 双形态(库 + 远端)是 B1 原则的预演
- **基线快照**(PR-2.5):Phase 3 收口可复用 BASELINE.md 模板

Phase 3 不重构 Phase 2 任何模块,**纯消费 + 叠加**。