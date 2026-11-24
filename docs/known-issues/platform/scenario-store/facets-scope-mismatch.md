# facets 端点 scope 词表与前端 mine 桶不匹配（恒 422,静默回落）

> **模块**：`gimbal-platform`（frontend `composables/useScenarioListView.ts` × backend `routers/scenarios.py`）
> **状态**：未修复（P2 —— 优雅降级:catch 置 null 回落池 uniq,UI 不坏）
> **来源**：2026-11-24 依赖升级轮无头浏览器冒烟偶得(前置问题,非该轮引入;
> 前端侧最后成形于 69b49079「全员视角镜头退役」)

---

## 0. 事实

「我的场景」页(mine 桶)挂载即拉 facets:

```ts
// useScenarioListView.ts(loadFacets)
bucket === 'mine'
  ? { q: effQ() || undefined, scope: 'private' as const }   // ← 发 private
```

而 facets 端点只收两值(routers/scenarios.py:611):

```python
scope: Literal["mine", "all"] = "all"
```

⇒ mine 桶的 facets **恒 422**(literal_error),前端 catch 置 `facets=null`,
FilterPopover 回落本地池 uniq(无计数)。列表端点(:672)三值都收
(`mine|all|private`),所以列表本身正常,只有筛选计数降级。

## 1. 为什么是 P2

- 降级路径是**设计内**的("静默失败(置 null 即回落池)"),UI 无感;
- 只影响 mine 桶的筛选弹出层计数精度,不影响数据正确性。

## 2. 修复方向(重开本条时二选一)

- **改前端**(倾向):mine 桶发 `scope: 'mine'`(后端语义"只统计自己创建的",
  与桶意图一致;`private` 是列表口径"我名下且未发布/私有",facets 本就没实现它);
- 或后端把 facets 的 Literal 扩到 `private` 并对齐列表语义 —— 但这会引入
  第二个"分桶参数"分支,不如前端对词表。

验收:`GET /api/scenarios/facets?scope=mine` 200,且 FilterPopover 计数非池兜底。
