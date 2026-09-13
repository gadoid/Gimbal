# `CaseComposerCatalog` 全仓零测试覆盖

> **模块**：`gimbal-platform/frontend`（嵌入式接口目录面板）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 事实（本会话核实）

`src/gimbal-platform/frontend/src/components/composer/CaseComposerCatalog.vue` 是**生产代码**，被唯一一处引用：

- `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue:538`
  `import CaseComposerCatalog from './CaseComposerCatalog.vue'`（并在 `:8` 的模板里挂载）

**没有任何测试 import 或 mount 它**。全仓检索（`*.ts` / `*.vue`，含 `__tests__`）它一共出现 10 处，其中落在测试文件里的**只有两条注释**：

- `src/gimbal-platform/frontend/src/api/__tests__/plate.test.ts:6`（「会拼出 `/api/plate/...` 的错误路径 — 与 CaseComposerCatalog 的先例一致」）
- `src/gimbal-platform/frontend/src/api/__tests__/scenario-composer.full.test.ts:6`（「含**不经**共享缓存的 `CaseComposerCatalog` 浏览面板」）

其余为产品侧注释（`useEndpointFull.ts:5`、`:26`、`api/scenario-composer.ts:229`、`api/plate.ts:6`、`utils/catalog-services.ts:5`）。

即：**两条注释在拿它当参照物，但它自己一行测试也没有。**

---

## 1. 为什么值得登记

它在架构上有两个**特殊身份**，两处都只靠注释约束、没有回归保护：

1. **唯一绕开共享缓存的 `/full` 消费者**：`useEndpointFull.ts:5-6` 明文「**不是唯一取数口**：`CaseComposerCatalog` 的目录面板直接调 `getFullEndpoint`（用户触发的浏览取数，不属判定路径，故不合并）」；代码印证：`CaseComposerCatalog.vue:257` 直接 `import { getFullEndpoint }`、`:398` 直接调它。—— 它的取数**不经过**会话级缓存、**不经过**负缓存、**不经过**在飞收敛；它拿到的是 `getFullEndpoint` 的**出口消毒**结果（`useEndpointFull.ts:24-30` 说明消毒上移到出口正是为了覆盖它）。
2. **路径拼接先例的当事人**：`api/plate.ts:6` 与 `plate.test.ts:6` 都在引用「CaseComposerCatalog 的先例」来解释「axios 的 `baseURL=/api` 会拼出错路径」—— 它是这条纪律的**来源**，却没有任何用例把它钉住。

**残余风险**：

- 「出口消毒覆盖到了它」这一保证只写在注释里（`scenario-composer.ts:229`、`useEndpointFull.ts:26`）；若哪次改动把消毒挪回缓存层（或让 `getFullEndpoint` 变成非唯一出口），它会在无人察觉的情况下拿到**未消毒**的声明树（后果见 `children-shape-unreachable.md` §2：`path` 非串会让画布渲染硬抛白屏）。
- 它的 `baseURL` / 路径拼接一旦回归，没有用例会红；`plate.test.ts` 守的是**另一个** API 模块（`api/plate.ts`）的同类纪律。

---

## 2. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 当前行为正确（读过源：它按设计直连 `getFullEndpoint`，且出口消毒覆盖它）；
- 缺的是**回归保护**，不是缺陷；风险要等到相关改动发生时才兑现。

**可选的收口方向（仅备查，不是结论）**：给它补一个最小 mount 用例（mock `getFullEndpoint` 的返回值，断言渲染 + 断言它确实调的是**未经缓存**的 API 口）—— 这条同时把上面两个特殊身份钉成可回归的事实。

---

## 3. 何时重开

1. **消毒边界移动**（出口 → 缓存层，或新增第二个出口）—— 本条的残余风险立刻兑现；
2. **`/full` 取数口收编**（spec §7 的 I 项）—— **已落地（阶段二·①）**：取数归 `plate_client.get_endpoint_full(endpoint_id, *, timeout=None)`（**TTL 不是形参**，由 `DECLARED_PATHS_TTL_SEC` 在缓存实例构造时冻结），`endpoint_declarations` 退为其上的派生层。前端这一侧（本记录 §0/§1 描述的出口消毒与浏览取数）仍然零覆盖，收编带来的取数口变化应一并补测；
3. **目录面板功能变更**（做实例级标注、字段浏览增强等）—— 零覆盖的组件不宜承载新逻辑；
4. **前端测试覆盖率的任何门槛化要求**（例如 CI 覆盖率门禁）。
