# facets 端点 scope 词表与前端 mine 桶不匹配（恒 422,静默回落）

> **模块**：`gimbal-platform`（frontend `composables/useScenarioListView.ts` × backend `routers/scenarios.py`）
> **状态**：**已修复**（2026-11-24 收尾轮：改前端发 `scope='mine'` + API 类型面收窄 + 前后端双钉）
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

## 修复记录（2026-11-24,fix/core-wrapup 轮）

按 §2 的**倾向方向**（改前端）落地:

- `useScenarioListView.loadFacets` mine 桶改发 `scope='mine'`
  （后端语义「只统计自己创建的」,与桶意图一致;列表口径的 `scope=
  private` 不动 —— 列表端点三值都收）;
- **API 类型面收窄**:`fetchScenarioFacets` 的 `scope` 从
  `'private'|'mine'|'all'` 收到端点词表 `'mine'|'all'` —— 正是类型面
  留着 `private` 才让这次误用编译期不响;docstring 同步注明;
- 双钉:前端 `useScenarioListView.test.ts` 的 facets 用例改钉
  `{scope:'mine'}`（修前该用例钉的是 bug 行为）;后端新增
  `test_facets_scope_mine`（`?scope=mine` 200 + 只统计自己创建的 +
  member 零创建零计数）;
- 验证:前端定向 37 绿、后端 facets 6 绿。
