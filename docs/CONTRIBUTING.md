# 贡献规范（CONTRIBUTING）

> 五条铁律 + 门纪律。来源:缺陷检查与 UI 走查(2026-10-13)沉淀,2026-10-14 建档。

## 铁律

1. **禁止类型逃逸**。跨层传值一律过对应模型(M2/plate 视图/平台 schema),
   不许 `Any` 直通。反例教训:plate `ConfigView` 的视图专有键
   (`is_authenticated`)被原样预填进场景存储,执行即被 M2
   `extra_forbid` 拒收(A-1 根因,2026-10-14 修)。
   视图字段进存储前必须显式剥除(写入口统一剥,不靠单个消费点)。
2. **新增测试必须「去掉被测功能后会失败」**。空断言/恒真断言不合并
   —— 复核三轮发现的 `wait_until` 超时静默返回就造出过一批假绿用例
   (已改为超时抛错)。
3. **新接口先检索已有路由**。`grep -rn "APIRouter" src/gimbal-platform/backend/app/routers/`,
   防止同义端点重复注册(历史教训:重复路由评审清理过一轮)。
4. **根因说明要附复现步骤**。提交信息/缺陷单写:触发路径(页面或 API
   调用序列)→ 期望 → 实际 → 根因层(哪一层污染了哪一层)。
   「复现不了的修不动」。
5. **宽捕获必须注明是旁路**。`except Exception` 只允许出现在台账/
   通知/缓存/告警等旁路上并写明降级后果;主链路(解析/认证/投影/执行)
   只捕获具体异常或显式失败。新增宽捕获不带注释 → 评审打回。

## 门纪律(提交前)

| 侧 | 命令 | 要求 |
|---|---|---|
| 后端 | `TEST_DATABASE_URL=postgresql+asyncpg://… pytest src/gimbal-platform/backend/tests -q` | 全绿(PG-only,SQLite 已退役) |
| plate | `python -m pytest tests/plate -q` | 全绿 |
| 执行器 | `python -m pytest tests/unit tests/integration -q` | 全绿 |
| 前端 | `npm run test -- --run` + `npm run typecheck` | 全绿 + vue-tsc 零错 |
| 生成物 | `python scripts/gen_m2.py check --targets schema,ext,py,ts,dbgcmd` | 无漂移 |
| 契约 | `plate check --all --json` | 零 finding |

- 后端与前端全量**勿并发跑**(端口/资源互踩,历史偶发红)。
- 改后端代码必须重启服务(`src/restart-services.ps1`,无 --reload,单 worker)。
- alembic 新迁移:先 pg_dump 备份 → 手动 `upgrade head` → 起服只校验
  (PG 起服不迁移,runbook-pg §4)。

## 提交分组

按仓库既有风格:`fix(<域>): <一句话>` / `feat(<域>):` / `docs(...)` / `chore(...)`;
正文写根因+验证证据(测试数/探针结果),历史叙述(评审第 N 轮之类)留在
提交信息,不写进代码注释。
