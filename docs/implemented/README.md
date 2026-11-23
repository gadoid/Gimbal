# implemented/ —— 已实现文档归档

> 2026-11-23 文档拆分:设计/计划类文档按实现状态二分 —— 本目录收
> **使命完结**件(设计已全部落地、计划已执行完毕);`docs/` 主目录与
> `docs/superpowers/` 留**待实现**与**现行参考**文档。
>
> 判定口径:以**代码现实**为准(状态行化石不采信 —— 多个 spec 标
> 「待实施」但代码早已落地,已随批补记状态行);被取代的废弃件另行
> 归档至 `design/archive/`(如 assertion-registry-field-binding 被 v3
> 取代)。

## 内容

| 子目录/位置 | 内容 |
|---|---|
| `specs/` | 25 份已实现设计 spec(2026-06 ~ 2026-11:场景变量生成器、plate 统一、策略语法服务、IO 卡、变量工作台、carry/filler 字段、声明统一、深路径、绑定配置、字段三态、动态值源、字段恢复导出、数据集驱动、断言注册表 v3、架构收敛、判定面收敛、方案工作台、SUT 双生生成器、变量锁、平台自举、入站参数等) |
| `plans/` | 27 件已完成实施计划(含 gimbal-platform-refactor-plan / scenario-library-design / scenario_refector_design / workbench-cards-design 四目录与散件计划) |
| 顶层 | 5 件根目录完结件:凭证与调用身份治理设计(阶段 0-4 全✅)、身份注册表驱动方案(阶段 0-4 全✅)、组件影响台账(C1-C5 全销账)、残留清理记录 2026-11-22、plate HTTP API 测试报告 |

## 留在原地的(勿迁)

- `docs/service-registry-redesign.md` —— 现行架构权威参考(§8/§9 系列为行为规范现行定义)
- `docs/service-registry-progress.md` —— 活进度文档
- `docs/project-detail-stitch-plan.md` —— B/C 级能力待排期
- `docs/known-issues/` —— 活登记(未修复项 + 重开条件)
- 各参考文档(概念地图 / http-api / PRD / REQUIREMENTS / 运行手册 / API 契约文档等)

归档不改写历史正文(含当时的路径引用与命令记录);交叉引用已按
新位置改写,`.superpowers/sdd/` 为 git-ignored 历史工作区引用,
保持原样。
