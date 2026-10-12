# 剩余任务清单（2026-10-12 收口）

> 产出背景：缺口收口计划（`claude/plate-gap-closure-dev-plan.md`）的 P0/P1/P2 与波次 A/B/C 已全部落地。
> 当日基线：`fin@1.0#1` + `platform@1.0#1` 均已签发并推远端（构件分支 `plate/artifacts` 头 = `739941c2`）；
> 36 个场景已钉修订（fin×10 + platform×26），34 个锚定场景零 working；
> 门：后端 825 绿 / 前端 1214 绿 / plate 639 绿 / vue-tsc 零错。
> 本清单 = 剩余波次 D + 计划外挂账 + 待拍板项，供后续批次排期。

## 一、波次 D（收口计划 P3/P4）—— ✅ 2026-10-12 当日全部落地

W19(14241574 RunOptions 形状/上限64/Q4 折回)、W20(31e6a894 镜像清零:UserCredential 组合/DebugCommandIn 生成化/checks→CheckDecl/director 改读 /api/m2)、W21(执行详情修订台账+趋势切换点+m2_hash 派发回填)、W22(ccc6db8c 应用到同类步骤)、W23(62d7cbd9 事件表 fields 修复+hash_mismatch 入表)、W24(63425b6e 按修订缓存+strict_ref 删除)、W25(test_cold_archive 六例)、W26(dev-plan/收口计划勾选+runbook-pg 0019/0020 记录)。门:后端 846 绿 / plate 670 绿 / 前端 vue-tsc 0 错。

原建议顺序：W19 → W20 → W24 → W23 → W22 → W21 → W25 → W26（先定形状再清镜像；台账 UI 最后做、一次吃齐全量出参）。

| 项 | 内容 | 验收/要点 | 规模 |
|---|---|---|---|
| **W19（P3.1/B-4）RunRequest 形状** | `RunRequest` 平铺的 `stepTo`/`nRuns`/`parallel` 改 RunOptions 生成物形状；上限对齐 64（dev-plan T1.1 的 Q4 结论）；`DebugLaunchSpec` 一并生成物化；**折回 M2 方案 Q4 行成文** | CI 三形态重生成守卫绿；`scripts/gen_m2.py gen/check` 往返一致 | M |
| **W20（P3.2/B-5）镜像清零收尾** | 平台 `AuthSession` 改持有生成的 `UserCredential`；`DebugCommandIn`、`DebugLaunchSpec` 生成物化；Suite `checks` dict→生成物；director skill 改读 `/api/m2`（删静态 scenario-schema.md） | 每项自带测试；平台侧手写 M2 镜像类清零 | M |
| **W21（P3.3/B-1/B-2）执行详情修订台账（前端）** | 显示「当时的修订」（`plate_pins`）与「重跑将使用的修订」，不一致时提示；执行趋势图在修订/版本线变化处标切换点；**并入 W11 挪来的执行详情三态展示**；**并入 m2_hash 派发回填（见二.1）** | 台账字段在执行详情/列表可见；不一致提示可复现 | M |
| **W22（P3.4/B-3）应用到同类步骤** | RS4b「应用到同类步骤」批量应用（`submit-suite` 已有同类聚合，补单场景同类步骤面） | 用例绿 | S |
| **W23（P3.5/B-6）事件表 payload** | ext 快照 24 个事件的 `fields` 填充；`m2.hash_mismatch` 从 `server_debug.py` 移入 `events/` 并入表 | 事件表口径一致 | M |
| **W24（P3.6/B-7）plate_client 按修订缓存** | 修订条目不设 TTL、只按容量淘汰（与 b4a8fc0 修订缓存同机制）；`declarations_of_at` 入缓存；删 `strict_ref` 死代码 | 缓存命中测试 + 死代码零引用 | S |
| **W25（P4.1）RS5 冷化测试** | `release/cold_archive.py` 全仓零测试引用——补判定查询测试：被场景引用 / 可能成为生效修订 / 被执行记录 `plate_pins` 引用的修订不在冷化清单 | 测试绿 | S |
| **W26（P4.2/P4.3）文档收尾** | dev-plan v1.0 勾选同步（T1.1①/T1.6/T4.1/T4.2/T5.2）；**本计划 P0/P2 勾选补齐（活已完成、框未勾）**；生产部署清单刷新（并入构件分支重建+必推远端、alembic 0019/0020） | 文档与现状一致 | S |

## 二、计划外已挂账的技术项（开工前先核实现状）

1. ~~**`executions.m2_hash` 派发回填**~~ ✅ 已随 W21 落地（/convert 响应 m2 身份 → executions.m2_hash,整执行一次,台账性质）。
2. **外部接口登记**——external 服务的结构化升级：平台侧轻量目录（URL 模式 + method + 可选 JSON Schema，支持 OpenAPI 导入），登记后步骤可锚点化、恢复结构化表单与保存校验。计划明确「不在 P1 范围」，是三态模型 external 的下一步；与下条合流做。
3. **集成卡 P2 缺口**（记忆挂账：personal 422 / G1 认证分派 / G2+G7 随 task3c / 外部系统定义）——IA 轮后部分可能已交付，**开工前逐条核实**。
4. **倒排索引硬化尾巴**——断言侧与 via_var 两个盲区仍挂起（锚点行/容器匹配/refs-drift 三项已硬化；注意 refs-drift 端点本身已随 A-6 删除，此处指索引层盲区）。
5. **plate-s1 第四轮评估项**——N1 空值 `''`（resolver 首字符须列表含 `''`）、pydantic-settings、冷启动先 diff（空 spec_json 静默）、兜底保险恢复、wheel 零 gimbal_plate（packages+force-include 修法）、F3 补 check、C1/C3 拍板不冲突口径。**部分可能已被 S1.5a 收口覆盖，开工前核实清单。**

## 三、待拍板（用户决策）

- **M2 方案未决项 L1 / V5 / step 表达力**——评估轮遗留的三个分层决策（见 `claude/` 下 M2 相关方案文档）。
- **外部接口登记排期**——决定二.2/二.3 进哪个批次。

## 四、已核实关闭的旧挂账（勿再追）

- `$.response_status` 旧断言迁移：DB 内已 **0 条**（后续批次已迁移），挂账关闭（记忆已更新）。
- EXEC_CHAIN：默认链已切 server（280 活体验证），放量完成。

## 五、恢复工作的环境要点

- 三服务：plate `:8765`（`python run_plate.py`，cwd `src/gimbal-plate`，须带 `PLATE_ARTIFACTS_PATH=D:\Gimbal\plate-artifacts`）；后端 `:8000`（uvicorn，**改代码必须重启**，无 --reload）；vite `:5173`。
- **重启后端后拉 OpenAPI 再做交叉类核对**——旧进程会给出已删路由（评审轮实证）。
- 构件分支：`D:\Gimbal\plate-artifacts`（worktree）；发版后**必推 origin**；工作区必须净（B1 门）。
- 门纪律：后端全量 pytest / 前端全量 vitest（**两者勿并发跑**）/ plate `python -m pytest tests/plate`；提交分组见收口计划 §波次。
- 已知坑索引：见记忆 `gap-closure-wave-a-complete`、`w17-w18-platform-review-onboarding`（`_commit_artifacts` 祖先 .git、dispatch 基线须测试同源重钉、watch(immediate) TDZ、手动保存测试须 mock @/api/shares、composer_scenarios 双列 id/scenario_id）。
